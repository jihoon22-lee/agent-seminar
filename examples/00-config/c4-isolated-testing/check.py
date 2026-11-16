"""C4 검사: isolated.py 가 정말 실제 경로를 건드리지 않는지, 격리 스위치가 문서대로 동작하는지 (모델 호출 없음)."""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "tools"))
from octest import check, find_opencode, finish, strip_ansi  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
ENV = {**os.environ, "PYTHONUTF8": "1"}


def isolated(*args: str, cwd: pathlib.Path = HERE) -> subprocess.CompletedProcess:
    proc = subprocess.run([sys.executable, str(HERE / "isolated.py"), *args], cwd=str(cwd), env=ENV,
                          capture_output=True, stdin=subprocess.DEVNULL, timeout=300)
    proc.out = strip_ansi(proc.stdout.decode("utf-8", errors="replace"))
    proc.err = strip_ansi(proc.stderr.decode("utf-8", errors="replace"))
    return proc


def parse_paths(text: str) -> dict:
    return {m.group(1): pathlib.Path(m.group(2).strip()) for m in re.finditer(r"^(\w+)\s+(\S.*)$", text, re.M)}


def snapshot(path: pathlib.Path) -> dict:
    """실제 경로의 최상위 항목과 log 폴더 목록 (이름 -> 크기/수정시각). 격리가 새어 나가지 않았는지 비교하는 용도."""
    snap = {}
    for folder in (path, path / "log"):
        if folder.is_dir():
            for p in folder.iterdir():
                try:
                    st = p.stat()
                    snap[str(p)] = (st.st_size, st.st_mtime_ns)
                except OSError:
                    pass
    return snap


# 격리 없이 실행했을 때의 경로 (debug paths 는 읽기 전용이라 실제 설정을 바꾸지 않는다)
plain_env = {k: v for k, v in ENV.items() if not k.startswith("XDG_")}
proc = subprocess.run([find_opencode(), "debug", "paths"], capture_output=True, env=plain_env, timeout=60,
                      stdin=subprocess.DEVNULL, cwd=str(HERE))
normal = parse_paths(strip_ansi(proc.stdout.decode("utf-8", errors="replace")))
check("격리 없이 debug paths: config/data/cache/state 출력", {"config", "data", "cache", "state"} <= set(normal), str(normal))

real_dirs = [normal[k] for k in ("config", "data", "state") if k in normal]
before = {str(d): snapshot(d) for d in real_dirs}

# 1. isolated.py debug paths
proc = isolated("debug", "paths")
check("isolated.py debug paths 정상 종료", proc.returncode == 0, proc.err[-400:])
match = re.search(r"샌드박스: (.+?)  \(cwd", proc.err)
check("isolated.py: 샌드박스 경로를 stderr 에 알려 줌", bool(match), proc.err[-300:])
sandbox_root = pathlib.Path(match.group(1)) if match else pathlib.Path("?")
iso = parse_paths(proc.out)
inside = [k for k in ("data", "log", "cache", "config", "state", "tmp") if k in iso and sandbox_root in iso[k].parents]
check("격리 경로: data/log/cache/config/state/tmp 가 모두 샌드박스 아래", len(inside) == 6, str(iso))
check("격리 경로가 평소 경로와 다름", all(iso.get(k) != normal.get(k) for k in ("config", "data", "state")))
check("실행이 끝나면 샌드박스 폴더가 지워짐", not sandbox_root.exists(), str(sandbox_root))

# 2. --keep 으로 남기고, 그곳에만 쓰기가 일어났는지 본다
proc = isolated("--keep", "debug", "skill")
kept = re.search(r"샌드박스: (.+?)  \(cwd", proc.err)
kept_root = pathlib.Path(kept.group(1)) if kept else pathlib.Path("?")
try:
    check("--keep: 샌드박스가 남아 있음", kept_root.exists(), proc.err[-300:])
    check("--keep: 로그/데이터가 샌드박스 안에만 생김", (kept_root / "data" / "opencode").exists())
    skills = {s["name"] for s in json.loads(proc.out[proc.out.find("["):])}
    check("격리 샌드박스에서도 프로젝트 스킬은 보임", "c4-local-skill" in skills, str(skills))
