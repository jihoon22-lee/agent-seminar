// p12 의 두 플러그인(context-injection, bash-reminder)을 훅 직접 호출로 검증합니다. (Node 18+, git 필요)
//   node tests/hooks.test.mjs
import { execFileSync } from "node:child_process";
import { copyFileSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const tmp = mkdtempSync(join(tmpdir(), "context-injection-test-"));
const load = async (file) => {
  copyFileSync(join(here, "..", ".opencode", "plugins", file), join(tmp, file.replace(/\.js$/, ".mjs")));
  return import(pathToFileURL(join(tmp, file.replace(/\.js$/, ".mjs"))).href);
};
const ctx = await load("context-injection.js");
const rem = await load("bash-reminder.js");

const identity = { GIT_AUTHOR_NAME: "t", GIT_AUTHOR_EMAIL: "t@example.invalid", GIT_COMMITTER_NAME: "t", GIT_COMMITTER_EMAIL: "t@example.invalid" };
const git = (cwd, ...args) => execFileSync("git", args, { cwd, env: { ...process.env, ...identity }, stdio: "pipe" }).toString().trim();
function repo(name, branch = "main") {
  const dir = join(tmp, name);
  mkdirSync(dir);
  git(dir, "init", "-q", "-b", branch);
  writeFileSync(join(dir, "f.txt"), "x");
  git(dir, "add", ".");
  git(dir, "commit", "-q", "-m", "init");
  return dir;
}

let failed = 0, total = 0;
const ok = (cond, label, extra = "") => { total++; if (!cond) { failed++; console.log("FAIL:", label, extra); } };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// 훅을 한 번 호출하고 system 배열을 돌려준다
async function inject(hooks, existing = ["BASE-PROMPT"]) {
  const output = { system: [...existing] };
  await hooks["experimental.chat.system.transform"]({ sessionID: "s", model: {} }, output);
  return output.system;
}
const blockOf = (system) => system[system.length - 1];

// ---- 기본 블록
{
  const dir = repo("a", "main");
  const hooks = await ctx.ContextInjection({ directory: dir });
  const sys = await inject(hooks);
  ok(sys.length === 2 && sys[0] === "BASE-PROMPT", "기존 시스템 항목은 그대로 두고 끝에 하나만 붙인다", JSON.stringify(sys));
  const b = blockOf(sys);
  const d = new Date();
  const wd = ["일", "월", "화", "수", "목", "금", "토"][d.getDay()];
  const ymd = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  ok(b.startsWith("## 지금 상황"), "제목으로 시작", b);
  ok(b.includes(`- 오늘: ${ymd} (${wd})`), "오늘 날짜와 요일", b);
  ok(b.includes("- git 브랜치: main"), "브랜치", b);
  ok(b.includes("- 작업 트리: 깨끗함"), "깨끗한 작업 트리", b);
  ok(!b.includes("지금 하는 일"), "now.md 가 없으면 그 항목을 뺀다", b);
  ok(b.length < 300, "now.md 없는 블록은 300자 미만", String(b.length));
}

// ---- 브랜치 종류
{
  const f = repo("feat", "main"); git(f, "switch", "-q", "-c", "feat/login");
  ok(blockOf(await inject(await ctx.ContextInjection({ directory: f }))).includes("- git 브랜치: feat/login"), "feature 브랜치");
  const d = repo("det", "main"); git(d, "checkout", "-q", "--detach");
  const sha = git(d, "rev-parse", "--short", "HEAD");
  ok(blockOf(await inject(await ctx.ContextInjection({ directory: d }))).includes(`- git 브랜치: (detached HEAD ${sha})`), "detached HEAD");
  const plain = join(tmp, "plain"); mkdirSync(plain);
  const b = blockOf(await inject(await ctx.ContextInjection({ directory: plain })));
  ok(b.includes("- 오늘:") && !b.includes("git 브랜치") && !b.includes("작업 트리"), "git 저장소가 아니면 git 항목만 뺀다", b);
}

// ---- 작업 트리 변경 개수 / 캐시
{
  process.env.CONTEXT_TTL_MS = "0";
  const dir = repo("dirty");
  const hooks = await ctx.ContextInjection({ directory: dir });
  writeFileSync(join(dir, "u1.txt"), "1"); writeFileSync(join(dir, "u2.txt"), "2"); writeFileSync(join(dir, "f.txt"), "changed");
  const dflt = blockOf(await inject(hooks));
  ok(dflt.includes("- 작업 트리: 커밋되지 않은 변경 있음") && !/\d개/.test(dflt), "기본(flag)은 있음/없음만 적는다");
  writeFileSync(join(dir, "u3.txt"), "3");
  ok(blockOf(await inject(hooks)) === dflt, "기본(flag)은 파일이 더 바뀌어도 블록이 그대로다 (프롬프트 캐시 설계)");
  process.env.CONTEXT_DIRTY = "count";
  const cnt = blockOf(await inject(hooks));
  delete process.env.CONTEXT_DIRTY;
  ok(cnt.includes("- 작업 트리: 커밋되지 않은 변경 4개"), "CONTEXT_DIRTY=count 는 수정 1 + 새 파일 3 = 4개");
  git(dir, "add", "."); git(dir, "commit", "-q", "-m", "all");
  ok(blockOf(await inject(hooks)).includes("- 작업 트리: 깨끗함"), "커밋하면 다시 깨끗함 (TTL 0 이면 바로 반영)");

  process.env.CONTEXT_TTL_MS = "300";
  const cached = await ctx.ContextInjection({ directory: dir });
  const first = blockOf(await inject(cached));
  writeFileSync(join(dir, "late.txt"), "x");
  const second = blockOf(await inject(cached));
  ok(first === second && second.includes("깨끗함"), "TTL 안에서는 git 결과를 캐시해 바뀐 것을 아직 모른다 (오래된 값)", second);
  await sleep(400);
  ok(blockOf(await inject(cached)).includes("변경 있음"), "TTL 이 지나면 새로 읽는다");
  delete process.env.CONTEXT_TTL_MS;
}

// ---- now.md
{
  const dir = repo("now");
  mkdirSync(join(dir, ".opencode"));
  writeFileSync(join(dir, ".opencode", "now.md"), "- 로그인 오류 메시지 번역 중\n- 끝나면 PR\n");
  const hooks = await ctx.ContextInjection({ directory: dir });
  const b = blockOf(await inject(hooks));
  ok(b.includes("- 지금 하는 일 (.opencode/now.md):\n  - 로그인 오류 메시지 번역 중\n  - 끝나면 PR"), "now.md 내용을 들여써서 넣는다", b);
  writeFileSync(join(dir, ".opencode", "now.md"), "가".repeat(2000));
  const long = blockOf(await inject(hooks));
  ok(long.includes("가".repeat(800) + "\n  (이하 생략)") && !long.includes("가".repeat(801)), "800자를 넘으면 자르고 (이하 생략)", String(long.length));
  writeFileSync(join(dir, ".opencode", "now.md"), "  \n\n");
  ok(!blockOf(await inject(hooks)).includes("지금 하는 일"), "내용이 비어 있으면 뺀다");
  writeFileSync(join(dir, "todo.txt"), "- 다른 파일\n");
  process.env.CONTEXT_NOW_FILE = "todo.txt";
  const other = blockOf(await inject(hooks));
  delete process.env.CONTEXT_NOW_FILE;
  ok(other.includes("(todo.txt):\n  - 다른 파일"), "CONTEXT_NOW_FILE 로 다른 파일을 가리킬 수 있다", other);
}

// ---- 어떤 경우에도 throw 하지 않는다
{
  const dir = repo("robust");
  const hooks = await ctx.ContextInjection({ directory: dir });
  const h = hooks["experimental.chat.system.transform"];
  let threw = null;
  try {
    await h(undefined, { system: [] });
    await h({}, undefined);
    await h({}, {});
    await h({}, { system: "not-array" });
    const nogitDir = repo("nogit");
    const savedPath = process.env.PATH;
    process.env.PATH = "";
    const noGit = { system: [] };
    await (await ctx.ContextInjection({ directory: nogitDir }))["experimental.chat.system.transform"]({}, noGit);
    process.env.PATH = savedPath;
    ok(noGit.system.length === 1 && noGit.system[0].includes("- 오늘:") && !noGit.system[0].includes("git 브랜치"), "git 을 실행할 수 없어도 날짜 블록은 나온다", JSON.stringify(noGit));
    const missing = await ctx.ContextInjection({ directory: join(tmp, "does-not-exist") });
    await h.call(null, {}, { system: [] });
    const out = { system: [] };
    await missing["experimental.chat.system.transform"]({}, out);
    ok(out.system.length === 1, "작업 폴더가 없어도 throw 하지 않는다");
  } catch (e) { threw = e; }
  ok(threw === null, "이상한 입력/환경에서 throw 하지 않는다", String(threw));
}

// ---- bash-reminder (tool.definition)
{
  const hooks = await rem.BashReminder();
  const hook = hooks["tool.definition"];
  const original = "Executes bash commands.";
  const o = { description: original, parameters: { type: "object", marker: 1 } };
  await hook({ toolID: "bash" }, o);
  ok(o.description.startsWith(original + "\n\n프로젝트 규칙: 명령은 한 줄로") && o.parameters.marker === 1, "bash 설명 끝에 규칙을 붙이고 원래 설명/파라미터는 그대로");
  const e = { description: original, parameters: {} };
  await hook({ toolID: "edit" }, e);
  ok(e.description === original, "다른 도구는 건드리지 않는다");
  const again = { description: original, parameters: {} };
  await hook({ toolID: "bash" }, again);
  ok(again.description === o.description && (again.description.match(/프로젝트 규칙/g) || []).length === 1, "새 정의마다 한 번만 붙는다 (누적되지 않음)");
  process.env.BASH_REMINDER = "DEMO-LINE";
  const c = { description: "d", parameters: {} };
  await hook({ toolID: "bash" }, c);
  delete process.env.BASH_REMINDER;
  ok(c.description === "d\n\nDEMO-LINE", "BASH_REMINDER 로 문장을 바꾼다", c.description);
  let threw = null;
  try { await hook(undefined, {}); await hook({ toolID: "bash" }, undefined); await hook({ toolID: "bash" }, { description: 5 }); } catch (err) { threw = err; }
  ok(threw === null, "이상한 입력에서 throw 하지 않는다", String(threw));
}

rmSync(tmp, { recursive: true, force: true });
console.log(`context-injection: ${total} checks, ${failed} failed`);
process.exit(failed ? 1 : 0);
