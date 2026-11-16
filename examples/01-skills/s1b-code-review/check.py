"""s1b 검증: 샘플의 결함이 실제로 재현되는지 + (선택) 모델이 스킬을 읽고 표 형식으로 리뷰하는지."""
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "tools"))
from octest import Sandbox, check, finish, model_check, model_enabled, skill_loaded  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from fake_llm import FakeLLM  # noqa: E402  (이 폴더의 복사본)
OC = HERE / ".opencode"


def run_fake(sb, cwd, script):
    """진짜 모델 대신 가짜 LLM 서버(fake_llm.py)를 붙여 opencode 를 실행하고, 모델이 받은 요청을 돌려준다.
    script 의 ("tool", 이름, 인자) 는 '모델이 그 도구를 호출한 것처럼' 흉내 낸다. 모델 한도·무작위성이 없다."""
    with FakeLLM(script=script) as llm:
        sb.opencode(["run", "-m", "fake/echo", "--auto", "테스트"], cwd, timeout=180,
                    extra_env={"OPENCODE_CONFIG_CONTENT": json.dumps(llm.provider_config()), "PWD": str(cwd)})
        return llm, llm.main_requests()


def system_text(llm, request):
    return "\n".join(llm.message_text(m) for m in request["messages"] if m["role"] == "system")


def tool_texts(llm, request):
    return [llm.message_text(m) for m in request["messages"] if m["role"] == "tool"]


def pwd(path):
    """octest 는 cwd 만 바꾸고 환경 변수 PWD 는 그대로 둔다. opencode 는 PWD 를 보므로 같이 맞춘다."""
    return {"PWD": str(path)}


had_oc_gitignore = (OC / ".gitignore").exists()


def snapshot() -> set[str]:
    """예제 폴더의 파일 목록 (opencode 가 자동으로 만드는 .opencode 부속물은 제외)."""
    files = set()
    for p in HERE.rglob("*"):
        rel = p.relative_to(HERE).as_posix()
        if p.is_file() and "__pycache__" not in rel and not (
                rel.startswith(".opencode/") and not rel.startswith(".opencode/skills/")):
            files.add(rel)
    return files


try:
    # 1. 샘플 코드가 문법적으로 올바르고, 심어 둔 결함이 실제로 재현된다
    sys.dont_write_bytecode = True
    compile((HERE / "sample" / "orders.py").read_text(encoding="utf-8"), "orders.py", "exec")
    check("sample/orders.py 컴파일", True)

    sys.path.insert(0, str(HERE / "sample"))
    import orders  # noqa: E402

    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE orders (id INTEGER, customer TEXT, total INTEGER, paid INTEGER DEFAULT 0)")
    db.execute("INSERT INTO orders (id, customer, total) VALUES (1, 'kim', 100), (2, 'lee', 200)")
    check("결함 1: SQL 인젝션이 재현됨 (다른 사람 주문까지 조회)",
          len(orders.get_orders(db, "x' OR '1'='1")) == 2)
    check("결함 2: API 키가 소스에 하드코딩", orders.PAYMENT_API_KEY == "demo-payment-key-123")

    old = os.getcwd()
    with tempfile.TemporaryDirectory() as tmp:
        os.chdir(tmp)
        try:
            pathlib.Path("receipts").mkdir()
            orders.export_receipt("../escaped.txt", "x")
            check("결함 3: 경로 탐색으로 receipts 밖에 파일이 써짐", pathlib.Path("escaped.txt").exists())
        finally:
            os.chdir(old)

    src = (HERE / "sample" / "orders.py").read_text(encoding="utf-8")
    check("결함 4: 맨 except + pass", re.search(r"except:\n\s+pass", src) is not None)
    check("결함 5: 의미 없는 이름 proc", "def proc(" in src)
    check("결함 6: 카드 번호를 print", re.search(r"print\(.*card_number", src) is not None)

    with Sandbox("s1b") as sb:
        skills = {s["name"]: s for s in sb.debug_skills(cwd=HERE, extra_env=pwd(HERE))}
        check("debug skill 에 code-review 표시", "code-review" in skills)
        desc = skills["code-review"]["description"]
        check("description 에 한국어 트리거 문구", "리뷰해줘" in desc, desc)
        check("본문에 세 가지 보안 항목이 모두 있음",
              all(k in skills["code-review"]["content"] for k in ("문자열 포매팅", "하드코딩", "path traversal")))

        llm, reqs = run_fake(sb, HERE, [("tool", "skill", {"name": "code-review"}), "DONE"])
        check("가짜 LLM: 스킬 도구 호출이 처리됨", len(reqs) == 2, str(len(reqs)))
        if len(reqs) == 2:
            sysmsg = system_text(llm, reqs[0])
            check("시스템 프롬프트에 이름과 한국어 description 이 있고 체크리스트 본문은 없음",
                  "<name>code-review</name>" in sysmsg and "리뷰해줘" in sysmsg and "path traversal" not in sysmsg)
            body = "\n".join(tool_texts(llm, reqs[1]))
            check("스킬을 불러오면 체크리스트 본문이 전달됨", "path traversal" in body and "## 요약" in body)

        if model_enabled():
            before = snapshot()
            out = sb.run_model("sample/orders.py 리뷰해줘", cwd=HERE, extra_env=pwd(HERE), timeout=240)
            model_check("모델이 code-review 스킬을 불러옴", out, skill_loaded(out, "code-review"))
            model_check("심각도 표 형식 (치명 등급 + 표 머리글)", out,
                        "치명" in out and re.search(r"\|\s*심각도\s*\|", out) is not None)
            model_check("요약 섹션이 있음", out, "요약" in out)
            keys = {
                "SQL 인젝션": r"SQL.{0,40}(인젝션|injection)|(인젝션|injection).{0,40}SQL",
                "하드코딩 키": r"하드\s?코딩|hard-?coded|PAYMENT_API_KEY",
                "경로 탐색": r"경로\s?탐색|path.?traversal|\.\./",
                "오류 삼킴": r"except:|bare.?except|맨 ?except|삼[키켜]|무시",
                "이름": r"\bproc\b",
                "카드 번호 로깅": r"card_number|카드 ?번호",
            }
            found = [k for k, pat in keys.items() if re.search(pat, out, re.I | re.S)]
            model_check(f"심어 둔 결함 6개 중 5개 이상 지적 ({len(found)}/6: {', '.join(found)})", out, len(found) >= 5)
            created = snapshot() - before
            model_check("리뷰만 하고 파일을 만들거나 고치지 않음", out, not created)
finally:
    if not had_oc_gitignore and (OC / ".gitignore").exists():
        (OC / ".gitignore").unlink()
    for name in ("node_modules", "package.json", "package-lock.json", "bun.lock"):
        p = OC / name
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        elif p.exists():
            p.unlink()
    shutil.rmtree(HERE / "sample" / "__pycache__", ignore_errors=True)

finish()
