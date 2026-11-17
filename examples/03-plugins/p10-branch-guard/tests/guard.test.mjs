// branch-guard 의 tool.execute.before 훅을 임시 git 저장소로 검증합니다. (Node 18+, git 필요)
//   node tests/guard.test.mjs
// 명령을 실행하지 않고 훅에 문자열만 넘깁니다. git 은 임시 저장소를 만들 때와 브랜치를 물을 때만 실행됩니다.
import { execFileSync } from "node:child_process";
import { copyFileSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const tmp = mkdtempSync(join(tmpdir(), "branch-guard-test-"));
copyFileSync(join(here, "..", ".opencode", "plugins", "branch-guard.js"), join(tmp, "plugin.mjs"));
const mod = await import(pathToFileURL(join(tmp, "plugin.mjs")).href);

const identity = { GIT_AUTHOR_NAME: "t", GIT_AUTHOR_EMAIL: "t@example.invalid", GIT_COMMITTER_NAME: "t", GIT_COMMITTER_EMAIL: "t@example.invalid" };
const git = (cwd, ...args) => execFileSync("git", args, { cwd, env: { ...process.env, ...identity }, stdio: "pipe" }).toString().trim();

// ws/ (git 저장소 아님) 안에: main(main 브랜치) feat(feat/x 브랜치) det(detached) rel(release/1.0) 네 저장소
const ws = join(tmp, "ws");
mkdirSync(ws);
function repo(name, branch, commit = true) {
  const dir = join(ws, name);
  mkdirSync(dir);
  git(dir, "init", "-q", "-b", branch);
  if (commit) { writeFileSync(join(dir, "f.txt"), "x"); git(dir, "add", "."); git(dir, "commit", "-q", "-m", "init"); }
  return dir;
}
const mainRepo = repo("main", "main");
const featRepo = repo("feat", "main"); git(featRepo, "switch", "-q", "-c", "feat/x");
const detRepo = repo("det", "main"); git(detRepo, "checkout", "-q", "--detach");
const relRepo = repo("rel", "release/1.0");
const unborn = repo("unborn", "master", false); // 커밋이 아직 없는 저장소의 첫 커밋
const plain = join(ws, "plain"); mkdirSync(plain);

let failed = 0, total = 0;

// 차단되면 규칙 id, 통과하면 null
async function verdict(command, dir = mainRepo, extra = {}) {
  const hooks = await mod.BranchGuard({ directory: dir });
  try {
    await hooks["tool.execute.before"]({ tool: extra.tool ?? "bash", sessionID: "s", callID: "c" }, { args: { command, ...(extra.args ?? {}) } });
    return null;
  } catch (e) {
    const m = /^\[branch-guard:([\w-]+)\]/.exec(String(e.message));
    return m ? m[1] : `other-error: ${e.message}`;
  }
}
async function expect(command, dir, want, label) {
  total++;
  const got = await verdict(command, dir);
  if (got !== want) { failed++; console.log(`FAIL: ${label ?? command}\n   기대=${want} 실제=${got}  (폴더 ${dir.split(/[\\/]/).pop()})`); }
}
const BLOCK = "protected-branch";

// ---- 기본: 브랜치에 따라 달라진다 (같은 명령, 다른 폴더)
await expect("git commit -m x", mainRepo, BLOCK);
await expect("git commit -m x", featRepo, null);
await expect("git commit -m x", relRepo, null);
await expect("git commit -m x", plain, null, "git 저장소가 아니면 허용");
await expect("git commit -m x", detRepo, null, "detached HEAD 면 허용");
await expect("git commit -m x", unborn, BLOCK, "첫 커밋 전의 master 도 보호 대상");
await expect("git commit --amend --no-edit", mainRepo, BLOCK);
await expect("git commit -am 'fix: a'", mainRepo, BLOCK);

// ---- push
await expect("git push", mainRepo, "push-to-protected");
await expect("git push origin", mainRepo, "push-to-protected");
await expect("git push origin main", featRepo, "push-to-protected", "feature 브랜치에서 main 으로 push");
await expect("git push -u origin HEAD", mainRepo, "push-to-protected");
await expect("git push -u origin HEAD", featRepo, null);
await expect("git push origin HEAD:main", featRepo, "push-to-protected");
await expect("git push origin feat/x:refs/heads/main", featRepo, "push-to-protected");
await expect("git push origin +feat/x:master", featRepo, "push-to-protected");
await expect("git push origin :main", featRepo, "push-to-protected", "원격 main 삭제");
await expect("git push", featRepo, null);
await expect("git push -u origin feat/x", featRepo, null);
await expect("git push origin feat/x", mainRepo, null, "main 에 있어도 다른 브랜치를 명시해 올리는 push 는 허용");
await expect("git push --force-with-lease origin feat/x", featRepo, null);
await expect("git push --all", featRepo, "push-to-protected");
await expect("git push --mirror origin", featRepo, "push-to-protected");
await expect("git push --tags", mainRepo, null, "태그만 올리는 push");
await expect("git push --dry-run", mainRepo, null);
await expect("git push -n origin main", mainRepo, null);
await expect("git push", plain, null);
await expect("git push", detRepo, null);
await expect("git push -o ci.skip origin feat/x", mainRepo, null, "-o 값이 refspec 으로 오해되지 않음");

// ---- gh pr
await expect("gh pr create --draft --title x --body y", featRepo, "draft-pr");
await expect("gh pr create --title x --draft", plain, "draft-pr", "브랜치와 상관없이 막는다");
await expect("gh pr create -d -t x", featRepo, "draft-pr");
await expect("gh pr create --draft=true", featRepo, "draft-pr");
await expect("gh pr ready --undo", featRepo, "draft-pr");
await expect("gh.exe pr create --draft", featRepo, "draft-pr");
await expect("gh pr create --title x --body y", featRepo, null, "준비된 PR 은 허용");
await expect("gh pr create --draft=false", featRepo, null);
await expect("gh pr create --fill", mainRepo, null, "PR 생성 자체는 브랜치를 보지 않는다");
await expect("gh pr ready 12", featRepo, null);
await expect("gh pr view 12 --json isDraft", featRepo, null);
await expect("gh pr list --draft", featRepo, null);

// ---- 복합 명령 (bash)
await expect("cd main && git commit -m x", ws, BLOCK, "cd 후 main 저장소");
await expect("cd feat && git commit -m x", ws, null, "cd 후 feature 저장소");
await expect("cd main; cd ../feat; git commit -m x", ws, null, "상대 경로 cd 를 순서대로 따라감");
await expect("cd feat; cd ../main; git commit -m x", ws, BLOCK);
await expect("cd feat && cd .. && git commit -m x", ws, null, "cd .. 로 저장소 밖으로 나오면 허용");
await expect("git add . ; git commit -m x", mainRepo, BLOCK);
await expect("git add . && git commit -m x && git push", mainRepo, BLOCK);
await expect("git add . && git commit -m x && git push", featRepo, null);
await expect("git diff --quiet || git commit -am x", mainRepo, BLOCK);
await expect("git status | cat; git commit -m x", mainRepo, BLOCK);
await expect("git -C main commit -m x", ws, BLOCK);
await expect("git -C feat commit -m x", ws, null);
await expect("git -C ../feat commit -m x", mainRepo, null);
await expect("git -c user.name=a -c user.email=b commit -m x", mainRepo, BLOCK);
await expect("git --no-pager commit -m x", mainRepo, BLOCK);
await expect("FOO=1 git commit -m x", mainRepo, BLOCK);
await expect("sudo git commit -m x", mainRepo, BLOCK);
await expect("sudo -u root git commit -m x", mainRepo, BLOCK);
await expect("if true; then git commit -m x; fi", mainRepo, BLOCK);
await expect("(git commit -m x)", mainRepo, BLOCK);
await expect("echo $(git commit -m x)", mainRepo, BLOCK);
await expect('echo "$(git commit -m x)"', mainRepo, BLOCK);
await expect("echo `git commit -m x`", mainRepo, BLOCK);
await expect("bash -c 'git commit -m x'", mainRepo, BLOCK);
await expect('bash -lc "cd feat && git commit -m x"'.replace("-lc", "-c"), ws, null, "bash -c 안의 cd 도 따라감");
await expect('sh -c "git commit -m x"', mainRepo, BLOCK);
await expect('eval "git commit -m x"', mainRepo, BLOCK);
await expect("git commit -m x\ngit push", mainRepo, BLOCK);
await expect("git commit -m x &\n", mainRepo, BLOCK);
await expect("true && git push origin HEAD", mainRepo, "push-to-protected");
await expect("git commit -m \"$(cat <<'EOF'\nfix: 메시지\n\nEOF\n)\"", mainRepo, BLOCK, "heredoc 메시지로 커밋하는 흔한 형태");
await expect("git commit -m \"$(cat <<'EOF'\nfix: 메시지\nEOF\n)\"", featRepo, null);

// ---- PowerShell / Windows 형태
await expect("git.exe commit -m x", mainRepo, BLOCK);
await expect('& git commit -m "x"', mainRepo, BLOCK);
await expect('& "C:\\Program Files\\Git\\bin\\git.exe" commit -m x', mainRepo, BLOCK);
await expect("Set-Location main; git commit -m x", ws, BLOCK);
await expect("Set-Location -Path feat; git commit -m x", ws, null);
await expect("sl feat ; git commit -m x", ws, null);
await expect("cd main ; if ($?) { git commit -m x }", ws, BLOCK);
await expect("git add -A; if ($LASTEXITCODE -eq 0) { git commit -m 'x' }", mainRepo, BLOCK);
await expect("git add .\r\ngit commit -m x", mainRepo, BLOCK);
await expect('powershell -Command "git commit -m x"', mainRepo, BLOCK);
await expect('pwsh -c "Set-Location feat; git commit -m x"', ws, null);
await expect("Invoke-Expression 'git commit -m x'", mainRepo, BLOCK);
await expect("git commit -m x; gh pr create --draft", featRepo, "draft-pr");

// ---- 막으면 안 되는 것: 따옴표/주석/heredoc 안, 무해한 형태, 다른 명령
await expect('echo "git commit -m x"', mainRepo, null);
await expect("echo 'git push origin main'", mainRepo, null);
await expect("git status && echo 'git commit' > note.txt", mainRepo, null);
await expect('git commit -m "fix: a; git push"', featRepo, null);
await expect("grep -r 'git commit' docs/", mainRepo, null);
await expect("printf '%s' \"git commit\" > f", mainRepo, null);
await expect("cat <<'EOF' > notes.md\ngit commit -m x\ngit push\nEOF", mainRepo, null, "heredoc 본문은 명령이 아님");
await expect("cat <<-EOF\n\tgit commit\n\tEOF\nls", mainRepo, null);
await expect("ls # git commit", mainRepo, null);
await expect("git commit --help", mainRepo, null);
await expect("git commit -h", mainRepo, null);
await expect("git commit --dry-run", mainRepo, null);
await expect("git commit-graph write", mainRepo, null);
await expect("git commit-tree HEAD^{tree}", mainRepo, null);
await expect("git status", mainRepo, null);
await expect("git log --oneline -5", mainRepo, null);
await expect("git diff && git add -A", mainRepo, null);
await expect("git switch -c feat/new", mainRepo, null);
await expect("git config alias.ci commit", mainRepo, null);
await expect("git pull", mainRepo, null);
await expect("git push --help", mainRepo, null);
await expect("echo hello", mainRepo, null);
await expect("", mainRepo, null);

// ---- 알려진 한계 (README 의 "주의할 점"): 막지 못하는 것을 일부러 허용으로 고정해 둔다
await expect("git merge feat/x", mainRepo, null, "한계: merge 도 커밋을 만들지만 보지 않음");
await expect("git cherry-pick abc123", mainRepo, null, "한계: cherry-pick");
await expect("git ci -m x", mainRepo, null, "한계: git 별칭");
await expect("make release", mainRepo, null, "한계: 스크립트 안의 git");
await expect('cd "$DIR" && git commit -m x', ws, null, "한계: 변수가 든 경로는 풀지 못해 허용");
await expect("(cd ../feat); git commit -m x", mainRepo, null, "한계: 서브셸의 cd 가 바깥으로 샌다");
await expect('git commit -m "--dry-run"', mainRepo, null, "한계: 옵션 이름과 같은 메시지 값");
await expect("git push", relRepo, null, "한계: release/1.0 는 기본 보호 목록에 없다");

// ---- 환경: 판단할 수 없는 상황은 모두 허용하고 기록 (로그는 플러그인의 directory 아래 logs/ 에 쌓인다)
{
  const logAt = (dir) => { try { return readFileSync(join(dir, "logs", "branch-guard.log"), "utf8"); } catch { return ""; } };
  const results = [
    ["not-a-repo", /ALLOW not-a-repo :: git commit/, plain, await verdict("git commit -m x", plain)],
    ["detached", /ALLOW detached :: git commit/, detRepo, await verdict("git commit -m x", detRepo)],
    ["dir-missing", /ALLOW dir-missing :: cd no-such-dir/, ws, await verdict("cd no-such-dir && git commit -m x", ws)],
  ];
  process.env.BRANCH_GUARD_GIT = "git-that-does-not-exist";
  results.push(["git-missing", /ALLOW git-missing :: git commit/, mainRepo, await verdict("git commit -m x", mainRepo)]);
  delete process.env.BRANCH_GUARD_GIT;
  for (const [label, needle, dir, got] of results) {
    total++;
    if (got !== null) { failed++; console.log(`FAIL: ${label} 이면 허용해야 함 (실제 ${got})`); }
    total++;
    if (!needle.test(logAt(dir))) { failed++; console.log(`FAIL: 허용 이유가 기록되지 않음: ${label}\n${logAt(dir)}`); }
  }
}

// ---- 차단 기록과 메시지
total++;
{
  rmSync(join(mainRepo, "logs"), { recursive: true, force: true });
  const hooks = await mod.BranchGuard({ directory: mainRepo });
  let msg = "";
  try { await hooks["tool.execute.before"]({ tool: "bash" }, { args: { command: "git commit -m x" } }); } catch (e) { msg = e.message; }
  const wanted = ["[branch-guard:protected-branch]", "'main'", "git switch -c <type>/<name>"];
  if (!wanted.every((w) => msg.includes(w))) { failed++; console.log("FAIL: 차단 메시지에 브랜치 이름과 대안이 없음:", msg); }
  let draft = "";
  try { await hooks["tool.execute.before"]({ tool: "bash" }, { args: { command: "gh pr create --draft" } }); } catch (e) { draft = e.message; }
  total++;
  if (!draft.includes("--draft`(`-d`) 없이") || !draft.includes("gh pr create --title")) { failed++; console.log("FAIL: draft 메시지에 대안이 없음:", draft); }
  total++;
  const blockedLog = readFileSync(join(mainRepo, "logs", "branch-guard.log"), "utf8");
  if (!/BLOCKED rule=protected-branch :: git commit -m x/.test(blockedLog) || !/BLOCKED rule=draft-pr/.test(blockedLog)) { failed++; console.log("FAIL: BLOCKED 기록 없음:", blockedLog); }
}

// ---- 설정/입력
{
  process.env.BRANCH_GUARD_PROTECTED = "main,release/1.0";
  total++; const a = await verdict("git commit -m x", relRepo);
  total++; const b = await verdict("git commit -m x", featRepo);
  delete process.env.BRANCH_GUARD_PROTECTED;
  if (a !== BLOCK) { failed++; console.log("FAIL: BRANCH_GUARD_PROTECTED 로 release/1.0 보호", a); }
  if (b !== null) { failed++; console.log("FAIL: 보호 목록 밖은 허용", b); }
  total++; const w = await verdict("git commit -m x", ws, { args: { workdir: "main" } });
  if (w !== BLOCK) { failed++; console.log("FAIL: bash 의 workdir 인자를 작업 폴더로 쓴다", w); }
  total++; const w2 = await verdict("git commit -m x", mainRepo, { args: { workdir: join(ws, "feat") } });
  if (w2 !== null) { failed++; console.log("FAIL: 절대 경로 workdir", w2); }
  total++; const t = await verdict("git commit -m x", mainRepo, { tool: "read" });
  if (t !== null) { failed++; console.log("FAIL: bash 가 아닌 도구는 보지 않는다", t); }
  total++;
  const hooks = await mod.BranchGuard({ directory: mainRepo });
  let threw = null;
  try {
    await hooks["tool.execute.before"]({ tool: "bash" }, { args: {} });
    await hooks["tool.execute.before"]({ tool: "bash" }, { args: { command: 42 } });
    await hooks["tool.execute.before"]({ tool: "bash" }, {});
    await hooks["tool.execute.before"]({ tool: "bash" }, { args: { command: "echo '미완성 따옴표 $( \"" } });
  } catch (e) { threw = e; }
  if (threw) { failed++; console.log("FAIL: 이상한 입력에서 throw", threw.message); }
}

rmSync(tmp, { recursive: true, force: true });
console.log(`branch-guard: ${total} cases, ${failed} failed`);
process.exit(failed ? 1 : 0);
