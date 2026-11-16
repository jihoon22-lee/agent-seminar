"""s5c 검증: 스킬 범위 (전역 / 프로젝트 / skills.paths / skills.urls).

하드 체크(모델 없음): demo.py 의 시나리오를 그대로 돌려 위치 표를 확인한다.
  - 같은 이름 충돌은 병렬 로딩 때문에 승자가 매번 같지 않다 -> 승자를 단정하지 않고,
    "이름은 하나만 남는다 / 경고 로그가 찍힌다 / 이긴 쪽은 둘 중 하나" 만 하드 체크, 비율은 soft.
모델 체크(--model): team-skills 폴더의 스킬을 모델이 실제로 불러오는지 1번.
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "tools"))
sys.path.insert(0, str(HERE))

from octest import MODEL_UNAVAILABLE, RATE_LIMIT_RE, DEFAULT_MODEL, Sandbox, check, finish, model_check, model_enabled

import demo
import lab

RUNS = 5


class Box:
    """octest.Sandbox 를 lab/demo 가 기대하는 모양(opencode(), skills(), config_dir, root)으로 감싼다."""

    def __init__(self, sb: Sandbox) -> None:
        self.sb, self.bin, self.env, self.root = sb, sb.bin, sb.env, sb.root
        self.config_dir = sb.opencode_config_dir

    def opencode(self, args, cwd, overlay=None, timeout=180, extra_env=None):
        return lab.run_opencode(self.bin, self.env, args, cwd, overlay=overlay, timeout=timeout,
                                extra_env=extra_env, scratch=self.root)

    def skills(self, cwd, overlay=None):
        proc = self.opencode(["debug", "skill"], cwd, overlay=overlay)
        return [s for s in lab.parse_json(proc.stdout) if s["name"] != "customize-opencode"]


with Sandbox("s5c") as sb:
    box = Box(sb)

    cfg = sb.debug_config(HERE / "project")
    check("project/opencode.json 의 skills.paths 가 ../team-skills 로 병합됨",
          cfg.get("skills", {}).get("paths") == ["../team-skills"], str(cfg.get("skills")))
    real = {s["name"]: s for s in box.skills(HERE / "project")}
    check("예제 그대로 project/ 에서 실행하면 프로젝트 스킬 + team-skills 스킬(하위 폴더 포함)이 모두 보임",
          set(real) == {"project-conventions", "code-review-style", "release-notes"}, str(sorted(real)))
    check("team-skills/backend/code-review-style 처럼 깊은 폴더도 찾음 (**/SKILL.md 재귀 탐색)",
          real.get("code-review-style", {}).get("location", "").replace("\\", "/").endswith("team-skills/backend/code-review-style/SKILL.md"))

    r = demo.run_all(box, runs=RUNS, port=0, verbose=False)

    g = r["global_only"].get("greeting", {})
    check("전역 스킬만 있으면 전역 폴더의 위치로 보임", demo.kind(g.get("location", "")) == "전역", str(g))
    check("프로젝트 스킬과 전역 스킬은 합쳐서 보임",
          set(r["project_only"]) == {"greeting", "project-conventions"}, str(sorted(r["project_only"])))
    tally = r["same_name_tally"]
    check("같은 이름이 전역·프로젝트에 있어도 하나만 남고, 이긴 쪽은 둘 중 하나",
          sum(tally.values()) == RUNS and set(tally) <= {"전역", "프로젝트"}, str(dict(tally)))
    check("같은 이름 충돌 때 'duplicate skill name' 경고가 로그에 찍힘",
          any("duplicate skill name" in w and "name=greeting" in w for w in r["same_name_warning"]), str(r["same_name_warning"]))
    check("[soft] 같은 이름 충돌에서 프로젝트가 과반 승리 (병렬 로딩이라 항상은 아님)",
          tally["프로젝트"] > RUNS / 2, str(dict(tally)), soft=True)

    check("skills.paths 상대 경로: 프로젝트 루트에서는 team-skills 를 찾음",
          {"code-review-style", "release-notes", "project-conventions"} <= set(r["paths_root"]))
    check("[실패 확인] 하위 폴더에서 실행하면 상대 경로가 실행 폴더 기준이라 team-skills 가 사라지고 프로젝트 스킬만 남음",
          set(r["paths_deeper"]) == {"project-conventions"}, str(sorted(r["paths_deeper"])))
    check("그때 'skill path not found' 경고에 project/sub/team-skills 가 찍힘",
          any("skill path not found" in w and "sub/team-skills" in re.sub(r"[\\/]+", "/", w) for w in r["paths_deeper_warning"]),
          str(r["paths_deeper_warning"]))
    check("절대 경로로 쓰면 하위 폴더에서도 team-skills 를 찾음", "code-review-style" in r["paths_absolute_deeper"])
    check("'~/team-skills' 도 홈 폴더 기준으로 풀림", "code-review-style" in r["paths_tilde"], str(sorted(r["paths_tilde"])))
    t5 = r["paths_vs_project_tally"]
    check("프로젝트와 skills.paths 에 같은 이름이면 둘 중 하나가 이김",
          sum(t5.values()) == RUNS and set(t5) <= {"skills.paths", "프로젝트"}, str(dict(t5)))
    check("[soft] 같은 이름 충돌에서 skills.paths 쪽이 과반 승리 (뒤에 등록된 쪽이 덮어씀, 병렬 로딩이라 항상은 아님)",
          t5["skills.paths"] > RUNS / 2, str(dict(t5)), soft=True)

    first = r["url_first"].get("remote-glossary", {})
    check("skills.urls: index.json 을 읽고 스킬을 캐시 폴더로 내려받음",
          demo.kind(first.get("location", "")) == "url" and "v1" in first.get("description", ""), str(first))
    check("skills.urls: version 이 없으면 서버 내용을 바꿔도 캐시(v1)가 계속 쓰임",
          "v1" in r["url_changed_no_version"]["remote-glossary"]["description"])
    check("skills.urls: index.json 의 version 을 올리면 다시 내려받음(v2)",
          "v2" in r["url_bumped"]["remote-glossary"]["description"])
    check("skills.urls: index.json 의 files 목록이 모두 캐시에 저장됨(+ .opencode-version)",
          r["url_cache_files"] == [".opencode-version", "SKILL.md", "examples.md"], str(r["url_cache_files"]))
    check("[실패 확인] 서버가 꺼지면 캐시가 있어도 URL 스킬이 사라짐", "remote-glossary" not in r["url_offline"])

    import tempfile
    with tempfile.TemporaryDirectory(prefix="s5c-name-") as t:
        demo.write_skill(Path(t) / "proj" / ".opencode" / "skills" / "folder-name", "other-name", "이름이 폴더와 다른 스킬")
        names = {s["name"] for s in box.skills(Path(t) / "proj")}
    check("스킬은 폴더 이름이 아니라 frontmatter 의 name 으로 등록됨 (폴더와 달라도 거부되지 않음)", names == {"other-name"}, str(names))

    mono = r["mono"]
    if mono:
        check("모노레포: 하위 폴더(pkg/a/src)에서 실행하면 pkg/a 의 스킬과 저장소 루트의 스킬이 함께 보임 (skill 단수형 폴더도 인식)",
              set(mono["pkg/a/src"]) == {"pkg-a", "repo-root"}, str(sorted(mono["pkg/a/src"])))
        check("모노레포: 형제·하위 패키지의 스킬(pkg/a)은 상위 폴더(pkg)에서 보이지 않음", set(mono["pkg"]) == {"repo-root"}, str(sorted(mono["pkg"])))
        check("저장소(git 루트) 바깥 위쪽 폴더의 스킬은 보이지 않음", all("above-repo" not in m for m in mono.values()))
    else:
        print("[SKIP] git 이 없어 모노레포 시나리오를 건너뜀")

    if model_enabled():
        out = lab.run_model(box, "code-review-style 스킬을 사용해서 리뷰 때 지적 순서를 한 줄로 알려줘.",
                            HERE / "project", DEFAULT_MODEL)
        if RATE_LIMIT_RE.search(out) or out.startswith("<<timeout>>"):
            out = MODEL_UNAVAILABLE + "\n" + out
        model_check("실제 모델: skills.paths 로 연결한 team-skills 의 스킬을 모델이 불러옴",
                    out, 'Skill "code-review-style"' in out)
# octest.Sandbox 는 Windows 에서 읽기 전용 git 객체 파일을 못 지우고 폴더를 남기므로 한 번 더 정리한다
lab.rmtree_force(sb.root)
finish()
