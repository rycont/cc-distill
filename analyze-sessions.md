# cc-distill

Distill inefficiencies from Claude Code sessions into actionable improvements.

**Respond in the user's primary language** (detect from their session messages).

---

## Step 1: Extract

Run both scripts from this repository:

```bash
python3 extract_sessions.py           # → /tmp/session_analysis.json + /tmp/session_0.json, session_1.json, ...
python3 collect_existing.py           # → /tmp/existing_context.json
```

`extract_sessions.py` args: `[num_sessions] [days]` (default: 20, 7 days).

---

## Step 2: Analyze (two parallel tracks)

1. Read `/tmp/existing_context.json` — study existing skills and AGENTS.md as classification reference.
2. Read `/tmp/session_analysis.json` — this is the combined file for your cross-session analysis.
3. Launch Track B subagents (see below), then immediately start Track A yourself.

### Track A: Cross-session patterns (you, directly — do NOT delegate this)

Look across ALL sessions simultaneously for:

- Same or similar user instructions appearing in multiple sessions
- Same type of failure/struggle happening across sessions (check `bash_commands` for repeated failures)
- User manually orchestrating the same multi-step workflow each time
- User interrupting or correcting Claude the same way (`Request interrupted`, angry corrections)
- Existing skills that should have been invoked but weren't

### Track B: Per-session deep dive (one Sonnet subagent per session, all background)

Spawn one subagent per session. All at once, all in background, all using `model: "sonnet"`. Each subagent reads **its own file** — `/tmp/session_0.json`, `/tmp/session_1.json`, etc. (NOT the combined file). Each returns:

```
OK — no significant waste
```
or one `WASTE` line per issue found (there can be multiple):
```
WASTE: <what happened> — <scale>
WASTE: <what happened> — <scale>
```

No classification, no suggestions — just list every significant waste with evidence.

### After both tracks complete, merge results

Deduplicate: Track B individual findings that match Track A cross-session patterns get merged (the cross-session pattern is more important). Track B findings that are unique stay as standalone items.

---

## Step 2.5: Root-cause analysis for existing rules that failed

**This is the most important step.** After merging Track A + Track B, identify every finding that already has a corresponding rule in existing skills, AGENTS.md, or memory files.

For each such finding, spawn a **Sonnet subagent in background** to investigate why the rule failed. Give each subagent:
- The exact existing rule (quoted from `/tmp/existing_context.json`)
- The session IDs where it was violated
- The individual session files (`/tmp/session_N.json`) to examine

Each subagent reads the relevant sessions and returns:

```
RULE: <quote the existing rule>
VIOLATED IN: <session IDs>
CAUSE: <one of: subagent-no-inherit | too-vague | buried-in-long-file | conflicts-with-X | compaction-dropped | other: ...>
EVIDENCE: <what Claude was doing right before the violation — be specific>
FIX: <proposed fix addressing the root cause>
```

Launch all root-cause subagents at once (background, `model: "sonnet"`), then wait for all to complete before proceeding to Step 3.

**Key principle: Do NOT propose adding a rule that already exists in the same form. That is useless.** Fixes must address the root cause:
- Subagents don't see it → inject into subagent prompts, or add a hook
- Too vague → rewrite with exact commands/paths
- Buried → move to top of AGENTS.md, or split into a dedicated section
- Unenforceable by prompt → suggest a hook (`settings.json`) that blocks the action mechanically

---

## Step 3: Classify and output

**Classify each finding** as Skill, AGENTS.md, Hook, or Rule Rewrite. Use existing assets as reference.

**Important: Skills and AGENTS.md must reference each other.**
- If you propose a new Skill (e.g., `/e2e-setup`), also propose an AGENTS.md entry telling Claude when to use it (e.g., "Before E2E testing, run `/e2e-setup`").
- If you propose an AGENTS.md guideline that a Skill could automate, note that too.
- If an existing Skill should be mentioned in AGENTS.md but isn't, flag it.

### Output format

Three tables. **Rule Fixes first** (highest value — fixing what's already broken), then new proposals.

#### Rule Fixes (existing rules that aren't working)

| # | Current rule | Why it failed | Fix | Evidence |
|---|-------------|---------------|-----|----------|
| 1 | memory: "agent-browser 사용, gstack 금지" | Subagents don't inherit memory files; rule only in feedback, not AGENTS.md | Move to AGENTS.md top section + add hook blocking `gstack` binary | a55bead5 (143 calls), 16b298fc (66 calls) |
| 2 | AGENTS.md: "회고 검색 후 작업 시작" | Rule is vague — doesn't specify search keywords or directory | Rewrite: "작업 시작 전 `rg <관련키워드> notes/` 실행하여 회고 확인" | 46fe6c33, 0f68f9e9 |

#### New Skills

| # | Name | Action | AGENTS.md link | Evidence |
|---|------|--------|----------------|----------|
| 1 | `/e2e-setup` (new) | Docker + DB seed + auth + health check 자동화 | → AGENTS.md #N | 0f68f9e9, a55bead5 |

#### New AGENTS.md entries

| # | Project | Guideline | Skill link | Evidence |
|---|---------|-----------|------------|----------|
| N | horang | E2E 테스트 전에 `/e2e-setup` 실행 | ← Skill #1 | 0f68f9e9, a55bead5 |

Session IDs truncated to first 8 chars. One sentence per cell max.

Then ask: "Which of these should I apply? (e.g., `1, 3, 5` or `all`)"

**Rules:**
- Every row must cite session IDs
- Skills without a corresponding AGENTS.md entry are incomplete — always pair them
- Rule Fixes must explain WHY it failed, not just what to change
- Do NOT propose adding a rule that already exists in the same form
- No sensitive data in output
- If nothing meaningful is found, say so
