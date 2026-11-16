# 글꼴

발표 자료에 쓰는 글꼴은 아래 원본에서 **발표에 나오는 글자만 남기고 줄인(subset)** 파일입니다.

| 파일 | 원본 | 바꾼 이름 |
|---|---|---|
| `seminar-sans-400/600/700.woff2` | IBM Plex Sans KR (Regular, SemiBold, Bold) | Seminar Sans KR |
| `seminar-mono-400/600.woff2` | IBM Plex Mono (Regular, SemiBold) | Seminar Mono |

원본은 SIL Open Font License 1.1로 배포되며 "Plex"가 예약 글꼴 이름(Reserved Font Name)입니다.
글자를 줄이는 것도 수정에 해당하므로, 라이선스 조건에 따라 글꼴 이름을 바꿨습니다.
라이선스 전문은 `OFL-IBMPlexSansKR.txt`, `OFL-IBMPlexMono.txt`에 있습니다.

## 슬라이드를 고친 뒤

`python tools/build_slides.py`만 실행해도 `slides/index.html`은 다시 만들어집니다(추가 패키지 없음).
다만 줄인 글꼴에 없는 글자를 새로 쓰면 그 글자만 시스템 글꼴(맑은 고딕 등)로 보입니다. 깨지지는 않지만 모양이 섞이니, 글자를 많이 바꿨다면 글꼴도 다시 줄이세요.

1. 원본 TTF 다섯 개를 한 폴더에 받습니다. Google Fonts의 IBM Plex Sans KR, IBM Plex Mono에서 받을 수 있습니다(저장소 `google/fonts`의 `ofl/ibmplexsanskr`, `ofl/ibmplexmono`).
   - `IBMPlexSansKR-Regular.ttf`, `IBMPlexSansKR-SemiBold.ttf`, `IBMPlexSansKR-Bold.ttf`
   - `IBMPlexMono-Regular.ttf`, `IBMPlexMono-SemiBold.ttf`
2. `pip install fonttools brotli`
3. `python tools/build_slides.py --fonts <그 폴더>`
