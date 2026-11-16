// 이벤트 훅을 직접 호출해 알림 로직을 검증합니다. (Node 18+, 표준 라이브러리만)
//   node tests/notify.test.mjs
// NOTIFY_DRY_RUN=1 이라 소리·토스트·notify-send 는 실행되지 않습니다.
import { copyFileSync, existsSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

process.env.NOTIFY_DRY_RUN = "1";
process.env.NOTIFY_LOG_ALL_EVENTS = "1";
const here = dirname(fileURLToPath(import.meta.url));
const tmp = mkdtempSync(join(tmpdir(), "notify-test-"));
copyFileSync(join(here, "..", ".opencode", "plugins", "notify-on-idle.js"), join(tmp, "plugin.mjs"));
const mod = await import(pathToFileURL(join(tmp, "plugin.mjs")).href);
const hooks = await mod.NotifyOnIdle({ directory: tmp });

let failed = 0;
const ok = (cond, label) => { if (!cond) { failed++; console.log("FAIL:", label); } };
const ev = (type, properties) => hooks.event({ event: { type, properties } });
const notifyLog = () => (existsSync(join(tmp, "logs", "notify.log")) ? readFileSync(join(tmp, "logs", "notify.log"), "utf8") : "");

// opencode 1.19.5 가 실제로 내보낸 모양
await ev("session.status", { sessionID: "ses_a", status: { type: "busy" } });
await ev("message.part.updated", { sessionID: "ses_a" });
ok(notifyLog() === "", "관련 없는 이벤트는 알리지 않는다");

await ev("permission.asked", { id: "per_1", sessionID: "ses_a", permission: "bash", patterns: ["echo hello"], metadata: { command: "echo hello" }, always: ["echo *"], tool: { messageID: "m", callID: "c" } });
ok(/\tpermission\tses_a\t.*bash.*echo hello/.test(notifyLog()), "permission.asked → 알림 기록");

await ev("session.status", { sessionID: "ses_a", status: { type: "idle" } });
ok(!notifyLog().includes("\tidle\t"), "session.status idle 은 무시(중복 방지)");
await ev("session.idle", { sessionID: "ses_a" });
ok(/\tidle\tses_a\t/.test(notifyLog()), "session.idle → 알림 기록");

await ev("session.idle", { sessionID: "ses_a" });
ok(notifyLog().split("\tidle\t").length === 2, "1.5초 안의 중복 idle 은 한 번만");

await ev("session.created", { sessionID: "ses_child", info: { id: "ses_child", parentID: "ses_a" } });
await ev("session.idle", { sessionID: "ses_child" });
ok(!notifyLog().includes("ses_child"), "서브에이전트 세션의 idle 은 알리지 않는다");

const events = readFileSync(join(tmp, "logs", "events.log"), "utf8");
ok(events.includes("\tsession.idle") && events.includes("\tpermission.asked") && events.includes("\tmessage.part.updated"), "NOTIFY_LOG_ALL_EVENTS=1 이면 모든 type 기록");

rmSync(tmp, { recursive: true, force: true });
console.log(`notify-on-idle: ${failed} failed`);
process.exit(failed ? 1 : 0);
