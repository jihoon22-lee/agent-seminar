"""같은 스킬 본문을 description 만 바꿔 두 번 두고, 실제 모델이 스킬을 여는 비율을 잽니다.

    python compare.py                       # 프롬프트 4개 x 변형 2개 x 3회 = 24번 실행 (모델 호출, 시간이 걸림)
    python compare.py --runs 5
    python compare.py --model opencode/big-pickle --prompts 1,2   # 일부만
    python compare.py -m <provider/model>   # 평소 쓰는 모델로 (README: "평소 쓰는 모델로 실행하면 됩니다")

모델 출력은 매번 달라지므로 "3번 중 몇 번"으로 정직하게 셉니다. 스킬이 열렸는지는 모델의 말이 아니라
opencode 가 찍는 `→ Skill "team-glossary"` 표식으로 판단합니다. 인터넷이 필요한 건 모델 호출뿐입니다.
Linux에서 `python` 명령이 없으면 `python3` 로 바꿔 실행하세요.
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
import tempfile
from pathlib import Path

import lab

HERE = Path(__file__).resolve().parent
VARIANTS = ["variant-bad", "variant-good"]
SKILL_MARK = '→ Skill "team-glossary"'
LIMIT_RE = re.compile(r"FreeTierError|rate.?limit|\b429\b|quota exceeded", re.I)

# (표시 이름, 프롬프트, 정답에 들어 있어야 하는 말 - 스킬 본문을 읽었다는 증거)
PROMPTS = [
    ("1 뭐야", "우리 팀에서 쓰는 '블루문'이 정확히 뭐야?", "동결"),
    ("2 약어", "회고 문서에 'RFC-lite'랑 '팔콘'이라고 적혀 있던데, 이 약어들 무슨 뜻이야?", "결제"),
    ("3 팀 용어", "신규 팀원한테 보낼 거야. 우리 팀 용어 중에 꼭 알아야 할 것 3개만 한 줄씩 정리해 줘.", "동결"),
    ("4 대조군", "파이썬으로 리스트의 중복을 없애면서 순서는 유지하는 함수를 짧게 만들어 줘.", None),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-m", "--model", default="opencode/big-pickle", help="provider/model (기본: 무료 모델 opencode/big-pickle)")
    ap.add_argument("--runs", type=int, default=3, help="프롬프트·변형마다 반복 횟수")
    ap.add_argument("--prompts", default="1,2,3,4", help="실행할 프롬프트 번호 (쉼표 구분)")
    ap.add_argument("--variants", default=",".join(VARIANTS))
    args = ap.parse_args()
    chosen = {int(x) for x in args.prompts.split(",")}
    variants = args.variants.split(",")

    table: dict[tuple[str, str], list[str]] = {}
    # 모델은 스킬의 <location> 경로도 보므로, 폴더 이름(variant-good)이 힌트가 되지 않게 중립적인 이름으로 복사해서 돌립니다.
    neutral = {"variant-bad": "proj-a", "variant-good": "proj-b"}
    with lab.Sandbox() as sb, tempfile.TemporaryDirectory(prefix="s5a-") as tmp:
        for variant in variants:
            shutil.copytree(HERE / variant / ".opencode", Path(tmp) / neutral[variant] / ".opencode",
                            ignore=shutil.ignore_patterns("node_modules", "package*.json", "bun.lock", ".gitignore"))
        for label, prompt, evidence in PROMPTS:
            if int(label.split()[0]) not in chosen:
                continue
            for variant in variants:
                cells = []
                for i in range(args.runs):
                    out = lab.run_model(sb, prompt, Path(tmp) / neutral[variant], args.model)
                    if LIMIT_RE.search(out) or out.startswith("<<timeout>>"):
                        cells.append("n/a")
                        print("     (모델 호출 실패 - 쿼터/속도 제한이거나 시간 초과: " + out.strip().replace("\n", " ")[-160:] + ")")
                    else:
                        loaded = SKILL_MARK in out
                        used = loaded and evidence is not None and evidence in out
                        cells.append("열림+정답" if used else ("열림" if loaded else "안 열림"))
                    print(f"  [{label}] {variant} #{i + 1}: {cells[-1]}", flush=True)
                table[(label, variant)] = cells

    print(f"\n== 결과 (모델 {args.model}, 칸마다 {args.runs}회) : 스킬이 열린 횟수 / 실행 횟수")
    header = "프롬프트".ljust(14) + "".join(v.ljust(22) for v in variants)
    print(header)
    for label, _, _ in PROMPTS:
        if int(label.split()[0]) not in chosen:
            continue
        row = label.ljust(14)
        for variant in variants:
            cells = table[(label, variant)]
            valid = [c for c in cells if c != "n/a"]
            opened = sum(c.startswith("열림") for c in valid)
            row += f"{opened}/{len(valid)}".ljust(22)
        print(row)
    print("\n(대조군 4번은 팀 용어와 무관한 질문입니다. 여기서 스킬이 열리면 description 이 너무 넓다는 뜻입니다.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
