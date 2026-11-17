// p11-output-filter: 도구 결과가 모델에게 가기 전에 가공하는 플러그인 (tool.execute.after).
//
//   1. 비밀처럼 보이는 값을 *** 로 가린다.
//        - 이름에 TOKEN/SECRET/PASSWORD/PASSWD/API_KEY/ACCESS_KEY/PRIVATE_KEY/CREDENTIAL 이 들어간 key=value, key: value, "key": "value"
//          값이 따옴표로 감싸여 있으면 닫는 따옴표까지 전부(공백 포함) 가린다: PASSWORD="a b c" -> PASSWORD="***"
//          따옴표가 없는 값은 공백, 따옴표, 세미콜론(;) 에서 끝난다. 쉼표는 바로 뒤에 공백·따옴표·세미콜론이 오면 거기서 끝나고, 아니면 값의 일부다.
//        - JSON 객체(MCP 의 structuredContent 같은)는 키 이름이 위 단어를 포함하고 값이 문자열이면 값을 가린다
//        - --token 값, --password=값 같은 옵션
//        - Authorization: Bearer 값 (그리고 단독 `Bearer 값`)
//   2. 아주 긴 출력은 앞부분 + 뒷부분만 남기고 가운데를 "(N줄 생략)" 표시로 바꾼다. (bash 와 MCP 도구만)
//
// 실측(opencode 1.19.5, README 참고):
//   - 내장 도구(bash, read, grep ...)의 결과는 output.output(문자열) 이다. 이것을 바꾸면 모델이 받는 결과와
//     저장되는 state.output 이 바뀌고, bash 의 화면 출력도 바뀐다.
//   - MCP 도구는 output.output 이 없고 output.content = [{type:"text", text} | {type:"resource", resource:{text}} | ...] 모양이다.
//     structuredContent 가 있으면 output.structuredContent 에 객체로 같이 온다. 그래서 MCP 결과는 모든 항목의 모든 문자열을 재귀적으로 가린다.
//     (이미지·오디오의 base64 data, resource.blob 은 들여다보지 않는다.)
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
// 값이 $변수, <자리표시>, {템플릿}, (식) 으로 시작하거나 이미 *** 면 비밀이 아니라 코드/자리표시로 보고 건너뜁니다. 값은 4글자 이상일 때만 봅니다.
//   "큰따옴표 값"(\\" 이스케이프 허용), '작은따옴표 값'  -> 닫는 따옴표까지 전부
//   닫는 따옴표가 없는 "...  -> 그 줄 끝까지
//   따옴표 없는 값 -> 공백, 따옴표, ; 에서 끝. 쉼표는 바로 뒤에 공백·따옴표·; 가 오면 거기서 끝(`f(password: str, x)`), 아니면 값의 일부(`abc,defghijkl`)
const NOT_PLACEHOLDER = "(?![$<{%(*])";
const VALUE =
  `(?:"${NOT_PLACEHOLDER}(?:[^"\\\\\\n]|\\\\.){4,}"` +
  `|'${NOT_PLACEHOLDER}[^'\\n]{4,}'` +
  `|"${NOT_PLACEHOLDER}(?:[^"\\\\\\n]|\\\\.){4,}(?=\\n|$)` +
  `|'${NOT_PLACEHOLDER}[^'\\n]{4,}(?=\\n|$)` +
  `|${NOT_PLACEHOLDER}(?:[^\\s"';,]|,(?![\\s"';]|$)){4,})`;
const lead = (v) => (v[0] === '"' || v[0] === "'" ? v[0] : "");
// 값의 겉모양만 남기고 가린다: "abc def" -> "***" (닫는 따옴표가 있을 때만 닫는다)
const maskValue = (v) => {
  const q = lead(v);
  return q ? (v.length > 1 && v.endsWith(q) ? `${q}***${q}` : `${q}***`) : "***";
};
const RULES = [
  // Authorization: Bearer 값 / Authorization=Basic 값 / "Authorization": "값"
  [/(authorization["']?\s*[:=]\s*["']?)(?:(Bearer|Basic|Token)\s+)?(?![*])[^\s"',;]{4,}/gi, (m, head, scheme) => `${head}${scheme ? scheme + " " : ""}***`],
  // 단독 Bearer 값 (헤더 이름 없이 curl -H 'x' 안에 있거나 로그에 찍힌 경우)
  [/\b(Bearer)\s+(?![*])[A-Za-z0-9._~+\/=-]{8,}/g, (m, scheme) => `${scheme} ***`],
  // NAME_TOKEN=값, "api_key": "값", password: 값
  [new RegExp(`([A-Za-z0-9_.-]*${KEY_WORDS}[A-Za-z0-9_.-]*)(["']?\\s*[=:]\\s*)(${VALUE})`, "gi"), (m, key, sep, value) => `${key}${sep}${maskValue(value)}`],
  // --token 값, --password=값, --api-key 값
  [new RegExp(`(--[A-Za-z-]*${KEY_WORDS}[A-Za-z-]*(?:=|\\s+))(${VALUE})`, "gi"), (m, flag, value) => `${flag}${maskValue(value)}`],
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

// 이름이 비밀 단어를 포함하는 키(JSON 객체의 "DB_PASSWORD": "값")의 문자열 값은 문장 규칙으로는 못 잡으므로 키 이름으로 가린다.
const SECRET_KEY = new RegExp(KEY_WORDS, "i");
const PLACEHOLDER_VALUE = /^[$<{%(*]/;
const SKIP_KEYS = new Set(["data", "blob"]); // 이미지·오디오의 base64 data, resource.blob: 들여다보지 않는다

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
    for (const [k, v] of Object.entries(value)) {
      if (SKIP_KEYS.has(k) && typeof v === "string") copy[k] = v;
      else if (SECRET_KEY.test(k) && typeof v === "string" && v.length >= 4 && !PLACEHOLDER_VALUE.test(v)) { copy[k] = "***"; stats.count++; }
      else copy[k] = maskDeep(v, stats);
    }
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
          // content 의 항목은 종류가 다양하다: text, resource({resource:{text,blob}}), resource_link, image, audio ...
          // text 라는 이름의 문자열(항목 안, resource 안)은 가리고 줄이며, 나머지 문자열도 모두 재귀적으로 가린다.
          const maskPart = (part) => {
            if (typeof part === "string") return process_(part);
            if (!part || typeof part !== "object" || Array.isArray(part)) return maskDeep(part, stats);
            const copy = {};
            for (const [k, v] of Object.entries(part)) {
              if (k === "text" && typeof v === "string") copy[k] = process_(v);
              else if (k === "resource" && v && typeof v === "object") copy[k] = maskPart(v);
              else if (SKIP_KEYS.has(k) && typeof v === "string") copy[k] = v;
              else copy[k] = maskDeep(v, stats);
            }
            return copy;
          };
          output.content.forEach((part, i) => { output.content[i] = maskPart(part); });
          // structuredContent, _meta 등 content 밖의 키도 같은 규칙으로 가린다 (title, metadata, attachments 는 아래/제외)
          for (const key of Object.keys(output)) {
            if (["content", "output", "title", "metadata", "attachments"].includes(key)) continue;
            output[key] = maskDeep(output[key], stats);
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
