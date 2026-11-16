"""스킬 범위(전역 / 프로젝트 / 공용 폴더 / URL)를 임시 샌드박스에서 확인합니다 (모델 불필요, 인터넷 불필요).

    python demo.py                 # 전체 시나리오
    python demo.py --runs 20       # 같은 이름 충돌 시 승자를 20번 세어 봄
    python demo.py --port 8851     # skills.urls 실험용 로컬 HTTP 서버 포트 (기본 8851, 127.0.0.1 에만 열림)

내 진짜 ~/.config/opencode 는 건드리지 않습니다. "전역 스킬 폴더"는 임시 폴더 안에 새로 만든 가짜입니다.
각 시나리오마다 `opencode debug skill` 이 돌려준 "이름 -> 위치" 표를 보여 줍니다.
Linux에서 `python` 명령이 없으면 `python3` 로 바꿔 실행하세요.
"""
from __future__ import annotations

import argparse
import collections
import functools
import json
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import lab

HERE = Path(__file__).resolve().parent
IGNORE = shutil.ignore_patterns("node_modules", "package*.json", "bun.lock", ".gitignore")


def write_skill(folder: Path, name: str, description: str | None, body: str = "본문") -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    head = f"---\nname: {name}\n" + (f"description: {description}\n" if description else "") + "---\n"
    path = folder / "SKILL.md"
    path.write_text(head + body + "\n", encoding="utf-8")
    return path


def workspace(tmp: Path, name: str, *, config: dict | None = "shipped", project_skills: bool = True) -> Path:
    """tmp/<name>/project 와 tmp/<name>/team-skills 를 이 예제에서 복사해 만든다 (상대 경로 ../team-skills 가 그대로 성립)."""
    base = tmp / name
    shutil.copytree(HERE / "team-skills", base / "team-skills", ignore=IGNORE)
    project = base / "project"
    if project_skills:
        shutil.copytree(HERE / "project" / ".opencode", project / ".opencode", ignore=IGNORE)
    else:
        project.mkdir(parents=True)
    if config == "shipped":
        shutil.copy(HERE / "project" / "opencode.json", project / "opencode.json")
    elif config is not None:
        (project / "opencode.json").write_text(json.dumps(config), encoding="utf-8")
    return project


def where(location: str, sb: lab.Sandbox, ws_root: Path | None = None) -> str:
    """위치를 사람이 읽기 좋게 줄인다."""
    loc = re.sub(r"[\\/]+", "/", location)  # 로그에 찍힌 Windows 경로는 역슬래시가 겹쳐 있을 수 있음
    for base, label in ((sb.root, "<샌드박스>"), (ws_root, "<작업폴더>")):
        if base is not None:
            loc = loc.replace(re.sub(r"[\\/]+", "/", str(base)), label)
    return loc


def kind(location: str) -> str:
    loc = location.replace("\\", "/")
    if "/config/opencode/skills/" in loc:
        return "전역"
    if "/cache/opencode/skills/" in loc:
        return "url"
    if "/team-skills/" in loc:
        return "skills.paths"
    if "/.opencode/skills/" in loc or "/.opencode/skill/" in loc:
        return "프로젝트"
    return "?"


def table(sb: lab.Sandbox, cwd: Path, title: str, overlay: dict | None = None, ws_root: Path | None = None,
          verbose: bool = True) -> dict[str, dict]:
    skills = {s["name"]: s for s in sb.skills(cwd, overlay=overlay)}
    if verbose:
        print(f"\n-- {title}")
        print(f"   (opencode 를 실행한 폴더: {where(str(cwd), sb, ws_root)})")
        for name, s in sorted(skills.items()):
            print(f"   {name}  [{kind(s['location'])}]  {where(s['location'], sb, ws_root)}")
            if kind(s["location"]) == "url":
                print(f"      description: {s.get('description')}")
        if not skills:
            print("   (스킬 없음 - 내장 customize-opencode 는 생략)")
    return skills


def tally(sb: lab.Sandbox, cwd: Path, name: str, runs: int, overlay: dict | None = None) -> collections.Counter:
    counts: collections.Counter = collections.Counter()
    for _ in range(runs):
        skills = {s["name"]: s for s in sb.skills(cwd, overlay=overlay)}
        counts[kind(skills[name]["location"])] += 1
    return counts


def duplicate_warning(sb: lab.Sandbox, cwd: Path, overlay: dict | None = None) -> list[str]:
    proc = sb.opencode(["debug", "skill", "--print-logs"], cwd, overlay=overlay)
    return [line.split("message=", 1)[-1] for line in proc.stderr.splitlines() if "duplicate skill name" in line]


