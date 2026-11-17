// p9-format-on-save (Part B): write/edit 직후 검사기를 돌려 결과를 도구 결과 뒤에 붙이는 플러그인.
//
// 내장 `formatter` 는 파일을 고쳐 쓰기만 하고 모델에게 아무것도 알리지 않습니다.
// 이 플러그인은 tool.execute.after 에서 scripts/check_file.py 를 실행하고,
// 그 출력을 output.output 뒤에 붙여 모델이 다음 단계에서 바로 고치게 합니다.
//
// 실측(opencode 1.19.5): 이 훅이 불리는 시점에 내장 formatter 는 이미 끝나 있습니다(파일이 정렬된 상태로 읽힘).
//
// 튼튼하게 만든 점: 검사기가 없거나, 실패하거나, 시간 초과여도 편집은 그대로 두고 logs/format-check.log 에만 남깁니다.
// after 훅에서 throw 하지 않습니다. 실측: throw 하면 파일은 이미 써진 뒤인데도 모델은 "도구 실패"로 받습니다
// (자세한 내용은 README).
//
// 환경변수(모두 선택): P9_PYTHON 검사기를 돌릴 파이썬 실행 파일, P9_TIMEOUT_MS 제한 시간(기본 10000)
//
// 주의: 이 파일은 "플러그인 함수"만 export 합니다. 함수가 아닌 값을 export 하면 opencode 가 파일 전체를 건너뜁니다.
import { execFile } from "node:child_process";
import { appendFileSync, existsSync, mkdirSync } from "node:fs";
import { extname, isAbsolute, join, relative, resolve } from "node:path";

const TOOLS = new Set(["write", "edit"]);
const EXTENSIONS = new Set([".py", ".json"]);
const MAX_APPENDED = 2000; // 모델에게 붙이는 검사 결과의 최대 글자 수

function run(command, args, cwd, timeout) {
  return new Promise((done) => {
    execFile(
      command,
      args,
      { cwd, timeout, windowsHide: true, maxBuffer: 1 << 20, env: { ...process.env, PYTHONUTF8: "1" } },
      (error, stdout, stderr) => {
        done({
          // error.code 는 종료 코드(숫자) 또는 "ENOENT" 같은 문자열, 시간 초과/신호면 error.killed
          code: error ? (error.killed ? "TIMEOUT" : error.code) : 0,
          stdout: String(stdout ?? ""),
          stderr: String(stderr ?? ""),
        });
      },
    );
  });
}

export const FormatCheck = async ({ directory }) => {
  function log(line) {
    try {
      mkdirSync(join(directory, "logs"), { recursive: true });
      appendFileSync(join(directory, "logs", "format-check.log"), `${new Date().toISOString()} ${line}\n`, "utf8");
    } catch {
      // 로그를 못 남겨도 편집은 계속됩니다.
    }
  }

  log("format-check loaded");
  return {
    "tool.execute.after": async (input, output) => {
      try {
        if (!TOOLS.has(input.tool)) return;
        const rawPath = input.args?.filePath;
        if (typeof rawPath !== "string" || !EXTENSIONS.has(extname(rawPath).toLowerCase())) return;
        if (typeof output?.output !== "string") return;
        const file = isAbsolute(rawPath) ? rawPath : resolve(directory, rawPath);
        const checker = join(directory, "scripts", "check_file.py");
        const shown = relative(directory, file) || file;
        if (!existsSync(checker)) return log(`SKIP ${shown}: 검사기 없음 (${checker})`);
        if (!existsSync(file)) return log(`SKIP ${shown}: 파일 없음`);

        const timeout = Number(process.env.P9_TIMEOUT_MS) || 10000;
        const pythons = process.env.P9_PYTHON ? [process.env.P9_PYTHON] : ["python", "python3"];
        let result;
        for (const py of pythons) {
          result = await run(py, [checker, file], directory, timeout);
          if (result.code !== "ENOENT") break; // 그 이름의 파이썬이 없을 때만 다음 후보를 시도
        }
        // 종료 코드 1 인데 출력이 없으면 검사기가 예외로 죽은 것입니다(파이썬은 예외 때 1 로 끝남).
        if ((result.code !== 0 && result.code !== 1) || (result.code === 1 && !result.stdout.trim())) {
          return log(`FAIL ${shown}: 검사기 종료 코드=${result.code} ${result.stderr.trim().slice(0, 200)}`);
        }
        const findings = result.stdout.trim();
        if (result.code === 0) {
          output.output += `\n\n[린트 결과] ${shown}: 문제 없음`;
          return log(`OK ${shown}`);
        }
        const body = findings.length > MAX_APPENDED ? `${findings.slice(0, MAX_APPENDED)}\n…(이하 생략)` : findings;
        output.output += `\n\n[린트 결과] ${shown}: 문제 발견. 다음 단계에서 고쳐 주세요.\n${body}`;
        log(`FOUND ${shown}: ${findings.split("\n").length}건`);
      } catch (err) {
        // 어떤 이유로든 편집을 실패로 만들지 않습니다.
        log(`ERROR ${String(err?.message ?? err).slice(0, 200)}`);
      }
    },
  };
};
