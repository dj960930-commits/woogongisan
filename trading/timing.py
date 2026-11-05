"""Display-only loan timing research; never used by the order planner."""
FINGERPRINT = '843872c60ae50f38722e3b07a313ca54fa49308055a7b98230d45b3cb1ceb488'
RULE = 'loan-transition-A-v1'


def timing(current, previous, fingerprint):
    from models.registry import load_model
    # V2 changes only defense selection; this display-only attack transition
    # research retains the same state semantics. Unknown models stay rejected.
    supported = fingerprint in {FINGERPRINT, load_model('woogong-v2').fingerprint} and type(current) is int and type(previous) is int and current in range(5) and previous in range(5)
    phase = ('entry' if current == 0 and previous != 0 else
             'hold' if current == 0 else 'exit' if previous == 0 else 'wait') if supported else 'unavailable'
    labels = {'entry': '진입 조건 충족 · 차입 검토', 'hold': '공격 유지 · 신규 차입 대기',
              'exit': '공격 종료 · 차입분 상환 검토', 'wait': '방어 구간 · 신규 차입 대기',
              'unavailable': '규칙 검증 대기'}
    return {'rule_id': RULE, 'phase': phase, 'label': labels[phase], 'current_state': current,
            'previous_state': previous, 'supported': supported, 'research_only': True,
            'borrowing_approved': False,
            'entry_rule': '전 거래일 비공격 → 당일 공격(0), 확정 종가 기준. 다음 체결 전 공격 종료 시 취소.',
            'exit_rule': '첫 공격 종료 후 차입분 매도 → 결제·환전 후 상환. 잔존 원금·이자 완제 전 재차입 금지.',
            'scope': '풀매수는 공격 전환의 별칭입니다. 마통 한도 전액 사용이나 현금 0%를 뜻하지 않습니다.',
            'checks': '대출 잔액·미지급 이자·금리·상환 여력은 미확인입니다. 메리츠 잔고로 은행 부채를 확인할 수 없습니다.',
            'risk': '연구 기본안 17회 중 6회 손실. 이전 시기 대용 검증 최악 -17.38%는 손실 상한이 아닙니다. 차입 실행·주문 증액에는 연결되지 않습니다.'}
