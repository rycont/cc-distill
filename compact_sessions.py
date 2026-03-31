#!/usr/bin/env python3
"""Compact large session data to a manageable size."""
import json

data = json.loads(open("/tmp/session_analysis.json").read())
for s in data:
    msgs = s["user_messages"]
    if len(msgs) > 10:
        s["user_messages"] = msgs[:4] + [f"...({len(msgs)-8} omitted)..."] + msgs[-4:]
    s["user_messages"] = [m[:1000] + "..." if len(m) > 1000 else m for m in s["user_messages"]]
open("/tmp/session_analysis.json", "w").write(json.dumps(data, ensure_ascii=False, indent=1))
print("Compacted:", round(len(json.dumps(data, ensure_ascii=False)) / 1024), "KB")
