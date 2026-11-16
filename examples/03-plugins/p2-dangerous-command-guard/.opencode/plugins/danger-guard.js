// p2-dangerous-command-guard: 위험한 bash 명령을 실행 전에 막는 플러그인.
//
// 규칙을 추가하려면 아래 RULES 배열에 { id, pattern, message } 한 줄을 더하면 됩니다.
//   - pattern : 명령 전체 문자열에 대해 검사하는 정규식 (대소문자 무시는 "i" 플래그)
//   - unless  : (선택) 이 정규식에도 걸리면 허용 — 예: git clean 의 --dry-run
//   - message : 모델에게 보여 줄 한국어 안내. "무엇이 위험한지 + 대신 무엇을 하라"를 적습니다.
//
// 주의: 이 파일은 "플러그인 함수"만 export 합니다. 숫자·문자열·객체 같은 함수가 아닌 값을 export 하면
//       opencode 가 이 파일 전체를 건너뜁니다(평소엔 아무 출력이 없고 `--print-logs` 에만
//       "Plugin export is not a function" 오류가 보입니다). 보조 함수를 export 해도 그것까지 플러그인으로
//       호출되므로 export 하지 않습니다.
import { appendFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";

// 한 명령 안의 "다음 명령" 경계(; && || | 줄바꿈)를 넘지 않도록 [^;&|\n]* 를 씁니다.
const SEG = "[^;&|\\n]*";
// rm 류가 지우려는 "너무 큰" 대상: / /* ~ ~/ ~/* $HOME * ./* . ./ (따옴표 허용)
const BIG_POSIX = "[\"']?(?:\\/\\*?|~\\/?\\*?|\\$HOME\\/?\\*?|\\$\\{HOME\\}\\/?\\*?|\\*|\\.(?:\\/\\*?)?)[\"']?";
// 윈도 쪽 대상: C:\ C:/ C:\* \ / ~ $HOME $env:USERPROFILE %USERPROFILE% * . .\ .\*
const BIG_WIN =
  "[\"']?(?:[A-Za-z]:[\\\\/]?\\*?|\\\\\\*?|\\/\\*?|~[\\\\/]?\\*?|\\$HOME[\\\\/]?\\*?|\\$env:USERPROFILE[\\\\/]?\\*?|%USERPROFILE%[\\\\/]?\\*?|\\*|\\.(?:[\\\\/]\\*?)?)[\"']?";
const END = "(?=\\s|$|[;&|)])";

const RULES = [
  {
    id: "rm-recursive-big-target",
    // rm 에 재귀 옵션(-r, -rf, -fr, -R, --recursive, PowerShell 의 -Recurse)이 있고, 대상 중 하나가 / ~ * . 같은 큰 경로
    pattern: new RegExp(
      `\\brm\\b(?=${SEG}\\s(?:-[A-Za-z]*[rR][A-Za-z]*|--recursive)\\b)${SEG}\\s${BIG_POSIX}${END}`,
      "i",
    ),
    message: "루트(/)·홈(~)·현재 폴더 전체(* , .)를 재귀 삭제하는 명령은 막혀 있습니다. 지울 폴더나 파일을 구체적인 경로로 지정해서 다시 시도하세요.",
  },
  {
    id: "powershell-remove-item-root",
    // PowerShell 에서는 rm/rmdir/rd/del/erase 도 Remove-Item 의 별칭이라 -Recurse 를 받습니다.
    pattern: new RegExp(`\\b(?:Remove-Item|ri|rm|rmdir|rd|del|erase)\\b(?=${SEG}\\s-r(?:ecurse)?\\b)${SEG}\\s${BIG_WIN}${END}`, "i"),
    message: "드라이브 루트·홈 폴더·* 를 대상으로 하는 Remove-Item -Recurse 는 막혀 있습니다. 지울 대상을 구체적인 하위 경로로 지정하세요.",
  },
  {
    id: "cmd-del-root",
    pattern: new RegExp(`\\b(?:rd|rmdir|del|erase)\\b(?=${SEG}\\s\\/s\\b)${SEG}\\s${BIG_WIN}${END}`, "i"),
    message: "드라이브 루트·홈 폴더·* 를 대상으로 하는 rd/del /s 는 막혀 있습니다. 지울 대상을 구체적인 하위 경로로 지정하세요.",
  },
  {
    id: "git-push-force",
    // --force, -f, -fu 같은 묶음 옵션, +브랜치 refspec. --force-with-lease 는 허용.
    pattern: new RegExp(`\\bgit\\s+push\\b${SEG}\\s(?:--force(?![-\\w])|-(?!-)[A-Za-z]*f[A-Za-z]*(?=\\s|$|[;&|)])|\\+[^\\s;&|)]+)`, "i"),
    message: "git push --force / -f 는 원격 이력을 덮어쓸 수 있어 막혀 있습니다. 꼭 필요하면 --force-with-lease 를 쓰거나, 사용자에게 직접 실행해 달라고 요청하세요.",
  },
  {
    id: "git-reset-hard",
    pattern: new RegExp(`\\bgit\\s+reset\\b${SEG}--hard\\b`, "i"),
    message: "git reset --hard 는 커밋하지 않은 변경을 지웁니다. 먼저 git stash 나 git status 로 상태를 확인하고, 되돌릴 파일만 git restore <경로> 로 복구하세요.",
  },
  {
    id: "git-clean-force",
    // git clean -f / -fd / -fdx / -xdf / --force. -n, --dry-run 이 함께 있으면 미리보기라서 허용.
    pattern: new RegExp(`\\bgit\\s+clean\\b${SEG}\\s(?:--force\\b|-(?!-)[A-Za-z]*f[A-Za-z]*(?=\\s|$|[;&|)]))`, "i"),
    unless: /\s(?:--dry-run\b|-(?!-)[A-Za-z]*n[A-Za-z]*(?=\s|$|[;&|)]))/i,
    message: "git clean -f 는 추적되지 않은 파일을 영구 삭제합니다. git clean -n 으로 지워질 목록을 먼저 확인하고, 사용자 동의를 받은 뒤 실행하세요.",
  },
  {
    id: "sql-drop",
    pattern: /\bDROP\s+(?:TABLE|DATABASE|SCHEMA)\b/i,
    message: "DROP TABLE/DATABASE/SCHEMA 는 데이터를 영구 삭제합니다. 이 에이전트에서는 실행할 수 없으니, 필요한 SQL 을 파일로 작성해 사용자가 직접 검토 후 실행하도록 안내하세요.",
  },
  {
    id: "sql-truncate",
    // `truncate -s 0 파일` (리눅스 명령)과 구분하려고 뒤에 테이블 이름이 오는 경우만 봅니다.
    pattern: /\bTRUNCATE\s+(?:TABLE\s+)?[\w."`\[]/i,
    message: "TRUNCATE 는 테이블의 모든 행을 되돌릴 수 없게 지웁니다. 필요한 SQL 을 파일로 작성해 사용자가 직접 검토 후 실행하도록 안내하세요.",
  },
  {
    id: "sql-delete-without-where",
    pattern: /\bDELETE\s+FROM\s+[\w."`\[\]]+\s*(?:;|["']|$)/i,
    message: "WHERE 없는 DELETE FROM 은 테이블 전체 행을 지웁니다. WHERE 조건을 붙이거나 사용자에게 먼저 확인받으세요.",
  },
  {
    id: "chmod-recursive-777",
    pattern: new RegExp(`\\bchmod\\b(?=${SEG}\\s(?:-[A-Za-z]*R[A-Za-z]*|--recursive)\\b)${SEG}\\s(?:0?777|a\\+rwx|ugo\\+rwx)\\b`),
    message: "chmod -R 777 은 모든 사용자에게 쓰기 권한을 열어 보안 문제를 만듭니다. 필요한 파일에만 chmod 644(파일)·755(실행 파일/폴더) 처럼 최소 권한을 주세요.",
  },
  {
    id: "pipe-to-shell",
    pattern: new RegExp(`\\b(?:curl|wget)\\b${SEG}\\|\\s*(?:sudo\\s+)?(?:ba|z)?sh\\b`, "i"),
    message: "내려받은 스크립트를 바로 셸에 넘기는 curl | sh 형태는 막혀 있습니다. 파일로 저장해서 내용을 확인한 뒤 실행하세요.",
  },
];

function segmentAt(command, index) {
  let start = index;
  while (start > 0 && !/[;&|\n]/.test(command[start - 1])) start--;
  let end = index;
  while (end < command.length && !/[;&|\n]/.test(command[end])) end++;
  return command.slice(start, end);
}

function findRule(command) {
  if (typeof command !== "string") return null;
  for (const rule of RULES) {
    const m = rule.pattern.exec(command);
    if (!m) continue;
    // unless 는 걸린 명령이 들어 있는 구간(; && || | 줄바꿈 사이)에서만 봅니다.
    // `git clean -fd; head -n 5 x` 의 -n 때문에 git clean 이 풀려나지 않게 하려는 것입니다.
    if (rule.unless && rule.unless.test(segmentAt(command, m.index))) continue;
    return rule;
  }
  return null;
}

function append(directory, file, line) {
  try {
    mkdirSync(join(directory, "logs"), { recursive: true });
    appendFileSync(join(directory, "logs", file), line + "\n", "utf8");
  } catch {
    // 로그를 못 남겨도 차단 기능은 계속 동작해야 합니다.
  }
}

export const DangerousCommandGuard = async ({ directory }) => {
  append(directory, "plugin-load.log", `${new Date().toISOString()} danger-guard loaded (${RULES.length} rules)`);
  return {
    "tool.execute.before": async (input, output) => {
      if (input.tool !== "bash") return;
      const command = output.args?.command;
      const rule = findRule(command);
      if (!rule) return;
      append(
        directory,
        "danger-guard.log",
        `${new Date().toISOString()} BLOCKED rule=${rule.id} :: ${String(command).replace(/\s+/g, " ").slice(0, 160)}`,
      );
      // throw 하면 명령이 실행되지 않고, 이 메시지가 모델에게 오류로 전달됩니다.
      throw new Error(`[danger-guard:${rule.id}] ${rule.message}`);
    },
  };
};
