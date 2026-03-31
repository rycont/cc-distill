#!/usr/bin/env python3
"""
Claude Code session data extractor.
Sources:
  - ~/.claude/transcripts/*.jsonl (legacy format)
  - ~/.claude/projects/*/*.jsonl (current format)
  - Subagents included (*/subagents/*.jsonl)

Extracts:
  - User messages
  - Tool usage with inputs (file paths, commands, search patterns)
  - Struggle signals (repeated errors, retry loops, edit churn)
  - Subagent prompts

Output: /tmp/session_analysis.json
"""
import sys, json, os, time, re
from pathlib import Path
from collections import Counter

NUM = int(sys.argv[1]) if len(sys.argv) > 1 else 20
DAYS = int(sys.argv[2]) if len(sys.argv) > 2 else 30
CLAUDE_DIR = Path.home() / ".claude"
OUT = Path("/tmp/session_analysis.json")
CUTOFF = time.time() - DAYS * 86400

# Patterns that look like secrets
SECRET_RE = re.compile(
    r"(?i)(password|passwd|secret|token|api[_-]?key|authorization)[=:\"' ]+\S+",
)


def mask_secrets(text):
    """Replace potential secrets with [REDACTED]."""
    return SECRET_RE.sub(r"\1=[REDACTED]", text)


def find_all_sessions():
    """Find main session files modified within last N days, sorted by size desc."""
    files = []
    for d in [CLAUDE_DIR / "transcripts", CLAUDE_DIR / "projects"]:
        if not d.exists():
            continue
        for f in d.rglob("*.jsonl"):
            if "/subagents/" in str(f):
                continue
            if f.stat().st_mtime >= CUTOFF:
                files.append(f)
    files.sort(key=lambda f: f.stat().st_size, reverse=True)
    return files[:NUM]


def find_subagents(session_path):
    """Find subagent JSONL files belonging to a main session."""
    sa_dir = session_path.with_suffix("") / "subagents"
    if sa_dir.is_dir():
        return sorted(sa_dir.glob("*.jsonl"), key=lambda f: f.stat().st_size, reverse=True)
    return []


