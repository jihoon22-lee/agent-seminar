# M14 런타임 없이 실행 파일 하나로 된 서버 (Rust)

> 구성: Rust 크레이트 1개(`serde_json`만 사용) + 빌드 스크립트 | 난이도: ★★★ | 필요: opencode 1.19.5, Python 3.10+(빌드 스크립트와 check), **Rust(cargo)**, 첫 빌드 때 crates 레지스트리 또는 미러 | 슬라이드: MCP — 배포 방법

## 무엇을 보여 주나

M1 의 용어집 서버(Python)와 **똑같은 일**을 하는 서버를 Rust 로 다시 만들어, 빌드 결과가 **실행 파일 하나**가 되는 것을 본다.
용어집(`glossary.json`)도 빌드할 때 실행 파일 안에 들어가므로 배포할 파일이 이것 하나다. 받는 쪽 PC 에는 Python 도 Node 도 필요 없다.

JSON-RPC 부분은 M1 과 같다. 한 줄 읽고, `initialize` / `tools/list` / `tools/call` / `ping` 을 처리하고, 알림(`id` 없음)에는 답하지 않고, 모르는 method 에는 `-32601` 을 돌려준다. 코드는 약 175줄(주석 포함)이다.

## 실무에서는

- **받는 쪽에 런타임을 깔 수 없거나 깔기 싫을 때.** Python 이나 Node 가 없는 서버·PC 에서, 또는 버전이 제각각인 PC 여러 대에서 같은 MCP 서버를 돌려야 하면 실행 파일 하나를 공유 폴더에 두고 `command` 가 그 경로를 가리키게 하면 된다. 가상환경, `pip install`, `npx` 다운로드가 없다.
- **시작이 빠르다.** 이 PC 에서 잰 값은 아래 "기대 결과"에 있다. 에이전트를 켤 때마다 MCP 서버가 새로 뜨므로, 서버가 여러 개일수록 차이가 모인다. (다만 30초 시작 제한에 걸리는 일이 없는 한 체감 차이는 크지 않다.)
- **값을 치르는 것들.** 만드는 PC 에 툴체인(Rust, 또는 Go)이 필요하고, **OS 마다 따로 빌드**해야 한다(Linux 용 파일은 Windows 에서 안 돈다). 팀원이 코드를 고치려면 그 언어를 읽어야 한다. 도구가 몇 개 안 되고 자주 안 바뀌고 널리 배포할 때 어울린다. 빠르게 고쳐 가며 쓰는 도구는 Python 이 낫다.
- **Go 도 같은 목적에 쓸 수 있다.** 단일 실행 파일, 런타임 없음, 교차 빌드가 쉽다는 점이 같다. 이 예제는 Rust 로 만들었고 Go 는 이 PC 에 설치되어 있지 않아 **만들어 보지 않았다**(미검증). 팀이 이미 아는 언어를 고르면 된다.

## 파일 구성

```
m14-single-binary/
  README.md        이 문서
  Cargo.toml       크레이트 설정. 의존 라이브러리는 serde_json 하나, 릴리스는 크기 우선(opt-level="s", lto, strip)
  Cargo.lock       cargo 가 만든 버전 고정 파일 (실행 파일을 만드는 프로젝트는 같이 보관한다)
  src/main.rs      MCP 서버 본체 (한국어 주석, 약 175줄)
  glossary.json    용어집 (M1 과 같은 14개). 빌드할 때 실행 파일 안으로 들어간다 (include_str!)
  build.py         cargo build --release 를 하고 bin/glossary-mcp(.exe) 로 복사
  opencode.json    mcp.glossary: ["./bin/glossary-mcp"]  (두 OS 공용 한 줄)
  check.py         자동 검증 (cargo 가 없거나 crates 를 못 받으면 경고만 내고 건너뜀)
  fake_llm.py      가짜 LLM 서버
  .gitignore       target/ 과 bin/ (아래 "주의할 점" 참고)
  target/, bin/    (빌드가 생성)
```

## 따라 하기

