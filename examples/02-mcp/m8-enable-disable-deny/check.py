"""m8 검증: MCP 서버·도구를 켜고 끄고 막는 방법이 모델이 받는 도구 목록에 어떻게 반영되는가.

가짜 LLM(fake_llm.py)이 opencode 가 보낸 요청의 `tools` 배열을 기록하므로 모델 없이도 결정적으로 확인된다.
"""
import json
import pathlib
import shutil
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "tools"))
from octest import MODEL_UNAVAILABLE, Sandbox, check, finish, model_check, model_enabled, tool_called  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import count_tool_tokens  # noqa: E402
from fake_llm import FakeLLM  # noqa: E402
from show_model_tools import model_tools  # noqa: E402

PY = sys.executable


def names(tools):
    return {t["name"] for t in tools}


def rules(agent_json):
    return [(r["permission"], r["action"]) for r in agent_json["permission"]]


def debug_agent(sb, agent, cwd):
    proc = sb.opencode(["debug", "agent", agent], cwd, timeout=120, extra_env={"PWD": str(cwd)})
    text = proc.stdout
    return json.loads(text[text.index("{"):])


config = json.loads((HERE / "opencode.json").read_text(encoding="utf-8"))

# --- 1. 설정과 서버 (모델 없음) --------------------------------------------------------
check("opencode.json: 서버 3개, legacy 는 enabled:false",
      list(config["mcp"]) == ["docs", "ops", "legacy"] and config["mcp"]["legacy"]["enabled"] is False)
check("opencode.json: 'model' 키 없음", "model" not in config)

report = count_tool_tokens.analyse(config, HERE)
by = {s["name"]: s for s in report}
check("count_tool_tokens: 도구 수 docs=2 ops=6 legacy=12", [len(by[n]["tools"]) for n in ("docs", "ops", "legacy")] == [2, 6, 12],
      str({n: len(s["tools"]) for n, s in by.items()}))
hidden = sorted(t["name"] for t in by["ops"]["tools"] if t["hidden"])
check("count_tool_tokens: permission deny 규칙(ops_noisy_*)에 걸린 도구 4개",
      hidden == ["noisy_gc_stats", "noisy_heap_dump", "noisy_thread_dump", "noisy_trace_dump"], str(hidden))
legacy_chars = sum(t["chars"] for t in by["legacy"]["tools"])
other_chars = sum(t["chars"] for n in ("docs", "ops") for t in by[n]["tools"])
check("legacy 서버(꺼짐)의 정의가 나머지 합보다 크다 → 꺼 두는 쪽이 이득", legacy_chars > other_chars, f"{legacy_chars} vs {other_chars}")

