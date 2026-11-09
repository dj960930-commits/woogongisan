"""Final historical research delivery: evidence, limits, reproducible specification."""
import json,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from research_defense_redesign import ROOT

OUT=ROOT/'release/model-research/studies/adaptive-validation'

def table(frame,fields):
    lines=['| '+' | '.join(t for k,t,fn in fields)+' |','|'+'|'.join(['---']*len(fields))+'|']
    for _,r in frame.iterrows():lines.append('| '+' | '.join(fn(r[k]) for k,t,fn in fields)+' |')
    return '\n'.join(lines)+'\n'

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    r=pd.read_csv(ROOT/'release/model-research/studies/past-selection/metrics.csv');boundary=pd.read_csv(ROOT/'release/model-research/studies/entry-boundaries/boundary_metrics.csv')
    init=pd.read_csv(ROOT/'release/model-research/studies/entry-boundaries/initialization_metrics.csv');u=pd.read_csv(ROOT/'release/model-research/studies/selection-uncertainty/block_diagnostics.csv')
    logs=pd.read_csv(ROOT/'release/model-research/studies/past-selection/selection_log.csv')
    names={'baseline':'기존','fixed_candidate':'초기 진입 후보 고정','annual_all':'모든 후보 연별 선택','monthly_all':'모든 후보 월별 선택',
        'quarterly36_all':'모든 후보 최근36개월 분기 선택','monthly_pair':'두 로직 월별 선택',
        'monthly_pair_closed3':'두 로직 월별·완료3회 요구','monthly_pair_entrygate':'두 로직 월별·진입 승인 고정',
        'monthly_pair_entrygate_closed3':'두 로직 월별·진입 승인·완료3회 요구'}
    basic=r[(r.period=='actual_BITO')&(r.window=='full')&(r['mode']=='next_open')&(r.slippage==0)]
    s='''# 여러 아이디어를 적용한 방어 로직 보완 연구 — 추가 검증 결론

2026-11-05. 사용자 목적은 손실 변동을 감수하더라도 장기 수익을 우선하는 것이다.

## 연구 결론

**검토 범위에서 과거 수익을 개선한 보완 후보와, 과거 정보만으로 두 로직을 선택하는 방법을 도출했다.** 가장 유망한 구조는 방어 초기에만 단기 개입을 허용하고, 월별로 기존 대비 비용 후 성과가 양수인지 확인해 다음 개입을 승인하는 것이다.

다만 실전 우위는 입증되지 않았다. 최근 실제 구간의 고정 후보 효과는2026년 두 번의 개입에 집중되고, 월별 승인도 완료 사례 한 번 뒤에 시작됐다. 블록 재표집과 여러 후보 탐색을 고려하면 통계적으로 확실한 우위라고 할 수 없다. 연구 결과를 운영 모델·자동매매에 적용하지 않았다.

## 보완 로직을 고정하면

1. 기본은 기존 EMA84/378 선택, 기존 현금 보호, 기존 공격/방어 전환을 따른다.
2. 공격 상태0에서 정상 방어2/3/4로 바뀌는 날, 기존 선택이 금이면 단기 개입을 평가한다.
3. GLD/BRK 비율의 EMA5가 EMA21보다 낮고 장기 금 우위가21거래일 전보다 줄었다면 후보는 버크셔다.
4. 개입 후 단기가 다시 금을 선택하면 기존 배분으로 돌아간다. 같은 방어 구간 중간에 새 개입을 반복하지 않는다.
5. 공격 재진입·기존 현금 대피·강제 잠금·기존 자산 선택 변경이 우선한다. 기존 현금 비중은 보존한다.

이렇게 하면 단기 지표가 흔들릴 때마다 보유 자산을 전량 왕복하는 행동을 줄인다. 코드와 별개로 개입 구간을 재구성한 목표 비중도 일치했다.

## 두 로직의 선택법

월초마다 직전까지 완료된 월별 자료만 사용한다. 최소24개월이 필요하며, 기존 유지와 위 후보를 같은 거래정책·비용으로 실행한 가상 장부의 월별 로그수익 차이를 계산한다. 평균 차이가 양수일 때만 후보에 승인 권한을 준다. 승인 자체는 방어 개입 시작 시점에 확인하고, 그 구간이 끝날 때까지 고정한다. 이후에 승인이 생겼다는 이유로 진행 중인 구간에 뒤늦게 합류하지 않는다.

더 보수적인 대조군은 최소3개의 완료된 개입 기회까지 요구했다. 이 숫자는 연구용 표본 제한이며 통계적 신뢰수준을 보장하지 않는다.

실제 구간의 월별 선택기는2026년6월 결과가 확정된 뒤7월부터 후보를 승인했다. 그 이전에는 기존을 유지했고,10월에 후보를 사용했다. 이는 **규칙을 미리 정해두었다고 가정한 과거 재현**이다. 해당 규칙을 실제로6월 전에 발견했거나 실거래했다고 주장하지 않는다. 후보 자체가2026년을 본 뒤 선택됐다는 편향은 남는다.

## 최근 실제 구간

2021-10-20~2026-10-20, 달러, 다음 거래일 시가, 편도 수수료0.1%, 분배금·현금이자·자기금융·12.5%p 밴드. 세금·환전·시장충격·장중 낙폭 제외.

'''
    fields=[('model','정책',lambda x:names[x]),('cagr','연복리',lambda x:f'{x:.2%}'),('mdd','최대낙폭',lambda x:f'{x:.2%}'),('trade_days','매매일',lambda x:str(int(x)))]
    s+=table(basic,fields)+'\n'
    s+='''많은 후보 중 과거 최고 성적을 자주 골라 바꾸는 방법은 손해였다. 반면 두 로직으로 후보를 제한한 월별 승인 방식은49.21%였고, 개입 시작 승인 고정 방식도 실제 구간에서는 같았다. 엄격하게 완료3회를 요구하면 실제 구간에서는 기존을 유지했다. 단순히 월별 갱신이 좋아졌다는 일반 결론은 아니다.

## 비용·지연과 장기 자료

'''
    q=r[(r.window=='full')&r.model.isin(['baseline','monthly_pair_entrygate'])]
    s+=table(q,[('period','자료',str),('model','정책',lambda x:names[x]),('mode','체결',str),('slippage','추가 슬리피지',lambda x:f'{x:.2%}'),('delay','지연 거래일',lambda x:str(int(x))),('cagr','연복리',lambda x:f'{x:.2%}'),('mdd','최대낙폭',lambda x:f'{x:.2%}')])+'\n'
    s+='''장기 자료는2015년7월부터이며 상장 전 BITO가 BTC 대체 가격인 합성 경로다. 실제 구간과 독립 표본으로 합치거나 절대 수익률을 직접 비교하지 않는다. 엄격한3회 승인도 장기 자료에서는2020·2021·2026년의 완료 기회 세 개를 센 뒤10월 후보를 사용할 수 있었다.

## 날짜 경계와 시작 조건

방어 초기에 한 번만 개입하되, 최초1일/2일/3일/5일 동안 진입 기회를 허용하는 대조를 했다. 별도로 방어2일째 또는3일째에만 판단하는 경우도 비교했다. 이는 민감도 점검이며 사후 최고값인5일 창을 새 대표 정책으로 바꾸지 않았다.

'''
    s+=table(boundary[boundary.slippage==0],[('period','자료',str),('model','진입 창',str),('cagr','연복리',lambda x:f'{x:.2%}'),('relative_final','기존 대비 마지막 자산',lambda x:f'{x:+.2%}')])+'\n'
    s+='''초기1~3일 허용 창은 실제 구간에서 같았고 장기 자료에서도 기본 조건의 개선이 유지됐다. 반면3일째만 판단하면 실제 구간은 기존보다 낮아졌다. '어느 날짜에 결정해도 같은 효과'는 아니며 신속한 진입 판단에 민감하다. 이는 기존 신호를3일 늦게 체결하는 실험과 다른 의사결정 규칙이다.

현금으로 시작하거나 같은 기존 포트폴리오를 이미 보유한 상태에서 시작하는 대조도 했다. 실제 자료의 여러 시작일에서 후보/기존의 마지막 자산 비율은 거의 같았다. 다만 동일한2026년 사건을 반복 포함하므로 여러 독립 성공 사례로 세지 않는다.

'''
    s+=table(init[(init.model=='day1')&(init.initial=='preowned_baseline')],[('period','자료',str),('start','시작일',str),('relative_final','기존 대비 마지막 자산',lambda x:f'{x:+.2%}')])+'\n'
    s+='''## 소수 사례와 선택 편향

기존 자료의 순차적 지표 탐색을 거쳐 후보를 골랐으므로 과거 우위가 우연일 수 있다. 이번 목표에서 비교한33개 전문가 정의(실제 구간에서는23개의 서로 다른 수익 경로)를 함께 놓고, 일별 비용 후 로그 초과수익을21일·63일 원형 블록으로2,000회 재표집했다.

아래는 과거 수익 차이의 재표집 백분위다. 미래 수익률의 신뢰구간이나 투자 성공 확률이 아니다. 연252거래일로 환산한 로그수익 차이이며, 위 표의 CAGR 차이와 단위가 다르다.

'''
    def pct(x):return f'{0 if abs(x)<1e-12 else x:+.2%}'
    s+=table(u,[('period','자료',str),('block_sessions','블록 길이',lambda x:str(int(x))),('primary_observed_annual_log_excess','관측 로그 초과수익',pct),('resampled_p025','재표집2.5백분위',pct),('resampled_p975','재표집97.5백분위',pct)])+'\n'
    s+='''실제 구간의 하단은0 부근이고, 장기 자료에서는 음수다. 평균을0으로 맞춘 뒤 후보군의 최대값을 재표집하는 보조 진단도 강한 우위 근거를 주지 않았다. 그 수치를 '과최적화일 확률'로 해석하지 않는다. 이전의 수많은 연구와 기존 모델 선택까지 포함한 완전한 보정도 아니다. 재표집은 관측한 드문 사례를 반복할 뿐 새로운 시장 국면을 만들어 주지 않는다.

방법론 배경은 [White의 데이터 재사용·모델 선택 연구](https://doi.org/10.1111/1468-0262.00152)다. 이번 단순 블록 진단을 그 논문의 가정과 이론을 모두 충족한 공식 검정이라고 주장하지 않는다.

## 전달할 보완안과 운영 판단

연구용 보완안은 **기존 유지＋방어 초기의 단기 개입＋두 로직만 비교하는 과거 성과 승인**으로 고정할 수 있다. 코드와 규칙·과거 성과·실행 제약은 확인했다. 하지만 예측 우위의 확실성은 부족하므로 실전 자동매매·정식 모델 승격을 권하지 않는다. 손실을 더 감수한다는 사용자 선호도 표본 부족을 해소하지는 않는다.

당장 후보군을 더 늘려 과거 최고 성적을 찾는 것보다, 규칙을 사전 고정한 이후 새 구간의 모의 기록을 기존 재검사와 분리하는 것이 다음 실전 승격 조건이다. 이는 미래 성과 확인의 조건이며 이번 역사적 연구가 그러한 성과를 이미 입증했다는 뜻은 아니다.

## 검증과 재현

- 생성한 모든 전문가 목표를 재실행한 NAV가 저장된 원장과 일치했다.
- 모든 선택 시점은 이전의 완료된 월만 사용했고, 미래 전문가 수익만 바꾸어도 과거 선택은 같았다.
- 방어 초기1일 정책은 이전 대표 후보와 같고, 새로운 시작 포트폴리오 원장의 현금 시작은 기존 원장과 일치했다.
- 과거 절단, 비중 합계, 공격 비중 불변 및 기존 기본 원장 재현 검사는 계속 유지했다.
- 실제 앱·모델 프로필·배포·주문 동작은 변경하지 않았다.

'''
    for folder,file,title in [('past-selection','metrics.csv','선택기 전체 지표'),('past-selection','selection_log.csv','날짜별 과거 선택 로그'),('entry-boundaries','boundary_metrics.csv','진입 경계 지표'),('entry-boundaries','initialization_metrics.csv','초기 보유·시작일 지표'),('selection-uncertainty','block_diagnostics.csv','재표집 진단'),('adaptive-audit','audit.json','원장·구간 독립 재검산')]:
        s+=f'- [{title}](../{folder}/{file})\n'
    s+='\n[앞 단계 전체 연구](../adaptive-research/report.md). 운영 코드와 별도로 저장한 연구 후보 사양은 candidate_spec.json에 있다.\n'
    (OUT/'report.md').write_text(s,encoding='utf-8')
    spec=dict(candidate_id='defense-entry-short-research-20261105',status='research_only_not_live',
        baseline='woogong-1.3-d',entry='state0 to normal defense2/3/4; baseline Gold; price-ratio GLD/BRK EMA5<EMA21; log(EMA84/EMA378) below21sessions ago',
        hold='until fast Gold, original risk/cash/forced-lock/asset change; no mid-episode re-entry',
        approval='previous complete-month net log excess>0 after24 months; check approval only at intervention entry',
        permission_variants=dict(permissive='no minimum closed-count beyond month history; exploratory',conservative='at least3 completed counterfactual intervention opportunities'),
        orders_enabled=False,live_approved=False,future_superiority_proven=False,
        source_files=['tools/research_bounded_intervention.py','tools/research_past_selection.py'],
        constraints=['preserve original cash budget','preserve attack timing','do not execute on same close as signal'],
        limitations=['post2026 candidate selection','only2 recent interventions, one ongoing','partial-family uncertainty does not establish predictive superiority'])
    (OUT/'candidate_spec.json').write_text(json.dumps(spec,indent=2),encoding='utf-8')
    sources=[ROOT/'tools'/n for n in ['adaptive_family.py','research_past_selection.py','research_entry_boundaries.py','research_selection_uncertainty.py','research_bounded_intervention.py','report_adaptive_validation.py']]
    (OUT/'manifest.json').write_text(json.dumps(dict(code_hashes={str(x):hashlib.sha256(x.read_bytes()).hexdigest() for x in sources},
        result_files=['../past-selection/metrics.csv','../entry-boundaries/boundary_metrics.csv','../selection-uncertainty/block_diagnostics.csv'],
        scope='historical improvement candidate and selection research; no claim of reliable future outperformance'),indent=2),encoding='utf-8')
    print('Saved report.md, candidate_spec.json and manifest.json')

if __name__=='__main__':main()