> 이 단계는 **Rust 툴체인**(https://rustup.rs)과, 첫 빌드 때 `serde_json` 을 받을 **crates 레지스트리(또는 미러)**가 필요하다. 한 번 받아 두면 `python build.py --offline` 으로 인터넷 없이 다시 빌드할 수 있다.
> Linux에서 `python` 명령이 없으면 `python3`로 바꾸세요.

모든 명령은 이 예제 폴더(`examples/02-mcp/m14-single-binary`)에서 실행한다.

**1. 빌드**

```powershell
cd examples\02-mcp\m14-single-binary
python build.py
```

```bash
cd examples/02-mcp/m14-single-binary
python3 build.py
```

**2. 에이전트 없이 대화 확인** — 실행 파일을 띄우고 JSON 줄을 넣는다. (M1 의 `raw_session.py` 는 `python server.py` 를 띄우므로 쓰지 않는다. 같은 내용을 손으로 넣는다.)

```powershell
.\bin\glossary-mcp.exe
```

```bash
./bin/glossary-mcp
```

```
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25"}}
{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"lookup_term","arguments":{"term":"ADR"}}}
```

종료는 `Ctrl+C` (Linux 는 `Ctrl+D` 도 된다).

**3. opencode 로 연결과 질문**

```powershell
opencode mcp list
opencode run -m opencode/big-pickle --auto "팀 용어집에서 ADR이 무슨 뜻인지 찾아줘"
```

```bash
opencode mcp list
opencode run -m opencode/big-pickle --auto "팀 용어집에서 ADR이 무슨 뜻인지 찾아줘"
```

**4. (선택) 파일 하나만 옮겨서 돌려 보기** — `bin/glossary-mcp` 만 빈 폴더에 복사해서 같은 JSON 줄을 넣어도 동작한다. 용어집이 파일 안에 있기 때문이다.

## 기대 결과

`python build.py` (Linux, cargo 1.99.1, 처음 빌드):

```
$ cargo build --release --target-dir target
   Compiling serde_json v1.0.154
   ...
   Compiling glossary-mcp v1.0.0 (...)
    Finished `release` profile [optimized] target(s) in 6.33s
복사: target/release/glossary-mcp -> bin/glossary-mcp (355 KiB)
```

`check.py` 가 출력하는 크기와 시작 시간 (같은 PC, 같은 방법: 프로세스를 띄우고 `initialize` 응답을 받을 때까지, 15회의 중앙값):

```
실행 파일 크기: 355 KiB (glossary-mcp, 파이썬 없이 이 파일만으로 실행)
시작~initialize 응답 (15회): Rust 중앙값 1.3ms (최소 1.1) / Python M1 중앙값 27.9ms (최소 23.6)  -> 약 22배
```

Python 쪽은 인터프리터 시작 비용이 대부분이다. 수치는 이 PC 의 한 번 측정이고 PC 마다 다르다. `opencode mcp list`:

```
●  ✓ glossary connected
│      ./bin/glossary-mcp
```

가짜 모델이 `glossary_lookup_term` 을 부르면 M1 과 똑같은 한글 결과가 돌아간다. `check.py` 는 M1 의 Python 서버와 같은 질문(ADR, 전체 목록)에 **글자 하나까지 같은 답**이 나오는지도 확인한다.

## 동작 원리

### 코드

`src/main.rs` 는 M1 의 `server.py` 와 구조가 같다. 대응표:

| M1 (Python) | M14 (Rust) |
|---|---|
| `json.loads(line)` | `serde_json::from_str::<Value>(&line)` |
| `{"content": [...]}` 딕셔너리 | `json!({ "content": [...] })` 매크로 |
| `for line in sys.stdin` | `for line in io::stdin().lock().lines()` |
| `sys.stdout.reconfigure(encoding="utf-8")` | 필요 없음. Rust 는 문자열이 항상 UTF-8 이고 `\n` 을 `\r\n` 으로 바꾸지 않는다 |
| `glossary.json` 을 `Path.read_text` 로 읽음 | `include_str!("../glossary.json")` — **빌드할 때** 파일 내용이 실행 파일에 들어간다 |

M9 에서 본 Windows 인코딩 함정(cp949)은 이 서버에는 해당 없다. 대신 Rust 에는 "stdin 에 UTF-8 이 아닌 바이트가 오면 `lines()` 가 오류를 낸다"는 성질이 있고, 서버는 그때 반복을 끝낸다.

### 빌드 스크립트와 전역 `target-dir`

`build.py` 는 `cargo build --release --target-dir target` 으로 빌드한다. `--target-dir target` 을 명시한 이유는 이 예제를 만든 PC 의 `~/.cargo/config.toml` 에 `build.target-dir` 이 전역으로 지정되어 있어서, 옵션 없이 빌드하면 결과가 이 폴더의 `target/` 이 아니라 그 전역 폴더에 생겼기 때문이다. 이런 설정이 있는 PC 가 드물지 않으므로 경로를 명시해 둔다.

### `command` 의 상대 경로 (Linux 에서 확인한 것)

`opencode.json` 은 `"command": ["./bin/glossary-mcp"]` 한 줄이다. 임시 프로젝트 폴더에 `bin/glossary-mcp` 를 두고 `opencode mcp list` 를 실행해 본 결과:

| `command` | 프로젝트 폴더에서 실행 | 하위 폴더에서 실행 |
|---|---|---|
| `["./bin/glossary-mcp"]` | connected | failed |
| `["bin/glossary-mcp"]` | connected | failed |
| `["bin/glossary-mcp.exe"]` | failed (Linux 에는 그 파일이 없다) | failed |
| `["/절대/경로/bin/glossary-mcp"]` | connected | connected |

즉 상대 경로는 M1 의 `python server.py` 와 똑같이 **opencode 를 실행한 폴더 기준**이다. 설정 파일 위치 기준이 아니다.

### Windows

- **확인한 것**: Linux 에서 `cargo xwin build --target x86_64-pc-windows-msvc` 로 만든 `.exe`(204 KiB)를 `bin\glossary-mcp.exe` 로 두고 Windows 의 opencode 1.19.5 에서 `opencode mcp list` 를 실행했더니 `connected` 였다. 설정은 Linux 와 같은 `["./bin/glossary-mcp"]` 그대로다. 즉 opencode 는 Windows 에서 `.exe` 를 붙이지 않은 이름으로도 실행 파일을 찾는다. `opencode.json` 하나로 두 OS 를 모두 쓸 수 있다.
- **확인하지 못한 것**: Windows 에서 `cargo build` 로 직접 빌드하는 과정(시험한 Windows 에 cargo 가 없었다). 그래서 Windows 에서 `check.py` 는 경고 한 줄을 내고 건너뛴다.
- Windows 에서 빌드하면 `build.py` 가 `bin\glossary-mcp.exe` 로 복사한다.

### 링크 방식과 glibc (이 PC 에서 확인한 것만)

- 기본 `cargo build --release`(Linux, `x86_64-unknown-linux-gnu`)의 결과는 **동적 링크**다. `ldd` 가 `libc.so.6`, `libgcc_s.so.1` 을 보여 주고, 필요한 glibc 심볼 버전은 최대 `GLIBC_2.34` 였다. 빌드한 PC 의 glibc 는 2.43 이다. 즉 이 파일은 **glibc 2.34 보다 오래된 배포판에서는 실행되지 않을 가능성이 높다**(오래된 배포판에서 실제로 돌려 보지는 않았다. 필요 버전은 `objdump -T` 로 읽은 값이다). "런타임이 필요 없다"는 말은 Python/Node 가 필요 없다는 뜻이지, 시스템 C 라이브러리까지 없어도 된다는 뜻이 아니다.
- 대안으로 `rustup target add x86_64-unknown-linux-musl` 후 `cargo build --release --target x86_64-unknown-linux-musl` 를 하면 **정적 링크**(`ldd` 가 `statically linked`)된 459,512 바이트 파일이 나왔다. 이 PC 에서 빌드와 `ldd` 까지만 확인했고, 다른 배포판에서 실행해 보지는 않았다.
- 오래된 배포판에서 빌드해서 낮은 glibc 에 맞추는 방법도 있지만 이 예제에서는 시도하지 않았다.

## 직접 바꿔 보기

1. **용어 추가** — `glossary.json` 에 용어를 넣고 `python build.py` 를 다시 실행한다. M1 과 달리 **다시 빌드해야** 반영된다. (파일을 읽는 게 아니라 안에 들어 있기 때문이다.)
2. **크기 줄이기/늘리기** — `Cargo.toml` 의 `[profile.release]` 세 줄을 지우고 다시 빌드해서 크기가 얼마나 늘어나는지 `build.py` 가 출력하는 KiB 를 비교한다.
3. **도구 추가** — `tool_definitions()` 에 정의를 하나 넣고 `call_tool()` 의 `match` 에 분기를 추가한다. 컴파일러가 빠뜨린 곳을 알려 준다.
4. **정적 링크 빌드** — 위 musl 명령으로 빌드하고 `ldd` 로 동적/정적을 비교한다.
5. **다른 폴더에서 호출** — 절대 경로 `command` 로 바꾸고 하위 폴더에서 `opencode mcp list` 를 실행해 위 표의 마지막 행을 재현한다.

## 주의할 점 / 문제 해결

- **`.gitignore`**: 레포 루트의 `.gitignore` 에는 `target/` 과 `bin/` 이 **없다**. 그래서 이 예제 폴더 안에 별도 `.gitignore`(`target/`, `bin/`)를 두었다. 이 폴더를 다른 곳에 복사해 쓸 때도 같이 가져가야 빌드 결과가 커밋되지 않는다.
- **`cargo` 를 찾을 수 없음** — `build.py` 가 종료 코드 2 로 끝난다. https://rustup.rs 로 설치한다. `check.py` 는 이때 경고만 내고 건너뛴다.
- **crates 를 받을 수 없음** — 인터넷이 없고 한 번도 받은 적이 없으면 `serde_json` 을 구할 수 없어 빌드가 안 된다(`build.py` 종료 코드 3, `check.py` 는 경고 후 건너뜀). 레지스트리 접속은 3초 안에 판정하고 안 되면 `--offline` 으로 시도한다. 패키지 미러를 쓴다면 `~/.cargo/config.toml` 에 `[source.crates-io] replace-with` 로 미러를 지정한다(이 설정은 이 PC 에서 시험하지 않았다).
- **`opencode mcp list` 가 failed** — `bin/glossary-mcp` 가 있는지(빌드했는지), opencode 를 이 예제 폴더에서 실행했는지부터 본다. 위 표처럼 하위 폴더에서 실행하면 실패한다.
- **서버 코드를 고쳤는데 반영이 안 된다** — `python build.py` 를 다시 실행하고 opencode 를 재시작한다. `bin/` 의 파일이 실행 중이면 Windows 에서는 덮어쓸 수 없으니 opencode 를 먼저 끈다(미확인).
- 실행 파일은 **만든 OS·CPU 용**이다. Linux 에서 만든 파일을 Windows 로 복사해도 실행되지 않는다. 교차 빌드는 가능하지만(위 Windows 항목) 별도 설정이 필요하다.
