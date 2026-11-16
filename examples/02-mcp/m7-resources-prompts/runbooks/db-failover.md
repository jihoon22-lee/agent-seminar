# DB 장애 조치(failover) 런북

1. 복제 지연(`replication_lag`)이 5초 미만인지 확인한다.
2. 쓰기 트래픽을 점검 모드로 전환한다.
3. 대기(standby) 노드를 primary로 승격한다.
4. 애플리케이션 연결 문자열이 새 primary를 가리키는지 확인한다.
5. 이전 primary는 복구 후 standby로 재투입한다.
