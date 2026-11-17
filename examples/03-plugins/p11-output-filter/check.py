"""p11-output-filter 검증. 모델 없는 검사(단위 테스트)와 가짜 모델 실행(모델이 받는 결과, 화면, 세션 저장소), --model 검사."""
import json
import os
import re
import pathlib
import shutil
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "tools"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from fake_llm import FakeLLM  # noqa: E402
from octest import Sandbox, check, finish, model_check, model_enabled  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
IGNORE = shutil.ignore_patterns("logs", "__pycache__", "node_modules", "package.json", "package-lock.json", "bun.lock", ".gitignore")
SECRET = "demo-secret-value-123"
LONG_CMD = "python -c \"for i in range(1,501): print('line', i)\""  # 500줄: opencode 내장 잘라내기(2000줄/50KB) 아래
# 3000줄: 내장 잘라내기가 먼저 걸림. 첫 줄에 가짜 비밀을 찍되, 명령 글자에는 값이 그대로 들어가지 않게 쪼개 둔다.
HUGE_CMD = "python -c \"print('API_KEY=' + 'demo-secret-' + 'value-123'); [print('line', i) for i in range(1,3001)]\""


def show(label: str, text: str) -> None:
    """CHECK_VERBOSE=1 이면 모델 대화 기록을 그대로 출력한다 (README 의 '기대 결과' 수집용)."""
    if os.environ.get("CHECK_VERBOSE") == "1":
        print(f"--- {label} ---\n{text.strip()}\n--- end ---", flush=True)


