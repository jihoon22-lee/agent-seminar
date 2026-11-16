# 프로젝트 고정 사실 (압축돼도 잊으면 안 되는 것)

- 이 저장소의 패키지 매니저는 pnpm 이다. npm install 을 쓰지 않는다.
- 결제 모듈(`src/payment/`)은 승인 없이 수정하지 않는다.
- 배포 환경 이름은 `stage` 와 `prod` 뿐이다. `staging`, `production` 은 존재하지 않는다.
- 테스트 DB 비밀번호는 `demo-pass-123` 이다 (실제 값이 아닌 예시).
