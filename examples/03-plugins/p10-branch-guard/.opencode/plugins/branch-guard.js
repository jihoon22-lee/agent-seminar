// p10-branch-guard: 저장소의 "현재 상태"(브랜치)를 보고 막는 가드.
//
//   1. 현재 브랜치가 main/master 일 때 `git commit`, `git push` 를 막는다.
//      (push 는 목적지가 main/master 인 경우도 막는다: `git push origin HEAD:main`)
//   2. `gh pr create --draft`(-d) 와 `gh pr ready --undo` 를 막는다. (팀 규칙의 예: 이 "초안 PR 금지"는 읽는 사람이 자기 팀 규칙으로 바꿔 쓰라고 넣은 예시이지 일반적인 권장이 아닙니다)
//
// P2(danger-guard)는 명령 문자열 모양만 봅니다. 이 가드는 명령이 "어디서" 실행되는지 보고 git 에게 직접 묻습니다.
//   - 브랜치는 셸 없이 인자 배열로 `git symbolic-ref -q --short HEAD` 를 실행해 알아냅니다(tool 의 작업 폴더 기준).
//   - git 저장소가 아니거나, HEAD 가 detached 이거나, git 이 실패하거나 없으면 **허용**하고 이유를 기록합니다.
//     (판단을 못 하는 상황에서 모든 명령을 막아 버리면 에이전트가 멈춥니다.)
//   - 명령 문자열은 따옴표를 아는 작은 분해기로 나눠 봅니다: `cd x && git commit`, `a ; git commit`, `$(git commit)`,
//     `bash -c "git commit"`, PowerShell 의 `git.exe`, `Set-Location x; git commit` 을 잡고,
//     따옴표 안 글자(`echo "git commit"`, `git commit -m "a; git push"`)와 heredoc 본문은 명령으로 보지 않습니다.
//     `git commit --help/-h/--dry-run`, `git push --dry-run/-n` 은 아무것도 바꾸지 않으므로 허용합니다.
//   - 한 명령 줄 안에서 브랜치가 바뀌는 경우도 따라갑니다: `git switch main && git commit`(막음), `git switch -c feat/y && git commit`(허용).
//     `git switch`/`git checkout` 의 목적지를 알 수 없으면(`git switch -`, 경로인지 브랜치인지 모를 `git checkout x`) 처음 브랜치 기준으로 판단하고 로그에 `NOTE` 를 남깁니다.
//
// 환경변수(모두 선택): BRANCH_GUARD_PROTECTED 보호할 브랜치(쉼표로 구분, 기본 "main,master")
//                      BRANCH_GUARD_GIT       git 실행 파일 이름(테스트용)
//
// 주의: 이 파일은 "플러그인 함수"만 export 합니다. 함수가 아닌 값을 export 하면 opencode 가 파일 전체를 건너뜁니다.
import { execFile } from "node:child_process";
import { appendFileSync, existsSync, mkdirSync } from "node:fs";
import { homedir } from "node:os";
import { join, resolve } from "node:path";

// ---------- 명령 문자열 분해 ----------

const KEYWORDS = new Set(["then", "do", "else", "elif", "if", "while", "until", "!", "{", "}"]);
const WRAPPERS = new Set(["sudo", "doas", "command", "builtin", "exec", "nohup", "nice", "time", "env"]);
const WRAPPER_ARG_FLAGS = new Set(["-u", "-g", "-U", "-C"]); // sudo -u 사용자 처럼 값을 하나 받는 옵션
const SHELLS = new Set(["bash", "sh", "zsh", "dash", "ash", "ksh", "fish", "pwsh", "powershell"]);
const PS_SHELLS = new Set(["pwsh", "powershell"]);
const CD_NAMES = new Set(["cd", "chdir", "pushd", "set-location", "sl"]);
const EVAL_NAMES = new Set(["eval", "iex", "invoke-expression"]);
const ENV_ASSIGN = /^[A-Za-z_][A-Za-z0-9_]*=/;
const HEREDOC = /<<(-?)\s*(?:'([^']*)'|"([^"]*)"|([A-Za-z_][\w-]*))/y;

