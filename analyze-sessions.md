# Claude Code Session Analyzer

최근 긴 Claude Code 세션들을 분석하여:
1. **반복 지시 패턴**을 찾아 스킬 후보를 제안
2. **비효율적 탐색 패턴**을 찾아 AGENTS.md 가이드라인을 제안

---

## Step 1: 세션 데이터 추출

아래 Python 스크립트를 `/tmp/extract_sessions.py`에 저장하고 실행하세요.
인자: `python3 script.py [세션수] [기간(일)]` (기본: 상위 10개, 최근 7일)

```python
#!/usr/bin/env python3
"""
Claude Code 세션 데이터 추출기
- ~/.claude/transcripts/*.jsonl (구형식)
- ~/.claude/projects/*/*.jsonl (신형식)
- 서브에이전트 포함 (*/subagents/*.jsonl)

출력: /tmp/session_analysis.json
"""
import sys, json, os
from pathlib import Path

import time

NUM = int(sys.argv[1]) if len(sys.argv) > 1 else 10
DAYS = int(sys.argv[2]) if len(sys.argv) > 2 else 7
CLAUDE_DIR = Path.home() / ".claude"
OUT = Path("/tmp/session_analysis.json")
CUTOFF = time.time() - DAYS * 86400


def find_all_sessions():
    """최근 N일 내 수정된 메인 세션 중 크기순 상위 NUM개"""
    files = []
    for d in [CLAUDE_DIR / "transcripts", CLAUDE_DIR / "projects"]:
        if not d.exists():
            continue
        for f in d.rglob("*.jsonl"):
            if "/subagents/" in str(f):
                continue
            if f.stat().st_mtime >= CUTOFF:
                files.append(f)
    files.sort(key=lambda f: f.stat().st_size, reverse=True)
    return files[:NUM]


def find_subagents(session_path):
    """메인 세션에 딸린 서브에이전트 파일 목록"""
    sa_dir = session_path.with_suffix("") / "subagents"
    if sa_dir.is_dir():
        return sorted(sa_dir.glob("*.jsonl"), key=lambda f: f.stat().st_size, reverse=True)
    return []


def parse_jsonl(fpath):
    """JSONL 파일을 파싱하여 (user_messages, tool_sequence, tool_counts, cwd) 반환"""
    user_msgs, tools, counts, cwd = [], [], {}, None

    with open(fpath, "r", errors="replace") as f:
        for line in f:
            try:
                d = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            dtype = d.get("type", "")

            # ── 신형식: type=user, message.content ──
            if dtype == "user" and "message" in d:
                content = d["message"].get("content", "")
                text = _extract_text(content)
                if text:
                    user_msgs.append(text[:3000])
                if d.get("cwd") and not cwd:
                    cwd = d["cwd"]

            # ── 신형식: type=assistant, tool_use blocks ──
            elif dtype == "assistant" and "message" in d:
                for block in (d["message"].get("content") or []):
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        tn = block.get("name", "?")
                        tools.append(tn)
                        counts[tn] = counts.get(tn, 0) + 1

            # ── 구형식: type=user (content 직접) ──
            elif dtype == "user" and "message" not in d:
                text = _extract_text(d.get("content", ""))
                if text:
                    user_msgs.append(text[:3000])

            # ── 구형식: type=tool_use ──
            elif dtype == "tool_use":
                tn = d.get("tool_name", "?")
                tools.append(tn)
                counts[tn] = counts.get(tn, 0) + 1

    return user_msgs, tools, counts, cwd


def _extract_text(content):
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for b in content:
            if isinstance(b, str):
                parts.append(b)
            elif isinstance(b, dict) and b.get("type") == "text":
                parts.append(b.get("text", ""))
        return "\n".join(parts).strip()
    return ""


def repeated_patterns(tool_seq, min_count=3):
    """길이 2~5 슬라이딩 윈도우로 반복 도구 시퀀스 탐지"""
    pats = {}
    for ws in range(2, 6):
        for i in range(len(tool_seq) - ws + 1):
            p = " -> ".join(tool_seq[i : i + ws])
            pats[p] = pats.get(p, 0) + 1
    return {k: v for k, v in sorted(pats.items(), key=lambda x: -x[1])[:15] if v >= min_count}


# ── Main ──
sessions = find_all_sessions()
result = []

for spath in sessions:
    msgs, tools, tcounts, cwd = parse_jsonl(spath)

    # 서브에이전트
    sa_files = find_subagents(spath)
    subagents = []
    all_sa_tools = []
    for sa in sa_files:
        _, sa_tools, sa_counts, _ = parse_jsonl(sa)
        all_sa_tools.extend(sa_tools)
        subagents.append({
            "name": sa.name.replace(".jsonl", ""),
            "size_kb": round(sa.stat().st_size / 1024),
            "tool_counts": sa_counts,
            "repeated_patterns": repeated_patterns(sa_tools),
        })

    # 소스 판별
    src = "transcripts" if "/transcripts/" in str(spath) else str(spath).split("/projects/")[1].split("/")[0] if "/projects/" in str(spath) else "?"

    result.append({
        "session_id": spath.stem[:24],
        "source": src,
        "cwd": cwd,
        "size_kb": round(spath.stat().st_size / 1024),
        "user_message_count": len(msgs),
        "user_messages": msgs,
        "main_tool_counts": tcounts,
        "main_tool_calls": sum(tcounts.values()),
        "main_repeated_patterns": repeated_patterns(tools),
        "subagent_count": len(subagents),
        "subagent_total_calls": len(all_sa_tools),
        "subagent_tool_counts": dict(
            sorted(
                {k: v for sa in subagents for k, v in sa["tool_counts"].items()}.items(),
                key=lambda x: -x[1],
            )[:20]
        ) if subagents else {},
        "subagent_repeated_patterns": repeated_patterns(all_sa_tools),
        "subagent_details": subagents,
    })

OUT.write_text(json.dumps(result, ensure_ascii=False, indent=1))
print(f"추출 완료: {len(result)}개 세션 (최근 {DAYS}일, 상위 {NUM}개) → {OUT}")
for s in result:
    sa = f", subagents={s['subagent_count']}" if s["subagent_count"] else ""
    print(f"  {s['session_id']}  {s['size_kb']}KB  msgs={s['user_message_count']}  tools={s['main_tool_calls']}{sa}  [{s['source'][:30]}]")
```

