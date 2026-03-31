# cc-distill

Distill your Claude Code sessions into Skills, AGENTS.md guidelines, and fixes for rules that aren't working.

## Copy & Paste Prompt

```
Follow this document: https://raw.githubusercontent.com/rycont/cc-distill/refs/heads/master/analyze-sessions.md
```

## What it does

1. Extracts recent sessions (last 7 days, top 20 by size) with full bash commands, tool usage, and subagent prompts
2. Finds cross-session patterns (repeated instructions, repeated failures, workflow bottlenecks)
3. Deep-dives each session via parallel Sonnet subagents to find per-session waste
4. **Root-cause analyzes existing rules that aren't being followed** — diagnoses WHY and proposes structural fixes
5. Outputs three tables: Rule Fixes, New Skills, New AGENTS.md — with cross-references between them