def parse_jsonl(fpath, extract_struggles=True):
    """Parse JSONL → rich session data including struggle signals."""
    user_msgs = []
    assistant_text_lens = []  # length of each assistant text reply
    tool_details = []  # [{name, input_summary, timestamp}, ...]
    tool_counts = {}
    cwd = None
    timestamps = []

    # Struggle tracking
    errors = []           # [{tool, error_preview, timestamp}, ...]
    bash_commands = []     # [{command, failed, timestamp}, ...]
    edited_files = []      # file paths from Edit/Write
    read_files = []        # file paths from Read

    # Pending tool_use IDs → names (for matching results in new format)
    pending_tools = {}

    with open(fpath, "r", errors="replace") as f:
        for line in f:
            try:
                d = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            dtype = d.get("type", "")
            ts = d.get("timestamp", "")

            # ── New format: type=user ──
            if dtype == "user" and "message" in d:
                msg = d["message"]
                content = msg.get("content", "")

                # Extract user text
                text = _extract_text(content)
                if text:
                    user_msgs.append(mask_secrets(text[:3000]))

                if d.get("cwd") and not cwd:
                    cwd = d["cwd"]
                if ts:
                    timestamps.append(ts)

                # Extract tool_results from user messages (new format)
                if isinstance(content, list):
                    for b in content:
                        if isinstance(b, dict) and b.get("type") == "tool_result":
                            tool_id = b.get("tool_use_id", "")
                            is_err = b.get("is_error", False)
                            result_text = str(b.get("content", ""))[:500]
                            tool_name = pending_tools.pop(tool_id, "?")

                            if is_err or _looks_like_error(result_text):
                                errors.append({
                                    "tool": tool_name,
                                    "error": mask_secrets(result_text[:300]),
                                    "timestamp": ts,
                                })

            # ── New format: type=assistant ──
            elif dtype == "assistant" and "message" in d:
                asst_text_len = 0
                for b in (d["message"].get("content") or []):
                    if isinstance(b, dict) and b.get("type") == "tool_use":
                        tn = b.get("name", "?")
                        inp = b.get("input", {}) if isinstance(b.get("input"), dict) else {}
                        tool_id = b.get("id", "")

                        tool_counts[tn] = tool_counts.get(tn, 0) + 1
                        pending_tools[tool_id] = tn

                        summary = _summarize_tool_input(tn, inp)
                        tool_details.append({"name": tn, "summary": mask_secrets(summary), "timestamp": ts})

                        if extract_struggles:
                            _track_tool_for_struggles(tn, inp, ts, bash_commands, edited_files, read_files)
                    elif isinstance(b, dict) and b.get("type") == "text":
                        asst_text_len += len(b.get("text", ""))
                if asst_text_len > 0:
                    assistant_text_lens.append(asst_text_len)

            # ── Legacy format: type=user (no message wrapper) ──
            elif dtype == "user" and "message" not in d:
                text = _extract_text(d.get("content", ""))
                if text:
                    user_msgs.append(mask_secrets(text[:3000]))
                if ts:
                    timestamps.append(ts)

            # ── Legacy format: type=tool_use ──
            elif dtype == "tool_use":
                tn = d.get("tool_name", "?")
                inp = d.get("tool_input", {}) if isinstance(d.get("tool_input"), dict) else {}
                tool_counts[tn] = tool_counts.get(tn, 0) + 1

                summary = _summarize_tool_input(tn, inp)
                tool_details.append({"name": tn, "summary": mask_secrets(summary), "timestamp": ts})

                if extract_struggles:
                    _track_tool_for_struggles(tn, inp, ts, bash_commands, edited_files, read_files)

            # ── Legacy format: type=tool_result ──
            elif dtype == "tool_result":
                result_text = str(d.get("content", ""))[:500]
                is_err = d.get("is_error", False)
                if is_err or _looks_like_error(result_text):
                    errors.append({
                        "tool": "?",
                        "error": mask_secrets(result_text[:300]),
                        "timestamp": ts,
                    })

    # Build struggle analysis
    struggles = _analyze_struggles(errors, bash_commands, edited_files, read_files, tool_details, user_msgs, timestamps, assistant_text_lens) if extract_struggles else {}

    return {
        "user_messages": user_msgs,
        "tool_details": tool_details,
        "tool_counts": tool_counts,
        "cwd": cwd,
        "timestamps": timestamps,
        "struggles": struggles,
    }


def _extract_text(content):
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for b in content:
            if isinstance(b, str):
                parts.append(b)
            elif isinstance(b, dict) and b.get("type") == "text":
                parts.append(b.get("text", ""))
        return "\n".join(parts).strip()
    return ""


def _looks_like_error(text):
    """Heuristic: does this tool result look like an error?"""
    indicators = ["error", "Error", "ERROR", "exit code 1", "Exit code 1",
                  "Traceback", "FAILED", "failed", "command not found",
                  "No such file", "Permission denied", "ENOENT", "EACCES"]
    return any(ind in text[:500] for ind in indicators)


def _summarize_tool_input(tool_name, inp):
    """Extract the most relevant info from tool input."""
    if tool_name == "Bash":
        cmd = str(inp.get("command", ""))[:200]
        return f"$ {cmd}"
    elif tool_name in ("Read", "Edit", "Write"):
        fp = inp.get("file_path", "")
        if tool_name == "Edit":
            old = str(inp.get("old_string", ""))[:80]
            return f"{fp} (edit: {old}...)"
        return fp
    elif tool_name == "Grep":
        pattern = inp.get("pattern", "")
        path = inp.get("path", "")
        return f"/{pattern}/ in {path}" if path else f"/{pattern}/"
    elif tool_name == "Glob":
        return inp.get("pattern", "")
    elif tool_name == "Agent" or tool_name == "task":
        desc = inp.get("description", "")
        prompt = str(inp.get("prompt", ""))[:200]
        return f"{desc}: {prompt}" if desc else prompt
    else:
        # Generic: just list keys
        return ", ".join(f"{k}={str(v)[:60]}" for k, v in list(inp.items())[:3])


def _track_tool_for_struggles(tool_name, inp, ts, bash_commands, edited_files, read_files):
    """Track tool calls that might indicate struggles."""
    if tool_name == "Bash":
        cmd = str(inp.get("command", ""))[:300]
        bash_commands.append({"command": mask_secrets(cmd), "timestamp": ts})
    elif tool_name == "Edit":
        fp = inp.get("file_path", "")
        if fp:
            edited_files.append(fp)
    elif tool_name == "Write":
        fp = inp.get("file_path", "")
        if fp:
            edited_files.append(fp)
    elif tool_name == "Read":
        fp = inp.get("file_path", "")
        if fp:
            read_files.append(fp)