// 큰따옴표 안의 $(...) 와 `...` 는 실제로 실행되므로 안쪽 문자열을 따로 꺼냅니다.
function substitutions(raw) {
  const found = [];
  for (let k = 0; k < raw.length; k++) {
    if (raw[k] === "\\") { k++; continue; }
    if (raw[k] === "$" && raw[k + 1] === "(") {
      let depth = 1, j = k + 2;
      while (j < raw.length && depth > 0) { if (raw[j] === "(") depth++; else if (raw[j] === ")") depth--; j++; }
      found.push(raw.slice(k + 2, depth === 0 ? j - 1 : j));
      k = j - 1;
    } else if (raw[k] === "`") {
      const j = raw.indexOf("`", k + 1);
      found.push(raw.slice(k + 1, j < 0 ? raw.length : j));
      if (j < 0) break;
      k = j;
    }
  }
  return found;
}

// 명령 문자열 → { commands: 단어 배열의 목록, nested: 안쪽 명령 문자열 목록 }
function tokenize(src) {
  const commands = [], nested = [], pending = [];
  let words = [], cur = "", has = false, i = 0;
  const pushWord = () => { if (has) words.push(cur); cur = ""; has = false; };
  const endCommand = () => { pushWord(); if (words.length) commands.push(words); words = []; };
  while (i < src.length) {
    const c = src[i];
    if (c === "'") {
      const j = src.indexOf("'", i + 1), end = j < 0 ? src.length : j;
      cur += src.slice(i + 1, end); has = true; i = end + 1;
    } else if (c === '"') {
      let j = i + 1, body = "";
      while (j < src.length && src[j] !== '"') {
        if (src[j] === "\\" && j + 1 < src.length && '"\\$`'.includes(src[j + 1])) { body += src[j + 1]; j += 2; }
        else { body += src[j]; j++; }
      }
      nested.push(...substitutions(src.slice(i + 1, j)));
      cur += body; has = true; i = j + 1;
    } else if (c === "\\") {
      const n = src[i + 1];
      if (n === "\n") i += 2;
      else if (n !== undefined && " \t'\"\;&|$<>()".includes(n)) { cur += n; has = true; i += 2; }
      else { cur += "\\"; has = true; i++; } // C:\work\x 같은 윈도 경로의 역슬래시는 그대로 둔다
    } else if (c === " " || c === "\t" || c === "\r") {
      pushWord(); i++;
    } else if (c === "\n") {
      endCommand(); i++;
      for (const { delim, strip } of pending.splice(0)) { // heredoc 본문은 명령이 아니다
        while (i < src.length) {
          let e = src.indexOf("\n", i); if (e < 0) e = src.length;
          let line = src.slice(i, e).replace(/\r$/, ""); if (strip) line = line.replace(/^\t+/, "");
          i = Math.min(e + 1, src.length);
          if (line === delim) break;
        }
      }
    } else if (c === ";" || c === "|" || c === "&" || c === "(" || c === ")" || c === "`") {
      endCommand(); i++;
    } else if (c === "$" && src[i + 1] === "(") {
      endCommand(); i += 2;
    } else if (c === "#" && !has) {
      while (i < src.length && src[i] !== "\n") i++;
    } else if (c === "<" && src[i + 1] === "<" && src[i + 2] !== "<") {
      HEREDOC.lastIndex = i;
      const m = HEREDOC.exec(src);
      if (m) { pending.push({ delim: m[2] ?? m[3] ?? m[4], strip: m[1] === "-" }); i += m[0].length; }
      else { cur += c; has = true; i++; }
    } else {
      cur += c; has = true; i++;
    }
  }
  endCommand();
  return { commands, nested };
}

const baseName = (word) => word.split(/[\\/]/).pop().toLowerCase().replace(/\.exe$/, "");

function nextCwd(cwd, words) {
  let target;
  for (let k = 1; k < words.length; k++) {
    const w = words[k];
    if (/^-(path|literalpath)$/i.test(w)) { target = words[k + 1]; break; }
    if (!w.startsWith("-") || w === "-") { target = w; break; }
  }
  if (target === undefined) return homedir();
  if (target === "-") return cwd; // 이전 폴더: 알 수 없으니 그대로 둔다
  if (target === "~") return homedir();
  if (target.startsWith("~/") || target.startsWith("~\\")) return resolve(homedir(), target.slice(2));
  return resolve(cwd, target);
}

