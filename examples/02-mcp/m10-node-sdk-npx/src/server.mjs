#!/usr/bin/env node
// M10 - 공식 TypeScript SDK(@modelcontextprotocol/sdk)로 만든 팀 용어집 서버 (stdio).
//
// M1은 JSON-RPC를 직접 읽고 썼고, M2는 Python SDK를 썼다. 여기서는 같은 일을 Node SDK로 한다.
// SDK가 대신 해 주는 일: 줄 단위 입출력, initialize 협상, tools/list 응답 만들기, 인자 검증, 오류 변환.
// 우리가 쓰는 것은 "도구 이름 + 설명 + 입력 스키마(zod) + 실행 함수"뿐이다.
//
// 규칙은 M1과 같다: stdout은 프로토콜 전용. 로그는 console.error(stderr)로만 쓴다.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

const log = (...parts) => console.error("[team-glossary]", ...parts);

// glossary.json은 이 파일 기준 ../glossary.json. 실행 위치(cwd)와 상관없이 찾는다.
// npx나 npm pack으로 배포해도 "files"에 glossary.json이 들어 있으면 같은 상대 위치다.
const GLOSSARY_URL = new URL("../glossary.json", import.meta.url);
const TERMS = JSON.parse(readFileSync(fileURLToPath(GLOSSARY_URL), "utf-8")).terms;

function findTerm(query) {
  const q = query.trim().toLowerCase();
  return TERMS.find((item) => [item.term, ...(item.aliases ?? [])].some((n) => n.toLowerCase() === q));
}

// 용어집에 없을 때 비슷한 용어를 알려 준다 (M1의 difflib 대신 부분 문자열 비교로 단순화).
function nearTerms(query) {
  const q = query.trim().toLowerCase();
  return TERMS.filter((item) => {
    const t = item.term.toLowerCase();
    return t.includes(q) || q.includes(t) || [...q].filter((c) => t.includes(c)).length >= Math.ceil(q.length * 0.6);
  })
    .slice(0, 3)
    .map((item) => item.term);
}

const server = new McpServer({ name: "team-glossary-mcp", version: "1.0.0" });

server.registerTool(
  "lookup_term",
  {
    description:
      "팀 용어집에서 용어 하나의 뜻을 찾는다. " +
      "ADR, SLO, 롤백, 카나리 배포 같은 팀 내부 용어의 정의가 필요할 때 사용한다. " +
      "영어 이름이나 별칭으로도 찾을 수 있다.",
    inputSchema: { term: z.string().describe("찾을 용어. 예: 'ADR', '카나리 배포'") },
  },
  async ({ term }) => {
    log("lookup_term", term);
    const item = findTerm(term);
    if (item) {
      const aliases = (item.aliases ?? []).join(", ") || "-";
      return { content: [{ type: "text", text: `${item.term}: ${item.definition}\n(별칭: ${aliases})` }] };
    }
    // 프로토콜 오류가 아니라 isError 결과: 모델이 메시지를 읽고 다시 시도할 수 있다 (M1과 같은 규칙).
    const near = nearTerms(term);
    const hint = near.length ? ` 비슷한 용어: ${near.join(", ")}.` : "";
    return {
      isError: true,
      content: [{ type: "text", text: `'${term}'은(는) 용어집에 없습니다.${hint} list_terms로 전체 목록을 볼 수 있습니다.` }],
    };
  },
);

server.registerTool(
  "list_terms",
  {
    description: "팀 용어집에 등록된 모든 용어 이름을 나열한다. 어떤 용어가 있는지 모를 때 먼저 사용한다.",
  },
  async () => ({ content: [{ type: "text", text: TERMS.map((i) => `- ${i.term}`).join("\n") }] }),
);

await server.connect(new StdioServerTransport());
log(`시작: 용어 ${TERMS.length}개, stdin 대기 중`);
