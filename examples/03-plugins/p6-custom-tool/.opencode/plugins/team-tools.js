// P6: 플러그인으로 "커스텀 도구"를 등록한다.
// opencode 가 .opencode/ 안에 자동 설치하는 @opencode-ai/plugin 패키지에서 tool() 을 가져온다.
import { tool } from "@opencode-ai/plugin"
import { randomUUID } from "node:crypto"
import { readFileSync } from "node:fs"
import { join } from "node:path"

// 'YYYY-MM-DD' 문자열을 UTC 자정 Date 로 바꾼다. (시간대 영향을 없애려고 UTC 로 고정)
function parseDate(text) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(text)
  if (!m) throw new Error(`날짜 형식은 YYYY-MM-DD 여야 합니다: ${text}`)
  const d = new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3])))
  if (d.toISOString().slice(0, 10) !== text) throw new Error(`존재하지 않는 날짜입니다: ${text}`)
  return d
}

export const TeamTools = async ({ directory }) => {
  return {
    // hooks.tool 의 키가 곧 모델에게 보이는 도구 이름이다. (MCP 와 달리 접두사가 붙지 않는다)
    tool: {
      business_days: tool({
        description:
          "두 날짜 사이의 영업일 수(토·일 제외)를 센다. 시작일과 종료일을 모두 포함한다. 공휴일은 반영하지 않는다.",
        args: {
          from: tool.schema.string().describe("시작일, YYYY-MM-DD"),
          to: tool.schema.string().describe("종료일, YYYY-MM-DD"),
        },
        async execute(args) {
          const start = parseDate(args.from)
          const end = parseDate(args.to)
          if (end < start) throw new Error("종료일이 시작일보다 빠릅니다.")
          let count = 0
          for (let d = new Date(start); d <= end; d.setUTCDate(d.getUTCDate() + 1)) {
            const day = d.getUTCDay() // 0=일, 6=토
            if (day !== 0 && day !== 6) count += 1
          }
          return `${args.from} ~ ${args.to} 영업일: ${count}일 (토·일 제외, 공휴일 미반영)`
        },
      }),

      uuid_v4: tool({
        description: "무작위 UUID v4 를 하나 만든다. 인자는 없다.",
        args: {},
        async execute() {
          return randomUUID()
        },
      }),

      team_glossary: tool({
        description: "팀 용어 사전(glossary.json)에서 용어의 뜻을 찾는다. 없으면 등록된 용어 목록을 돌려준다.",
        args: {
          term: tool.schema.string().describe("찾을 용어. 예: ADR, SLO, 온콜"),
        },
        async execute(args, context) {
          // context.directory = 이 세션의 프로젝트 폴더. process.cwd() 대신 이것을 쓴다.
          const file = join(context.directory ?? directory, "glossary.json")
          const glossary = JSON.parse(readFileSync(file, "utf-8"))
          const key = Object.keys(glossary).find((k) => k.toLowerCase() === args.term.trim().toLowerCase())
          if (key) return `${key}: ${glossary[key]}`
          return `'${args.term}' 는 사전에 없습니다. 등록된 용어: ${Object.keys(glossary).join(", ")}`
        },
      }),
    },
  }
}
