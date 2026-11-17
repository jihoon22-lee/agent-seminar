// output-filter 의 tool.execute.after 훅을 직접 호출해 마스킹과 줄이기를 검증합니다. (Node 18+, 표준 라이브러리만)
//   node tests/filter.test.mjs
// 값은 모두 눈에 띄는 가짜입니다(demo-...). 진짜 토큰 모양은 쓰지 않습니다.
import { copyFileSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const tmp = mkdtempSync(join(tmpdir(), "output-filter-test-"));
copyFileSync(join(here, "..", ".opencode", "plugins", "output-filter.js"), join(tmp, "plugin.mjs"));
const mod = await import(pathToFileURL(join(tmp, "plugin.mjs")).href);
const hooks = await mod.OutputFilter({ directory: tmp });
const after = hooks["tool.execute.after"];

let failed = 0, total = 0;
const ok = (cond, label, extra = "") => { total++; if (!cond) { failed++; console.log("FAIL:", label, extra); } };

// 내장 도구 모양의 출력에 훅을 적용하고 output.output 을 돌려준다
async function run(text, tool = "bash", extra = {}) {
  const output = { title: "t", output: text, metadata: {}, ...extra };
  await after({ tool, sessionID: "s", callID: "c", args: {} }, output);
  return output;
}
const S1 = "demo-secret-value-123";

// ---- 마스킹: 바뀌어야 하는 것
const masked = [
  [`API_KEY=${S1}`, "API_KEY=***"],
  [`export DB_PASSWORD=${S1}`, "export DB_PASSWORD=***"],
  [`MY_SERVICE_TOKEN=${S1}`, "MY_SERVICE_TOKEN=***"],
  [`client_secret: ${S1}`, "client_secret: ***"],
  [`password = ${S1}`, "password = ***"],
  [`"api_key": "${S1}",`, `"api_key": "***",`],
  [`'secret_key':'${S1}'`, `'secret_key':'***'`],
  [`aws_access_key_id=${S1}`, "aws_access_key_id=***"],
  [`PRIVATE_KEY=${S1}`, "PRIVATE_KEY=***"],
  [`Authorization: Bearer ${S1}`, "Authorization: Bearer ***"],
  [`authorization: bearer ${S1}`, "authorization: bearer ***"],
  [`Authorization: Basic ${S1}`, "Authorization: Basic ***"],
  [`curl -H "Authorization: Bearer ${S1}" https://example.invalid/`, `curl -H "Authorization: Bearer ***" https://example.invalid/`],
  [`{"Authorization": "Bearer ${S1}"}`, `{"Authorization": "Bearer ***"}`],
  [`using Bearer ${S1} for the call`, "using Bearer *** for the call"],
  [`run --token ${S1} now`, "run --token *** now"],
  [`run --password=${S1}`, "run --password=***"],
  [`run --api-key ${S1}`, "run --api-key ***"],
  [`A=1\nGITHUB_TOKEN=${S1}\nB=2`, "A=1\nGITHUB_TOKEN=***\nB=2"],
  [`TOKEN=${S1}; SECRET=${S1}`, "TOKEN=***; SECRET=***"],
];
for (const [input, want] of masked) {
  const r = await run(input);
  ok(r.output === want, `마스킹: ${input}`, `-> ${JSON.stringify(r.output)}`);
  ok(!r.output.includes("demo-"), `원본 값이 남지 않음: ${input}`);
}

// ---- 마스킹: 바뀌면 안 되는 것
const untouched = [
  "hello world",
  "token count: 12",             // 값이 너무 짧음
  "password = $PASSWORD",         // 환경변수 참조
  "password: ${DB_PASSWORD}",     // 템플릿
  "password = <your-password>",   // 자리표시
  "def login(password: str, x):", // 코드의 타입 표기 (값 str 이 4자 미만)
  "TOKEN=",                       // 값 없음
  "API_KEY=***",                  // 이미 가려짐
  "Basic information about the app",   // 영어 단어 Basic
  "Bearer of bad news",           // 8자 미만 단어들
  "The secret of the garden",     // 구분자(=, :) 없음
  "git commit -m 'fix token refresh'",
];
for (const input of untouched) {
  const r = await run(input);
  ok(r.output === input, `그대로 둠: ${input}`, `-> ${JSON.stringify(r.output)}`);
}
{
  // 알려진 한계(오탐): 이름에 TOKEN 이 들어 있으면 값이 비밀이 아니어도 가린다
  const r = await run("max_tokens=1024");
  ok(r.output === "max_tokens=***", "알려진 한계: max_tokens=1024 도 가려진다", r.output);
  // 알려진 한계(오탐): 소스 코드의 `password: str):` 처럼 값 뒤에 닫는 괄호가 붙은 4자 이상 토큰
  const c = await run("def login(password: str):");
  ok(c.output === "def login(password: ***", "알려진 한계: 타입 표기 뒤 `str):` 도 가려진다", c.output);
}

// ---- 여러 줄, 멱등성, 다른 키 보존
{
  const r = await run(`name=demo\nDB_PASSWORD=${S1}\nmode=dev\n`);
  ok(r.output === "name=demo\nDB_PASSWORD=***\nmode=dev\n", "여러 줄 중 비밀 줄만 바뀐다", r.output);
  const again = await run(r.output);
  ok(again.output === r.output, "두 번 적용해도 같다(멱등)");
}

// ---- 어떤 도구에서도 마스킹 (read, grep, 임의 이름)
for (const tool of ["read", "grep", "glob", "webfetch", "custom_tool"]) {
  const r = await run(`API_KEY=${S1}`, tool);
  ok(r.output === "API_KEY=***", `마스킹은 모든 도구에 적용: ${tool}`);
}

// ---- 줄이기: bash 만 (그리고 MCP)
const lines = (n) => Array.from({ length: n }, (_, i) => `line ${i + 1}`).join("\n");
{
  const r = await run(lines(100));
  ok(r.output === lines(100), "100줄은 그대로 (경계)");
  const big = await run(lines(101));
  const out = big.output.split("\n");
  ok(out.length === 81, "101줄 -> 앞 40 + 표시 1 + 뒤 40 = 81줄", String(out.length));
  ok(out[0] === "line 1" && out[39] === "line 40", "앞 40줄 보존");
  ok(out[40] === "... (21줄 생략) ...", "생략 표시에 생략한 줄 수", out[40]);
  ok(out[41] === "line 62" && out[80] === "line 101", "뒤 40줄 보존");
  const huge = await run(lines(5000));
  ok(huge.output.includes("... (4920줄 생략) ..."), "5000줄 -> 4920줄 생략", huge.output.split("\n")[40]);
  ok(huge.output.length < 1000, "크기가 크게 줄어든다", String(huge.output.length));
  const rd = await run(lines(5000), "read");
  ok(rd.output === lines(5000), "read 의 출력은 줄이지 않는다 (read 자체에 쪽 나누기가 있음)");
  const gr = await run(lines(5000), "grep");
  ok(gr.output === lines(5000), "grep 의 출력도 줄이지 않는다");
  const nl = await run(lines(500) + "\n");
  ok(nl.output.endsWith("line 500\n") && nl.output.includes("... (420줄 생략) ..."), "끝의 줄바꿈은 줄 수에 넣지 않고 그대로 보존", nl.output.slice(-30));
  const one = await run("x".repeat(50000));
  ok(one.output.includes("... (30000자 생략) ...") && one.output.length < 21000, "한 줄짜리 거대 출력은 글자 단위로 자른다", `${one.output.length}`);
}
{
  // 비밀이 생략 구간에 있어도, 경계에 걸려도 새지 않는다 (마스킹을 먼저 한다)
  const body = [...Array.from({ length: 70 }, (_, i) => `row ${i}`), `PASSWORD=${S1}`, ...Array.from({ length: 70 }, (_, i) => `row ${i + 100}`)].join("\n");
  const r = await run(body);
  ok(!r.output.includes("demo-"), "긴 출력에서도 값이 남지 않음");
  const head = Array.from({ length: 39 }, (_, i) => `row ${i}`);
  const edge = await run([...head, `PASSWORD=${S1}`, ...Array.from({ length: 100 }, (_, i) => `r${i}`)].join("\n"));
  ok(edge.output.includes("PASSWORD=***") && !edge.output.includes("demo-"), "앞 구간 마지막 줄의 비밀도 가려져서 남는다");
}

// ---- 환경변수로 기준 바꾸기
{
  process.env.OUTPUT_FILTER_MAX_LINES = "10"; process.env.OUTPUT_FILTER_HEAD = "2"; process.env.OUTPUT_FILTER_TAIL = "3";
  const r = await run(lines(20));
  delete process.env.OUTPUT_FILTER_MAX_LINES; delete process.env.OUTPUT_FILTER_HEAD; delete process.env.OUTPUT_FILTER_TAIL;
  ok(r.output === "line 1\nline 2\n... (15줄 생략) ...\nline 18\nline 19\nline 20", "OUTPUT_FILTER_* 로 기준 변경", r.output);
}

// ---- MCP 모양: { content: [{ type, text }] } (output.output, title, metadata 없음)
{
  const output = { content: [{ type: "text", text: `DB_PASSWORD=${S1}\nmode=dev` }, { type: "image", data: "AAAA" }] };
  await after({ tool: "cfg_show_config", sessionID: "s", callID: "c", args: {} }, output);
  ok(output.content[0].text === "DB_PASSWORD=***\nmode=dev", "MCP content[].text 를 가린다", JSON.stringify(output));
  ok(output.content[1].data === "AAAA", "text 가 아닌 항목은 건드리지 않는다");
  ok(!("output" in output) && !("metadata" in output), "없던 키를 만들지 않는다");
  const long = { content: [{ type: "text", text: lines(300) }] };
  await after({ tool: "cfg_dump", sessionID: "s", callID: "c", args: {} }, long);
  ok(long.content[0].text.includes("(220줄 생략)"), "MCP 도구의 긴 출력도 줄인다", long.content[0].text.slice(0, 80));
}

// ---- metadata 사본 (bash: output, read: preview, edit: diff/filediff)
{
  const r = await run(`API_KEY=${S1}\n`, "bash", { metadata: { output: `API_KEY=${S1}\n`, exit: 0, truncated: false } });
  ok(r.metadata.output === "API_KEY=***\n" && r.metadata.exit === 0 && r.metadata.truncated === false, "metadata.output 사본도 가리고 숫자/불리언은 그대로", JSON.stringify(r.metadata));
  const e = await run("Edit applied successfully.", "edit", { metadata: { diff: `-x\n+API_KEY=${S1}`, filediff: { file: "/a", patch: `+TOKEN=${S1}`, additions: 1, deletions: 0 }, list: [`SECRET=${S1}`] } });
  ok(!JSON.stringify(e.metadata).includes("demo-") && e.metadata.filediff.additions === 1 && e.metadata.list[0] === "SECRET=***", "중첩된 metadata 의 문자열도 가린다", JSON.stringify(e.metadata));
  const orig = { output: `API_KEY=${S1}` };
  process.env.OUTPUT_FILTER_METADATA = "0";
  const o = await run("x", "bash", { metadata: orig });
  delete process.env.OUTPUT_FILTER_METADATA;
  ok(o.metadata === orig && orig.output.includes("demo-"), "OUTPUT_FILTER_METADATA=0 이면 metadata 를 건드리지 않음");
  const t = await run("ok", "bash", { title: `echo API_KEY=${S1}` });
  ok(t.title === "echo API_KEY=***", "title 도 가린다", t.title);
}

// ---- 이상한 입력에서 throw 하지 않는다
{
  let threw = null;
  try {
    await after({ tool: "bash" }, undefined);
    await after({ tool: "bash" }, null);
    await after({ tool: "bash" }, { output: 42 });
    await after({ tool: "bash" }, { output: null, metadata: null });
    await after({ tool: "x" }, { content: [null, { type: "text" }, { type: "text", text: 5 }] });
    await after(undefined, { output: "x" });
  } catch (e) { threw = e; }
  ok(threw === null, "이상한 입력에서도 throw 하지 않는다", String(threw));
}

// ---- 로그에는 개수만 있고 값은 없다
{
  const log = readFileSync(join(tmp, "logs", "output-filter.log"), "utf8");
  ok(/tool=bash masked=1/.test(log) && /shortened=101줄 -> 81줄/.test(log), "로그에 도구와 개수가 남는다", log.slice(0, 300));
  ok(!log.includes("demo-"), "로그에 비밀 값이 없다");
}

rmSync(tmp, { recursive: true, force: true });
console.log(`output-filter: ${total} checks, ${failed} failed`);
process.exit(failed ? 1 : 0);
