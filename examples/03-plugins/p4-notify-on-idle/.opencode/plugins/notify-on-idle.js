// p4-notify-on-idle: 세션이 끝났거나(session.idle) 권한 승인을 기다릴 때(permission.asked) 알림을 보냅니다.
//
// opencode 1.19.5 에서 관찰한 이벤트 (event 훅의 { event } 인자):
//   session.idle      { sessionID }                               응답이 모두 끝나고 입력을 기다리는 상태
//   permission.asked  { id, sessionID, permission, patterns, ... } 도구 실행 전에 사용자 승인이 필요함
// (session.status 도 idle 을 알리지만 session.idle 과 겹치므로 쓰지 않습니다.
//  SDK 타입 정의에는 permission.updated 가 있지만 이 버전은 permission.asked 를 내보냅니다.)
//
// 알림 방법: 항상 logs/notify.log 에 한 줄 기록한 뒤, 운영체제별 외부 명령을 실행합니다.
//   Windows : PowerShell 로 시스템 소리 + 토스트(추가 모듈 없이)
//   Linux   : notify-send 가 있으면 사용, 없으면 터미널 벨(\x07)
//
// 환경변수(모두 선택):
//   NOTIFY_DRY_RUN=1          외부 명령은 실행하지 않고 notify.log 에만 기록 (테스트용)
//   NOTIFY_LOG_ALL_EVENTS=1   받은 모든 이벤트 type 을 logs/events.log 에 기록 (새 이벤트를 찾을 때)
//
// 주의: 이 파일은 "플러그인 함수"만 export 합니다. 숫자·문자열·객체 같은 함수가 아닌 값을 export 하면
//       opencode 가 이 파일 전체를 건너뜁니다(평소엔 아무 출력이 없고 `--print-logs` 에만
//       "Plugin export is not a function" 오류가 보입니다). 보조 함수를 export 해도 그것까지 플러그인으로
//       호출되므로 export 하지 않습니다.
import { spawn } from "node:child_process";
import { appendFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";

function append(directory, file, line) {
  try {
    mkdirSync(join(directory, "logs"), { recursive: true });
    appendFileSync(join(directory, "logs", file), line + "\n", "utf8");
  } catch {
    // 로그 실패가 알림이나 에이전트를 멈추게 하면 안 됩니다.
  }
}

function oneLine(text, max = 100) {
  const flat = String(text ?? "").replace(/\s+/g, " ").trim();
  return flat.length > max ? flat.slice(0, max - 1) + "…" : flat;
}

// ---- 운영체제별 알림 ---------------------------------------------------------
// PowerShell 스크립트는 -EncodedCommand(UTF-16LE base64)로 넘겨 따옴표/한글 문제를 피합니다.
// 제목·본문·로그 경로는 환경변수로 전달합니다.
const WINDOWS_SCRIPT = `
$ErrorActionPreference = 'Stop'
$log = $env:NOTIFY_LOG
function Note($m) { Add-Content -LiteralPath $log -Encoding UTF8 -Value ("  └ " + $m) }
Note 'powershell started'
try { [System.Media.SystemSounds]::Asterisk.Play(); Start-Sleep -Milliseconds 700; Note 'sound ok' } catch { Note ('sound failed: ' + $_.Exception.Message) }
try {
  [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
  $xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
  $texts = $xml.GetElementsByTagName('text')
  $texts.Item(0).AppendChild($xml.CreateTextNode($env:NOTIFY_TITLE)) | Out-Null
  $texts.Item(1).AppendChild($xml.CreateTextNode($env:NOTIFY_BODY)) | Out-Null
  $toast = New-Object Windows.UI.Notifications.ToastNotification $xml
  # 등록되지 않은 앱 ID 로는 토스트가 표시되지 않으므로 Windows PowerShell 의 앱 ID 를 빌려 씁니다.
  $appId = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\\WindowsPowerShell\\v1.0\\powershell.exe'
  [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appId).Show($toast)
  Note 'toast ok'
} catch { Note ('toast failed: ' + $_.Exception.Message) }
`;

function launch(command, args, env, onFail) {
  try {
    // Windows 에서는 detached 옵션 대신 cmd 의 "start /b" 로 띄웁니다. (detached 로 띄운 PowerShell 은
    // 콘솔이 없어서 스크립트를 실행하지 못하고 조용히 끝났습니다.) Linux 는 detached + unref 로 분리합니다.
    // 참고: `opencode run` 은 응답이 끝나자마자 종료되면서 이 프로세스도 끊습니다. TUI 처럼 오래 사는
    //       opencode 에서는 소리·토스트까지 끝까지 실행됩니다. (README 참고)
    const child = spawn(command, args, { env: { ...process.env, ...env }, detached: process.platform !== "win32", stdio: "ignore", windowsHide: true });
    child.on("error", onFail);
    child.unref();
  } catch (e) {
    onFail(e);
  }
}

function sendNotification(directory, title, body) {
  const logFile = join(directory, "logs", "notify.log");
  if (process.platform === "win32") {
    const encoded = Buffer.from(WINDOWS_SCRIPT, "utf16le").toString("base64");
    launch(
      "cmd.exe",
      ["/c", "start", "", "/b", "powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded],
      { NOTIFY_TITLE: title, NOTIFY_BODY: body, NOTIFY_LOG: logFile },
      (e) => append(directory, "notify.log", `  └ cmd/powershell 실행 실패: ${e.message}`),
    );
    return;
  }
  const bell = () => {
    try { process.stderr.write("\x07"); } catch { /* 터미널이 없으면 무시 */ }
  };
  if (process.platform === "linux") {
    launch("notify-send", [title, body], {}, (e) => {
      // ENOENT: notify-send 가 설치되어 있지 않음 → 벨로 대체
      append(directory, "notify.log", `  └ notify-send 없음(${e.code ?? e.message}), 터미널 벨로 대체`);
      bell();
    });
    return;
  }
  bell();
}

// ---- 플러그인 ---------------------------------------------------------------
export const NotifyOnIdle = async ({ directory }) => {
  append(directory, "plugin-load.log", `${new Date().toISOString()} notify-on-idle loaded`);
  const childSessions = new Set(); // 서브에이전트(task 도구) 세션: 끝날 때마다 알리면 시끄러움
  const lastSent = new Map(); // `${종류}:${세션}` -> 마지막 알림 시각(ms), 중복 방지

  function notify(kind, sessionID, title, body) {
    const key = `${kind}:${sessionID}`;
    const now = Date.now();
    if (now - (lastSent.get(key) ?? 0) < 1500) return;
    lastSent.set(key, now);
    append(directory, "notify.log", `${new Date().toISOString()}\t${kind}\t${sessionID}\t${oneLine(title)} / ${oneLine(body)}`);
    if (process.env.NOTIFY_DRY_RUN === "1") return;
    sendNotification(directory, title, body);
  }

  return {
    event: async ({ event }) => {
      if (process.env.NOTIFY_LOG_ALL_EVENTS === "1") {
        append(directory, "events.log", `${new Date().toISOString()}\t${event.type}`);
      }
      const props = event.properties ?? {};
      switch (event.type) {
        case "session.created":
          if (props.info?.parentID) childSessions.add(props.info.id);
          break;
        case "session.idle":
          if (childSessions.has(props.sessionID)) break;
          notify("idle", props.sessionID, "opencode: 작업 완료", "응답이 끝났습니다. 결과를 확인하세요.");
          break;
        case "permission.asked":
          notify(
            "permission",
            props.sessionID,
            "opencode: 승인 필요",
            `${props.permission ?? "tool"} 실행 허락을 기다리는 중: ${oneLine((props.patterns ?? []).join(", "), 80)}`,
          );
          break;
      }
    },
  };
};
