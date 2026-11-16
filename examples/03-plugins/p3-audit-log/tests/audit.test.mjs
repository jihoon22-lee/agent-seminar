// 감사 로그 플러그인을 훅 호출로 검증합니다. (Node 18+, 표준 라이브러리만)
//   node tests/audit.test.mjs [출력 폴더]
// 출력 폴더를 주면 그 안의 logs/audit.jsonl 을 남겨 두어, check.py 가 summarize_audit.py 시험에 재사용합니다.
import { copyFileSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const keepDir = process.argv[2];
const tmp = mkdtempSync(join(tmpdir(), "audit-log-test-"));
copyFileSync(join(here, "..", ".opencode", "plugins", "audit-log.js"), join(tmp, "plugin.mjs"));
const mod = await import(pathToFileURL(join(tmp, "plugin.mjs")).href);

let failed = 0;
const ok = (cond, label) => { if (!cond) { failed++; console.log("FAIL:", label); } };

const work = keepDir ?? join(tmp, "work");
mkdirSync(work, { recursive: true });
const hooks = await mod.AuditLog({ directory: work });
const after = hooks["tool.execute.after"];
const S = "ses_demo000001";
const SECRET_CONTENT = "TOP-SECRET-FILE-BODY-" + "x".repeat(500);

// opencode 1.19.5 에서 관찰한 입력 모양 그대로
await after({ tool: "read", sessionID: S, callID: "c1", args: { filePath: "C:\\work\\app\\src\\main.py" } },
  { title: "src\\main.py", output: "<path>...</path>\n" + SECRET_CONTENT, metadata: {} });
await after({ tool: "write", sessionID: S, callID: "c2", args: { filePath: "/work/app/notes.txt", content: SECRET_CONTENT } },
  { title: "notes.txt", output: "Wrote file successfully.", metadata: {} });
await after({ tool: "edit", sessionID: S, callID: "c3", args: { filePath: "/work/app/a.py", oldString: SECRET_CONTENT, newString: "new" } },
  { title: "a.py", output: "", metadata: {} });
await after({ tool: "bash", sessionID: S, callID: "c4", args: { command: "echo " + "y".repeat(600), description: "긴 명령" } },
  { title: "echo yyy", output: "yyy\n", metadata: {} });
await after({ tool: "bash", sessionID: S, callID: "c5", args: { command: "curl -H 'Authorization: Bearer abc123SECRETxyz' --password hunter2 https://x.test/?api_key=sk-demo-999 postgres://u:pw-demo@db/x" } },
  { title: "curl", output: "", metadata: {} });
await after({ tool: "grep", sessionID: S, callID: "c6", args: { pattern: "beta", path: "/work/app" } },
  { title: "beta", output: "Found 1 match", metadata: {} });
// 이상한 입력이 와도 예외가 밖으로 나가면 안 된다
await after({ tool: "weird", sessionID: S, callID: "c7", args: null }, undefined);

const file = join(work, "logs", "audit.jsonl");
const lines = readFileSync(file, "utf8").trim().split("\n").map((l) => JSON.parse(l));
ok(lines.length === 7, `기록 7줄 (실제 ${lines.length})`);
ok(lines[0].tool === "read" && lines[0].args.filePath === "C:\\work\\app\\src\\main.py", "경로는 그대로 남는다");
ok(lines[0].sessionID === S && /^\d{4}-\d\d-\d\dT/.test(lines[0].ts), "sessionID, ISO 시각");
ok(lines[0].outputLength > 500 && lines[0].title === "src\\main.py", "출력 길이와 제목");
const raw = readFileSync(file, "utf8");
ok(!raw.includes("TOP-SECRET-FILE-BODY"), "파일 내용이 로그에 없다");
ok(lines[1].args.content.startsWith("<") && lines[1].args.content.includes("생략"), "write.content 는 길이만");
ok(lines[2].args.oldString.includes("생략") && lines[2].args.newString.includes("생략"), "edit 본문은 길이만");
ok(lines[3].args.command.length < 340 && lines[3].args.command.includes("…(+"), "긴 명령은 잘린다");
ok(!/abc123SECRETxyz|hunter2|sk-demo-999|pw-demo/.test(raw), "비밀처럼 보이는 값은 가려진다");
ok(raw.includes("***"), "가림 표시");
ok(lines[5].args.pattern === "beta" && lines[5].args.path === "/work/app", "grep 인자");
ok(lines[6].tool === "weird" && lines[6].outputLength === 0, "비정상 입력도 기록하되 예외 없음");

// 로테이션: 아주 작은 한도로 다시 불러오면 이전 파일이 audit.<시각>.jsonl 로 옮겨진다
process.env.AUDIT_MAX_BYTES = "400";
process.env.AUDIT_KEEP = "2";
const work2 = join(tmp, "rot");
mkdirSync(work2, { recursive: true });
const hooks2 = await mod.AuditLog({ directory: work2 });
for (let i = 0; i < 40; i++) {
  await hooks2["tool.execute.after"]({ tool: "bash", sessionID: S, callID: "r" + i, args: { command: "echo " + i } }, { title: "echo", output: "x", metadata: {} });
}
const names = readdirSync(join(work2, "logs"));
const rotated = names.filter((n) => /^audit\.\d{8}-\d{6}.*\.jsonl$/.test(n));
ok(names.includes("audit.jsonl"), "현재 파일 유지");
ok(rotated.length >= 1 && rotated.length <= 2, `이전 파일은 최대 AUDIT_KEEP(2)개 (실제 ${rotated.length})`);

rmSync(tmp, { recursive: true, force: true }); // 출력 폴더(keepDir)는 지우지 않는다
console.log(`audit-log: ${failed} failed`);
process.exit(failed ? 1 : 0);
