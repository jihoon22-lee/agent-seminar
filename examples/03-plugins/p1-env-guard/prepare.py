"""p1-env-guard 실습 준비: 가짜 값이 든 .env 와 견본 .env.example 을 만듭니다.

    python prepare.py        (Linux에서 python 명령이 없으면 python3)

.env 는 .gitignore 대상이라 저장소에 올라가지 않고, 다시 실행하면 처음부터 다시 만듭니다.
값은 실제 비밀이 아니라 데모용 가짜 문자열입니다.
"""
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = pathlib.Path(__file__).resolve().parent
FAKE_VALUE = "FAKE-" + "ENV-VALUE-" + "98765"  # 토큰처럼 보이지 않게 실행 시점에 조립

EXAMPLE = (
    "# 값은 비워 두고 \"어떤 변수가 필요한지\"만 적는 견본 파일입니다. 커밋해도 안전합니다.\n"
    "DEMO_API_KEY=\n"
    "DEMO_DB_URL=\n"
)


def main() -> None:
    (HERE / ".env").write_text(
        f"DEMO_API_KEY={FAKE_VALUE}\nDEMO_DB_URL=postgres://demo:demo-password@localhost:5432/demo\n",
        encoding="utf-8",
        newline="\n",
    )
    example = HERE / ".env.example"
    if not example.exists():
        example.write_text(EXAMPLE, encoding="utf-8", newline="\n")
    print(f"만들었습니다: {HERE / '.env'}  (가짜 값 {FAKE_VALUE})")
    print(f"견본 파일:   {example}")
    print("다음: 이 폴더에서 opencode 를 실행하고 \".env 파일 내용을 보여줘\" 라고 요청해 보세요.")


if __name__ == "__main__":
    main()
