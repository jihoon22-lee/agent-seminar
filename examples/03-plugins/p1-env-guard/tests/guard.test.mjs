// 플러그인 훅을 직접 호출해 판정 규칙을 검증합니다. (Node 18+, 표준 라이브러리만)
//   node tests/guard.test.mjs
// 플러그인 파일을 임시 .mjs 로 복사해서 불러오므로 package.json 이 없어도 동작합니다.
import { copyFileSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const tmp = mkdtempSync(join(tmpdir(), "env-guard-test-"));
copyFileSync(join(here, "..", ".opencode", "plugins", "env-guard.js"), join(tmp, "plugin.mjs"));
const mod = await import(pathToFileURL(join(tmp, "plugin.mjs")).href);
const hooks = await mod.EnvGuard({ directory: tmp });
const before = hooks["tool.execute.before"];

async function blocked(tool, args) {
  try {
    await before({ tool, sessionID: "s", callID: "c" }, { args });
    return false;
  } catch (e) {
    return String(e.message).includes("[env-guard]");
  }
}

const mustBlock = [
  ["read", { filePath: "/work/app/.env" }],
  ["read", { filePath: ".env" }],
  ["read", { filePath: "C:\\work\\app\\.env" }],
  ["read", { filePath: "C:\\work\\app\\.ENV" }],
  ["read", { filePath: "/work/app/.env.local" }],
  ["read", { filePath: "/work/app/.env.production" }],
  ["edit", { filePath: "/work/app/.env", oldString: "a", newString: "b" }],
  ["write", { filePath: "C:\\work\\.env.staging", content: "X=1" }],
  ["grep", { pattern: "KEY", path: "/work/app/.env" }],
  ["grep", { pattern: "KEY", path: "/work/app", include: ".env*" }],
  ["apply_patch", { patchText: "*** Begin Patch\n*** Update File: app/.env\n@@\n-a\n+b\n*** End Patch" }],
  ["bash", { command: "cat .env" }],
  ["bash", { command: "cat ./.env.local" }],
  ["bash", { command: "type .env" }],
  ["bash", { command: "type C:\\work\\app\\.env" }],
  ["bash", { command: "Get-Content .env" }],
  ["bash", { command: 'Get-Content -Path "C:\\work\\app\\.env"' }],
  ["bash", { command: "gc .\\.env" }],
  ["bash", { command: "Select-String KEY .env" }],
  ["bash", { command: "findstr KEY .env" }],
  ["bash", { command: "findstr /i key C:\\work\\app\\.env" }],
  ["bash", { command: "Get-Content -Path:.env" }],
  ["bash", { command: "Get-Content -LiteralPath:.env.local" }],
  ["bash", { command: "Get-Content -Path:'C:\\work\\app\\.env'" }],
  ["bash", { command: "head -n 3 ~/app/.env" }],
  ["bash", { command: "cat .env*" }],
  ["bash", { command: "echo ok && cat .env" }],
  ["bash", { command: "cat .env.example .env" }],
  ["bash", { command: "sed -n 1p '.env'" }],
  ["bash", { command: "source .env" }],
  ["bash", { command: "cat < .env" }],
  ["bash", { command: "echo $(cat .env)" }],
  ["bash", { command: "python -c \"print(open('.env').read())\"" }],
  ["bash", { command: "node -e \"console.log(require('fs').readFileSync('.env','utf8'))\"" }],
  ["bash", { command: "[IO.File]::ReadAllText('.env')" }],
];

const mustAllow = [
  ["read", { filePath: "/work/app/.env.example" }],
  ["read", { filePath: "C:\\work\\app\\.env.example" }],
  ["read", { filePath: "/work/app/README.md" }],
  ["read", { filePath: "/work/app/src/environment.py" }],
  ["read", { filePath: "/work/app/.envrc" }],
  ["write", { filePath: "/work/app/.env.example", content: "A=" }],
  ["grep", { pattern: "env", path: "/work/app/src" }],
  ["bash", { command: "cat .env.example" }],
  ["bash", { command: "type .env.example" }],
  ["bash", { command: "Get-Content .env.example" }],
  ["bash", { command: "findstr KEY .env.example" }],
  ["bash", { command: "Get-Content -Path:.env.example" }],
  ["bash", { command: "findstr KEY src\\config.py" }],
  ["bash", { command: "echo .env >> .gitignore" }],
  ["bash", { command: "ls -la" }],
  ["bash", { command: "ls -a .env" }],
  ["bash", { command: "git status" }],
  ["bash", { command: "echo $env:APP_ENV" }],
  ["bash", { command: "python -c \"import os; print(os.environ.get('APP_ENV'))\"" }],
  ["bash", { command: "cat src/environment.py" }],
  ["bash", { command: "node -e \"console.log(process.env.NODE_ENV)\"" }],
  ["bash", { command: "cat README.md" }],
  ["bash", { command: "" }],
  ["todowrite", { todos: [] }],
];

let failed = 0;
for (const [tool, args] of mustBlock) {
  if (!(await blocked(tool, args))) { failed++; console.log("FAIL (should block):", tool, JSON.stringify(args)); }
}
for (const [tool, args] of mustAllow) {
  if (await blocked(tool, args)) { failed++; console.log("FAIL (should allow):", tool, JSON.stringify(args)); }
}
rmSync(tmp, { recursive: true, force: true });
console.log(`env-guard: ${mustBlock.length} block cases, ${mustAllow.length} allow cases, ${failed} failed`);
process.exit(failed ? 1 : 0);
