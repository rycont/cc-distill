# Claude Code Session Analyzer

Analyze recent Claude Code sessions to find repeated patterns, then distill them into the right improvement — either a **skill** or an **AGENTS.md** guideline.

**Respond in the user's primary language** (detect from their session messages).

---

## Step 1: Extract session data

Run `extract_sessions.py` from this repository.
Args: `python3 extract_sessions.py [num_sessions] [days]` (default: top 20, last 30 days)

```bash
python3 extract_sessions.py           # last 30 days, top 20
python3 extract_sessions.py 30 60    # last 60 days, top 30
```

Output: `/tmp/session_analysis.json`

---

## Step 1.5: Collect existing skills and AGENTS.md

Run `collect_existing.py` to gather the user's existing skills and AGENTS.md files.
These serve two purposes:
1. Avoid duplicate suggestions
2. **Act as reference examples** for how this user structures skills vs AGENTS.md

```bash
python3 collect_existing.py
```

Output: `/tmp/existing_context.json`

---

## Step 2: Read data

Read `/tmp/existing_context.json` directly using the Read tool.
**Study the existing skills and AGENTS.md carefully** — understand what kinds of things this user puts in each. This informs your classification decisions in Step 3.

For `/tmp/session_analysis.json`, check the file size first (`wc -c`).
- **Under 200KB**: Read it directly.
- **200KB or larger**: Do NOT compact or truncate the data. Instead, spawn subagents (via the Agent tool) to read and summarize portions of the file in parallel. For example:
  - Subagent 1: Read sessions 1-7, summarize user message patterns and tool usage
  - Subagent 2: Read sessions 8-14, same task
  - Subagent 3: Read sessions 15-20, same task
  
  Each subagent should read its assigned portion of `/tmp/session_analysis.json` using the Read tool (with offset/limit or by parsing the JSON), then return a structured summary containing:
  - Recurring user message themes and exact quotes
  - Tool usage counts and repeated tool patterns
  - Subagent tool patterns
  
  Collect all subagent summaries before proceeding to Step 3.

---

## Step 3: Find patterns and classify

### 3a: Find all repeated patterns

Scan across sessions for any kind of repetition:

- **User message patterns**: similar instructions, recurring prefixes/suffixes, repeated requests
- **Tool usage patterns**: repeated tool sequences (Grep→Read→Grep→Read loops), subagent wandering, always searching for the same entry points
- **Workflow patterns**: multi-step processes the user triggers manually each time
- **Context-setting patterns**: boilerplate the user pastes to set up Claude's behavior

### 3b: Classify each pattern → Skill or AGENTS.md

For each pattern found, decide whether it should become a **skill** or an **AGENTS.md guideline**. Use the user's existing skills and AGENTS.md (from Step 2) as reference examples for how they draw this line.

General principles:

| Signal | → AGENTS.md | → Skill |
|---|---|---|
| Scope | Project-specific context | Cross-project or workflow-level |
| Trigger | Claude should just *know* this | User explicitly invokes it |
| Nature | Short directives, facts, file maps | Multi-step procedures, structured output |
| Examples | "Always read config.ts first in this project", "The DB schema is in /db/schema.prisma", "Don't mock the database in tests" | "/deploy", "/review-pr", "run tests → fix → commit cycle" |
| Repetition type | Same short instruction repeated across sessions in one project | Same multi-step workflow repeated across projects |
| Tool patterns | Agent always searches for the same files → tell it where to look | Grep→Read→Edit→Test loop repeated → automate the workflow |

**Edge cases — use judgment:**
- A pattern that repeats in only one project → likely AGENTS.md
- A pattern that repeats across many projects → likely a skill
- A short instruction that the user always gives at session start → could be either; check if it's project-specific or universal
- Subagent inefficiency in a specific codebase → AGENTS.md (give the agent a map)
- Subagent inefficiency that's structural (always too many agents, wrong tool choices) → skill or general guidance

### 3c: Cross-reference with existing assets

Before finalizing suggestions:

**For patterns classified as skills** — check `/tmp/existing_context.json` → `skills`:
- Already covered by existing skill → skip, or note if the existing skill needs updates
- Partially covered → suggest enhancing the existing skill
- Not covered → suggest a new skill

**For patterns classified as AGENTS.md** — check `/tmp/existing_context.json` → `agents_md`:
- Already covered in existing AGENTS.md → skip, or analyze why it's not working
- Partially covered → suggest additions
- No AGENTS.md exists for that project → suggest creating one

---

## Step 4: Present results

For each pattern, present:
1. **Pattern name**
2. **Evidence**: actual message excerpts or tool sequences (with session IDs)
3. **Classification**: Skill or AGENTS.md, with reasoning
4. **Relationship to existing assets**: `New` / `Enhance existing` / `Already covered (skip)`
5. **Draft**: skill definition or AGENTS.md guideline, ready to use. Or a diff to an existing file.

Then ask the user:
1. Which suggestions they want to apply
2. Whether any classifications should be flipped (skill ↔ AGENTS.md)
3. Whether to adjust scope (more sessions, specific project, etc.)

**Important:**
- Do not fabricate patterns without evidence from the data
- Be cautious about sensitive information (passwords, API keys, etc.) in user messages — do not output them
- Respond in the user's primary language (detect from their session messages)
