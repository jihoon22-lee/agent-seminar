// shell.env 훅을 직접 호출해 주입 결과를 검증합니다. (Node 18+, 표준 라이브러리만)
//   node tests/shell-env.test.mjs
import { copyFileSync, existsSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, isAbsolute, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "..");
const tmp = mkdtempSync(join(tmpdir(), "shell-env-test-"));
copyFileSync(join(root, ".opencode", "plugins", "shell-env.js"), join(tmp, "plugin.mjs"));
const mod = await import(pathToFileURL(join(tmp, "plugin.mjs")).href);
const hooks = await mod.ShellEnv({ directory: root }); // 실제 예제 폴더를 directory 로 (certs/ 경로 확인용)

let failed = 0;
const ok = (cond, label) => { if (!cond) { failed++; console.log("FAIL:", label); } };

// opencode 가 넘기는 모양: output.env 는 빈 객체로 시작
const output = { env: {} };
await hooks["shell.env"]({ cwd: root, sessionID: "ses_x", callID: "call_x" }, output);
ok(output.env.APP_ENV === "dev", "APP_ENV=dev");
ok(output.env.HTTP_PROXY?.startsWith("http://") && output.env.HTTPS_PROXY === output.env.HTTP_PROXY, "프록시 값");
ok(output.env.NO_PROXY === "*", "NO_PROXY=*");
ok(isAbsolute(output.env.REQUESTS_CA_BUNDLE) && existsSync(output.env.REQUESTS_CA_BUNDLE), "REQUESTS_CA_BUNDLE 는 실제로 존재하는 절대 경로");
ok(output.env.REQUESTS_CA_BUNDLE.endsWith("demo-ca.pem"), "demo-ca.pem");

// 이미 값이 있어도 덮어쓰고, sessionID 가 없는 호출(예: 터미널)도 처리
const output2 = { env: { APP_ENV: "prod", KEEP: "1" } };
await hooks["shell.env"]({ cwd: root }, output2);
ok(output2.env.APP_ENV === "dev" && output2.env.KEEP === "1", "기존 키는 덮어쓰고 나머지는 보존");

ok(readFileSync(join(root, "logs", "shell-env.log"), "utf8").includes("injected APP_ENV"), "shell-env.log 기록");
rmSync(join(root, "logs"), { recursive: true, force: true });
rmSync(tmp, { recursive: true, force: true });
console.log(`shell-env: ${failed} failed`);
process.exit(failed ? 1 : 0);
