# cc-distill

## Copy & Paste Prompt

```
Follow this document: https://raw.githubusercontent.com/rycont/cc-distill/refs/heads/master/analyze-sessions.md
```

## What it does

- Scans your recent Claude Code sessions (last 30 days)
- Detects struggles: repeated errors, edit churn, bash retries, thrashing
- Evaluates each session via subagents to find real inefficiencies
- Outputs a flat bullet list of actionable fixes (Skills or AGENTS.md)