실행:

```bash
python3 /tmp/extract_sessions.py 10 7    # 최근 7일, 상위 10개
python3 /tmp/extract_sessions.py 10 30   # 최근 30일, 상위 10개
```

---

## Step 2: 데이터 읽기

`/tmp/session_analysis.json`을 Read 도구로 읽으세요.
파일이 너무 크면 (200KB+) 아래 축소 스크립트를 먼저 실행하세요:

```python
#!/usr/bin/env python3
"""큰 세션 데이터를 분석 가능한 크기로 축소"""
import json
data = json.loads(open("/tmp/session_analysis.json").read())
for s in data:
    msgs = s["user_messages"]
    if len(msgs) > 10:
        s["user_messages"] = msgs[:4] + [f"...({len(msgs)-8}개 생략)..."] + msgs[-4:]
    s["user_messages"] = [m[:1000] + "..." if len(m) > 1000 else m for m in s["user_messages"]]
open("/tmp/session_analysis.json", "w").write(json.dumps(data, ensure_ascii=False, indent=1))
print("축소 완료:", round(len(json.dumps(data, ensure_ascii=False))/1024), "KB")
```

---

## Step 3: 분석

추출된 데이터를 바탕으로 아래 두 가지를 분석하세요.

### 분석 A: 반복 지시 패턴 → 스킬 후보

**사용자 메시지(`user_messages`)를 중심으로** 세션들을 횡단 분석하세요:

- 여러 세션에서 반복되는 비슷한 지시/요청 패턴
- 매번 붙이는 접두사/접미사 (시스템 프롬프트 역할을 하는 텍스트)
- 반복적으로 요청하는 워크플로우 (예: "테스트 돌리고 커밋해줘" 류)
- 특정 도구 조합을 매번 수동으로 지시하는 경우

각 패턴에 대해:
1. 패턴 이름
2. 발견 빈도 (N개 세션)
3. 실제 메시지 발췌 (증거)
4. 스킬로 만들면 어떤 형태가 될지 초안

### 분석 B: 비효율적 탐색 패턴 → AGENTS.md 가이드라인

**도구 사용 패턴(`main_repeated_patterns`, `subagent_*`)을 중심으로** 분석하세요:

- Grep → Read → Grep → Read 같은 반복 탐색 루프
- 서브에이전트들이 공통적으로 방황하는 패턴 (같은 파일을 여러 에이전트가 탐색 등)
- Agent를 과도하게 또는 부족하게 사용하는 패턴
- 특정 프로젝트에서 항상 같은 엔트리포인트를 찾아 헤매는 패턴
- 서브에이전트의 도구 사용 비율이 메인 세션과 크게 다른 경우 (비효율 신호)

각 패턴에 대해:
1. 어떤 비효율이 있는지
2. 어떤 프로젝트/상황에서 발생하는지
3. AGENTS.md에 넣으면 개선될 가이드라인 초안

---

## Step 4: 결과 제시

분석 결과를 사용자에게 보여주고, 다음을 물어보세요:

1. 제안된 스킬 중 실제로 만들고 싶은 것이 있는지
2. AGENTS.md 가이드라인을 특정 프로젝트에 생성할지
3. 분석 범위를 조정하고 싶은지 (더 많은 세션, 특정 프로젝트만 등)

**주의사항:**
- 데이터에서 근거를 찾을 수 없는 패턴은 제안하지 마세요
- 사용자 메시지에 민감 정보(비밀번호, API 키 등)가 있을 수 있으니 출력 시 주의하세요
- 한국어로 분석 결과를 작성하세요
