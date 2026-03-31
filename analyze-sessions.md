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

## Phase 2: Analyze

Read both files. The session data is ~800KB and fits in context.

Read `/tmp/existing_context.json` first — study existing skills and AGENTS.md. Understand what kinds of things this user puts in each. This is your reference for classification.

Then read `/tmp/session_analysis.json` in full. Look across ALL sessions simultaneously for:

### Cross-session patterns (most valuable)
- **Repeated user instructions**: same or similar text appearing across multiple sessions (e.g., always pasting a "council mode" prompt, always giving the same setup instructions)
- **Repeated struggles**: same type of failure happening in different sessions (e.g., Docker compose failing in worktrees every time, same build error across projects)
- **Repeated workflow triggers**: user manually orchestrating the same multi-step process each time
- **Repeated corrections**: user interrupting or correcting Claude the same way across sessions (check `Request interrupted` messages — what was Claude doing wrong?)
- **Skill underuse**: existing skills that should have been invoked but weren't (check `/command-name` messages vs available skills)

### Per-session signals
- **llm/human ratio** extremes: very high = Claude talked too much; very low with many tool calls = Claude worked silently but maybe inefficiently
- **Duration vs turns**: long duration with few user turns = Claude spinning alone
- **Subagent patterns**: what subagents were spawned for (check `subagents[].prompt`), whether similar prompts repeat

### Classify each finding → Skill or AGENTS.md

Use the user's existing skills and AGENTS.md as reference examples.

| → AGENTS.md | → Skill |
|---|---|
| Project-specific context | Cross-project workflow |
| Claude should just *know* this without being told | User explicitly invokes it |
| Short directives, file maps, facts | Multi-step procedures |
| Same correction repeated in one project | Same workflow repeated across projects |

### Cross-reference with existing assets

- Already covered by existing skill/AGENTS.md → skip, or note it's not working
- Partially covered → suggest enhancement
- Not covered → suggest new

---

## Output

**Flat bullet list. One line per issue. No headers, no sections.**

Format:
```
- [Skill: /name] or [AGENTS.md: project] — what to do, in one sentence (evidence: sessions X, Y, Z)
```

After the list, ask: "Which of these should I apply?"

**Rules:**
- Every bullet must cite specific session IDs as evidence
- No sensitive data in output (secrets are pre-masked, but double-check)
- If nothing meaningful is found, say so
