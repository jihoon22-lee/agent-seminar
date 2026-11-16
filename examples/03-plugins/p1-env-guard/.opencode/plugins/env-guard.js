// p1-env-guard: 에이전트가 .env 파일을 읽거나 고치지 못하게 막는 플러그인.
//
// 규칙: 이 파일은 "플러그인 함수"만 export 합니다. 숫자·문자열·객체 같은 함수가 아닌 값을 export 하면
//       opencode 가 이 파일 전체를 건너뜁니다(평소엔 아무 출력이 없고 `--print-logs` 에만
//       "Plugin export is not a function" 오류가 보입니다). 보조 함수를 export 해도 그것까지 플러그인으로
//       호출되므로 export 하지 않습니다.
import { appendFileSync, mkdirSync } from "node:fs";
import { join, win32 } from "node:path";

// ---- 설정 -------------------------------------------------------------------
// 읽어도 되는 파일 이름(소문자). 값이 없는 견본 파일만 허용합니다.
const ALLOWED_NAMES = new Set([".env.example"]);

// 파일 경로를 담고 있는 도구 인자 이름들 (read/edit/write/grep/glob 에서 관찰됨).
const PATH_ARG_KEYS = ["filePath", "path", "file_path", "filepath"];

// bash 명령에서 ".env 를 읽는다"고 보는 명령어들(Linux + PowerShell/cmd).
const READER_RE = new RegExp(
  "(?:^|[\\s;&|(`$:])(?:" +
    [
      "cat", "bat", "tac", "nl", "more", "less", "head", "tail", "type", "xxd", "od", "strings",
      "sed", "awk", "grep", "egrep", "rg", "cut", "sort", "uniq", "diff", "cp", "copy", "mv", "move",
      "source", "base64", "get-content", "gc", "select-string", "sls", "copy-item", "import-csv",
      "findstr", "readalltext", "readalllines", "readallbytes",
    ].join("|") +
    ")(?=[\\s(\\[:]|$)|(?:^|[\\s;&|(`])\\.(?=\\s)|\\b(?:python3?|py|node)\\s+-[ce]\\b",
  "i",
);

// ".env", ".env.local", ".env.production", ".env*" 처럼 "경로의 마지막 조각"이 .env 로 시작하는 토큰.
// os.environ, process.env.X, $env:NAME, .envrc 는 걸리지 않도록 앞뒤 경계를 요구합니다.
// 앞 경계의 ':' 는 PowerShell 의 `-Path:.env`, `-LiteralPath:.env` 형태를 잡기 위한 것입니다.
const ENV_TOKEN_RE = /(?:^|[\s"'`=<>(:\/\\])(\.env(?:\.[\w.*?-]+)?[*?]?)(?=$|[\s"'`;&|<>)])/gi;

// ---- 판정 함수 (export 하지 않음) ---------------------------------------------
function isProtectedName(name) {
  // 윈도에서는 끝의 점/공백이 무시되므로 먼저 떼어 냅니다.
  const n = String(name).replace(/[. ]+$/, "").toLowerCase();
  if (ALLOWED_NAMES.has(n)) return false;
  return n === ".env" || n.startsWith(".env.") || n.startsWith(".env*");
}

function isProtectedPath(p) {
  if (typeof p !== "string" || p === "") return false;
  // win32.basename 은 "/" 와 "\" 를 모두 구분자로 취급하므로 두 OS 경로를 함께 처리합니다.
  return isProtectedName(win32.basename(p.replace(/[\\/]+$/, "")));
}

function findProtectedInCommand(command) {
  if (typeof command !== "string") return null;
  ENV_TOKEN_RE.lastIndex = 0;
  let m;
  while ((m = ENV_TOKEN_RE.exec(command)) !== null) {
    if (isProtectedName(m[1]) && READER_RE.test(command)) return m[1];
  }
  return null;
}

// 이 호출이 보호 대상 파일을 건드리면 사유 문자열을, 아니면 null 을 돌려 줍니다.
function findViolation(tool, args) {
  if (!args || typeof args !== "object") return null;
  if (tool === "bash") {
    const hit = findProtectedInCommand(args.command);
    return hit ? `bash 명령에서 ${hit} 접근` : null;
  }
  for (const key of PATH_ARG_KEYS) {
    if (isProtectedPath(args[key])) return `${tool} 도구로 ${args[key]} 접근`;
  }
  if (isProtectedPath(args.include)) return `${tool} 도구의 include=${args.include}`;
  // 패치 형식 도구(apply_patch 등)는 본문에 "*** Update File: 경로" 줄이 있습니다. (모델에 따라 노출)
  if (typeof args.patchText === "string") {
    for (const line of args.patchText.split(/\r?\n/)) {
      const m = /^\*\*\* (?:Add|Update|Delete) File:\s*(.+)$/.exec(line);
      if (m && isProtectedPath(m[1].trim())) return `${tool} 도구의 패치 대상 ${m[1].trim()}`;
    }
  }
  return null;
}

function append(directory, file, line) {
  try {
    mkdirSync(join(directory, "logs"), { recursive: true });
    appendFileSync(join(directory, "logs", file), line + "\n", "utf8");
  } catch {
    // 로그를 못 남겨도 보호 기능 자체는 계속 동작해야 합니다.
  }
}

// ---- 플러그인 ---------------------------------------------------------------
export const EnvGuard = async ({ directory }) => {
  append(directory, "plugin-load.log", `${new Date().toISOString()} env-guard loaded`);
  return {
    "tool.execute.before": async (input, output) => {
      const reason = findViolation(input.tool, output.args);
      if (!reason) return;
      append(directory, "env-guard.log", `${new Date().toISOString()} BLOCKED ${input.tool} :: ${reason.slice(0, 160)}`);
      // throw 하면 도구가 실행되지 않고, 이 메시지가 모델에게 오류로 전달됩니다.
      throw new Error(
        "[env-guard] .env 파일은 비밀 값이 들어 있어 에이전트가 읽거나 수정할 수 없습니다. " +
          "변수 이름과 형식이 필요하면 .env.example 을 읽으세요. " +
          "실제 값이 필요하면 사용자에게 터미널에서 직접 확인해 달라고 요청하세요.",
      );
    },
  };
};
