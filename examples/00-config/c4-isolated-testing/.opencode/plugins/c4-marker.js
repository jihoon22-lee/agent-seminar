// C4 예제용 플러그인: 로드되면 C4_MARKER_FILE 이 가리키는 파일에 한 줄을 쓴다.
// C4_MARKER_FILE 이 없으면 아무것도 하지 않는다. 플러그인이 "로드되었는가"를 눈으로 확인하는 용도.
import { writeFileSync } from "node:fs"

export const C4Marker = async () => {
  const target = process.env.C4_MARKER_FILE
  if (target) writeFileSync(target, "c4-marker plugin loaded\n")
  return {}
}
