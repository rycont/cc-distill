#!/usr/bin/env python3
"""
Claude Code session data extractor.
Sources:
  - ~/.claude/transcripts/*.jsonl (legacy format)
  - ~/.claude/projects/*/*.jsonl (current format)
  - Subagents included (*/subagents/*.jsonl)

Output: /tmp/session_analysis.json
"""
import sys, json, os, time
from pathlib import Path

NUM = int(sys.argv[1]) if len(sys.argv) > 1 else 20
DAYS = int(sys.argv[2]) if len(sys.argv) > 2 else 30
CLAUDE_DIR = Path.home() / ".claude"
OUT = Path("/tmp/session_analysis.json")
CUTOFF = time.time() - DAYS * 86400


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


def parse_jsonl(fpath):
    """Parse JSONL file -> (user_messages, tool_sequence, tool_counts, cwd)"""
    user_msgs, tools, counts, cwd = [], [], {}, None

    with open(fpath, "r", errors="replace") as f:
        for line in f:
            try:
                d = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            dtype = d.get("type", "")

            # Current format: type=user, message.content
            if dtype == "user" and "message" in d:
                content = d["message"].get("content", "")
                text = _extract_text(content)
                if text:
                    user_msgs.append(text[:3000])
                if d.get("cwd") and not cwd:
                    cwd = d["cwd"]

            # Current format: type=assistant, tool_use blocks
            elif dtype == "assistant" and "message" in d:
                for block in (d["message"].get("content") or []):
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        tn = block.get("name", "?")
                        tools.append(tn)
                        counts[tn] = counts.get(tn, 0) + 1

            # Legacy format: type=user, content directly
            elif dtype == "user" and "message" not in d:
                text = _extract_text(d.get("content", ""))
                if text:
                    user_msgs.append(text[:3000])

            # Legacy format: type=tool_use
            elif dtype == "tool_use":
                tn = d.get("tool_name", "?")
                tools.append(tn)
                counts[tn] = counts.get(tn, 0) + 1

    return user_msgs, tools, counts, cwd


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


def repeated_patterns(tool_seq, min_count=3):
    """Detect repeated tool sequences using sliding windows of size 2-5."""
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
    msgs, tools, tcounts, cwd = parse_jsonl(spath)

    sa_files = find_subagents(spath)
    subagents = []
    all_sa_tools = []
    for sa in sa_files:
        _, sa_tools, sa_counts, _ = parse_jsonl(sa)
        all_sa_tools.extend(sa_tools)
        subagents.append({
            "name": sa.name.replace(".jsonl", ""),
            "size_kb": round(sa.stat().st_size / 1024),
            "tool_counts": sa_counts,
            "repeated_patterns": repeated_patterns(sa_tools),
        })

    src = "transcripts" if "/transcripts/" in str(spath) else str(spath).split("/projects/")[1].split("/")[0] if "/projects/" in str(spath) else "?"

    result.append({
        "session_id": spath.stem[:24],
        "source": src,
        "cwd": cwd,
        "size_kb": round(spath.stat().st_size / 1024),
        "user_message_count": len(msgs),
        "user_messages": msgs,
        "main_tool_counts": tcounts,
        "main_tool_calls": sum(tcounts.values()),
        "main_repeated_patterns": repeated_patterns(tools),
        "subagent_count": len(subagents),
        "subagent_total_calls": len(all_sa_tools),
        "subagent_tool_counts": dict(
            sorted(
                {k: v for sa in subagents for k, v in sa["tool_counts"].items()}.items(),
                key=lambda x: -x[1],
            )[:20]
        ) if subagents else {},
        "subagent_repeated_patterns": repeated_patterns(all_sa_tools),
        "subagent_details": subagents,
    })

OUT.write_text(json.dumps(result, ensure_ascii=False, indent=1))
print(f"Extracted {len(result)} sessions (last {DAYS} days, top {NUM}) -> {OUT}")
for s in result:
    sa = f", subagents={s['subagent_count']}" if s["subagent_count"] else ""
    print(f"  {s['session_id']}  {s['size_kb']}KB  msgs={s['user_message_count']}  tools={s['main_tool_calls']}{sa}  [{s['source'][:30]}]")
