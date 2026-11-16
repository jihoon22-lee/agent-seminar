# 글꼴

발표 자료에 쓰는 글꼴은 아래 원본에서 **발표에 나오는 글자만 남기고 줄인(subset)** 파일입니다.

| 파일 | 원본 | 바꾼 이름 |
|---|---|---|
| `seminar-sans-400/600/700.woff2` | IBM Plex Sans KR (Regular, SemiBold, Bold) | Seminar Sans KR |
| `seminar-mono-400/600.woff2` | IBM Plex Mono (Regular, SemiBold) | Seminar Mono |

원본은 SIL Open Font License 1.1로 배포되며 "Plex"가 예약 글꼴 이름(Reserved Font Name)입니다.
글자를 줄이는 것도 수정에 해당하므로, 라이선스 조건에 따라 글꼴 이름을 바꿨습니다.
라이선스 전문은 `OFL-IBMPlexSansKR.txt`, `OFL-IBMPlexMono.txt`에 있습니다.

슬라이드 글자가 바뀌면 `python tools/build_slides.py --fonts <원본 TTF 폴더>`로 다시 만듭니다.
이때 `fontTools`와 `brotli` 패키지가 필요합니다.