// git 의 전역 옵션을 건너뛰고 { dir, sub, args } 를 돌려준다. (-C 경로는 cwd 에 반영)
function parseGit(cwd, rest) {
  let dir = cwd, k = 0;
  for (; k < rest.length; k++) {
    const w = rest[k];
    if (w === "-C") { if (rest[k + 1] !== undefined) dir = resolve(dir, rest[++k]); }
    else if (w === "-c" || w === "--git-dir" || w === "--work-tree" || w === "--namespace") k++;
    else if (w.startsWith("-")) continue;
    else break;
  }
  return { dir, sub: rest[k], args: rest.slice(k + 1) };
}

// 셸이 받은 "명령 문자열" 인자를 꺼낸다. 못 꺼내면 null.
//   bash -c / -lc / -ec "…"   cmd /c "…" (/d /s /k 도)   powershell -Command "…" / -c / -EncodedCommand <base64>
function shellPayload(name, args) {
  if (name === "cmd") {
    const at = args.findIndex((a) => /^\/[ck]$/i.test(a));
    return at >= 0 && args[at + 1] !== undefined ? args.slice(at + 1).join(" ") : null;
  }
  if (PS_SHELLS.has(name)) {
    const at = args.findIndex((a) => /^-(c|com|comm|comma|comman|command)$/i.test(a));
    if (at >= 0 && args[at + 1] !== undefined) return args.slice(at + 1).join(" ");
    const enc = args.findIndex((a) => /^-(e|ec|en|enc|enco|encod|encode|encoded|encodedc|encodedco|encodedcom|encodedcomm|encodedcomma|encodedcomman|encodedcommand)$/i.test(a));
    if (enc >= 0 && args[enc + 1] !== undefined) return Buffer.from(args[enc + 1], "base64").toString("utf16le");
    return null;
  }
  const at = args.findIndex((a) => /^-[A-Za-z]*c[A-Za-z]*$/.test(a)); // -c, -lc, -ec …
  return at >= 0 && args[at + 1] !== undefined ? args.slice(at + 1).join(" ") : null;
}

