# cc-distill

Distill inefficiencies from Claude Code sessions into actionable improvements.

**Respond in the user's primary language** (detect from their session messages).

---

## Phase 1: Extract

Run both scripts from this repository:

```bash
python3 extract_sessions.py           # → /tmp/session_analysis.json
python3 collect_existing.py           # → /tmp/existing_context.json
```

`extract_sessions.py` args: `[num_sessions] [days]` (default: 20, 7 days).

---

## Phase 2: Analyze (two tracks in parallel)

First, read `/tmp/existing_context.json` — study existing skills and AGENTS.md as classification reference.

Then run **both tracks simultaneously**:

### Track A: Cross-session patterns (you, directly)

Read `/tmp/session_analysis.json` in full. Do NOT spawn subagents for this — you must see all sessions at once. Look for:

- **Repeated user instructions**: same or similar text across multiple sessions
- **Repeated struggles**: same type of failure in different sessions
- **Repeated workflow triggers**: user manually orchestrating the same multi-step process
- **Repeated corrections**: user interrupting or correcting Claude the same way (check `Request interrupted` and what preceded it)
- **Skill underuse**: existing skills that should have been invoked but weren't

### Track B: Per-session deep dive (subagents, in background)

Spawn one subagent per session (or batch 2-3 small ones). Run them all in the background while you work on Track A. Each subagent reads its assigned session from `/tmp/session_analysis.json` and answers:

> "What was the single biggest waste of time in this session? Look at bash commands that failed repeatedly, files edited over and over, long stretches of tool calls without progress. If nothing significant, say OK."

Each subagent returns one line:
```
OK
```
or:
```
WASTE | <what happened, specifically> | <how long / how many retries>
```

---

## Phase 3: Synthesize

Collect Track A findings and Track B subagent results. Merge them:

1. **Deduplicate** — Track B might find individual instances of what Track A found as a pattern. Merge these (the cross-session pattern is more valuable).
2. **Classify** — Skill or AGENTS.md? Use existing assets as reference:
   - Project-specific, short directive → AGENTS.md
   - Cross-project workflow, multi-step → Skill
3. **Cross-reference** — skip what's already covered by existing skills/AGENTS.md, or note if existing guidance isn't working.

---

## Output

Group findings by type. Use this exact format:

```
### Skills

| # | Name | Action | Evidence |
|---|------|--------|----------|
| 1 | `/dev-up` (new) | Docker compose + DB seed + health check를 한 커맨드로 | 0f68f9e9, 55c4b8ad, ecf9e93d |
| 2 | `/code-review` (enhance) | APPROVED까지 자동 반복 루프 추가 | 55c4b8ad, abe6ebd3, 46fe6c33 |

### AGENTS.md

| # | Project | Guideline | Evidence |
|---|---------|-----------|----------|
| 1 | horang | 작업 전 `/notes/task-log/` 회고 먼저 읽기 | 0f68f9e9, 55c4b8ad, 46fe6c33 |
| 2 | horang-frontend-v2 | 기존 컴포넌트 확인 후 UI 생성, px 하드코딩 금지 | a55bead5, 16b298fc |
```

Keep each Action cell to one sentence. Session IDs can be truncated to first 8 chars.

After the tables, ask: "Which of these should I apply? (e.g., `1, 3, 5` or `all`)"

**Rules:**
- Every row must cite specific session IDs as evidence
- No sensitive data in output
- If nothing meaningful is found, say so
