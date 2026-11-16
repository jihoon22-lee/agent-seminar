// p3-audit-log: 에이전트가 실행한 모든 도구 호출을 JSONL 한 줄씩 기록하는 플러그인.
//
// 기록하는 것 : 시각, 세션 ID, 도구 이름, 인자 요약(경로·명령은 유지, 긴 문자열은 잘라냄), 결과 제목, 결과 길이
// 기록하지 않는 것 : 파일 내용(write/edit 본문, 패치), 도구 출력 본문, 비밀처럼 보이는 값(***로 가림)
//
// 설정(환경변수, 모두 선택):
//   AUDIT_MAX_BYTES  파일이 이 크기를 넘으면 새 파일로 교체(로테이션). 기본 1048576 (1 MiB)
//   AUDIT_KEEP       보관할 이전 파일 개수. 기본 5
//
// 주의: 이 파일은 "플러그인 함수"만 export 합니다. 상수나 보조 함수를 export 하면
//       opencode 가 그것도 플러그인으로 호출하다가 모듈 전체를 조용히 건너뜁니다.
import { appendFileSync, mkdirSync, readdirSync, renameSync, rmSync, statSync } from "node:fs";
import { join } from "node:path";

const MAX_STRING = 120; // 일반 문자열 인자를 이 길이에서 자름
const MAX_COMMAND = 300; // bash 명령은 조금 더 길게 허용
const PATH_KEYS = new Set(["filePath", "path", "file_path", "filepath", "cwd", "workdir", "include", "pattern", "url"]);
// 내용 자체이므로 길이만 남기는 인자들 (write.content, edit.oldString/newString, apply_patch.patchText ...)
const CONTENT_KEYS = new Set(["content", "oldString", "newString", "patchText", "text", "prompt", "body", "data"]);

// 비밀처럼 보이는 조각을 *** 로 바꿉니다. 완벽하지 않으므로 "로그에 비밀이 없을 것"을 보장하지는 않습니다.
const SECRET_PATTERNS = [
  [/\b(Bearer|Basic)\s+[A-Za-z0-9._~+\/=-]{6,}/gi, "$1 ***"],
  [/((?:token|secret|passw(?:or)?d|pwd|api[_-]?key|access[_-]?key|authorization)["']?\s*[=:]\s*)["']?[^\s"'&;]+/gi, "$1***"],
  [/(--(?:token|password|passwd|secret|api-key)(?:=|\s+))\S+/gi, "$1***"],
  [/(:\/\/[^\s:@\/]+:)[^\s@\/]+@/g, "$1***@"], // postgres://user:비밀번호@host
];

function redact(text) {
  let out = text;
  for (const [re, rep] of SECRET_PATTERNS) out = out.replace(re, rep);
  return out;
}

function clip(text, max) {
  const flat = redact(String(text)).replace(/\s+/g, " ").trim();
  return flat.length > max ? `${flat.slice(0, max)}…(+${flat.length - max}자)` : flat;
}

function summarizeValue(key, value) {
  if (typeof value === "string") {
    if (CONTENT_KEYS.has(key)) return `<${value.length}자 생략>`;
    if (key === "command") return clip(value, MAX_COMMAND);
    // 경로는 그대로 두되(감사에 필요), 비정상적으로 길면 자름
    return PATH_KEYS.has(key) ? clip(value, 400) : clip(value, MAX_STRING);
  }
  if (typeof value === "number" || typeof value === "boolean" || value == null) return value;
  if (Array.isArray(value)) return `<배열 ${value.length}개>`;
  return "<객체>";
}

function summarizeArgs(args) {
  const summary = {};
  if (!args || typeof args !== "object") return summary;
  for (const [key, value] of Object.entries(args)) summary[key] = summarizeValue(key, value);
  return summary;
}

function stamp() {
  return new Date().toISOString().replace(/[-:]/g, "").replace(/\.\d+Z$/, "").replace("T", "-");
}

// 현재 파일이 너무 커졌으면 audit.<시각>.jsonl 로 이름을 바꾸고, 오래된 것은 AUDIT_KEEP 개만 남깁니다.
function rotateIfNeeded(dir, base) {
  const max = Number(process.env.AUDIT_MAX_BYTES) || 1024 * 1024;
  const keepEnv = process.env.AUDIT_KEEP;
  const keep = keepEnv && Number.isFinite(Number(keepEnv)) ? Number(keepEnv) : 5;
  const current = join(dir, base);
  let size = 0;
  try {
    size = statSync(current).size;
  } catch {
    return;
  }
  if (size < max) return;
  const stem = base.replace(/\.jsonl$/, "");
  let target = join(dir, `${stem}.${stamp()}.jsonl`);
  for (let i = 1; ; i++) {
    try {
      statSync(target);
      target = join(dir, `${stem}.${stamp()}-${i}.jsonl`);
    } catch {
      break;
    }
  }
  renameSync(current, target);
  const old = readdirSync(dir)
    .filter((f) => f.startsWith(`${stem}.`) && f.endsWith(".jsonl"))
    .sort(); // 이름에 시각이 들어 있어 사전순 = 시간순
  for (const f of old.slice(0, Math.max(0, old.length - keep))) rmSync(join(dir, f), { force: true });
}

function append(directory, file, line) {
  try {
    mkdirSync(join(directory, "logs"), { recursive: true });
    appendFileSync(join(directory, "logs", file), line + "\n", "utf8");
  } catch {
    // 감사 로그 실패가 에이전트 작업을 멈추게 하면 안 됩니다.
  }
}

export const AuditLog = async ({ directory }) => {
  const logDir = join(directory, "logs");
  append(directory, "plugin-load.log", `${new Date().toISOString()} audit-log loaded`);
  return {
    "tool.execute.after": async (input, output) => {
      try {
        const record = {
          ts: new Date().toISOString(),
          sessionID: input.sessionID,
          tool: input.tool,
          args: summarizeArgs(input.args),
          title: clip(output?.title ?? "", MAX_COMMAND),
          outputLength: typeof output?.output === "string" ? output.output.length : 0,
        };
        rotateIfNeeded(logDir, "audit.jsonl");
        append(directory, "audit.jsonl", JSON.stringify(record));
      } catch {
        // 위와 같은 이유로 조용히 무시합니다.
      }
    },
  };
};
