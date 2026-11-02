# 무료 장 마감 실행 예약

Cloudflare Workers Free의 Cron이 GitHub Actions `daily.yml`을 호출한다. 계산과 공개 결과 배포는 기존 GitHub에서 실행하며, 유료 Render 서버는 보류 상태다.

## 설정

1. `python tools/build_free_scheduler.py`로 단일 배포 코드 `release/free-scheduler-worker.mjs`를 생성한다.
2. Cloudflare Worker `woogongisan-close-scheduler`에 코드를 배포한다.
3. GitHub fine-grained PAT을 **eastgenie0909-cell/woogongisan 한 개**, **Actions read/write** 권한으로 직접 발급한다. 토큰을 코드·저장소·채팅에 넣지 않는다.
4. Cloudflare Worker의 암호화 Secret `GITHUB_TOKEN`에 직접 저장한다. 기존 PC Git 인증 토큰을 복사하지 않는다.
5. Cron Trigger `*/5 17-23 * * 1-5` (UTC)를 추가한다. 토큰 만료 전에 교체한다.

NYSE 정규장·조기폐장·휴장·서머타임 달력으로 장 마감 5분 뒤부터 90분까지 확인한다. 이미 게시되었거나 최근 20분 내 실행이 있으면 중복 요청하지 않는다. 달력은 2030-12-31까지 포함한다. HTTP 엔드포인트는 404만 반환하며, 외부 요청으로 계산을 실행할 수 없다.

GitHub도 요청 날짜와 최신 완료 거래일을 비교하고 이미 계산한 자료는 건너뛴다. 기존 GitHub 예약은 보조 경로로 유지한다. Cloudflare와 GitHub 모두 실행 시각을 보장하지 않으며, 공급자 자료 준비 시간도 영향을 준다.

## 검증 및 운영 상태

- 로컬 Python 109개, Android 70개, 무료 예약 Node 회귀 검사 통과.
- Cloudflare 코드 배포 확인: 2026-11-02, 버전 `4a877b8e`. Secret과 Cron 연결은 별도로 완료 확인해야 한다.
- 수동 GitHub dispatch 실측: 요청부터 실행 시작 약 15초, 게시 완료 약 58초(1회 측정). 보장 시간이 아니다.
- Firebase 푸시 인증과 실제 휴대폰 수신은 아직 검증되지 않았다. 서버 게시 개선과 휴대폰 즉시 푸시는 별도다.
