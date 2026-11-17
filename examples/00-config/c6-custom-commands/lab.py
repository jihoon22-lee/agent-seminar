"""C6 공통 도우미: 가짜 모델로 opencode 를 실행하고, 모델이 받은 요청을 분석한다 (demo.py 와 check.py 가 함께 씀)."""
from __future__ import annotations

import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "tools"))
sys.path.insert(0, str(HERE))
from fake_llm import FakeLLM  # noqa: E402  (이 폴더의 복사본)


def run_fake(sb, cwd, args, script=None, extra_models=()):
    """opencode run -m fake/echo <args> 를 가짜 모델로 실행. (결과, FakeLLM, 도구 목록이 붙은 요청들) 을 돌려준다."""
    cwd = pathlib.Path(cwd)
    with FakeLLM(script=script or ["FAKE-REPLY"]) as llm:
        cfg = llm.provider_config()
        for name in extra_models:
            cfg["provider"]["fake"]["models"][name] = {"name": name, "tool_call": True,
                                                       "limit": {"context": 100000, "output": 4000}}
        proc = sb.opencode(["run", "-m", "fake/echo", *args], cwd, timeout=180,
                           extra_env={"OPENCODE_CONFIG_CONTENT": json.dumps(cfg), "PWD": str(cwd)})
        return proc, llm, llm.main_requests()


def system_text(llm, request) -> str:
    return "\n".join(llm.message_text(m) for m in request["messages"] if m["role"] == "system").replace("\r\n", "\n")


def user_texts(llm, request) -> list[str]:
    return [llm.message_text(m).replace("\r\n", "\n") for m in request["messages"] if m["role"] == "user"]


def skill_entry(system: str, name: str) -> str:
    """시스템 프롬프트의 <available_skills> 에서 해당 스킬의 <skill>...</skill> 블록만 꺼낸다."""
    m = re.search(rf"<skill>\s*<name>{re.escape(name)}</name>.*?</skill>", system, re.S)
    return m.group(0) if m else ""


def body_of(markdown: str) -> str:
    """frontmatter(--- ... ---) 를 떼고 본문만."""
    parts = markdown.split("---\n", 2)
    return parts[2] if markdown.startswith("---\n") and len(parts) == 3 else markdown
