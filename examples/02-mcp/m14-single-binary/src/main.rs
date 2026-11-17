// M14 - 런타임 없이 실행 파일 하나로 도는 MCP 서버 (Rust, 의존 라이브러리는 serde_json 하나).
//
// M1의 server.py와 같은 일을 한다: 표준 입력으로 JSON 한 줄을 받고, 표준 출력으로 JSON 한 줄을 돌려준다.
//   - initialize / tools/list / tools/call / ping 을 처리한다
//   - id가 없는 메시지(알림)에는 답하지 않는다
//   - 모르는 method는 오류 -32601
// 용어집(glossary.json)은 빌드할 때 실행 파일 안에 넣어 버린다(include_str!). 그래서 배포할 파일이 하나다.
//
// Rust를 몰라도 읽을 수 있게 썼다. 알아 둘 것은 세 가지뿐이다.
//   - json!({...})  : JSON 값을 코드 안에 그대로 쓰는 매크로
//   - Value         : 어떤 JSON 값이든 담는 타입 (파이썬의 dict/list/str 같은 것)
//   - Option<T>     : "값이 있거나(Some) 없거나(None)". 파이썬의 None 반환과 같다

use serde_json::{json, Value};
use std::io::{self, BufRead, Write};

// 빌드할 때 이 파일의 내용이 실행 파일 안으로 들어간다. 실행할 때는 파일을 읽지 않는다.
const GLOSSARY: &str = include_str!("../glossary.json");

// 이 서버가 아는 프로토콜 버전 (최신순). 클라이언트가 이 중 하나를 요청하면 그대로 따른다.
const VERSIONS: [&str; 4] = ["2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05"];

// JSON-RPC 표준 오류 코드 (M1과 같다)
const PARSE_ERROR: i64 = -32700;
const METHOD_NOT_FOUND: i64 = -32601;
const INVALID_PARAMS: i64 = -32602;

// 로그는 stderr로. stdout은 프로토콜 전용이다.
fn log(msg: &str) {
    eprintln!("[glossary-rs] {}", msg);
}

// tools/call 결과의 표준 모양: content 블록 배열 + isError
fn text_result(text: &str, is_error: bool) -> Value {
    json!({ "content": [{ "type": "text", "text": text }], "isError": is_error })
}

fn rpc_error(id: Value, code: i64, message: &str) -> Value {
    json!({ "jsonrpc": "2.0", "id": id, "error": { "code": code, "message": message } })
}

// tools/list 가 돌려줄 도구 정의. 모델은 description과 inputSchema만 보고 도구를 고른다.
fn tool_definitions() -> Value {
    json!([
        {
            "name": "lookup_term",
            "description": "팀 용어집에서 용어 하나의 뜻을 찾는다. ADR, SLO, 롤백, 카나리 배포 같은 팀 내부 용어의 정의가 필요할 때 사용한다. 영어 이름이나 별칭으로도 찾을 수 있다.",
            "inputSchema": {
                "type": "object",
                "properties": { "term": { "type": "string", "description": "찾을 용어. 예: 'ADR', '카나리 배포'" } },
                "required": ["term"]
            }
        },
        {
            "name": "list_terms",
            "description": "팀 용어집에 등록된 모든 용어 이름을 나열한다. 어떤 용어가 있는지 모를 때 먼저 사용한다.",
            "inputSchema": { "type": "object", "properties": {} }
        }
    ])
}

// 이름이나 별칭이 (대소문자 무시하고) 정확히 일치하는 용어를 찾는다.
fn find_term<'a>(terms: &'a [Value], query: &str) -> Option<&'a Value> {
    let q = query.trim().to_lowercase();
    terms.iter().find(|item| {
        let mut names = vec![item["term"].as_str().unwrap_or("")];
        if let Some(aliases) = item["aliases"].as_array() {
            names.extend(aliases.iter().filter_map(|a| a.as_str()));
        }
        names.iter().any(|n| n.to_lowercase() == q)
    })
}

