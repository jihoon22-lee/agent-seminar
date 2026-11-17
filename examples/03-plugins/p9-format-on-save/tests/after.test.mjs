// format-check 플러그인의 tool.execute.after 훅을 직접 호출해 검증합니다. (Node 18+, 표준 라이브러리만)
//   node tests/after.test.mjs
// 모델도 opencode 도 필요 없습니다. 임시 프로젝트 폴더를 만들어 scripts/ 를 복사해 씁니다.
import { copyFileSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const tmp = mkdtempSync(join(tmpdir(), "format-check-test-"));
copyFileSync(join(here, "..", ".opencode", "plugins", "format-check.js"), join(tmp, "plugin.mjs"));
const mod = await import(pathToFileURL(join(tmp, "plugin.mjs")).href);

let failed = 0;
let total = 0;
const ok = (cond, label) => { total++; if (!cond) { failed++; console.log("FAIL:", label); } };

function project(name, checkerSource) {
  const dir = join(tmp, name);
  mkdirSync(join(dir, "scripts"), { recursive: true });
  if (checkerSource === undefined) copyFileSync(join(here, "..", "scripts", "check_file.py"), join(dir, "scripts", "check_file.py"));
  else if (checkerSource !== null) writeFileSync(join(dir, "scripts", "check_file.py"), checkerSource);
  return dir;
}
const logOf = (dir) => { try { return readFileSync(join(dir, "logs", "format-check.log"), "utf8"); } catch { return ""; } };
const BASE = "Wrote file successfully.";

async function call(dir, tool, file, content) {
  if (content !== undefined) writeFileSync(join(dir, file), content);
  const hooks = await mod.FormatCheck({ directory: dir });
  const output = { title: file, output: BASE, metadata: { keep: 1 } };
  let threw = null;
  try {
    await hooks["tool.execute.after"]({ tool, sessionID: "s", callID: "c", args: { filePath: join(dir, file) } }, output);
  } catch (e) { threw = e; }
  return { output, threw };
}

const dir = project("main");
let r = await call(dir, "write", "a.py", "import os\nimport sys\nprint(sys.argv)\n");
ok(!r.threw, "문제가 있어도 throw 하지 않는다");
ok(r.output.output.startsWith(BASE + "\n\n[린트 결과] a.py: 문제 발견"), "원래 결과 뒤에 붙는다");
ok(r.output.output.includes("1행: 쓰지 않는 import: os"), "쓰지 않는 import 를 알려 준다");
ok(!r.output.output.includes("import: sys"), "쓰는 import 는 알리지 않는다");
ok(r.output.title === "a.py" && r.output.metadata.keep === 1, "title/metadata 는 건드리지 않는다");

r = await call(dir, "edit", "b.py", "import os\nprint(os.getcwd())\n");
ok(r.output.output.endsWith("[린트 결과] b.py: 문제 없음"), "깨끗하면 한 줄로 알린다 (edit 도 동작)");

r = await call(dir, "write", "c.py", "def f(:\n    pass\n");
ok(r.output.output.includes("1행: 문법 오류"), "파이썬 문법 오류");

r = await call(dir, "write", "d.py", "x = '" + "a".repeat(120) + "'\n");
ok(/1행: 126자 줄 \(100자 초과\)/.test(r.output.output), "긴 줄");

r = await call(dir, "write", "e.json", '{"a": 1,}');
ok(r.output.output.includes("JSON 문법 오류"), "깨진 JSON");
r = await call(dir, "write", "f.json", '{"a": 1}');
ok(r.output.output.endsWith("f.json: 문제 없음"), "정상 JSON");

for (const [tool, file] of [["read", "a.py"], ["bash", "a.py"], ["write", "notes.txt"], ["write", "README"]]) {
  writeFileSync(join(dir, file), "x");
  r = await call(dir, tool, file);
  ok(r.output.output === BASE, `대상이 아니면 그대로 둔다: ${tool} ${file}`);
}
r = await call(dir, "write", "missing.py");
ok(r.output.output === BASE && /SKIP missing\.py: 파일 없음/.test(logOf(dir)), "파일이 없으면 건너뛰고 기록");

// 많은 결과는 잘라서 붙인다 (줄 번호 20건 상한은 검사기에서, 글자 상한은 플러그인에서)
r = await call(dir, "write", "many.py", Array.from({ length: 30 }, (_, i) => `import m${i}`).join("\n") + "\n");
ok((r.output.output.match(/쓰지 않는 import/g) || []).length === 20, "검사기는 최대 20건만 출력");

// 이상한 입력
const hooks = await mod.FormatCheck({ directory: dir });
let t1 = null;
try {
  await hooks["tool.execute.after"]({ tool: "write", sessionID: "s", callID: "c", args: null }, { output: BASE });
  await hooks["tool.execute.after"]({ tool: "write", sessionID: "s", callID: "c", args: { filePath: join(dir, "a.py") } }, undefined);
  await hooks["tool.execute.after"]({ tool: "write", sessionID: "s", callID: "c", args: { filePath: join(dir, "a.py") } }, { output: null });
} catch (e) { t1 = e; }
ok(t1 === null, "args/output 가 이상해도 throw 하지 않는다");

// 상대 경로
writeFileSync(join(dir, "rel.py"), "import os\n");
const out2 = { output: BASE };
await hooks["tool.execute.after"]({ tool: "write", sessionID: "s", callID: "c", args: { filePath: "rel.py" } }, out2);
ok(out2.output.includes("rel.py: 문제 발견"), "상대 경로는 프로젝트 폴더 기준");

// 검사기가 없음
const noChecker = project("nochecker", null);
r = await call(noChecker, "write", "a.py", "import os\n");
ok(r.output.output === BASE && !r.threw && /SKIP a\.py: 검사기 없음/.test(logOf(noChecker)), "검사기가 없으면 편집은 그대로, 기록만");

// 검사기가 비정상 종료 (종료 코드 3)
const crash = project("crash", "import sys\nprint('boom', file=sys.stderr)\nsys.exit(3)\n");
r = await call(crash, "write", "a.py", "import os\n");
ok(r.output.output === BASE && !r.threw && /FAIL a\.py: 검사기 종료 코드=3 boom/.test(logOf(crash)), "검사기 실패(종료 코드 3)는 기록만");

// 검사기가 예외로 죽음 (파이썬은 종료 코드 1 로 끝나지만 stdout 이 비어 있다)
const traceback = project("traceback", "raise RuntimeError('x')\n");
r = await call(traceback, "write", "a.py", "import os\n");
ok(!r.threw, "검사기가 예외로 죽어도 throw 하지 않는다");
ok(r.output.output === BASE && /FAIL a\.py: 검사기 종료 코드=1 Traceback/.test(logOf(traceback)), "빈 출력의 종료 코드 1(예외로 죽음)은 '문제 발견'으로 붙이지 않고 기록만");

// 시간 초과
const slow = project("slow", "import time\ntime.sleep(30)\n");
process.env.P9_TIMEOUT_MS = "400";
const started = Date.now();
r = await call(slow, "write", "a.py", "import os\n");
delete process.env.P9_TIMEOUT_MS;
ok(r.output.output === BASE && /FAIL a\.py: 검사기 종료 코드=TIMEOUT/.test(logOf(slow)) && Date.now() - started < 5000, "시간 초과는 기록만 하고 빨리 돌아온다");

// 파이썬 실행 파일이 없음
process.env.P9_PYTHON = "python-that-does-not-exist";
r = await call(dir, "write", "g.py", "import os\n");
delete process.env.P9_PYTHON;
ok(r.output.output === BASE && !r.threw && /FAIL g\.py: 검사기 종료 코드=ENOENT/.test(logOf(dir)), "파이썬이 없으면 기록만");

rmSync(tmp, { recursive: true, force: true });
console.log(`format-check: ${total} checks, ${failed} failed`);
process.exit(failed ? 1 : 0);
