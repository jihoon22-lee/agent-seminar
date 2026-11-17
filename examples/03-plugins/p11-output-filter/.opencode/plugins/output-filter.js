// p11-output-filter: 도구 결과가 모델에게 가기 전에 가공하는 플러그인 (tool.execute.after).
//
//   1. 비밀처럼 보이는 값을 *** 로 가린다.
//        - 이름에 TOKEN/SECRET/PASSWORD/PASSWD/API_KEY/ACCESS_KEY/PRIVATE_KEY/CREDENTIAL 이 들어간 key=value, key: value, "key": "value"
//        - --token 값, --password=값 같은 옵션
//        - Authorization: Bearer 값 (그리고 단독 `Bearer 값`)
//   2. 아주 긴 출력은 앞부분 + 뒷부분만 남기고 가운데를 "(N줄 생략)" 표시로 바꾼다. (bash 와 MCP 도구만)
//
// 실측(opencode 1.19.5, README 참고):
//   - 내장 도구(bash, read, grep ...)의 결과는 output.output(문자열) 이다. 이것을 바꾸면 모델이 받는 결과와
//     저장되는 state.output 이 바뀌고, bash 의 화면 출력도 바뀐다.
//   - MCP 도구는 output.output 이 없고 output.content = [{type:"text", text}] 모양이다. 이 text 를 바꿔야 한다.
//   - metadata 에는 같은 내용의 또 다른 사본이 있다(bash: metadata.output, read: metadata.preview, edit: diff).
//     모델에게는 가지 않지만 저장소(세션 DB)와 edit 의 화면 diff 에는 남으므로 문자열을 모두 훑어 같이 가린다.
//
// 가리는 것은 "모델에게 가는 글자"입니다. 명령은 이미 실행됐고 파일은 디스크에 그대로입니다.
//
// 환경변수(모두 선택): OUTPUT_FILTER_MAX_LINES(기본 100) OUTPUT_FILTER_HEAD(기본 40) OUTPUT_FILTER_TAIL(기본 40)
//                      OUTPUT_FILTER_MAX_CHARS(기본 20000)  OUTPUT_FILTER_METADATA=0 이면 metadata 는 건드리지 않음
//
// 주의: 이 파일은 "플러그인 함수"만 export 합니다. 함수가 아닌 값을 export 하면 opencode 가 파일 전체를 건너뜁니다.
import { appendFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";

const KEY_WORDS = "(?:TOKEN|SECRET|PASSWORD|PASSWD|API[_-]?KEY|ACCESS[_-]?KEY|PRIVATE[_-]?KEY|CREDENTIALS?)";
// 값이 $변수, <자리표시>, {템플릿}, (식) 으로 시작하거나 이미 *** 면 비밀이 아니라 코드/자리표시로 보고 건너뜁니다.
const VALUE = "(?![$<{%(*])[^\\s\"',;]{4,}";
const RULES = [
  // Authorization: Bearer 값 / Authorization=Basic 값 / "Authorization": "값"
  [/(authorization["']?\s*[:=]\s*["']?)(?:(Bearer|Basic|Token)\s+)?(?![*])[^\s"',;]{4,}/gi, (m, head, scheme) => `${head}${scheme ? scheme + " " : ""}***`],
  // 단독 Bearer 값 (헤더 이름 없이 curl -H 'x' 안에 있거나 로그에 찍힌 경우)
  [/\b(Bearer)\s+(?![*])[A-Za-z0-9._~+\/=-]{8,}/g, (m, scheme) => `${scheme} ***`],
  // NAME_TOKEN=값, "api_key": "값", password: 값
  [new RegExp(`([A-Za-z0-9_.-]*${KEY_WORDS}[A-Za-z0-9_.-]*)(["']?\\s*[=:]\\s*["']?)${VALUE}`, "gi"), (m, key, sep) => `${key}${sep}***`],
  // --token 값, --password=값, --api-key 값
  [new RegExp(`(--[A-Za-z-]*${KEY_WORDS}[A-Za-z-]*(?:=|\\s+))${VALUE}`, "gi"), (m, flag) => `${flag}***`],
];

function maskText(text) {
  let count = 0;
  let out = text;
  for (const [re, fn] of RULES) {
    out = out.replace(re, (...args) => {
      const replaced = fn(...args);
      if (replaced !== args[0]) count++;
      return replaced;
    });
  }
  return { text: out, count };
}

// 객체 안의 모든 문자열 값을 가린다. (원본은 건드리지 않고 사본을 돌려준다)
function maskDeep(value, stats) {
  if (typeof value === "string") {
    const r = maskText(value);
    stats.count += r.count;
    return r.text;
  }
  if (Array.isArray(value)) return value.map((v) => maskDeep(v, stats));
  if (value && typeof value === "object") {
    const copy = {};
    for (const [k, v] of Object.entries(value)) copy[k] = maskDeep(v, stats);
    return copy;
  }
  return value;
}

function envNumber(name, fallback) {
  const n = Number(process.env[name]);
  return Number.isFinite(n) && n > 0 ? n : fallback;
}

// 앞 head 줄 + 뒤 tail 줄만 남긴다. 줄 수가 적어도 글자가 너무 많으면(한 줄짜리 거대 출력) 글자 단위로 자른다.
function shorten(text) {
  const maxLines = envNumber("OUTPUT_FILTER_MAX_LINES", 100);
  const head = envNumber("OUTPUT_FILTER_HEAD", 40);
  const tail = envNumber("OUTPUT_FILTER_TAIL", 40);
  const maxChars = envNumber("OUTPUT_FILTER_MAX_CHARS", 20000);
  let out = text;
  let note = null;
  const trailing = out.endsWith("\n"); // 끝의 줄바꿈은 줄 수에 넣지 않는다
  const lines = (trailing ? out.slice(0, -1) : out).split("\n");
  if (lines.length > maxLines) {
    const omitted = lines.length - head - tail;
    out = [...lines.slice(0, head), `... (${omitted}줄 생략) ...`, ...lines.slice(-tail)].join("\n") + (trailing ? "\n" : "");
    note = `${lines.length}줄 -> ${head + tail + 1}줄`;
  }
  if (out.length > maxChars) {
    const keep = Math.floor(maxChars / 2);
    out = `${out.slice(0, keep)}\n... (${out.length - 2 * keep}자 생략) ...\n${out.slice(-keep)}`;
    note = `${note ? note + ", " : ""}${text.length}자 -> ${out.length}자`;
  }
  return { text: out, note };
}

export const OutputFilter = async ({ directory }) => {
  function log(line) {
    try {
      mkdirSync(join(directory, "logs"), { recursive: true });
      appendFileSync(join(directory, "logs", "output-filter.log"), `${new Date().toISOString()} ${line}\n`, "utf8");
    } catch {
      // 로그를 못 남겨도 필터는 계속 동작합니다. (로그에는 비밀 값 자체를 절대 쓰지 않고 개수만 씁니다.)
    }
  }

  log("output-filter loaded");
  return {
    "tool.execute.after": async (input, output) => {
      try {
        if (!output || typeof output !== "object") return;
        const stats = { count: 0 };
        const notes = [];
        const isMcp = Array.isArray(output.content); // MCP 도구: { content: [{ type: "text", text }] }
        const shortenIt = input.tool === "bash" || isMcp;

        const process_ = (text) => {
          let t = maskText(text);
          stats.count += t.count;
          if (!shortenIt) return t.text;
          const s = shorten(t.text);
          if (s.note) notes.push(s.note);
          return s.text;
        };

        if (typeof output.output === "string") output.output = process_(output.output);
        if (isMcp) {
          for (const part of output.content) {
            if (part && part.type === "text" && typeof part.text === "string") part.text = process_(part.text);
          }
        }
        if (typeof output.title === "string") {
          const t = maskText(output.title);
          stats.count += t.count;
          output.title = t.text;
        }
        if (output.metadata && typeof output.metadata === "object" && process.env.OUTPUT_FILTER_METADATA !== "0") {
          output.metadata = maskDeep(output.metadata, stats);
        }
        if (stats.count > 0 || notes.length > 0) {
          log(`tool=${input.tool} masked=${stats.count}${notes.length ? ` shortened=${notes.join(" / ")}` : ""}`);
        }
      } catch (err) {
        // 필터가 실패하면 결과를 그대로 둡니다(fail-open). 실패 사실만 기록합니다.
        log(`ERROR tool=${input?.tool} ${String(err?.message ?? err).slice(0, 160)}`);
      }
    },
  };
};
