# 우공이산 GitHub 연결

- 저장소: https://github.com/dj960930-commits/woogongisan
- 신호/화면 주소: https://dj960930-commits.github.io/woogongisan/
- GitHub 설정 → Pages → Build and deployment → Source: GitHub Actions
- 첫 배포: `Publish Woogongisan` Actions. `main` 코드 변경 시 테스트 후 정적 화면을 게시한다.
- 종가 갱신: `Woogong close calculation` Actions. NYSE 일정·완료 종가를 확인해 새 결과를 계산하고 게시한다.

## 메리츠 연결 확인

2026-10-26 개인 PC에서 숨김 입력으로 인증하고, QQQ·TQQQ·BRK.B·GLD·SOXL·BITO의
2026-10-23 일봉 조회를 확인했다. 계좌 조회·주문은 실행하지 않았다. 키는 파일과 GitHub에 저장하지 않았다.

메리츠 시세의 수정주가는 원본 모델의 SOXL/BITO 분배금 조정 계약과 같지 않아 공용 모델 시세로 사용하지 않는다.
Android의 메리츠 연결은 계좌·잔고 조회용으로 유지하고, 공용 모델은 별도 키 없이 Yahoo Finance와 Bitstamp로 계산한다.

다시 확인하려면 로컬에서 `./check_meritz.ps1`을 실행하고 App Key와 App Secret을 숨김 입력한다.
결과는 업로드에서 제외되는 `runtime/meritz-market-check.json`에 저장된다.
조회 도구는 해외 일봉 경로만 사용하며 계좌·주문 API는 호출하지 않는다.
현재 도구는 키를 유지하지 않으므로 상시 실행 서버의 비밀정보 설정은 별도다.
메리츠 계좌 키를 공개 소스·Pages·GitHub Secrets에 넣거나 APK에 내장하지 않는다. 사용자가 휴대폰 연결 화면에서 입력하는 키는 기기에만 암호화 저장한다.

## 모델 자동 계산 · 추가 키 불필요

`Woogong close calculation`은 미국장 완료 종가를 자동 조회·검증·계산·배포한다.
수동 Run workflow는 같은 거래일에도 공급자에 실제 재조회한다. 예약 실행은 이미 계산한 같은 거래일을 생략한다.
TIINGO_TOKEN 등록은 필요하지 않으며 더 이상 이 파이프라인에서 읽지 않는다.

원본 계약은 QQQ·TQQQ·BRK.B·GLD의 종가와 SOXL·BITO의 수정종가를 혼합한다.
`market_data.py`가 이 계약을 명시하고 원본 2026-10-20까지의 데이터는 변경하지 않는다.
이어붙이는 기준점 전 60거래일의 수익률 차이는 1e-6 이하여야 하며 모든 최신 거래일을 검사한다.
그 이전에 발견되는 공급자 과거 수정은 보고서에 기록하고 원본을 보존한다. BTC는 완료 UTC 일봉만 사용하며
기존 모델의 하루 이동 규칙을 유지한다. 전체 겹침·최신 검증 결과는 공개 `data-validation.json`에서 확인할 수 있다.

`status.json`의 `state: ready`와 최신 완료 미국 거래일을 함께 확인한다. 조회·가격기준·거래일 누락 오류가 있으면
이전 snapshot을 보존하고 `state: error`로 표시하며 마지막 배포 후 Actions 검사도 실패한다.
모델 본운용 승인과 실주문 허용 값은 계속 false다.

## 앱 연결

0.5.2부터 위 주소를 기본 결과 서버로 사용한다. 기존 버전은 설정 → GitHub Pages 연결에
`https://dj960930-commits.github.io/woogongisan`을 저장하고 최신 결과를 확인한다.
모델 결과 주소이므로 메리츠 인증키나 개인 자산을 전송하지 않는다.
0.6.0 Android의 **내 자산 → 메리츠 계좌**는 메리츠에 직접 연결한다. 키는 그 화면에 입력하며
기기에 암호화 저장한다. Pages 연결 설정에 메리츠 키를 넣지 않는다.
설정의 ‘우공이산 기본 주소로 복구’로 잘못 저장한 결과 주소를 복구할 수 있다.
메리츠 잔고·주문을 담당하는 개인 HTTPS 서버는 별도이며 GitHub Pages에서는 실행되지 않는다.

Firebase 푸시는 선택 사항이다. 사용할 때만 `GOOGLE_SERVICES_JSON`,
`FIREBASE_SERVICE_ACCOUNT_JSON`, `FCM_TOKENS`를 별도 설정한다.
개인 계좌 DB, 메리츠 인증키, 서버 토큰, 개발 도구·캐시는 이 저장소 업로드 대상에서 제외한다.

## 0.6.1 장 마감 알림

Firebase 등록이 없어도 새 확정 종가를 읽으면 기기에서 알림을 생성한다. 백그라운드 조회는 약 30분 간격이며 Android 절전·통신과 GitHub 게시 지연에 따라 늦어질 수 있다. 정각 알림 기능은 아니다. 모델 지문+미국 거래일로 중복을 막고 예시·오류·만료 결과는 알리지 않는다.
앱 설정 → 장 마감 알림에서 켜기/끄기·권한 확인·테스트가 가능하다. 테스트는 실제 결과의 발송 기록을 소비하지 않는다. 알림 허용은 휴대폰에서 사용자가 결정한다.