finally:
    shutil.rmtree(kept_root, ignore_errors=True)

# 3. --global-config / --cwd / -- 구분자 / --env
with tempfile.TemporaryDirectory(prefix="c4-check-") as tmp:
    empty = pathlib.Path(tmp)
    proc = isolated("--global-config", str(HERE / "fake-global.json"), "--cwd", str(empty), "debug", "config")
    cfg = json.loads(proc.out[proc.out.find("{"):])
    check("--global-config + --cwd: 전역 설정 대역이 적용됨", cfg.get("username") == "fake-global-user", str(cfg.get("username")))
    proc = isolated("--cwd", str(empty), "--", "--pure", "debug", "config")
    check("-- 뒤에 opencode 옵션(--pure) 전달", proc.returncode == 0, proc.err[-300:])
    proc = isolated("--env", "OPENCODE_CONFIG=" + str(HERE / "test-config.json"), "--cwd", str(empty), "debug", "config")
    cfg = json.loads(proc.out[proc.out.find("{"):])
    check("--env NAME=VALUE 전달 (OPENCODE_CONFIG)", cfg.get("username") == "c4-test-user", str(cfg.get("username")))
    check("OPENCODE_CONFIG 는 전역을 대체하지 않고 얹힘 (전역의 autoupdate=false 가 남음)", cfg.get("autoupdate") is False)

# 4. 스위치 비교표
proc = subprocess.run([sys.executable, str(HERE / "flags_demo.py")], capture_output=True, timeout=600, env=ENV, cwd=str(HERE))
table = proc.stdout.decode("utf-8", errors="replace")
check("flags_demo.py 정상 종료", proc.returncode == 0, proc.stderr.decode("utf-8", errors="replace")[-500:])
rows = {}
for line in table.splitlines():
    cells = re.split(r"\s{2,}", line.strip())
    if len(cells) == 5:
        rows[cells[0]] = cells[1:]
base = rows.get("(none) sandbox only", [])
check("기본: 프로젝트 설정/스킬/플러그인/외부 스킬 모두 적용", base == ["c4-project-user", "visible", "visible", "loaded"], str(base))
check("OPENCODE_DISABLE_EXTERNAL_SKILLS=1: 외부 스킬만 숨김",
      rows.get("OPENCODE_DISABLE_EXTERNAL_SKILLS=1") == ["c4-project-user", "visible", "hidden", "loaded"], str(rows))
check("OPENCODE_DISABLE_PROJECT_CONFIG=1: 프로젝트 설정·스킬·플러그인 모두 무시",
      rows.get("OPENCODE_DISABLE_PROJECT_CONFIG=1") == ["fake-global-user", "hidden", "visible", "not loaded"], str(rows))
check("--pure: 플러그인만 막음 (설정·스킬은 그대로)",
      rows.get("--pure") == ["c4-project-user", "visible", "visible", "not loaded"], str(rows))
check("OPENCODE_CONFIG 단독: 프로젝트 설정이 더 높은 우선순위라 이김",
      rows.get("OPENCODE_CONFIG=test-config.json") == ["c4-project-user", "visible", "visible", "loaded"], str(rows))
check("DISABLE_PROJECT_CONFIG + OPENCODE_CONFIG: 테스트 설정만 남음",
      rows.get("DISABLE_PROJECT_CONFIG + CONFIG") == ["c4-test-user", "hidden", "visible", "not loaded"], str(rows))

# 5. 실제 경로가 바뀌지 않았다 (동시에 다른 opencode 가 돌고 있으면 달라질 수 있으므로 soft)
after = {str(d): snapshot(d) for d in real_dirs}
check("실제 config/data/state 폴더 내용이 실행 전후 동일", before == after,
      "다른 opencode 프로세스가 동시에 쓴 것일 수 있음: " + str([k for k in after if after[k] != before.get(k)]), soft=True)
finish()
