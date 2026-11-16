// p5-shell-env: 에이전트가 실행하는 모든 셸 명령(bash 도구)에 환경변수를 주입하는 플러그인.
//
// shell.env 훅은 명령을 실행하기 직전에 호출됩니다. (opencode 1.19.5 에서 관찰)
//   input  = { cwd, sessionID, callID }   (경로는 윈도에서 "C:\\..." 형태)
//   output = { env: {} }                  처음에는 비어 있는 객체. 여기에 넣은 키만 기존 환경 위에 덮어씁니다.
// 에이전트가 쓰는 환경만 바뀌고, 사용자의 터미널·시스템 환경변수는 그대로입니다.
//
// 주의: 이 파일은 "플러그인 함수"만 export 합니다. 숫자·문자열·객체 같은 함수가 아닌 값을 export 하면
//       opencode 가 이 파일 전체를 건너뜁니다(평소엔 아무 출력이 없고 `--print-logs` 에만
//       "Plugin export is not a function" 오류가 보입니다). 보조 함수를 export 해도 그것까지 플러그인으로
//       호출되므로 export 하지 않습니다.
import { appendFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";

function append(directory, file, line) {
  try {
    mkdirSync(join(directory, "logs"), { recursive: true });
    appendFileSync(join(directory, "logs", file), line + "\n", "utf8");
  } catch {
    // 로그 실패가 명령 실행을 막으면 안 됩니다.
  }
}

export const ShellEnv = async ({ directory }) => {
  append(directory, "plugin-load.log", `${new Date().toISOString()} shell-env loaded`);

  // 주입할 변수 표. 한 줄 추가하면 다음 명령부터 에이전트의 모든 셸에 적용됩니다.
  const injected = {
    APP_ENV: "dev",
    // 데모용 프록시 값입니다. 실제 프록시가 없으므로 NO_PROXY=* 로 "프록시를 거치지 않게" 해 둡니다.
    // 실제 프록시를 쓰는 환경이라면 HTTP_PROXY/HTTPS_PROXY 를 그 주소로, NO_PROXY 를 필요한 예외 목록으로 바꾸세요.
    HTTP_PROXY: "http://127.0.0.1:3128",
    HTTPS_PROXY: "http://127.0.0.1:3128",
    NO_PROXY: "*",
    // 사설 인증서를 쓰는 환경에서 requests/pip 가 믿을 CA 묶음. 경로는 프로젝트 폴더 기준으로 절대 경로로 만듭니다.
    // certs/demo-ca.pem 은 자리만 채운 가짜 파일입니다.
    REQUESTS_CA_BUNDLE: join(directory, "certs", "demo-ca.pem"),
  };

  return {
    "shell.env": async (input, output) => {
      Object.assign(output.env, injected);
      append(directory, "shell-env.log", `${new Date().toISOString()} injected ${Object.keys(injected).join(",")} cwd=${input?.cwd ?? "?"}`);
    },
  };
};