with Sandbox("m8") as sb:
    status = sb.mcp_list(HERE)
    check("opencode mcp list: docs, ops connected / legacy disabled",
          status.get("docs") == "connected" and status.get("ops") == "connected" and status.get("legacy") == "disabled", str(status))

    merged = sb.debug_config(HERE)
    check("debug config: permission 규칙과 legacy enabled:false 가 합쳐진 설정에 보임",
          merged.get("permission", {}).get("ops_noisy_*") == "deny" and merged["mcp"]["legacy"]["enabled"] is False,
          json.dumps(merged.get("permission")))

    build = debug_agent(sb, "build", HERE)
    check("debug agent build: ops_noisy_* deny / ops_restart ask 규칙이 보임",
          ("ops_noisy_*", "deny") in rules(build) and ("ops_restart", "ask") in rules(build), str(rules(build)[-6:]))
    check("debug agent build: tools 에는 내장 도구만 있고 MCP 도구는 없음 (그래서 가짜 LLM 으로 확인한다)",
          not any(k.startswith(("docs_", "ops_")) for k in build["tools"]), str(list(build["tools"])))
    reviewer = debug_agent(sb, "reviewer", HERE)
    check("debug agent reviewer: 에이전트 tools:false 가 deny 규칙으로 번역됨 (ops_*, 그리고 edit/write 는 하나의 edit 권한)",
          {("ops_*", "deny"), ("edit", "deny")} <= set(rules(reviewer)), str(rules(reviewer)[-6:]))

    # --- 2. 모델이 실제로 받는 도구 (가짜 LLM) ---------------------------------------------
    tools = model_tools(HERE, opencode=sb.bin, env=sb.env)
    got = names(tools)
    check("build 에이전트: docs_*, ops_status, ops_restart 가 모델에게 전달",
          {"docs_lookup", "docs_outline", "ops_status", "ops_restart"} <= got, str(sorted(got)))
    check("build 에이전트: permission deny 한 ops_noisy_* 는 모델에게 전달되지 않음", not any(n.startswith("ops_noisy_") for n in got))
    check("build 에이전트: enabled:false 인 legacy_* 는 모델에게 전달되지 않음", not any(n.startswith("legacy_") for n in got))
    check("리소스가 없는 서버뿐이면 list_mcp_resources 같은 보조 도구도 붙지 않음", "read_mcp_resource" not in got)
    sent = {f"{s['name']}_{t['name']}" for s in report if s["enabled"] for t in s["tools"] if not t["hidden"]}
    check("count_tool_tokens 의 예측(켜짐 − 숨김)이 실제 전달된 MCP 도구와 일치",
          sent == {n for n in got if n.startswith(("docs_", "ops_"))}, f"{sorted(sent)} vs {sorted(got)}")

    rev = names(model_tools(HERE, agent="reviewer", opencode=sb.bin, env=sb.env))
    check("reviewer 에이전트: ops_* 전부와 edit/write 가 빠지고 docs_* 는 유지",
          not any(n.startswith("ops_") for n in rev) and not ({"edit", "write"} & rev) and "docs_lookup" in rev, str(sorted(rev)))
    check("에이전트별 설정은 다른 에이전트에 새지 않음 (build 는 그대로)", "ops_status" in got and "edit" in got)

    dbg = names(model_tools(HERE, agent="debugger", opencode=sb.bin, env=sb.env,
                            overlay={"agent": {"debugger": {"mode": "primary", "description": "d", "tools": {"ops_noisy_*": True}}}}))
    check("에이전트 tools:{\"ops_noisy_*\": true} 는 전역 permission deny 를 그 에이전트에서만 되살림",
          {"ops_noisy_heap_dump", "ops_status"} <= dbg, str(sorted(dbg)))

    on = model_tools(HERE, overlay={"mcp": {"legacy": {"enabled": True}}}, opencode=sb.bin, env=sb.env)
    check("mcp.legacy.enabled:true 로 덮어쓰면 legacy_op_01…12 가 모델에게 전달", sum(1 for n in names(on) if n.startswith("legacy_op_")) == 12)
    size = lambda ts: sum(len(json.dumps(t, ensure_ascii=False)) for t in ts)  # noqa: E731
    check("legacy 를 켜면 도구 정의 크기(=매 요청 컨텍스트)가 눈에 띄게 늘어남", size(on) > size(tools) + 4000, f"{size(on)} vs {size(tools)}")

    # 예전 방식 top-level tools:{패턴:false} 도 같은 효과 (permission 을 뺀 변형 설정으로 비교)
    variant = sb.root / "variant"
    variant.mkdir()
    shutil.copy(HERE / "mcp_server.py", variant / "mcp_server.py")
    legacy_cfg = {k: v for k, v in config.items() if k not in ("permission", "agent")}
    legacy_cfg["tools"] = {"ops_noisy_*": False}
    (variant / "opencode.json").write_text(json.dumps(legacy_cfg, ensure_ascii=False), encoding="utf-8")
    old_style = names(model_tools(variant, opencode=sb.bin, env=sb.env))
    check("top-level tools:{\"ops_noisy_*\": false} 도 같은 도구를 숨김 (permission deny 로 번역되는 옛 단축형)",
          "ops_status" in old_style and not any(n.startswith("ops_noisy_") for n in old_style), str(sorted(old_style)))

    # --- 3. 호출 시점의 동작 (스크립트된 가짜 모델이 도구를 호출) -----------------------------
    def run_call(tool, args, auto):
        with FakeLLM(script=[("tool", tool, args), "DONE"]) as llm:
            cmd = ["run", "-m", "fake/echo"] + (["--auto"] if auto else []) + ["go"]
            out = sb.opencode(cmd, HERE, timeout=120,
                              extra_env={"OPENCODE_CONFIG_CONTENT": json.dumps(llm.provider_config()), "PWD": str(HERE)})
            followup = [llm.message_text(m) for r in llm.main_requests() for m in r["messages"] if m.get("role") == "tool"]
            return out.stdout + out.stderr, followup

    text, _ = run_call("ops_restart", {"service": "pay"}, auto=False)
    check("permission ask + --auto 없이 run: 'auto-rejecting' 으로 거절되고 도구는 실행되지 않음",
          "auto-rejecting" in text and "ops_restart" in text and "실행됨" not in text, text[-400:])
    text, followup = run_call("ops_restart", {"service": "pay"}, auto=True)
    check("permission ask + --auto: 승인되어 실행되고 결과가 모델에게 돌아감", any("restart 실행됨" in f for f in followup), text[-400:])
    text, followup = run_call("ops_noisy_heap_dump", {}, auto=True)
    check("deny 된 도구를 모델이 억지로 호출하면 'unavailable tool' 오류가 돌아감 (실행되지 않음)",
          any("unavailable tool" in f for f in followup), str(followup))

    if model_enabled():
        try:
            out = sb.run_model("ops MCP 서버의 status 도구로 payment 서비스 상태를 확인해서 한 줄로 알려줘.", HERE,
                               extra_env={"PWD": str(HERE)})
        except Exception as exc:  # 모델 대기열 시간 초과 등은 '검증 불가'로 보고
            out = MODEL_UNAVAILABLE + f" {exc}"
        model_check("실제 모델이 ops_status 를 호출", out, tool_called(out, "ops_status"))

finish()
