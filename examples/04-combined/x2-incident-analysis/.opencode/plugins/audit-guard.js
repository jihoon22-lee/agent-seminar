// X2 플러그인: (1) 모든 도구 호출을 logs/audit.jsonl 에 기록하고 (2) reports/ 밖으로의 파일 쓰기를 막는다.
//
// 주의: 이 파일에서 export 하는 모든 함수는 opencode 가 플러그인으로 호출한다.
//       그래서 도우미 함수는 export 하지 않고 파일 안에서만 쓴다. (함수가 아닌 값을 export 하면 로드 자체가 실패한다)
import { appendFileSync, mkdirSync } from "node:fs"
import { isAbsolute, join, relative, resolve } from "node:path"

// 파일을 쓰는 내장 도구들. 도구 이름 -> 대상 경로를 꺼내는 함수
const WRITE_TOOLS = {
  write: (args) => [args.filePath],
  edit: (args) => [args.filePath],
  // apply_patch 는 패치 본문 안에 '*** Add File: 경로' 같은 줄이 들어 있다. (인자 이름에 의존하지 않도록 문자열 값을 모두 훑는다)
  apply_patch: (args) =>
    Object.values(args)
      .filter((value) => typeof value === "string")
      .join("\n")
      .split(/\r?\n/)
      .map((line) => /^\*\*\* (?:Add File|Update File|Delete File|Move to): (.+)$/.exec(line)?.[1])
      .filter(Boolean),
}

export const AuditGuard = async ({ directory }) => {
  const logFile = join(directory, "logs", "audit.jsonl")
  const reportsDir = resolve(directory, "reports")
  const started = new Map() // callID -> 시작 시각(ms)

  // 로그를 못 써도 도구 실행을 막지 않는다. (감사 로그가 서비스 장애 원인이 되면 안 된다)
  const log = (entry) => {
    try {
      mkdirSync(join(directory, "logs"), { recursive: true })
      appendFileSync(logFile, JSON.stringify({ ts: new Date().toISOString(), ...entry }) + "\n")
    } catch {}
  }
  const insideReports = (file) => {
    const rel = relative(reportsDir, resolve(directory, file))
    return rel !== "" && !rel.startsWith("..") && !isAbsolute(rel)
  }

  return {
    "tool.execute.before": async (input, output) => {
      started.set(input.callID, Date.now())
      const args = JSON.stringify(output.args ?? {})
      log({ phase: "call", tool: input.tool, session: input.sessionID, callID: input.callID, args: args.slice(0, 300) })

      const targets = WRITE_TOOLS[input.tool]?.(output.args ?? {})
      if (targets) {
        const outside = targets.filter((file) => !insideReports(file))
        if (outside.length > 0) {
          const reason = `reports/ 밖에는 파일을 쓸 수 없습니다: ${outside.join(", ")}. 리포트는 reports/ 폴더 안에 저장하세요.`
          log({ phase: "blocked", tool: input.tool, callID: input.callID, reason })
          throw new Error(`[audit-guard] ${reason}`) // 던진 오류가 모델에게 도구 오류로 전달된다
        }
      }
    },

    "tool.execute.after": async (input, output) => {
      const t0 = started.get(input.callID)
      started.delete(input.callID)
      // 내장 도구의 결과는 output.output(문자열)이고, MCP 도구의 결과는 MCP 원형({content: [{type, text}]})이다.
      const text = typeof output.output === "string" ? output.output : JSON.stringify(output.content ?? output)
      log({
        phase: "result",
        tool: input.tool,
        callID: input.callID,
        ms: t0 ? Date.now() - t0 : null,
        outputChars: text.length,
      })
    },
  }
}
