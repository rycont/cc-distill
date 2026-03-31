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

## Step 2: Analyze (two parallel tracks)

1. Read `/tmp/existing_context.json` — study existing skills and AGENTS.md as classification reference.
2. Read `/tmp/session_analysis.json` in full.
3. Launch **exactly 4 subagents** for Track B (see below), then immediately proceed with Track A yourself.

### Track A: Cross-session patterns (you, directly — do NOT delegate this)

Look across ALL sessions simultaneously for:

- Same or similar user instructions appearing in multiple sessions
- Same type of failure/struggle happening across sessions (check `bash_commands` for repeated failures)
- User manually orchestrating the same multi-step workflow each time
- User interrupting or correcting Claude the same way (`Request interrupted`, angry corrections)
- Existing skills that should have been invoked but weren't

### Track B: Per-session severe waste (exactly 4 background subagents)

Split the sessions into 4 roughly equal batches. Spawn exactly 4 subagents, all at once, all in background. Each reads its batch from `/tmp/session_analysis.json` and returns **one line per session**:

```
session_id | OK
session_id | WASTE: <what happened> — <scale: e.g., "47 failed docker commands", "same file edited 12 times">
```

That's it. No analysis, no suggestions — just flag waste with evidence. You handle classification in Step 3.

### After both tracks complete

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
