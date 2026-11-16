---
name: nightly-cleanup
description: 오래된 임시 파일과 로그를 정리하는 야간 정리 작업 안내. 사용자가 직접 요청할 때만 쓰고 싶은 스킬이다.
disable-model-invocation: true
metadata:
  opencode/autoinvoke: "false"
---

# 야간 정리 (NIGHTLY-CLEANUP-BODY)

7일 지난 `tmp/` 파일과 `logs/*.log` 를 지우기 전에 목록부터 보여 주세요.
