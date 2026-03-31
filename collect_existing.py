#!/usr/bin/env python3
"""
Collect existing skills and AGENTS.md files.
- ~/.claude/skills/*/SKILL.md
- AGENTS.md found in project roots (cwd-based search)

Output: /tmp/existing_context.json
"""
import json, os
from pathlib import Path

CLAUDE_DIR = Path.home() / ".claude"
OUT = Path("/tmp/existing_context.json")

result = {"skills": [], "agents_md": []}

# ── Collect skills ──
skills_dir = CLAUDE_DIR / "skills"
if skills_dir.is_dir():
    for skill_dir in sorted(skills_dir.iterdir()):
        skill_md = skill_dir / "SKILL.md"
        if skill_md.is_file():
            content = skill_md.read_text(errors="replace")
            result["skills"].append({
                "name": skill_dir.name,
                "path": str(skill_md),
                "content": content[:5000],
            })

# ── Collect AGENTS.md: extract cwds from project sessions, search for AGENTS.md ──
seen_cwds = set()
projects_dir = CLAUDE_DIR / "projects"
if projects_dir.is_dir():
    for proj_dir in projects_dir.iterdir():
        if not proj_dir.is_dir():
            continue
        for jsonl in proj_dir.glob("*.jsonl"):
            with open(jsonl, "r", errors="replace") as f:
                for line in f:
                    try:
                        d = json.loads(line)
                    except:
                        continue
                    if d.get("type") == "user" and d.get("cwd"):
                        seen_cwds.add(d["cwd"])
                        break
            if len(seen_cwds) > 50:
                break

for cwd in sorted(seen_cwds):
    p = Path(cwd)
    for check in [p, p.parent, p.parent.parent]:
        agents_md = check / "AGENTS.md"
        if agents_md.is_file():
            content = agents_md.read_text(errors="replace")
            result["agents_md"].append({
                "project_root": str(check),
                "path": str(agents_md),
                "content": content[:5000],
            })
            break

# Deduplicate
seen_paths = set()
deduped = []
for a in result["agents_md"]:
    if a["path"] not in seen_paths:
        seen_paths.add(a["path"])
        deduped.append(a)
result["agents_md"] = deduped

OUT.write_text(json.dumps(result, ensure_ascii=False, indent=1))
print(f"Collected -> {OUT}")
print(f"  Skills: {len(result['skills'])}")
for s in result["skills"]:
    print(f"    /{s['name']}")
print(f"  AGENTS.md: {len(result['agents_md'])}")
for a in result["agents_md"]:
    print(f"    {a['path']}")
