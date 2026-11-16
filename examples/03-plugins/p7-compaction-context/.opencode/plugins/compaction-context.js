// p7 — 세션 압축(compaction) 때 "고정 사실"을 요약 프롬프트에 끼워 넣는 플러그인.
//
// 훅: experimental.session.compacting   (실험적 훅 — 이름·모양이 다음 버전에서 바뀔 수 있다)
//   input  = { sessionID }
//   output = { context: string[], prompt?: string }      (1.19.5 에서 관찰한 모양)
//     - output.context 에 문자열을 push 하면 기본 압축 프롬프트 맨 끝에 덧붙는다.
//     - output.prompt 를 설정하면 기본 압축 프롬프트를 통째로 대체한다. 이때 context 는 무시된다. (이 예제는 쓰지 않는다)
//
// 훅: experimental.compaction.autocontinue   (역시 실험적. 자동 압축 직후 "계속하기" 턴을 만들지 결정)
//   input  = { sessionID, agent, model, provider, message, overflow }
//   output = { enabled: boolean }                          (기본 true)
//   이 예제는 건드리지 않고 로그만 남긴다.
//
// 파일 위치는 이 플러그인 파일 기준으로 계산한다 → opencode 를 어느 폴더에서 띄워도 같은 파일을 쓴다.
import { appendFileSync, existsSync, mkdirSync, readFileSync } from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"

const here = path.dirname(fileURLToPath(import.meta.url)) // <예제>/.opencode/plugins
const factsPath = path.resolve(here, "..", "memory", "project-facts.md")
const logPath = path.resolve(here, "..", "..", "logs", "compaction.log")

function log(entry) {
  mkdirSync(path.dirname(logPath), { recursive: true })
  appendFileSync(logPath, JSON.stringify({ at: new Date().toISOString(), ...entry }) + "\n", "utf8")
}

// 훅 안에서 예외가 나면 압축 자체가 실패한다(1.19.5 에서 확인: summarize 가 500 으로 끝남).
// 부가 기능 때문에 압축을 망치지 않도록 항상 감싼다.
const safe = (hook, fn) => async (input, output) => {
  try { await fn(input, output) } catch (err) { log({ event: "error", hook, message: String(err) }) }
}

export const CompactionContext = async () => {
  return {
    "experimental.session.compacting": safe("compacting", async (input, output) => {
      const facts = existsSync(factsPath) ? readFileSync(factsPath, "utf8").trim() : ""
      log({
        event: "compacting",
        sessionID: input.sessionID,
        inputKeys: Object.keys(input),
        outputKeys: Object.keys(output),
        contextBefore: output.context.length,
        promptSet: output.prompt !== undefined,
        factsChars: facts.length,
      })
      if (facts) {
        output.context.push(
          "다음은 대화가 압축되어도 반드시 유지해야 하는 프로젝트 고정 사실이다. 요약의 Important Details 에 그대로 포함하라.\n\n" + facts,
        )
      }
    }),

    "experimental.compaction.autocontinue": safe("autocontinue", async (input, output) => {
      log({
        event: "autocontinue",
        sessionID: input.sessionID,
        inputKeys: Object.keys(input),
        overflow: input.overflow,
        agent: input.agent,
        model: input.model && input.model.id,
        outputBefore: { ...output },
      })
    }),
  }
}
