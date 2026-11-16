#!/usr/bin/env python3
"""M2 - 공식 Python SDK(`mcp`)로 만든 같은 용어집 MCP 서버.

M1에서는 JSON-RPC 처리, 도구 목록, 스키마, 오류 코드를 직접 썼다.
SDK를 쓰면 "함수 + 타입 힌트 + docstring"만 쓰면 나머지를 SDK가 만든다.

    함수 이름        -> 도구 이름
    docstring        -> 도구 설명(description)
    매개변수 타입 힌트 -> inputSchema (JSON Schema). Field(description=...)는 인자 설명
    return 값        -> content 블록
    예외 발생         -> isError: true 결과 (모델이 읽고 다시 시도할 수 있다)

참고: mcp 2.x에서는 1.x의 `FastMCP`가 `MCPServer`로 이름이 바뀌었다.
인터넷의 예제 대부분은 `from mcp.server.fastmcp import FastMCP` (1.x)를 쓴다. 사용법은 거의 같다.
"""
import json
import sys
from pathlib import Path
from typing import Annotated

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field  # mcp가 의존하는 pydantic. 인자 설명(description)을 붙이는 데 쓴다

# SDK가 stdio를 UTF-8로 직접 다루지만, 디버깅용 print 등을 위해 습관적으로 맞춰 둔다.
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent
TERMS = json.loads((HERE / "glossary.json").read_text(encoding="utf-8"))["terms"]

mcp = MCPServer("glossary-m2", version="1.0.0")


@mcp.tool()
def lookup_term(term: Annotated[str, Field(description="찾을 용어. 예: 'ADR', '카나리 배포'")]) -> str:
    """팀 용어집에서 용어 하나의 뜻을 찾는다.

    ADR, SLO, 롤백, 카나리 배포 같은 팀 내부 용어의 정의가 필요할 때 사용한다.
    영어 이름이나 별칭으로도 찾을 수 있다.
    """
    query = term.strip().casefold()
    for item in TERMS:
        if query in (n.casefold() for n in [item["term"], *item.get("aliases", [])]):
            return f"{item['term']}: {item['definition']}\n(별칭: {', '.join(item.get('aliases', [])) or '-'})"
    # ToolError를 던지면 SDK가 isError: true 결과로 바꿔 준다.
    raise ToolError(f"'{term}'은(는) 용어집에 없습니다. list_terms로 전체 목록을 볼 수 있습니다.")


@mcp.tool()
def list_terms() -> str:
    """팀 용어집에 등록된 모든 용어 이름을 나열한다. 어떤 용어가 있는지 모를 때 먼저 사용한다."""
    return "\n".join(f"- {item['term']}" for item in TERMS)


if __name__ == "__main__":
    mcp.run()  # 기본이 stdio. 원격 HTTP는 mcp.run("streamable-http")