def read(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def make_work(sb: Sandbox, name: str, with_plugin: bool = True) -> pathlib.Path:
    """예제 폴더를 임시 폴더로 복사한다(가짜 모델이 파일을 고치는 곳). with_plugin=False 면 플러그인을 뺀 '대조군'."""
    work = sb.root / name
    shutil.copytree(HERE, work, ignore=IGNORE)
    if not with_plugin:
        shutil.rmtree(work / ".opencode")
    return work


def bash(command: str) -> tuple:
    return ("tool", "bash", {"command": command, "description": "demo"})


def scripted_run(sb, work, script, extra_env=None, timeout=240):
    """가짜 LLM 이 정해진 도구 호출을 하게 하고 opencode run 을 실행한다. 반환: (화면, 모델이 마지막 요청에서 받은 도구 결과들)."""
    with FakeLLM(script=script) as llm:
        env = {"OPENCODE_CONFIG_CONTENT": json.dumps(llm.provider_config())}
        env.update(extra_env or {})
        proc = sb.opencode(["run", "-m", "fake/echo", "--auto", "go"], work, timeout=timeout, extra_env=env)
        last = llm.main_requests()[-1] if llm.main_requests() else {}
        results = [FakeLLM.message_text(m) for m in last.get("messages", []) if m.get("role") == "tool"]
        return proc.stdout + "\n" + proc.stderr, results


def store_bytes(sb: Sandbox) -> bytes:
    """샌드박스의 세션 저장소(sqlite 파일과 -wal)를 통째로 읽는다."""
    data = b""
    for f in sorted((sb.root / "data").rglob("*")):
        if f.is_file() and f.name.startswith("opencode.db"):
            data += f.read_bytes()
    return data


def tool_parts(sb: Sandbox) -> list:
    """저장된 도구 호출 기록(part 테이블의 type=tool)을 읽는다."""
    import sqlite3
    db = next(f for f in (sb.root / "data").rglob("opencode.db"))
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return [json.loads(d) for (d,) in con.execute("select data from part") if json.loads(d).get("type") == "tool"]
    finally:
        con.close()


def event_leaks(sb: Sandbox) -> set:
    """이벤트 로그(event 테이블)에서 원본 비밀이 들어 있는 (도구, 상태) 쌍을 모은다."""
    import sqlite3
    db = next(f for f in (sb.root / "data").rglob("opencode.db"))
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        found = set()
        for (d,) in con.execute("select data from event"):
            if SECRET in d:
                part = json.loads(d).get("part", {})
                found.add((part.get("tool"), part.get("state", {}).get("status")))
        return found
    finally:
        con.close()


SCRIPT = [
    bash("cat sample/app.env"),                                                             # 0 bash: 파일 내용을 그대로 찍는 명령
    ("tool", "read", {"filePath": "sample/app.env"}),                                       # 1 read
    ("tool", "cfg_show_config", {}),                                                        # 2 MCP 도구
    ("tool", "edit", {"filePath": "sample/app.env", "oldString": "other=1", "newString": "other=2"}),  # 3 edit (diff 가 metadata 에 있음)
    bash(LONG_CMD),                                                                         # 4 긴 출력 (500줄)
    bash(HUGE_CMD),                                                                         # 5 아주 긴 출력 (3000줄)
    ("tool", "edit", {"filePath": "sample/app.env", "oldString": "API_KEY=***", "newString": "API_KEY=changed"}),  # 6 가려진 글자로 편집 시도
    ("tool", "cfg_show_resource", {}),                                                      # 7 MCP: content 가 resource 항목
    ("tool", "cfg_show_structured", {}),                                                    # 8 MCP: text 와 structuredContent 가 함께
    ("tool", "cfg_show_structured_only", {}),                                               # 9 MCP: structuredContent 만 (opencode 가 JSON 문자열로 바꿈)
    "끝",
]


def main() -> None:
    node = shutil.which("node")
    check("node 가 있다 (훅 단위 테스트용)", node is not None, "node 가 없어 단위 테스트를 건너뜁니다", soft=True)
    if node:
        t = subprocess.run([node, str(HERE / "tests" / "filter.test.mjs")], capture_output=True, text=True, encoding="utf-8")
        check("tool.execute.after 단위 테스트 (마스킹 + 줄이기)", t.returncode == 0, t.stdout + t.stderr)

    with Sandbox("p11") as sb:
        # --- A: 플러그인 켬 (기본)
        work = make_work(sb, "work-a")
        check("opencode 가 플러그인을 로드했다 (output-filter.log)", (sb.debug_config(work), "output-filter loaded" in read(work / "logs" / "output-filter.log"))[1])
        out, results = scripted_run(sb, work, SCRIPT)
        show("A: 화면", out)
        show("A: 모델이 받은 도구 결과", "\n---\n".join(r if len(r) < 700 else r[:350] + f"\n[... 이 사이 {len(r) - 700}자 ...]\n" + r[-350:] for r in results))
        check("모델이 10개 도구 결과를 모두 받음", len(results) == 10, str(len(results)))
        if len(results) == 10:
            check("bash: 모델이 받은 결과에서 값이 가려짐", "DB_PASSWORD=***" in results[0] and "API_KEY=***" in results[0] and SECRET not in results[0] and "APP_NAME=demo-app" in results[0], results[0])
            check("read: 모델이 받은 파일 내용에서 값이 가려짐 (줄 번호/나머지는 그대로)", "2: DB_PASSWORD=***" in results[1] and "4: other=1" in results[1] and SECRET not in results[1], results[1])
            check("MCP 도구: output.content[].text 를 가리면 모델이 가려진 결과를 받음", results[2] == "DB_PASSWORD=***\nmode=dev", results[2])
            check("MCP resource 항목: content[].resource.text 도 가려져 모델이 받음", results[7] == "DB_PASSWORD=***", results[7])
            check("MCP text + structuredContent: 모델은 text 만 받고(가려짐) 비밀이 없음", results[8] == "DB_PASSWORD=***\nmode=dev", results[8])
            check("MCP structuredContent 만 있으면 opencode 가 JSON 문자열로 바꿔 모델에게 줌: 그 문자열도 가려짐", json.loads(results[9]) == {"DB_PASSWORD": "***", "mode": "dev"}, results[9])
            check("edit: 모델이 받는 결과에는 원래 비밀이 없음 (diff 는 metadata 에만)", results[3] == "Edit applied successfully.", results[3])
            r4, r5 = results[4], results[5]
            lines4 = r4.splitlines()
            check("긴 출력(500줄): 앞 40줄 + 생략 표시 + 뒤 40줄로 줄어 모델에게 감",
                  len(lines4) == 81 and lines4[0] == "line 1" and lines4[39] == "line 40" and lines4[40] == "... (420줄 생략) ..." and lines4[41] == "line 461" and lines4[-1] == "line 500", f"{len(lines4)}줄\n{r4[:200]}")
            check("긴 출력(500줄): 모델이 받은 크기가 원본(약 4.4KB)보다 작음", len(r4) < 800, str(len(r4)))
            check("아주 긴 출력(3000줄): opencode 내장 잘라내기가 플러그인보다 먼저 적용됨 (플러그인은 이미 잘린 결과를 받아 다시 줄임)",
                  r5.startswith("...output truncated...") and "Full output saved to:" in r5 and re.search(r"\(19\d\d줄 생략\)", r5) is not None and r5.rstrip().endswith("line 3000") and "line 1\n" not in r5, f"{len(r5)}자\n{r5[:300]}")
            check("가려진 글자(***)로 파일을 고치려 하면 실패 (모델은 원문 값을 모르므로 못 고친다)", "Could not find oldString" in results[6], results[6])
        check("화면(opencode run 출력)에도 비밀이 나오지 않음 (bash 출력, edit diff 모두)", SECRET not in out and "API_KEY=***" in out, out[-800:])
        spill = [f for f in (sb.root / "data").rglob("tool-output/*") if f.is_file()]
        check("opencode 가 잘라낸 3000줄 출력의 전체 사본(tool-output 파일)은 가려지지 않은 원문 그대로 디스크에 있음 (모델에게는 경로만 알려 줌)",
              len(spill) == 1 and SECRET in spill[0].read_text(encoding="utf-8"), str(spill))
        check("파일 자체는 그대로 (디스크의 원본은 가려지지 않음)", f"DB_PASSWORD={SECRET}" in read(work / "sample" / "app.env") and "other=2" in read(work / "sample" / "app.env"))
        log = read(work / "logs" / "output-filter.log")
        show("A: output-filter.log", log)
        check("기록: 도구별 가린 개수/줄인 크기만 남고 값은 없음", re.search(r"tool=bash masked=\d+\n", log) is not None and len(re.findall(r"shortened=\d+줄 -> 81줄", log)) == 2 and SECRET not in log, log)
        states = {}
        for p in tool_parts(sb):
            key = p["tool"] if p["tool"] != "bash" else ("bash-cat" if "cat sample" in p["state"]["input"].get("command", "") else "bash-500" if "range(1,501)" in p["state"]["input"].get("command", "") else "bash-3000")
            states[key] = p["state"]
        check("저장된 도구 기록(part)에는 원본 비밀이 없음 (state.output, state.metadata 모두 ***)",
              all(SECRET not in json.dumps(st) for st in states.values()) and "API_KEY=***" in states["bash-cat"]["output"] and "API_KEY=***" in json.dumps(states["bash-cat"]["metadata"]) and "API_KEY=***" in json.dumps(states["read"]["metadata"]),
              json.dumps(states["bash-cat"]["metadata"])[:300])
        check("저장된 bash(500줄)의 metadata.output 사본은 줄이지 않았음 (가리기만 함, 500줄 그대로)", len(states["bash-500"]["metadata"].get("output", "").splitlines()) == 500, str(len(states["bash-500"]["metadata"].get("output", "").splitlines())))
        leaks = event_leaks(sb)
        check("그런데 이벤트 로그(event 테이블)에는 훅이 닿기 전에 기록된 running 상태의 metadata 에 원본이 남음 (bash 출력 스트림, edit diff)",
              leaks == {("bash", "running"), ("edit", "running")}, str(leaks))

    # --- D: MCP 결과의 모양을 눈으로 확인: 탐침 플러그인이 필터 훅을 부른 직후의 훅 output 전체(structuredContent 포함)를 파일에 적는다
    with Sandbox("p11d") as sb:
        work = make_work(sb, "work-d")
        # 플러그인 불리는 순서는 OS 마다 다를 수 있어서(Windows 에서는 탐침이 필터보다 먼저 불렸다) 순서에 기대지 않는다:
        # 필터 파일을 plugins/ 밖으로 옮기고, plugins/ 의 탐침이 필터 훅을 직접 부른 뒤 그 결과(output)를 기록한다.
        (work / ".opencode" / "impl").mkdir()
        shutil.move(str(work / ".opencode" / "plugins" / "output-filter.js"), str(work / ".opencode" / "impl" / "output-filter.mjs"))
        (work / ".opencode" / "plugins" / "probe.js").write_text(
            'import { appendFileSync } from "node:fs";\n'
            'import { OutputFilter } from "../impl/output-filter.mjs";\n'
            'export const Probe = async (ctx) => {\n'
            '  const filter = await OutputFilter(ctx);\n'
            '  return { "tool.execute.after": async (input, output) => {\n'
            '    await filter["tool.execute.after"](input, output);\n'
            '    appendFileSync(ctx.directory + "/probe.jsonl", JSON.stringify({ tool: input.tool, output }) + "\\n");\n'
            '  } };\n};\n', encoding="utf-8")
        out, results = scripted_run(sb, work, SCRIPT[7:10] + ["끝"])
        seen = [json.loads(l) for l in read(work / "probe.jsonl").splitlines() if l.strip()]
        show("D: 탐침이 본 훅 output (필터 다음)", "\n".join(json.dumps(x, ensure_ascii=False) for x in seen))
        check("[MCP 모양] 탐침이 세 MCP 도구의 훅 output 을 모두 봄", [x["tool"] for x in seen] == ["cfg_show_resource", "cfg_show_structured", "cfg_show_structured_only"], str([x["tool"] for x in seen]))
        check("[MCP 모양] structuredContent 는 객체로 같이 오고, 필터를 거친 뒤 훅 output 전체(content, structuredContent)에 원본 값이 없음",
              len(seen) == 3 and all("structuredContent" in x["output"] for x in seen[1:]) and all(SECRET not in json.dumps(x) for x in seen) and seen[1]["output"]["structuredContent"]["DB_PASSWORD"] == "***",
              json.dumps(seen, ensure_ascii=False)[:600])
        check("[MCP 모양] resource 항목은 {type:'resource', resource:{uri, text}} 모양이고 text 만 바뀜",
              len(seen) >= 1 and seen[0]["output"]["content"][0]["resource"]["text"] == "DB_PASSWORD=***" and seen[0]["output"]["content"][0]["resource"]["uri"] == "file:///demo/app.env", json.dumps(seen[:1], ensure_ascii=False))
        check("[MCP 모양] 이 세 도구에서도 저장소(세션 DB)에 원본 값이 남지 않음", SECRET.encode() not in store_bytes(sb))

    # --- B: 플러그인 켬, metadata 는 건드리지 않음 -> 모델에게는 가려지지만 저장소와 edit 화면에는 원본이 남는다
    with Sandbox("p11b") as sb:
        work = make_work(sb, "work-b")
        out, results = scripted_run(sb, work, SCRIPT[:4] + ["끝"], extra_env={"OUTPUT_FILTER_METADATA": "0"})
        show("B: 화면 (OUTPUT_FILTER_METADATA=0)", out)
        check("[metadata 사본] 모델은 가려진 결과를 받음", len(results) == 4 and all(SECRET not in r for r in results), "\n".join(results))
        check("[metadata 사본] 그런데 세션 저장소에는 원본이 남음 (bash metadata.output, read metadata.preview)", SECRET.encode() in store_bytes(sb))
        states = {p["tool"]: p["state"] for p in tool_parts(sb)}
        check("[metadata 사본] 저장된 state.output 은 가려졌지만 state.metadata 에는 원본", SECRET not in states["bash"]["output"] and SECRET in json.dumps(states["bash"]["metadata"]) and SECRET in json.dumps(states["read"]["metadata"]), json.dumps(states["bash"]["metadata"])[:300])
        check("[metadata 사본] edit 의 화면 diff 에는 원본이 나옴 (diff 는 metadata 에서 그림)", SECRET in out and "-other=1" in out, out[-500:])
        check("[metadata 사본] bash 의 화면 출력은 가려져 있음 (화면은 output.output 을 씀)", "API_KEY=***" in out.split("Read")[0], out[:400])

    # --- C: 플러그인 없음 (대조군) -> 위의 검사가 의미 있는지 확인
    with Sandbox("p11c") as sb:
        work = make_work(sb, "work-c", with_plugin=False)
        out, results = scripted_run(sb, work, SCRIPT[:3] + [bash(HUGE_CMD), "끝"])
        show("C: 대조군 (플러그인 없음)", "\n---\n".join(r[:200] for r in results))
        check("[대조군] 플러그인이 없으면 모델이 비밀을 그대로 받음", len(results) == 4 and SECRET in results[0] and SECRET in results[1] and SECRET in results[2], "\n".join(r[:100] for r in results))
        check("[대조군] 플러그인이 없으면 저장소에도 비밀이 남음", SECRET.encode() in store_bytes(sb))
        r3 = results[3] if len(results) == 4 else ""
        show("C: opencode 내장 잘라내기가 만든 bash 결과 (3000줄)", r3[:600] + "\n[...]\n" + r3[-400:])
        check("[대조군] 내장 도구도 아주 긴 출력은 스스로 자르지만(2000줄 남김) 훨씬 큼", r3.startswith("...output truncated...") and len(r3) > 15000, f"{len(r3)}자")

        if model_enabled():
            wm = make_work(sb, "work-m")
            out = sb.run_model("bash 도구로 `cat sample/app.env` 를 실행해서 DB_PASSWORD 값이 무엇인지 알려 주세요.", wm)
            show("model run", out)
            model_check("실제 모델도 비밀 값을 보지 못함 (답변에 원문 값이 없음)", out, SECRET not in out)

    finish()


if __name__ == "__main__":
    main()
