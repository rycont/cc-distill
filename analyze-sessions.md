# Claude Code Session Analyzer

Analyze recent long Claude Code sessions to:
1. Find **repeated instruction patterns** and suggest skill candidates
2. Find **inefficient exploration patterns** and suggest AGENTS.md guidelines

**Respond in the user's primary language** (detect from their session messages).

---

## Step 1: Extract session data

Run `extract_sessions.py` from this repository.
Args: `python3 extract_sessions.py [num_sessions] [days]` (default: top 20, last 7 days)

```bash
python3 extract_sessions.py          # last 7 days, top 20
python3 extract_sessions.py 20 30   # last 30 days, top 20
```

Output: `/tmp/session_analysis.json`

---

## Step 1.5: Collect existing skills and AGENTS.md

Run `collect_existing.py` to gather the user's existing skills and AGENTS.md files.

```bash
python3 collect_existing.py
```

Output: `/tmp/existing_context.json`

---

## Step 2: Read data

Read `/tmp/existing_context.json` directly using the Read tool.

For `/tmp/session_analysis.json`, check the file size first (`wc -c`).
- **Under 200KB**: Read it directly.
- **200KB or larger**: Do NOT compact or truncate the data. Instead, spawn subagents (via the Agent tool) to read and summarize portions of the file in parallel. For example:
  - Subagent 1: Read sessions 1-3, summarize user message patterns and tool usage
  - Subagent 2: Read sessions 4-6, same task
  - Subagent 3: Read sessions 7-10, same task
  
  Each subagent should read its assigned portion of `/tmp/session_analysis.json` using the Read tool (with offset/limit or by parsing the JSON), then return a structured summary containing:
  - Recurring user message themes and exact quotes
  - Tool usage counts and repeated tool patterns
  - Subagent tool patterns
  
  Collect all subagent summaries before proceeding to Step 3.

---

## Step 3: Analysis

Analyze the extracted data along two axes.

### Analysis A: Repeated instruction patterns → Skill candidates

**Cross-analyze `user_messages` across sessions** looking for:

- Similar instructions/requests appearing across multiple sessions
- Recurring prefixes/suffixes (text acting as a system prompt)
- Repeatedly requested workflows (e.g., "run tests and commit")
- Manual instructions for specific tool combinations

**Cross-reference with existing skills** (`/tmp/existing_context.json` → `skills`):
- If a pattern matches an existing skill → **suggest modifications/improvements** to the existing skill instead of a new one
- If an existing skill partially covers the pattern → suggest what to add specifically
- Only suggest new skills for patterns not covered by any existing skill

For each pattern:
1. Pattern name
2. Frequency (N sessions)
3. Evidence (actual message excerpts)
4. **Relationship to existing skills**: `New` / `Enhance /skill-name` / `Already covered by /skill-name (skip)`
5. Skill draft or diff to existing skill

### Analysis B: Inefficient exploration patterns → AGENTS.md guidelines

**Analyze tool usage patterns** (`main_repeated_patterns`, `subagent_*`) looking for:

- Repetitive search loops like Grep → Read → Grep → Read
- Common wandering patterns across subagents (e.g., multiple agents searching for the same files)
- Excessive or insufficient Agent tool usage
- Patterns where sessions always search for the same entry points in a project
- Significant divergence between main session and subagent tool usage ratios (inefficiency signal)

**Cross-reference with existing AGENTS.md** (`/tmp/existing_context.json` → `agents_md`):
- Projects that already have AGENTS.md → compare and **only suggest missing guidelines**
- If existing guidelines already cover the issue → skip, or analyze why they aren't working
- Projects without AGENTS.md → suggest creating one

For each pattern:
1. What inefficiency exists
2. Which project/context it occurs in
3. **Relationship to existing AGENTS.md**: `Create new` / `Augment existing (path)` / `Already covered (skip)`
4. Guideline draft or diff to existing file

---

## Step 4: Present results

Show the analysis to the user and ask:

1. Which suggested skills they want to create or modify
2. Whether to apply AGENTS.md guidelines (create new or augment existing)
3. Whether to adjust the analysis scope (more sessions, specific project only, etc.)

**Important:**
- Do not fabricate patterns without evidence from the data
- Be cautious about sensitive information (passwords, API keys, etc.) in user messages — do not output them
- Respond in the user's primary language (detect from their session messages)