def _analyze_struggles(errors, bash_commands, edited_files, read_files, tool_details, user_msgs, timestamps, assistant_text_lens):
    """Detect struggle patterns from collected signals."""
    struggles = {}

    # 0. Session duration
    if len(timestamps) >= 2:
        try:
            from datetime import datetime
            ts_sorted = sorted(timestamps)
            t0 = datetime.fromisoformat(ts_sorted[0].replace("Z", "+00:00"))
            t1 = datetime.fromisoformat(ts_sorted[-1].replace("Z", "+00:00"))
            duration_min = round((t1 - t0).total_seconds() / 60)
            struggles["duration_minutes"] = duration_min
        except:
            pass

    # 0b. Verbosity — assistant talks too much relative to user
    if assistant_text_lens and user_msgs:
        avg_asst = sum(assistant_text_lens) / len(assistant_text_lens)
        avg_user = sum(len(m) for m in user_msgs) / len(user_msgs)
        if avg_user > 0 and avg_asst / avg_user > 5:
            struggles["verbose_assistant"] = {
                "avg_assistant_chars": round(avg_asst),
                "avg_user_chars": round(avg_user),
                "ratio": round(avg_asst / avg_user, 1),
            }

    # 1. Repeated errors — same error appearing multiple times
    if errors:
        # Group errors by first 100 chars of error message
        error_groups = Counter()
        for e in errors:
            key = e["error"][:100]
            error_groups[key] += 1
        repeated_errors = {k: v for k, v in error_groups.most_common(10) if v >= 2}
        if repeated_errors:
            struggles["repeated_errors"] = {
                "count": sum(repeated_errors.values()),
                "unique_errors": len(repeated_errors),
                "top_errors": [{"error_preview": k, "occurrences": v} for k, v in repeated_errors.items()],
            }

    # 2. Edit churn — same file edited many times
    if edited_files:
        file_edits = Counter(edited_files)
        churn_files = {f: c for f, c in file_edits.most_common(10) if c >= 3}
        if churn_files:
            struggles["edit_churn"] = {
                "files": [{"path": f, "edit_count": c} for f, c in churn_files.items()],
            }

    # 3. Bash retry loops — similar commands retried
    if len(bash_commands) >= 3:
        # Normalize commands (strip whitespace, truncate) and find repeats
        normalized = Counter()
        for bc in bash_commands:
            # Normalize: collapse whitespace, take first 100 chars
            norm = re.sub(r'\s+', ' ', bc["command"])[:100]
            normalized[norm] += 1
        retries = {k: v for k, v in normalized.most_common(10) if v >= 3}
        if retries:
            struggles["bash_retries"] = {
                "commands": [{"command_preview": k, "attempts": v} for k, v in retries.items()],
            }

    # 4. Thrashing ratio — high tool calls per user message = Claude spinning
    total_tools = len(tool_details)
    total_user = len(user_msgs)
    if total_user > 0:
        ratio = total_tools / total_user
        if ratio > 15:  # More than 15 tool calls per user message = likely struggling
            struggles["thrashing"] = {
                "tool_calls": total_tools,
                "user_messages": total_user,
                "ratio": round(ratio, 1),
            }

    # 5. Read repetition — same file read many times
    if read_files:
        read_counts = Counter(read_files)
        repeated_reads = {f: c for f, c in read_counts.most_common(10) if c >= 4}
        if repeated_reads:
            struggles["repeated_reads"] = {
                "files": [{"path": f, "read_count": c} for f, c in repeated_reads.items()],
            }

    return struggles


def repeated_patterns(tool_details, min_count=3):
    """Detect repeated tool sequences using sliding windows of size 2-5."""
    tool_seq = [t["name"] for t in tool_details]
    pats = {}
    for ws in range(2, 6):
        for i in range(len(tool_seq) - ws + 1):
            p = " -> ".join(tool_seq[i : i + ws])
            pats[p] = pats.get(p, 0) + 1
    return {k: v for k, v in sorted(pats.items(), key=lambda x: -x[1])[:15] if v >= min_count}


