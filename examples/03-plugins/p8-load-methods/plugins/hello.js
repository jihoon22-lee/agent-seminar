// P8: 같은 플러그인을 여러 방법으로 로드해 보기 위한 아주 작은 플러그인.
// 하는 일은 두 가지뿐이다.
//   1) 로드될 때마다 마커 파일에 한 줄을 남긴다.  (어떻게 로드됐는지 눈으로 확인)
//   2) shell.env 훅으로 bash 도구의 환경 변수에 HELLO_LOADED=yes 를 넣는다.
import { appendFileSync, mkdirSync } from "node:fs"
import { dirname, join } from "node:path"

export const Hello = async ({ directory }, options) => {
  // demo.py 는 HELLO_MARKER 로 마커 위치를 지정한다. 없으면 <프로젝트>/logs/hello-loaded.log
  const marker = process.env.HELLO_MARKER || join(directory, "logs", "hello-loaded.log")
  mkdirSync(dirname(marker), { recursive: true })
  const line = { loadedFrom: import.meta.url, directory, options: options ?? null }
  appendFileSync(marker, JSON.stringify(line) + "\n")

  return {
    "shell.env": async (_input, output) => {
      output.env.HELLO_LOADED = "yes"
    },
  }
}
