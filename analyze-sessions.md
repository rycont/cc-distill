# cc-distill

Distill inefficiencies from Claude Code sessions into actionable improvements.

**Respond in the user's primary language** (detect from their session messages).

---

## Step 1: Extract

Run both scripts from this repository:

```bash
python3 extract_sessions.py           # → /tmp/session_analysis.json
python3 collect_existing.py           # → /tmp/existing_context.json
```

`extract_sessions.py` args: `[num_sessions] [days]` (default: 20, 7 days).

---

## Step 2: Read and analyze

Do NOT spawn subagents. Do everything yourself in this conversation.

1. Read `/tmp/existing_context.json` — study existing skills and AGENTS.md as classification reference.
2. Read `/tmp/session_analysis.json` in full. Look across ALL sessions for:

**Repeated patterns across sessions:**
- Same or similar user instructions appearing in multiple sessions
- Same type of failure/struggle happening across sessions (check `bash_commands` for repeated failures)
- User manually orchestrating the same multi-step workflow each time
- User interrupting or correcting Claude the same way (`Request interrupted`, angry corrections)
- Existing skills that should have been invoked but weren't

**Per-session severe issues:**
- Extreme `llm_human_ratio` (>5x = Claude talked too much)
- Long `duration_minutes` with few `user_turns` = Claude spinning alone
- Same bash command retried many times in one session

**Classify each finding:**
- Project-specific directive → AGENTS.md
- Cross-project workflow → Skill

**Cross-reference** with existing skills/AGENTS.md — skip what's already covered, or note it's not working.

---

## Step 3: Output

Two tables, then ask for selection.

### Skills

| # | Name | Action | Evidence |
|---|------|--------|----------|
| 1 | `/example` (new) | One sentence description | sess1, sess2 |

### AGENTS.md

| # | Project | Guideline | Evidence |
|---|---------|-----------|----------|
| 1 | project | One sentence directive | sess1, sess2 |

Session IDs truncated to first 8 chars. Each Action/Guideline is one sentence max.

Then ask: "Which of these should I apply? (e.g., `1, 3, 5` or `all`)"

**Rules:**
- Every row must cite session IDs
- No sensitive data in output
- If nothing meaningful is found, say so
