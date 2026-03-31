#!/usr/bin/env python3
"""
Claude Code session data extractor.
Collects raw session data from:
  - ~/.claude/transcripts/*.jsonl (legacy format)
  - ~/.claude/projects/*/*.jsonl (current format)
  - Subagents: */subagents/*.jsonl

Extracts facts only — no judgment. Outputs:
  - User messages, assistant text lengths
  - Tool calls with inputs
  - Subagent prompts
  - Session-level stats (turns, duration, LLM/human ratio)

Output: /tmp/session_analysis.json
"""
import sys, json, re, time
from pathlib import Path

NUM = int(sys.argv[1]) if len(sys.argv) > 1 else 20
DAYS = int(sys.argv[2]) if len(sys.argv) > 2 else 30
CLAUDE_DIR = Path.home() / ".claude"
OUT = Path("/tmp/session_analysis.json")
CUTOFF = time.time() - DAYS * 86400

SECRET_RE = re.compile(r"(?i)(password|passwd|secret|token|api[_-]?key|authorization)[=:\"' ]+\S+")


def mask(text):
    return SECRET_RE.sub(r"\1=[REDACTED]", text)


def find_sessions():
    files = []
    for d in [CLAUDE_DIR / "transcripts", CLAUDE_DIR / "projects"]:
        if not d.exists():
            continue
        for f in d.rglob("*.jsonl"):
            if "/subagents/" in str(f):
                continue
            try:
                if f.stat().st_mtime >= CUTOFF:
                    files.append(f)
            except OSError:
                continue
    files.sort(key=lambda f: f.stat().st_size, reverse=True)
    return files[:NUM]


def find_subagents(path):
    sa_dir = path.with_suffix("") / "subagents"
    if sa_dir.is_dir():
        return sorted(sa_dir.glob("*.jsonl"), key=lambda f: f.stat().st_size, reverse=True)
    return []


NOISE_PREFIXES = ("task-notification", "<task-notification", "command-name", "<command-name",
                   "<local-command-caveat", "Request interrupted", "[Request interrupted")

def _is_noise(text):
    """Filter out system-generated messages that aren't real user input."""
    stripped = text.strip().lstrip("<")
    return any(stripped.startswith(p.lstrip("<")) for p in NOISE_PREFIXES)


def text_of(content):
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return "\n".join(
            b.get("text", "") if isinstance(b, dict) and b.get("type") == "text"
            else b if isinstance(b, str) else ""
            for b in content
        ).strip()
    return ""


def tool_summary(name, inp):
    if not isinstance(inp, dict):
        return ""
    if name == "Bash":
        return mask(str(inp.get("command", ""))[:200])
    if name in ("Read", "Edit", "Write"):
        return inp.get("file_path", "")
    if name == "Grep":
        p, d = inp.get("pattern", ""), inp.get("path", "")
        return f"/{p}/ in {d}" if d else f"/{p}/"
    if name == "Glob":
        return inp.get("pattern", "")
    if name in ("Agent", "task"):
        return str(inp.get("description", "") or inp.get("prompt", ""))[:200]
    return ""


