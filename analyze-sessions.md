# cc-distill

Distill inefficiencies from Claude Code sessions into actionable improvements.

**Respond in the user's primary language** (detect from their session messages).

---

## Phase 1: Extract (mechanical)

Run both scripts from this repository:

```bash
python3 extract_sessions.py           # → /tmp/session_analysis.json
python3 collect_existing.py           # → /tmp/existing_context.json
```

`extract_sessions.py` args: `[num_sessions] [days]` (default: 20, 30 days).
Sessions are pre-sorted by struggle severity — worst first.

---

## Phase 2: Evaluate (batch subagents)

Read `/tmp/existing_context.json` first — study existing skills and AGENTS.md to understand what the user already has.

Then check the size of `/tmp/session_analysis.json` (`wc -c`).

Spawn **one subagent per session** (or per batch of 2-3 small sessions). Each subagent:

1. Reads its assigned session(s) from `/tmp/session_analysis.json`
2. Answers **one question**: "What went wrong here, if anything?"
3. Returns a **single-line verdict** in this format:

```
OK | no issues
INEFFICIENCY | <what happened> | <one-sentence fix>
```

Examples:
```
INEFFICIENCY | Docker compose failed 8 times — kept retrying same port config | AGENTS.md: "In horang-backend, run `docker compose config` to validate before `up`"
INEFFICIENCY | User pasted the same analysis-mode prompt in 5 sessions | Skill: create /analyze skill with this prompt baked in
INEFFICIENCY | Subagents all searched for schema.prisma independently | AGENTS.md: "Schema is at /db/schema.prisma, read it first"
OK | long session but steady progress, no repeated failures
```

The subagent should look at:
- `struggles` field (pre-computed: errors, retries, churn, thrashing, verbosity, duration)
- `user_messages` (repeated instructions across sessions)
- `subagent_details` (wandering, duplicate work)
- `main_tool_details` (what actually happened step by step)

---

## Phase 3: Synthesize (orchestrator)

Collect all subagent verdicts. Filter out `OK` sessions.

For each `INEFFICIENCY`:
1. **Deduplicate** — group similar issues across sessions
2. **Classify** — Skill or AGENTS.md? Use the user's existing assets as reference:
   - Project-specific, short directive → AGENTS.md
   - Cross-project workflow, multi-step → Skill
3. **Cross-reference** — already covered by existing skill/AGENTS.md? → skip or suggest enhancement
4. **Merge** — if multiple sessions show the same issue, combine into one suggestion

---

## Output format

Present the final result as a **flat bullet list**. One line per issue. No headers, no sections, no explanations beyond the bullet.

Format:
```
- [Skill: /name] or [AGENTS.md: project] — what to do, in one sentence
```

Examples:
```
- [Skill: /analyze] — Create skill with the analysis-mode prompt that's pasted at session start in 5/20 sessions
- [AGENTS.md: horang-backend] — Add "DB schema is at prisma/schema.prisma" — agents search for it in 3 sessions
- [AGENTS.md: horang-frontend-v2] — Add "run `pnpm tsc --noEmit` before committing" — type errors caught late in 4 sessions
- [Skill: /review → enhance] — Add SQL injection check — user manually requests it in 3 sessions
- [AGENTS.md: dalbit-yaksok] — Add "parser rules are in core/prepare/parse/, start there" — subagents wander every time
```

After the list, ask: "Which of these should I apply?"

**Rules:**
- No fabricated patterns — every bullet must cite session evidence
- No sensitive data in output (secrets are pre-masked, but double-check)
- If nothing meaningful is found, say so — don't force suggestions
