# 상시 계산 서버 배포

현재 상태: 코드와 로컬 검증 완료를 목표로 준비한 구성이다. Render 서비스 생성·유료 자원·운영 URL 전환은 별도 연결 및 승인 후 진행한다. 운영 서버가 이미 배포됐다는 뜻이 아니다.

## 구성

`render.yaml`은 Python 상시 웹 서비스 1개와 영구 디스크 1GB를 정의한다. `python model_server.py --host 0.0.0.0` 한 프로세스 안에서 계산 스케줄러와 읽기 전용 API를 운영한다. GitHub Actions 예약·Pages 배포를 거치지 않고 공개 결과를 저장한다. 배포된 Python 3.12 환경에서 `requirements.txt`를 설치한다.

뉴욕 거래 일정은 기존 `pipeline.session()`을 사용한다. 장 마감 5분 뒤부터 30초 간격으로 최신 완료 거래일을 확인한다. 아직 시세가 없으면 같은 모델의 이전 공개 결과를 보존하고 상태를 오류/대기로 표시한다. 완료된 같은 거래일은 다시 계산하지 않는다. 조기 폐장과 서머타임은 NYSE 캘린더에 따른다. 시세 제공 지연·서버 장애까지 없애는 SLA는 아니다.

기존 계산기를 별도 프로세스로 실행하며 `WOOGONG_SITE_DIR`로 후보 결과를 임시 디렉터리에 격리한다. 모델 지문·가격 계약·거래일·만료·주문 잠금·배분·확장 백테스트를 검사한 후 하나의 `current.json`을 원자적으로 교체한다. 영구 상태는 `WOOGONG_STATE_DIR=/var/data/woogong`에 보관한다. 재시작해도 마지막 검증 결과와 발송 기록은 유지된다. 한 서비스만 같은 디스크를 사용하며 프로세스 잠금으로 중복 스케줄러를 막는다.

공개 API에는 모델 결과만 있다. 메리츠 키·계좌·주문 경로·임의 파일 읽기·원격 계산 실행 API를 제공하지 않는다. HTTP 동시 처리는 16개로 제한한다. 인터넷 HTTPS는 Render가 종료하고 내부 Python 포트로 전달한다.

## 계정과 비용 확인

1. Render를 연결하고 사용할 워크스페이스를 선택한다.
2. 이 저장소의 `render.yaml` 구성을 검토한다. 기존에 같은 이름의 서비스가 있으면 새로 덮어쓰지 말고 먼저 확인한다.
3. 소유자의 비용 승인 뒤 자원을 생성한다. 2026-11-02 공식 가격 기준 `0.5c-512mb` 서버는 월 $7, 디스크는 GB당 월 $0.25이므로 이 구성의 기본 증분 비용은 **월 $7.25**다. 세금·추가 전송량·워크스페이스 요금은 별도이며 생성 화면에서 다시 확인한다.
4. 무료 웹 서비스는 유휴 시 잠들어 같은 목적을 충족하지 못하므로 이 구성에 무료 플랜을 대신 적용하지 않는다.

공식 문서: [요금](https://render.com/pricing), [Blueprint](https://render.com/docs/blueprint-spec), [영구 디스크](https://render.com/docs/disks), [무료 서비스 제한](https://render.com/docs/free).

## 배포 후 필수 확인

- `/healthz`가 200이고 `scheduler_running=true`인지 확인한다.
- `/bundle.json`의 `documents.status.json.state=ready`, `market_date`가 최신 완료 미국 거래일인지 확인한다.
- `snapshot.json`, `model.json`, `status.json`의 모델 지문이 원본과 같은지 확인한다.
- 재시작한 뒤 같은 generation과 결과가 유지되는지 확인한다. 테스트 목적으로 날짜를 바꾸거나 결과를 최신으로 가장하지 않는다.
- 실패 상태에서 기존 snapshot이 남고 status가 대기로 표시되는지 검증한다.
- 연결할 서버 URL을 Android 설정 → 모델 결과 HTTPS 주소에 저장한다. 현재 0.6.4도 개별 JSON 경로를 읽을 수 있다. 준비 중인 0.6.5는 단일 bundle을 읽어 세대 혼합을 피하고, 계산 대기에서는 짧은 재시도를 한다.
- Android에 실제 서버 주소가 연결되고 실거래일의 게시 시각을 확인하기 전에는 기존 GitHub 예약을 끄지 않는다. GitHub 코드는 계속 원본으로 보관한다.

`/status.json`의 `publication`에는 마지막 시도·성공 시각·푸시 상태만 담긴다. 인증키나 토큰은 공개하지 않는다. `close_to_publish_seconds`는 초기 배포 때 이전 금요일을 다시 계산한 경우에도 그 금요일 종가부터 계산되므로 정상 연속 운용 지연과 구분한다.

## 즉시 푸시

결과를 공개한 뒤에만 기존 `notify.py`를 호출한다. 발송 기록은 영구 디스크 `outbox/`에 두며 실패한 발송은 다시 시도한다. 다음 두 환경 변수는 Render 비밀 환경 변수로 직접 등록한다. 값은 소스·채팅·공개 API에 넣지 않는다.

- `FIREBASE_SERVICE_ACCOUNT_JSON`: 해당 Firebase 프로젝트의 서버 발송 인증 정보
- `FCM_TOKENS`: 허용한 개인 Android 기기의 토큰 목록(JSON 배열)

Android APK도 같은 Firebase 프로젝트의 `google-services.json`으로 빌드돼야 한다. 현재 운영 APK에는 이 구성이 없으므로 서버만 배포해도 즉시 푸시가 자동 연결되는 것은 아니다. 구성 전에는 `push_state=not_configured`이며 앱의 마감 예약·보조 조회가 사용된다. 메리츠 자격증명은 이 서버에 등록하지 않는다.

## 로컬 검증

```powershell
python -m pytest tests -q
python model_server.py --once --state runtime/model-server-smoke
python model_server.py --host 127.0.0.1 --port 8780 --state runtime/model-server-smoke
```

일회 실행은 푸시를 보내지 않는다. 장중의 미완료 가격으로 새 거래일을 만들지 않는다. 원본 `site/`는 수정하지 않고 검증한 결과만 지정한 state에 기록한다.
