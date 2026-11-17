// p12-context-injection (2/2): bash 도구의 설명(description)에 프로젝트 규칙 한 줄을 덧붙이는 플러그인 (tool.definition).
//
// 시스템 프롬프트가 아니라 "이 도구를 쓰는 순간" 모델이 읽는 도구 설명에 붙으므로, 특정 도구에만 해당하는 규칙에 알맞습니다.
// 도구 정의는 요청마다 새로 만들어져서 훅도 요청마다 불립니다(한 번만 덧붙고 중복되지 않음은 check.py 가 확인).
//
// 환경변수(선택): BASH_REMINDER 덧붙일 문장을 바꾼다.
//
// 주의: 이 파일은 "플러그인 함수"만 export 합니다. 함수가 아닌 값을 export 하면 opencode 가 파일 전체를 건너뜁니다.
const DEFAULT_LINE = "프로젝트 규칙: 명령은 한 줄로 쓰고, 여러 명령은 &&(PowerShell 5.1 에서는 ;)로 잇습니다. heredoc 이나 줄바꿈이 든 명령은 쓰지 않습니다.";

export const BashReminder = async () => ({
  "tool.definition": async (input, output) => {
    try {
      if (input?.toolID !== "bash" || typeof output?.description !== "string") return;
      output.description = `${output.description}\n\n${process.env.BASH_REMINDER || DEFAULT_LINE}`;
    } catch {
      // 실패해도 원래 설명 그대로 갑니다.
    }
  },
});