# ── Main ──
sessions = find_all_sessions()
result = []

for spath in sessions:
    data = parse_jsonl(spath, extract_struggles=True)

    # Subagents
    sa_files = find_subagents(spath)
    subagents = []
    all_sa_tool_details = []
    for sa in sa_files:
        sa_data = parse_jsonl(sa, extract_struggles=True)
        all_sa_tool_details.extend(sa_data["tool_details"])
        subagents.append({
            "name": sa.name.replace(".jsonl", ""),
            "size_kb": round(sa.stat().st_size / 1024),
            "prompt": sa_data["user_messages"][0][:500] if sa_data["user_messages"] else None,
            "tool_counts": sa_data["tool_counts"],
            "repeated_patterns": repeated_patterns(sa_data["tool_details"]),
            "struggles": sa_data["struggles"],
        })

    src = "transcripts" if "/transcripts/" in str(spath) else str(spath).split("/projects/")[1].split("/")[0] if "/projects/" in str(spath) else "?"

    # Trim tool_details for output (keep summary, drop verbose fields)
    trimmed_tools = [{"name": t["name"], "summary": t["summary"]} for t in data["tool_details"]]

    session_out = {
        "session_id": spath.stem[:24],
        "source": src,
        "cwd": data["cwd"],
        "size_kb": round(spath.stat().st_size / 1024),
        "user_message_count": len(data["user_messages"]),
        "user_messages": data["user_messages"],
        "main_tool_counts": data["tool_counts"],
        "main_tool_calls": sum(data["tool_counts"].values()),
        "main_tool_details": trimmed_tools,
        "main_repeated_patterns": repeated_patterns(data["tool_details"]),
        "struggles": data["struggles"],
        "subagent_count": len(subagents),
        "subagent_total_calls": len(all_sa_tool_details),
        "subagent_tool_counts": dict(
            sorted(
                {k: v for sa in subagents for k, v in sa["tool_counts"].items()}.items(),
                key=lambda x: -x[1],
            )[:20]
        ) if subagents else {},
        "subagent_repeated_patterns": repeated_patterns(all_sa_tool_details),
        "subagent_details": subagents,
    }
    result.append(session_out)

# Sort by struggle severity (sessions with more struggles first)
def struggle_score(s):
    st = s.get("struggles", {})
    score = 0
    score += st.get("repeated_errors", {}).get("count", 0) * 3
    score += sum(f["edit_count"] for f in st.get("edit_churn", {}).get("files", [])) * 2
    score += sum(c["attempts"] for c in st.get("bash_retries", {}).get("commands", [])) * 2
    score += st.get("thrashing", {}).get("ratio", 0)
    score += min(st.get("duration_minutes", 0) / 10, 10)  # long sessions get mild boost
    if "verbose_assistant" in st:
        score += st["verbose_assistant"]["ratio"]
    # Include subagent struggles
    for sa in s.get("subagent_details", []):
        sa_st = sa.get("struggles", {})
        score += sa_st.get("repeated_errors", {}).get("count", 0) * 2
    return score

result.sort(key=struggle_score, reverse=True)

OUT.write_text(json.dumps(result, ensure_ascii=False, indent=1))
print(f"Extracted {len(result)} sessions (last {DAYS} days, top {NUM}) -> {OUT}")
print(f"Sorted by struggle severity (most struggles first)\n")
for s in result:
    sa = f", subagents={s['subagent_count']}" if s["subagent_count"] else ""
    st = s.get("struggles", {})
    struggle_parts = []
    if "repeated_errors" in st:
        struggle_parts.append(f"errors={st['repeated_errors']['count']}")
    if "edit_churn" in st:
        struggle_parts.append(f"churn={len(st['edit_churn']['files'])}files")
    if "bash_retries" in st:
        struggle_parts.append(f"retries={len(st['bash_retries']['commands'])}cmds")
    if "thrashing" in st:
        struggle_parts.append(f"thrash={st['thrashing']['ratio']}x")
    struggle_str = f"  STRUGGLES: {', '.join(struggle_parts)}" if struggle_parts else ""
    print(f"  {s['session_id']}  {s['size_kb']}KB  msgs={s['user_message_count']}  tools={s['main_tool_calls']}{sa}  [{s['source'][:30]}]{struggle_str}")
