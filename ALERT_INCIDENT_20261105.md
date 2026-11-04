# 2026-11-05 최종 결과 알림 미수신

사용자 증상: 06:05 전후 장 마감 결과 대기 안내는 수신했으나 최종 결과를 받지 못함.

확인한 사실:
- GitHub run 41926090869 및 41919549143 계산 실패. 공개 status는 expected_date=2026-11-04 / state=error, snapshot은 2026-11-03에서 멈췄다.
- 실패를 재현하면 `BITO: price basis/handoff mismatch`가 발생했다. 공급자 자료가 2026-10-01 분배금 사건과 그 이전 수정주가 조정을 누락했다.
- 공식 ProShares 분배금 $0.017381, 동결 Yahoo 자료의 3자리 사건 표현은 $0.017이다. 원본이 사용하는 조정을 복원하면 60거래일 최대 일간 수익률 차이가 1.758824e-7로 기존 허용오차 1e-6 이내다.
- 복원은 BITO/해당 날짜/사건 누락/검증 불일치에 한해서만 시도한다. 이미 올바른 수정주가에는 적용하지 않으며, 사건이 존재하거나 복원 후 기존 검증을 통과하지 못하면 차단한다. 동결 prefix는 변경하지 않는다.
- 전체 회귀 116개 통과. 실제 최신 계산 2026-11-04 live/ready 성공.

공식 자료: https://www.proshares.com/our-etfs/find-proshares-etfs?product=Product+Overview+&search=&strategy=MoneyMarket

남은 확인:
- Firebase 푸시 설정은 없다. 결과 게시 후 폰의 조회가 실행되어야 최종 알림이 표시된다. 사용자 대기 안내 수신으로 로컬 예약 알림이 실행된 것은 확인되지만, 실제 최종 수신은 이번 서버 검증과 별개다.
- 최근 GitHub daily 실행에서 Cloudflare workflow_dispatch는 발견되지 않았다. Cloudflare 로그 접근은 브라우저 자동 승인 검토의 사용량 제한으로 거부되어 확인하지 못했다. 우회하지 않았다. 무료 Cloudflare 경로의 정상 운영을 이번 복구로 입증한 것은 아니다.
