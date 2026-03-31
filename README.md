# cc-distill

Distill repeated patterns from your Claude Code sessions into reusable skills and AGENTS.md guidelines.

## Usage

Just copy and paste below prompt:

```
Follow this document: https://raw.githubusercontent.com/rycont/cc-distill/refs/heads/master/analyze-sessions.md
```

## Files

| File | Description |
|---|---|
| `analyze-sessions.md` | Main prompt — analysis instructions |
| `extract_sessions.py` | Extract session data from `~/.claude/` |
| `collect_existing.py` | Collect existing skills and AGENTS.md |
| `compact_sessions.py` | Compact large session data for analysis |
