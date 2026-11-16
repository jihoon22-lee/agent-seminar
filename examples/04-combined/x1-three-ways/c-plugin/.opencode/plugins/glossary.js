// 팀 용어 사전 조회를 플러그인 커스텀 도구로 만든 버전. 모델에게는 `team_glossary` 라는 이름으로 보인다.
import { tool } from "@opencode-ai/plugin"
import { readFileSync } from "node:fs"
import { join } from "node:path"

export const Glossary = async ({ directory }) => ({
  tool: {
    team_glossary: tool({
      description:
        "팀 용어 사전에서 용어(ADR, SLO, 에러 버짓, 온콜, 카나리, 핫픽스 등)의 뜻을 찾는다. 팀마다 값이 다르므로 추측하지 말고 이 도구로 확인한다.",
      args: {
        term: tool.schema.string().describe("찾을 용어. 예: ADR"),
      },
      async execute(args, context) {
        const file = join(context.directory ?? directory, "glossary.json")
        const glossary = JSON.parse(readFileSync(file, "utf-8"))
        const key = Object.keys(glossary).find((k) => k.toLowerCase() === args.term.trim().toLowerCase())
        if (key) return `${key}: ${glossary[key]}`
        return `'${args.term}' 는 사전에 없습니다. 등록된 용어: ${Object.keys(glossary).join(", ")}`
      },
    }),
  },
})