// 도구 실행. 성공하면 Ok(결과), 요청 자체가 잘못됐으면 Err((코드, 메시지)).
fn call_tool(terms: &[Value], name: &str, args: &Value) -> Result<Value, (i64, String)> {
    match name {
        "lookup_term" => {
            let term = match args["term"].as_str() {
                Some(t) if !t.trim().is_empty() => t,
                _ => return Err((INVALID_PARAMS, "'term'(문자열) 인자가 필요합니다".to_string())),
            };
            match find_term(terms, term) {
                Some(item) => {
                    let aliases: Vec<&str> = item["aliases"]
                        .as_array()
                        .map(|a| a.iter().filter_map(|x| x.as_str()).collect())
                        .unwrap_or_default();
                    let text = format!(
                        "{}: {}\n(별칭: {})",
                        item["term"].as_str().unwrap_or(""),
                        item["definition"].as_str().unwrap_or(""),
                        if aliases.is_empty() { "-".to_string() } else { aliases.join(", ") }
                    );
                    Ok(text_result(&text, false))
                }
                // 도구는 정상이지만 결과가 없다 -> 프로토콜 오류가 아니라 isError 결과 (M1과 같은 이유)
                None => Ok(text_result(
                    &format!("'{}'은(는) 용어집에 없습니다. list_terms로 전체 목록을 볼 수 있습니다.", term),
                    true,
                )),
            }
        }
        "list_terms" => {
            let lines: Vec<String> = terms
                .iter()
                .map(|i| format!("- {}", i["term"].as_str().unwrap_or("")))
                .collect();
            Ok(text_result(&lines.join("\n"), false))
        }
        _ => Err((INVALID_PARAMS, format!("알 수 없는 도구: {}", name))),
    }
}

// 메시지 하나를 처리한다. 알림이면 None(= 아무것도 쓰지 않음).
fn handle(terms: &[Value], msg: &Value) -> Option<Value> {
    // 알림에는 id가 없다. 알림에는 절대 답장하지 않는다 (모르는 알림도 조용히 무시).
    if msg["id"].is_null() {
        return None;
    }
    let id = msg["id"].clone();
    let params = &msg["params"];
    let outcome: Result<Value, (i64, String)> = match msg["method"].as_str().unwrap_or("") {
        "initialize" => {
            let wanted = params["protocolVersion"].as_str().unwrap_or("");
            let version = if VERSIONS.contains(&wanted) { wanted } else { VERSIONS[0] };
            Ok(json!({
                "protocolVersion": version,
                "capabilities": { "tools": {} },
                "serverInfo": { "name": "glossary-m14", "version": "1.0.0" }
            }))
        }
        "tools/list" => Ok(json!({ "tools": tool_definitions() })),
        "tools/call" => {
            let name = params["name"].as_str().unwrap_or("");
            log(&format!("tools/call: {} {}", name, params["arguments"]));
            call_tool(terms, name, &params["arguments"])
        }
        "ping" => Ok(json!({})),
        other => Err((METHOD_NOT_FOUND, format!("모르는 method: {}", other))),
    };
    Some(match outcome {
        Ok(result) => json!({ "jsonrpc": "2.0", "id": id, "result": result }),
        Err((code, message)) => rpc_error(id, code, &message),
    })
}

fn main() {
    // 용어집은 실행 파일 안에 들어 있다. 한 번 읽어 둔다.
    let data: Value = serde_json::from_str(GLOSSARY).expect("내장 glossary.json이 올바른 JSON이 아님");
    let terms: Vec<Value> = data["terms"].as_array().cloned().unwrap_or_default();
    log(&format!("시작: 용어 {}개, stdin 대기 중", terms.len()));

    let stdout = io::stdout();
    let mut out = stdout.lock();
    // 한 줄 읽고, 처리하고, 한 줄 쓴다. stdin이 닫히면 반복이 끝나고 프로세스가 정상 종료한다.
    for line in io::stdin().lock().lines() {
        let line = match line {
            Ok(l) => l,
            Err(_) => break, // UTF-8이 아닌 입력 등 읽기 오류
        };
        if line.trim().is_empty() {
            continue;
        }
        let response = match serde_json::from_str::<Value>(&line) {
            Ok(msg) if msg.is_object() => handle(&terms, &msg),
            Ok(_) => Some(rpc_error(Value::Null, -32600, "객체가 아님")),
            Err(_) => Some(rpc_error(Value::Null, PARSE_ERROR, "JSON 파싱 실패")),
        };
        if let Some(resp) = response {
            // writeln!은 항상 "\n"만 쓴다 (Windows에서도 \r\n으로 바꾸지 않는다). flush를 빼먹으면 응답이 버퍼에 갇힌다.
            writeln!(out, "{}", resp).ok();
            out.flush().ok();
        }
    }
    log("stdin 종료, 서버를 마칩니다");
}