def path_warnings(sb: lab.Sandbox, cwd: Path) -> list[str]:
    proc = sb.opencode(["debug", "skill", "--print-logs"], cwd)
    return [line.split("message=", 1)[-1] for line in proc.stderr.splitlines() if "skill path not found" in line]


class _Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *args):  # 접속 로그 숨김
        pass


def start_skill_server(root: Path, port: int) -> ThreadingHTTPServer:
    """root 폴더를 http://127.0.0.1:<port>/ 로 서빙. 인터넷으로는 나가지 않는다."""
    server = ThreadingHTTPServer(("127.0.0.1", port), functools.partial(_Quiet, directory=str(root)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def publish(root: Path, version: str | None, text: str) -> None:
    """원격 스킬 1개(remote-glossary)를 root/skills/ 아래에 index.json 과 함께 쓴다."""
    skill_dir = root / "skills" / "remote-glossary"
    write_skill(skill_dir, "remote-glossary", f"원격 서버에서 내려받는 스킬 ({text})", body=text)
    (skill_dir / "examples.md").write_text("보조 파일\n", encoding="utf-8")
    entry: dict = {"name": "remote-glossary", "files": ["SKILL.md", "examples.md"]}
    if version is not None:
        entry["version"] = version
    (root / "skills" / "index.json").write_text(json.dumps({"skills": [entry]}), encoding="utf-8")


def monorepo(tmp: Path) -> Path | None:
    """git 저장소 안에 .opencode/skills 를 여러 층에 두고, 저장소 바깥(위)에도 하나 둔다. git 이 없으면 None."""
    base = tmp / "mono"
    repo = base / "repo"
    try:
        (repo / "pkg" / "a" / "src").mkdir(parents=True)
        subprocess.run(["git", "init", "-q"], cwd=str(repo), check=True, stdin=subprocess.DEVNULL, capture_output=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    write_skill(base / ".opencode" / "skills" / "above-repo", "above-repo", "저장소 바깥(위) 폴더의 스킬")
    write_skill(repo / ".opencode" / "skill" / "repo-root", "repo-root", "저장소 루트의 스킬 (폴더 이름이 skill 단수형)")
    write_skill(repo / "pkg" / "a" / ".opencode" / "skills" / "pkg-a", "pkg-a", "pkg/a 패키지의 스킬")
    return repo


def run_all(sb: lab.Sandbox, runs: int = 10, port: int = 8851, verbose: bool = True) -> dict:
    out: dict = {}
    with tempfile.TemporaryDirectory(prefix="s5c-") as t:
        tmp = Path(t)

        # 1. 전역 스킬만 있을 때
        write_skill(sb.config_dir / "skills" / "greeting", "greeting", "전역 인사 스킬 (전역 버전)", "GLOBAL")
        empty = tmp / "empty"
        empty.mkdir()
        out["global_only"] = table(sb, empty, "1. 전역 스킬만 있고 프로젝트에는 스킬이 없음", ws_root=tmp, verbose=verbose)

        # 2. 프로젝트 스킬 (skills.paths 없음)
        ws = workspace(tmp, "ws-plain", config=None)
        out["project_only"] = table(sb, ws, "2. 프로젝트 .opencode/skills 만 (+ 위의 전역 greeting 도 같이 보임)", ws_root=tmp, verbose=verbose)

        # 3. 같은 이름이 전역과 프로젝트에 모두 있을 때
        write_skill(ws / ".opencode" / "skills" / "greeting", "greeting", "프로젝트 인사 스킬 (프로젝트 버전)", "PROJECT")
        out["same_name_tally"] = tally(sb, ws, "greeting", runs)
        out["same_name_warning"] = duplicate_warning(sb, ws)
        if verbose:
            print(f"\n-- 3. 같은 이름 greeting 이 전역과 프로젝트에 모두 있음 ({runs}번 반복해서 어느 쪽 위치가 이겼는지 셈)")
            for k, v in out["same_name_tally"].most_common():
                print(f"   {k}: {v}/{runs}")
            for w in out["same_name_warning"][:1]:
                print("   opencode 경고 로그:", where(w, sb, tmp)[:230])

        # 4. skills.paths 로 팀 공용 폴더 연결
        sb_global_greeting = sb.config_dir / "skills" / "greeting"
        shutil.rmtree(sb_global_greeting)  # 이후 시나리오가 헷갈리지 않게 전역 greeting 제거
        ws = workspace(tmp, "ws-paths")
        out["paths_root"] = table(sb, ws, "4-a. skills.paths = [\"../team-skills\"], project/ 에서 실행", ws_root=tmp, verbose=verbose)
        deeper = ws / "sub" / "deeper"
        deeper.mkdir(parents=True)
        out["paths_deeper"] = table(sb, deeper, "4-b. 같은 프로젝트의 하위 폴더 project/sub/deeper 에서 실행 (상대 경로가 실행 폴더 기준이라 공용 스킬이 사라짐)", ws_root=tmp, verbose=verbose)
        out["paths_deeper_warning"] = path_warnings(sb, deeper)
        if verbose:
            for w in out["paths_deeper_warning"][:1]:
                print("   opencode 경고 로그:", where(w, sb, tmp))
        abs_overlay = {"skills": {"paths": [str((ws.parent / "team-skills").resolve())]}}
        out["paths_absolute_deeper"] = table(sb, deeper, "4-c. 절대 경로로 쓰면 어디서 실행해도 찾음", overlay=abs_overlay, ws_root=tmp, verbose=verbose)
        home = tmp / "fake-home"
        shutil.copytree(HERE / "team-skills", home / "team-skills", ignore=IGNORE)
        tilde = sb.opencode(["debug", "skill"], deeper, overlay={"skills": {"paths": ["~/team-skills"]}},
                            extra_env={"HOME": str(home), "USERPROFILE": str(home)})
        out["paths_tilde"] = {s["name"]: s for s in lab.parse_json(tilde.stdout) if s["name"] != "customize-opencode"}
        if verbose:
            print(f"\n-- 4-d. \"~/team-skills\" (HOME 을 임시 폴더로 바꿔서 실행): {sorted(out['paths_tilde'])}")

        # 5. skills.paths 와 프로젝트에 같은 이름
        write_skill(ws / ".opencode" / "skills" / "release-notes", "release-notes", "프로젝트 버전 릴리스 노트", "PROJECT")
        out["paths_vs_project_tally"] = tally(sb, ws, "release-notes", runs)
        if verbose:
            print(f"\n-- 5. release-notes 가 프로젝트 .opencode/skills 와 team-skills 양쪽에 있음 ({runs}번 반복)")
            for k, v in out["paths_vs_project_tally"].most_common():
                print(f"   {k}: {v}/{runs}")

        # 6. skills.urls
        srv_root = tmp / "srv"
        publish(srv_root, None, "v1")
        server = start_skill_server(srv_root, port)
        try:
            url_overlay = {"skills": {"urls": [f"http://127.0.0.1:{server.server_address[1]}/skills/"]}}
            plain = tmp / "url-project"
            plain.mkdir()
            out["url_first"] = table(sb, plain, f"6-a. skills.urls = [\"http://127.0.0.1:{server.server_address[1]}/skills/\"] (index.json + 스킬 파일을 내려받음)", overlay=url_overlay, ws_root=tmp, verbose=verbose)
            publish(srv_root, None, "v2")
            out["url_changed_no_version"] = table(sb, plain, "6-b. 서버 내용을 v2 로 바꿨지만 index.json 에 version 이 없음 -> 캐시가 그대로 쓰임", overlay=url_overlay, ws_root=tmp, verbose=verbose)
            publish(srv_root, "2", "v2")
            out["url_bumped"] = table(sb, plain, "6-c. index.json 에 \"version\": \"2\" 를 넣음 -> 다시 내려받음", overlay=url_overlay, ws_root=tmp, verbose=verbose)
            cached = sorted(p.name for p in (sb.root / "cache" / "opencode" / "skills" / "remote-glossary").iterdir())
            out["url_cache_files"] = cached
            if verbose:
                print(f"   캐시 폴더 {where(str(sb.root / 'cache' / 'opencode' / 'skills' / 'remote-glossary'), sb)} 안: {cached}")
        finally:
            server.shutdown()
            server.server_close()
        out["url_offline"] = table(sb, plain, "6-d. 서버를 끄고 다시 실행 -> 캐시가 있는데도 URL 스킬이 사라짐", overlay=url_overlay, ws_root=tmp, verbose=verbose)

        # 7. 모노레포: 실행 폴더에서 git 루트까지 위로 올라가며 .opencode/skills 를 모은다
        repo = monorepo(tmp)
        out["mono"] = {}
        if repo is not None:
            for label, sub in (("repo 루트", "."), ("pkg", "pkg"), ("pkg/a/src", "pkg/a/src")):
                out["mono"][label] = table(sb, (repo / sub).resolve(), f"7. 모노레포 - {label} 에서 실행", ws_root=tmp, verbose=verbose)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=10, help="같은 이름 충돌에서 승자를 세는 반복 횟수")
    ap.add_argument("--port", type=int, default=8851, help="skills.urls 실험용 로컬 서버 포트")
    args = ap.parse_args()
    with lab.Sandbox() as sb:
        run_all(sb, args.runs, args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
