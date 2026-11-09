"""Current evidence and unfinished validation for the active research goal."""
import json
import numpy as np
import pandas as pd
from research_defense_redesign import ROOT

OUT=ROOT/'release/model-research/studies/adaptive-research'

def table(frame,fields):
    lines=['| '+' | '.join(t for k,t,fn in fields)+' |','|'+'|'.join(['---']*len(fields))+'|']
    for _,r in frame.iterrows():lines.append('| '+' | '.join(fn(r[k]) for k,t,fn in fields)+' |')
    return '\n'.join(lines)+'\n'

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    a=pd.read_csv(ROOT/'release/model-research/studies/adaptive-defense/metrics.csv');b=pd.read_csv(ROOT/'release/model-research/studies/adaptive-context/metrics.csv');c=pd.read_csv(ROOT/'release/model-research/studies/bounded-intervention/metrics.csv')
    q=c[(c.scope=='portfolio')&(c.window=='full')&c.model.isin(['baseline','entry_only'])]
    ids=['period','mode','slippage','delay','cash_zero'];wide=q.pivot(index=ids,columns='model',values='cagr').reset_index();wide['delta_pp']=(wide.entry_only-wide.baseline)*100
    wide.to_csv(OUT/'candidate_robustness.csv',index=False)
    audit=pd.read_csv(ROOT/'release/model-research/studies/adaptive-audit/leave_one_out_metrics.csv');intervals=pd.read_csv(ROOT/'release/model-research/studies/adaptive-audit/intervention_intervals.csv')
    latest=pd.read_csv(ROOT/'release/model-research/studies/execution-refresh/metrics.csv')
    fields=[('period','자료',str),('mode','체결',str),('slippage','추가 슬리피지',lambda x:f'{x:.2%}'),('delay','거래일 지연',lambda x:str(int(x))),('cash_zero','현금금리0 가정',str),('baseline','기존 연복리',lambda x:f'{x:.2%}'),('entry_only','후보 연복리',lambda x:f'{x:.2%}'),('delta_pp','차이',lambda x:f'{x:+.3f}%p')]
    text='''# 방어 로직 보완 연구 — 현재 증거와 남은 검증

2026-11-05. 사용자 목표: 여러 아이디어를 적용해 보완 방법 탐색. 장기 수익 우선.

## 현재 판단

서로 다른 원리를 적용한 세 단계 연구에서 **공격→방어 전환 시점에만 단기 개입을 허용하는 후보**를 찾았다. 현재 고정 데이터의 14개 기본·비용·지연 시나리오 모두에서 기존보다 연복리가 높았다. 주문 목표 갱신이라는 별도 실행 가정에서도 개선 방향이 유지됐다.

다만 최근 실제 구간의 증분은 2026년 두 구간에만 집중되며, 10월 구간은 데이터 종료 시점에 아직 진행 중이다. 과거만 보고 이 규칙을 선택할 수 있었는지와 통계적 불확실성 검토는 남아 있다. **보완 후보를 찾은 단계이며 정식 모델 승격·미래 우위 검증 완료가 아니다.** 연구 목표는 계속 진행 중이다.

## 적용한 아이디어

1. **추세 표현 변경:** 가격비율 대신 로그비율 EMA, 극단 일별 변화의 변동성 기준 절삭. 새 선택에 맞춰 Cross/D25를 다시 계산했다.
2. **상황별 속도:** 추세 효율성, 회귀 기울기, 변동성으로 표준화한 CUSUM, 과거 가격 채널 돌파를 비교했다. 지표 값은 예측 확률이나 검정 유의수준으로 해석하지 않는다.
3. **비중과 시장 상황:** 효율성에 비례한 부분 개입, QQQ 장기 추세·변동성·방어 상태·장기 지표 예상 교차 시점으로 진입을 제한했다. 문맥은 진입 시 판단하고 보유 규칙은 따로 고정했다.
4. **개입의 손해 제한:** 단기 개입의 상대 손실·상대 고점 대비 손실 중단, 실제 신호 보유일, 방어 진입 시에만 선택하는 방식을 비교했다.
5. **실행 가정:** 연기된 주문이 예전 목표를 유지하는 경우와, 예정 체결 시점까지 최신의 직전 종가 목표로 갱신·취소하는 경우를 같은 기준으로 비교했다.

1차16개 신규 정책, 2차9개 문맥 정책, 3차7개 보완 정책과 기존 단기 대조군을 검토했다. 일부 정책은 같은 거래를 만들어 결과가 같았다. 각 정책이나 비용 조건을 서로 독립된 성공 사례로 세지 않는다. 순차적으로 결과를 보고 설계한 연구이므로 선택 편향이 있다.

## 현재 대표 후보: entry_only

- 공격 상태0에서 정상 방어 상태2/3/4로 바뀌는 그날만 단기 개입을 판단한다.
- 기존 선택이 GLD이고, GLD/BRK 비율의 EMA5가 EMA21보다 낮아 단기는 BRK를 선택하며, 기존 장기 금 우위 `log(EMA84/EMA378)`가 21거래일 전보다 줄었을 때 BRK로 전환한다.
- 이후 단기가 다시 금을 선택하면 기존 배분으로 돌아간다. 같은 방어 구간 중간에 다시 새 개입을 시작하지 않는다.
- 공격 재진입, 강제 잠금 state1, 기존 선택 변경·현금 대피는 그대로 따른다. 원래 현금 예산을 유지하고 투자된 방어 예산만 옮긴다.
- 금→BRK에만 적용한다. 반대 방향까지 무조건 확장하면 성과가 나빠졌던 기존 연구를 반영한 비대칭 연구 가설이다.

이 규칙의 주요 차이는 단기 EMA를 더 짧게 만든 것이 아니라 **전환을 허용하는 시점과 재진입 횟수**다. 방어 중간의 모든 상대강도 반등을 새 매매로 만들지 않는다.

## 수익·비용·지연

실제 BITO 구간은2021-10-20~2026-10-20, 달러 기준이다. 편도 수수료0.1%, 분배금·현금이자·자기금융·12.5%p 리밸런싱 밴드를 반영했다. 슬리피지는 별도 추가 비용이다. 세금·환전·시장충격·장중 낙폭은 제외했다.

'''
    text+=table(wide,fields)+'\n'
    text+='''기본 실제 구간의 최대낙폭은 둘 다 −17.25%, 매매일은78→77일이었다. 2015 장기 자료는 상장 전 BITO를 BTC 가격 대용으로 합성한 경로다. 2012 조건부 확장은 동결 주식 신호 종가·전날 UTC BTC 가격을 실행 대용으로 사용한다. 이 세 자료의 절대 수익률을 같은 실적처럼 합치지 않는다. 모든 기간은 이미 여러 차례 살펴본 자료다.

## 개선의 집중도

전체 신호 역사에서 실제로 원래 배분과 달라진 구간은 다음과 같다. 이는 독립적인 실계좌 거래가 아니라 목표 차이가 발생한 구간이다.

'''
    text+=table(intervals,[('start','시작',str),('end','종료 신호',lambda x:'진행 중' if pd.isna(x) else str(x)),('ongoing','진행 중',str)])+'\n'
    text+='''최근 실제 구간에는2026년6월과10월 두 구간만 해당한다. 2025년 말까지의 실제 구간 성과는 기존과 완전히 같았다.

'''
    aq=audit[(audit.period=='actual_BITO')&(audit['mode']=='next_open')&(audit.slippage==0)&audit.model.isin(['baseline','entry_only'])]
    text+=table(aq,[('model','정책',str),('window','범위',str),('cagr','연복리',lambda x:f'{x:.2%}'),('relative_final','기존 대비 마지막 자산',lambda x:f'{x:+.2%}')])+'\n'
    text+='''현재10월을 빼도 9월 말까지 상대 자산은 +2.36%였지만, 이는 한 번의 완료된6월 구간에서 나온 효과다. 전체 마지막 자산 차이 +7.96%에는 진행 중인10월 효과가 포함된다. 이 두 사례를 근거로 일반적인 예측 승률을 제시하지 않는다.

## 실행 방식도 바꾸어 보면

아래는 기존과 후보에 모두 같은 '최신 목표 갱신' 규칙을 적용한 별도 가정이다. 예정 체결 시점을 미루지는 않고, 체결 이전 종가까지 알려진 목표만 갱신하거나 필요 없으면 취소한다. 당일 시가에 당일 종가 신호를 사용하지 않았다.

'''
    l=latest[(latest.execution=='latest_target')&(latest.delay==3)&latest.model.isin(['baseline','entry_only'])]
    text+=table(l,[('period','자료',str),('mode','체결',str),('model','정책',str),('cagr','연복리',lambda x:f'{x:.2%}'),('mdd','최대낙폭',lambda x:f'{x:.2%}')])+'\n'
    text+='''실제 시가의3일 지연에서는 후보 수익이 조금 높지만 낙폭은 기존보다 약1.01%p 커졌다. 기본 가정의 낙폭 동일을 모든 실행 가정으로 확대하지 않는다. 최신 목표 갱신이 모든 전략을 개선하는 것도 아니었다. 앱의 실제 주문 동작을 수정한 실험은 아니다.

## 독립 재검산

- 진입 조건과 종료 조건으로 개입 구간을 별도로 재구성한 목표 비중이 원래 상태머신 결과와 일치했다.
- 과거 구간 절단·미래 가격 변조 후 과거 목표 불변, 공격 비중 동일, 비중 합계와 음수 제약을 통과했다.
- 기존 실제·장기 원장의 NAV를 재현했다.
- 보관된 별도 `portable_replay.run` 원장으로 새 후보·구간 제거 후보들을9개 시나리오에서 재검산했다. 동일 NAV를 확인했다.
- 지연1일에서는 저장 목표 방식과 최신 목표 방식이 일치했고, 미래 목표만 바꿔도 과거 NAV는 변하지 않았다.

이 검사는 구현·인과성·비용 계산에 관한 것이다. 새로운 경제적 예측 능력이나 통계적 유의성을 증명하는 검사는 아니다.

## 아직 남은 검증

1. 새 후보군을 과거만으로 선택했을 때도 개선되는지 확인한다. 특히2026년 성과를 보고 고른 규칙이므로 그 전 정보만으로 승인할 수 있었는지 따로 봐야 한다.
2. 소수 개입 구간에 집중된 이익과 여러 후보를 고른 선택 편향을 정량화한다. 같은 자료의 비용 시나리오를 독립 표본으로 취급하지 않는다.
3. 초기 조건·가격 기준·의사결정 경계에 조금 다른 가정을 적용해 특정 날짜에만 민감한 개선인지 확인한다. 같은 역사에 조건을 무한히 붙이는 탐색은 제한한다.
4. 연구 후보를 사전 고정한 이후의 새 자료 기록은 기존 재검사와 분리한다. 아직 실제 미래 성과를 관측한 것은 아니다.

## 재현 자료

'''
    for folder in ['adaptive-defense','adaptive-context','bounded-intervention','execution-refresh','adaptive-audit']:
        text+=f'- [{folder}](../{folder}/): 코드·지표·프로토콜 및 해당 감사 결과.\n'
    text+='\n[후보 전체 강건성 표](candidate_robustness.csv). 운영 모델·앱·배포·실제 주문은 변경하지 않았다.\n\n'
    text+='원리 참고: [Kaufman 효율성 비율 설명](https://www.metatrader5.com/en/terminal/help/indicators/trend_indicators/ama), [NIST CUSUM 설명](https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc323.htm). 본 연구의 임계값이나 성과를 보증하는 자료는 아니다.\n'
    (OUT/'report.md').write_text(text,encoding='utf-8')
    state=dict(goal='여러 아이디어를 적용해서 보완방법을 찾아봐.',status='candidate_found_validation_incomplete',
        primary_candidate='entry_only',evidence=dict(positive_canonical_scenarios=int((wide.delta_pp>0).sum()),total_scenarios=len(wide),
            recent_interventions=2,completed_recent_interventions=1),remaining=['past-only selection of new candidates','concentration and selection-bias uncertainty','boundary and initialization sensitivity'])
    (OUT/'research_state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(state,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