def parse(fpath):
    user_msgs, tools, timestamps = [], [], []
    user_chars, assistant_chars = 0, 0
    user_turns, assistant_turns = 0, 0
    cwd = None

    with open(fpath, "r", errors="replace") as f:
        for line in f:
            try:
                d = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            dtype = d.get("type", "")
            ts = d.get("timestamp", "")
            if ts:
                timestamps.append(ts)

            # --- New format ---
            if dtype == "user" and "message" in d:
                text = text_of(d["message"].get("content", ""))
                if text and not _is_noise(text):
                    user_msgs.append(mask(text[:1000]))
                    user_chars += len(text)
                    user_turns += 1
                if d.get("cwd") and not cwd:
                    cwd = d["cwd"]

            elif dtype == "assistant" and "message" in d:
                assistant_turns += 1
                for b in (d["message"].get("content") or []):
                    if isinstance(b, dict):
                        if b.get("type") == "tool_use":
                            name = b.get("name", "?")
                            tools.append({"name": name, "input": tool_summary(name, b.get("input"))})
                        elif b.get("type") == "text":
                            assistant_chars += len(b.get("text", ""))

            # --- Legacy format ---
            elif dtype == "user" and "message" not in d:
                text = text_of(d.get("content", ""))
                if text and not _is_noise(text):
                    user_msgs.append(mask(text[:1000]))
                    user_chars += len(text)
                    user_turns += 1

            elif dtype == "tool_use":
                name = d.get("tool_name", "?")
                tools.append({"name": name, "input": tool_summary(name, d.get("tool_input", {}))})

            elif dtype == "assistant":
                assistant_turns += 1
                text = text_of(d.get("content", ""))
                assistant_chars += len(text)

    # Duration
    duration_min = None
    if len(timestamps) >= 2:
        try:
            from datetime import datetime
            ts_sorted = sorted(timestamps)
            t0 = datetime.fromisoformat(ts_sorted[0].replace("Z", "+00:00"))
            t1 = datetime.fromisoformat(ts_sorted[-1].replace("Z", "+00:00"))
            duration_min = round((t1 - t0).total_seconds() / 60)
        except Exception:
            pass

    # Summarize tools: counts + top file paths
    from collections import Counter
    tool_counts = Counter(t["name"] for t in tools)
    file_paths = [t["input"] for t in tools if t["name"] in ("Read", "Edit", "Write") and t["input"]]
    file_counts = Counter(file_paths).most_common(10)
    bash_cmds = [t["input"] for t in tools if t["name"] == "Bash" and t["input"]]
    grep_patterns = [t["input"] for t in tools if t["name"] == "Grep" and t["input"]]

    return {
        "user_messages": user_msgs,
        "tool_summary": {
            "counts": dict(tool_counts.most_common()),
            "top_files": [{"path": f, "times": c} for f, c in file_counts],
            "bash_commands": bash_cmds[:20],
            "grep_patterns": grep_patterns[:10],
        },
        "cwd": cwd,
        "stats": {
            "user_turns": user_turns,
            "assistant_turns": assistant_turns,
            "tool_calls": len(tools),
            "user_chars": user_chars,
            "assistant_chars": assistant_chars,
            "llm_human_ratio": round(assistant_chars / user_chars, 1) if user_chars > 0 else None,
            "duration_minutes": duration_min,
        },
    }


# --- Main ---
sessions = find_sessions()
result = []

for spath in sessions:
    data = parse(spath)

    # Skip short sessions
    if data["stats"]["user_turns"] < 5:
        continue

    sa_list = []
    for sa in find_subagents(spath):
        sa_data = parse(sa)
        sa_list.append({
            "name": sa.stem,
            "prompt": sa_data["user_messages"][0][:500] if sa_data["user_messages"] else None,
            "stats": sa_data["stats"],
        })

    src = "transcripts" if "/transcripts/" in str(spath) else str(spath).split("/projects/")[1].split("/")[0] if "/projects/" in str(spath) else "?"

    result.append({
        "session_id": spath.stem[:24],
        "source": src,
        "cwd": data["cwd"],
        "size_kb": round(spath.stat().st_size / 1024),
        "stats": data["stats"],
        "user_messages": data["user_messages"],
        "tool_summary": data["tool_summary"],
        "subagents": sa_list,
    })

OUT.write_text(json.dumps(result, ensure_ascii=False, indent=1))
print(f"Extracted {len(result)} sessions (last {DAYS}d, top {NUM}) -> {OUT}")
for s in result:
    st = s["stats"]
    sa = f"  sa={len(s['subagents'])}" if s["subagents"] else ""
    ratio = f"  llm/human={st['llm_human_ratio']}x" if st["llm_human_ratio"] else ""
    dur = f"  {st['duration_minutes']}min" if st["duration_minutes"] else ""
    print(f"  {s['session_id'][:20]}  {s['size_kb']}KB  turns={st['user_turns']}+{st['assistant_turns']}  tools={st['tool_calls']}{ratio}{dur}{sa}")