// git switch / git checkout 한 번이 가리키는 브랜치 변화. 못 알아내면 { kind: "unknown" }.
//   { kind: "branch", name }  이름이 정해진 브랜치(새로 만들거나 switch 로 가는 곳)
//   { kind: "detached" }      --detach
//   { kind: "maybe", name }   `git checkout x`: x 가 브랜치인지 경로인지는 실행 직전에 git 에게 물어 정한다
//   null                      브랜치가 바뀌지 않음(`git checkout -- file`, `git checkout HEAD`)
function switchChange(sub, args) {
  const takesValue = sub === "switch" ? ["-c", "-C", "--create", "--force-create", "--orphan"] : ["-b", "-B", "--orphan"];
  let created, detach = false, dashdash = false, firstPositional, track = false;
  for (let k = 0; k < args.length; k++) {
    const a = args[k];
    if (dashdash) continue;
    if (a === "--") { dashdash = true; continue; }
    if (takesValue.includes(a)) { created = args[k + 1]; k++; continue; }
    const attached = /^(-[cCbB])(.+)$/.exec(a); // -cname, -bname
    if (attached && takesValue.includes(attached[1])) { created = attached[2]; continue; }
    const eq = /^(--[a-z-]+)=(.*)$/.exec(a);
    if (eq && takesValue.includes(eq[1])) { created = eq[2]; continue; }
    if (a === "-d" || a === "--detach") { detach = true; continue; }
    if (a === "-t" || a === "--track" || a.startsWith("--track=")) { track = true; continue; }
    if (a === "-") { firstPositional ??= a; continue; }
    if (a.startsWith("-")) continue;
    firstPositional ??= a;
  }
  if (created !== undefined && created !== "") return { kind: "branch", name: created, created: true };
  if (created === "") return { kind: "unknown" };
  if (detach) return { kind: "detached" };
  if (dashdash || firstPositional === undefined) return null;
  const x = firstPositional;
  if (x === "-" || x.startsWith("@") || track || /[~^:{$`*?]/.test(x)) return { kind: "unknown" }; // 이전 브랜치, @{-1}, HEAD~1, 변수($)가 든 이름, 원격 추적 …
  if (x === "HEAD") return null;
  return sub === "switch" ? { kind: "branch", name: x } : { kind: "maybe", name: x };
}

// gh pr create 의 --draft / -d (합친 짧은 옵션 `-dt 제목`, `-fd` 포함) 를 찾는다.
// 값을 받는 짧은 옵션(a B b H l m p r T t)이 나오면 그 묶음의 나머지는 그 옵션의 값이다. (`-tdraft` 의 d 는 값의 글자)
const GH_VALUE_SHORT = new Set("aBbHlmprTt");
function ghDraft(args) {
  for (let k = 0; k < args.length; k++) {
    const a = args[k];
    if (a === "--draft" || /^--draft=(true|1|t|TRUE|True)$/.test(a)) return true;
    if (a.startsWith("--") || !a.startsWith("-") || a === "-") continue;
    for (let c = 1; c < a.length; c++) {
      const ch = a[c];
      if (ch === "d") { if (a[c + 1] === "=") { if (/^(true|1|t)$/i.test(a.slice(c + 2))) return true; } else return true; break; }
      if (GH_VALUE_SHORT.has(ch)) break;
    }
  }
  return false;
}

// 명령 문자열 → 검사할 일의 목록: { type: "commit" | "push" | "draft-pr" | "pr-undo-ready", cwd, ... }
function scan(src, startCwd, depth = 0, events = [], moves = new Map()) {
  if (depth > 4 || typeof src !== "string") return events;
  const { commands, nested } = tokenize(src);
  for (const inner of nested) scan(inner, startCwd, depth + 1, events, moves);
  let cwd = startCwd;
  for (const original of commands) {
    const w = original.slice();
    while (w.length) {
      const base = baseName(w[0]);
      if (ENV_ASSIGN.test(w[0]) || KEYWORDS.has(w[0])) w.shift();
      else if (WRAPPERS.has(base)) {
        w.shift();
        while (w.length && w[0].startsWith("-")) { const f = w.shift(); if (WRAPPER_ARG_FLAGS.has(f) && w.length) w.shift(); }
      } else break;
    }
    if (!w.length) continue;
    const name = baseName(w[0]);
    const args = w.slice(1);
    if (CD_NAMES.has(name)) cwd = nextCwd(cwd, w);
    else if (SHELLS.has(name) || name === "cmd") {
      const payload = shellPayload(name, args);
      if (payload !== null) scan(payload, cwd, depth + 1, events, moves);
    } else if (EVAL_NAMES.has(name)) scan(args.join(" "), cwd, depth + 1, events, moves);
    else if (name === "git") {
      const g = parseGit(cwd, args);
      const harmless = g.args.some((a) => ["--help", "-h", "--dry-run"].includes(a));
      const moved = () => (moves.get(g.dir) ?? []).slice(); // 이 명령 줄 안에서 이미 일어난 브랜치 변화
      if ((g.sub === "switch" || g.sub === "checkout") && !g.args.some((a) => ["--help", "-h"].includes(a))) {
        const change = switchChange(g.sub, g.args);
        if (change) moves.set(g.dir, [...moved(), change]);
      }
      if (g.sub === "commit" && !harmless) events.push({ type: "commit", cwd: g.dir, moves: moved() });
      if (g.sub === "push" && !g.args.some((a) => ["--help", "-h", "--dry-run", "-n"].includes(a))) {
        const positional = [];
        for (let k = 0; k < g.args.length; k++) {
          const a = g.args[k];
          if (["-o", "--push-option", "--repo", "--receive-pack", "--exec"].includes(a)) k++;
          else if (!a.startsWith("-")) positional.push(a);
        }
        events.push({
          type: "push", cwd: g.dir, moves: moved(), specs: positional.slice(1),
          all: g.args.some((a) => a === "--all" || a === "--mirror"), tags: g.args.includes("--tags"),
        });
      }
    } else if (name === "gh") {
      const rest = args.slice();
      while (rest.length && /^(-R|--repo)$/.test(rest[0])) rest.splice(0, 2); // gh -R 소유자/저장소 pr create
      if (rest[0] === "pr") {
        if ((rest[1] === "create" || rest[1] === "new") && ghDraft(rest.slice(2))) events.push({ type: "draft-pr" });
        if (rest[1] === "ready" && rest.includes("--undo")) events.push({ type: "pr-undo-ready" });
      }
    }
  }
  return events;
}

// ---------- git 에게 브랜치 묻기 (셸 없음) ----------

function runGit(gitBin, cwd, args) {
  return new Promise((done) => {
    execFile(gitBin, args, { cwd, timeout: 5000, windowsHide: true, env: { ...process.env, GIT_OPTIONAL_LOCKS: "0" } },
      (error, stdout, stderr) => done({
        code: error ? (error.killed ? "TIMEOUT" : error.code) : 0, stdout: String(stdout ?? "").trim(), stderr: String(stderr ?? "").trim(),
      }));
  });
}

export const BranchGuard = async ({ directory }) => {
  function log(line) {
    try {
      mkdirSync(join(directory, "logs"), { recursive: true });
      appendFileSync(join(directory, "logs", "branch-guard.log"), `${new Date().toISOString()} ${line}\n`, "utf8");
    } catch {
      // 로그를 못 남겨도 가드는 계속 동작합니다.
    }
  }

  // 브랜치 이름, 또는 판단 불가 이유를 돌려준다: { branch } | { skip: "not-a-repo" | "detached" | ... }
  async function currentBranch(cwd) {
    const gitBin = process.env.BRANCH_GUARD_GIT || "git";
    if (!existsSync(cwd)) return { skip: "dir-missing" };
    const r = await runGit(gitBin, cwd, ["symbolic-ref", "-q", "--short", "HEAD"]);
    if (r.code === 0 && r.stdout) return { branch: r.stdout };
    if (r.code === "ENOENT") return { skip: "git-missing" };
    if (r.code === "TIMEOUT") return { skip: "git-timeout" };
    if (r.code === 1 && !r.stderr) return { skip: "detached" }; // -q: 심볼릭 ref 가 아니면 조용히 종료 코드 1
    if (/not a git repository/i.test(r.stderr)) return { skip: "not-a-repo" };
    return { skip: `git-failed(code=${r.code}) ${r.stderr.slice(0, 120)}` };
  }

  log("branch-guard loaded");
  return {
    "tool.execute.before": async (input, output) => {
      if (input.tool !== "bash") return;
      const command = output.args?.command;
      if (typeof command !== "string") return;

      let events;
      try {
        const workdir = typeof output.args?.workdir === "string" && output.args.workdir ? resolve(directory, output.args.workdir) : directory;
        events = scan(command, workdir);
      } catch (err) {
        log(`ALLOW parse-error: ${String(err?.message ?? err).slice(0, 120)}`); // 분해기가 터져도 모든 명령을 막지 않는다
        return;
      }
      if (events.length === 0) return;

      const protectedBranches = (process.env.BRANCH_GUARD_PROTECTED || "main,master").split(",").map((s) => s.trim()).filter(Boolean);
      const isProtected = (name) => protectedBranches.includes(name);
      const cache = new Map();
      const branchOf = (cwd) => { if (!cache.has(cwd)) cache.set(cwd, currentBranch(cwd)); return cache.get(cwd); };
      let noted = false;
      // 이 명령 줄 안의 git switch/checkout 을 순서대로 반영한 "이 이벤트가 실행될 때의 브랜치".
      // 목적지를 알 수 없는 전환은 무시하고(= 명령 시작 때의 브랜치로 판단) 로그에 NOTE 를 한 번 남긴다.
      const branchFor = async (ev) => {
        let state = null, unknown = false;
        for (const m of ev.moves ?? []) {
          if (m.kind === "branch") state = { branch: m.name, switched: true };
          else if (m.kind === "detached") state = { skip: "detached-by-switch" };
          else if (m.kind === "maybe") {
            const isBranch = isProtected(m.name) || (existsSync(ev.cwd) && (await runGit(process.env.BRANCH_GUARD_GIT || "git", ev.cwd, ["show-ref", "--verify", "--quiet", `refs/heads/${m.name}`])).code === 0);
            if (isBranch) state = { branch: m.name, switched: true }; else unknown = true;
          } else unknown = true;
        }
        if (unknown && !noted) { noted = true; log(`NOTE switch-destination-unknown (judged by the branch before this command) :: ${short}`); }
        return state ?? branchOf(ev.cwd);
      };
      const short = String(command).replace(/\s+/g, " ").slice(0, 160);
      const deny = (id, message) => {
        log(`BLOCKED rule=${id} :: ${short}`);
        throw new Error(`[branch-guard:${id}] ${message}`);
      };
      const skipped = (why) => log(`ALLOW ${why} :: ${short}`);

      for (const ev of events) {
        if (ev.type === "draft-pr") {
          deny("draft-pr", "초안(draft) PR 은 만들지 않는 규칙입니다. `--draft`(`-d`) 없이 바로 리뷰할 수 있는 PR 로 여세요: gh pr create --title \"<제목>\" --body \"<설명>\". 아직 덜 끝났다면 PR 을 열지 말고 브랜치에서 더 작업하세요.");
        }
        if (ev.type === "pr-undo-ready") {
          deny("draft-pr", "PR 을 초안으로 되돌리는 `gh pr ready --undo` 는 쓰지 않는 규칙입니다. 수정이 더 필요하면 같은 브랜치에 커밋을 추가하세요.");
        }
        if (ev.type === "commit") {
          const b = await branchFor(ev);
          if (b.skip) { skipped(b.skip); continue; }
          if (isProtected(b.branch)) {
            deny("protected-branch", `${b.switched ? `이 명령은 먼저 '${b.branch}' 로 전환한 뒤 커밋합니다.` : `현재 브랜치가 '${b.branch}' 입니다.`} ${protectedBranches.join("/")} 에는 직접 커밋하지 않습니다. 먼저 새 브랜치를 만드세요: git switch -c <type>/<name> (예: git switch -c feat/login-form). 변경한 파일은 그대로 따라옵니다. 그다음 같은 커밋 명령을 다시 실행하세요.`);
          }
        }
        if (ev.type === "push") {
          if (ev.all) deny("push-to-protected", "git push --all / --mirror 는 보호된 브랜치까지 함께 올립니다. 작업 브랜치 이름을 지정해서 푸시하세요: git push -u origin <브랜치>");
          if (ev.tags && ev.specs.length === 0) continue; // 태그만 올리는 push 는 브랜치를 건드리지 않는다
          const targets = [];
          let needBranch = ev.specs.length === 0;
          for (const spec of ev.specs) {
            const dst = (spec.replace(/^\+/, "").split(":").pop() || "").replace(/^refs\/heads\//, "");
            if (dst === "HEAD" || dst === "@") needBranch = true; else targets.push(dst);
          }
          let current;
          if (needBranch) {
            const b = await branchFor(ev);
            if (b.skip) skipped(b.skip); else { current = b.branch; targets.push(b.branch); }
          }
          const hit = targets.find(isProtected);
          if (hit) {
            deny("push-to-protected", hit === current
              ? `${ev.moves?.length ? `이 명령은 먼저 '${hit}' 로 전환한 뒤 푸시합니다.` : `현재 브랜치가 '${hit}' 입니다.`} ${protectedBranches.join("/")} 로는 직접 푸시하지 않습니다. 작업 브랜치를 만들어(git switch -c <type>/<name>) 커밋한 뒤 그 브랜치를 푸시하고(git push -u origin <브랜치>), PR 로 합치세요.`
              : `'${hit}' 로 직접 푸시하는 명령입니다. 작업 브랜치를 푸시하고(git push -u origin <브랜치>) PR 로 합치세요.`);
          }
        }
      }
    },
  };
};
