// p12-context-injection (1/2): 매 모델 요청의 시스템 프롬프트 끝에 "지금 상황" 블록을 붙이는 플러그인.
//
// AGENTS.md 는 정적입니다. 브랜치, 작업 트리 상태, 오늘 날짜, 지금 하는 일처럼 "시간에 따라 바뀌는 사실"은 담을 수 없습니다.
// 이 훅(experimental.chat.system.transform)은 요청을 만들 때마다 불리므로 그런 사실을 매번 새로 넣을 수 있습니다.
//
// !! 이름이 experimental. 로 시작합니다: opencode 버전이 바뀌면 이름·모양이 바뀌거나 사라질 수 있습니다(1.19.5 기준).
//    check.py 가 동작을 고정해 두었으니, 버전을 올린 뒤 check.py 가 깨지면 이 훅부터 의심하세요.
//
// 넣는 것(작게, 한 블록): 날짜(요일), git 브랜치, 작업 트리 변경 여부(기본 있음/없음, 선택 시 개수만), .opencode/now.md 내용(있으면, 최대 800자)
// 비용을 줄이는 법: git 조회 결과를 CONTEXT_TTL_MS(기본 5000ms) 동안 캐시합니다. 어떤 실패도 throw 하지 않고 블록을 생략합니다.
// 주의: 시스템 프롬프트가 바뀌면 그 뒤의 대화 전체가 공급자의 프롬프트 캐시에서 빠질 수 있습니다(README 참고).
//       그래서 기본값은 작업 트리를 "있음/없음"(flag)으로만 적어, 파일을 고칠 때마다 블록이 바뀌지 않게 합니다.
//       개수가 필요하면 CONTEXT_DIRTY=count 로 켭니다. (설계상의 고려이며, 공급자 쪽 캐시 효과는 이 예제에서 측정하지 않았습니다.)
//
// 환경변수(모두 선택): CONTEXT_TTL_MS, CONTEXT_DIRTY(flag|count, 기본 flag), CONTEXT_NOW_FILE(기본 .opencode/now.md)
//
// 주의: 이 파일은 "플러그인 함수"만 export 합니다. 함수가 아닌 값을 export 하면 opencode 가 파일 전체를 건너뜁니다.
import { execFile } from "node:child_process";
import { appendFileSync, mkdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

const WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"];
const MAX_NOW_CHARS = 800;

function git(cwd, args) {
  return new Promise((done) => {
    execFile("git", args, { cwd, timeout: 3000, windowsHide: true, env: { ...process.env, GIT_OPTIONAL_LOCKS: "0" } },
      (error, stdout) => done(error ? null : String(stdout).trim()));
  });
}

function today() {
  const d = new Date();
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} (${WEEKDAYS[d.getDay()]})`;
}

export const ContextInjection = async ({ directory }) => {
  let cache = null; // { at, lines }

  function log(line) {
    try {
      mkdirSync(join(directory, "logs"), { recursive: true });
      appendFileSync(join(directory, "logs", "context-injection.log"), `${new Date().toISOString()} ${line}\n`, "utf8");
    } catch {
      // 로그를 못 남겨도 주입은 계속됩니다.
    }
  }

  // git 에게 묻는 부분만 캐시한다 (날짜와 now.md 는 싸니까 매번 새로 읽는다)
  async function gitLines() {
    const ttl = process.env.CONTEXT_TTL_MS !== undefined ? Number(process.env.CONTEXT_TTL_MS) : 5000;
    if (cache && Date.now() - cache.at < ttl) return { lines: cache.lines, cached: true };
    const [branch, status] = await Promise.all([
      git(directory, ["symbolic-ref", "-q", "--short", "HEAD"]),
      git(directory, ["status", "--porcelain", "--", ".", ":(exclude)logs"]), // 플러그인 자신의 logs/ 는 세지 않는다
    ]);
    const lines = [];
    if (status !== null) { // status 가 성공해야 git 저장소다
      let where = branch;
      if (!where) where = `(detached HEAD ${(await git(directory, ["rev-parse", "--short", "HEAD"])) ?? ""})`.replace(" )", ")");
      lines.push(`- git 브랜치: ${where}`);
      const changed = status === "" ? 0 : status.split("\n").length;
      if (process.env.CONTEXT_DIRTY === "count") lines.push(`- 작업 트리: ${changed ? `커밋되지 않은 변경 ${changed}개` : "깨끗함"}`);
      else lines.push(`- 작업 트리: ${changed ? "커밋되지 않은 변경 있음" : "깨끗함"}`);
    }
    cache = { at: Date.now(), lines };
    return { lines, cached: false };
  }

  function nowFile() {
    try {
      const file = process.env.CONTEXT_NOW_FILE || join(".opencode", "now.md");
      const text = readFileSync(join(directory, file), "utf8").trim();
      if (!text) return [];
      const body = text.length > MAX_NOW_CHARS ? `${text.slice(0, MAX_NOW_CHARS)}\n(이하 생략)` : text;
      return [`- 지금 하는 일 (${file.replace(/\\/g, "/")}):`, ...body.split("\n").map((l) => `  ${l}`)];
    } catch {
      return []; // 파일이 없거나 읽을 수 없으면 그냥 뺀다
    }
  }

  log("context-injection loaded");
  return {
    "experimental.chat.system.transform": async (input, output) => {
      try {
        if (!output || !Array.isArray(output.system)) return;
        const g = await gitLines();
        const block = ["## 지금 상황 (플러그인이 요청마다 갱신)", `- 오늘: ${today()}`, ...g.lines, ...nowFile()].join("\n");
        output.system.push(block);
        log(`inject session=${input?.sessionID ?? "-"} chars=${block.length} gitCached=${g.cached}`);
      } catch (err) {
        log(`ERROR ${String(err?.message ?? err).slice(0, 160)}`); // 실패하면 아무것도 붙이지 않는다
      }
    },
  };
};
