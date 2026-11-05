"""Create a reviewable chart-hint research report from saved outputs."""
import json
import numpy as np
import pandas as pd
from research_chart_hints import ROOT,OUT,RAW,CONFIGS

def table(df,fields):
    lines=['| '+' | '.join(t for k,t,fmt in fields)+' |','|'+'|'.join(['---']*len(fields))+'|']
    for _,r in df.iterrows():lines.append('| '+' | '.join(fmt(r[k]) for k,t,fmt in fields)+' |')
    return '\n'.join(lines)+'\n'

def main():
    m=pd.read_csv(OUT/'metrics.csv');t=pd.read_csv(OUT/'october_timeline.csv',index_col=0,parse_dates=True)
    e=pd.read_csv(OUT/'failure_features.csv');nav=pd.read_csv(OUT/'nav_actual_BITO_next_open.csv',index_col=0,parse_dates=True)
    first=[]
    for name,rule,w,sym in CONFIGS:
        test=t.loc['2026-10-02':];days=test.index[(test.state.isin([2,3,4]))&(test[name+'_brk']>test.baseline_brk+1e-9)]
        first.append(dict(model=name,first_october_brk_target=str(days[0].date()) if len(days) else None))
    pd.DataFrame(first).to_csv(OUT/'first_october_signal.csv',index=False)
    annual=[]
    for y in sorted(set(nav.index.year)):
        pos=np.flatnonzero(nav.index.year==y);lo=max(0,pos[0]-1);hi=pos[-1]
        for name in ['baseline','weak_flow','weak_flow_armed','all_hints_armed']:
            annual.append(dict(year=int(y),model=name,return_=nav[name].iloc[hi]/nav[name].iloc[lo]-1))
    pd.DataFrame(annual).to_csv(OUT/'selected_annual.csv',index=False)
    s='# 우공이산 차트·수학 힌트 기반 방어 조합 연구\n\n'
    s+='## 결론\n\n사용자가 제안한 상대강도 전환·금 추세 약화·일중 가격 움직임 차이는 수치화할 수 있었다. 기존 장기 로직에 결합한 연구 후보 중, 공격구간부터 방어 후보를 미리 추적하는 `weak_flow_armed`가 기본 실제 구간에서 연복리47.63→49.26%, 최대낙폭17.25%동일로 개선됐다. 그러나 다음종가·3일지연·2020이후합성장기 조건에서는 기존보다 낮았다. **유망한 사후 연구 후보이며 정식 승격안은 아니다.**\n\n'
    s+='공통 힌트가 있다는 것과 미래의 오답을 충분히 정확하게 구별할 수 있다는 것은 다른 주장이다. 기존 실패창의 단순 특징 빈도에서는 강한 공통 분리 근거를 확인하지 못했다. 최근 사례를 본 뒤 정의한 조건이므로 실제 구분 능력은 새 자료에서 확인해야 한다.\n\n'
    s+='## 10월2일 확인\n\n원본 보관 OHLC(아래 가격은 수정 종가 연결값이 아닌 일봉 원시 가격):\n\n|자산|시가|고가|저가|종가|시가대비 종가|CLV|\n|---|---:|---:|---:|---:|---:|---:|\n'
    for sym,ticker in [('BRK.B','BRK-B'),('GLD','GLD')]:
        row=pd.read_csv(RAW/f'{ticker}_prices.csv',index_col=0,parse_dates=True).loc['2026-10-02']
        clv=(2*row.close-row.high-row.low)/(row.high-row.low)
        s+=f'|{sym}|{row.open:.2f}|{row.high:.2f}|{row.low:.2f}|{row.close:.2f}|{row.close/row.open-1:+.2%}|{clv:+.3f}|\n'
    s+='\n10/2당일 BRK상승/GLD하락 차이는 확인된다. 5일 평균으로는 일중차이 확인이 늦어10/6에 조건이 처음 같이 나타났고, 바닥 다지기의 고점/저점 확정을 미래로 소급하지 않았다. 일봉만으로 저가가 발생한 시각이나 실제 매수주도 주문 흐름은 알 수 없다. 동일 날짜 종가로 계산한 신호는 그날 시가에 거래할 수 없다.\n\n'
    s+='## 수치 정의\n\n- R 상대강도: BRK/GLD비율의 EMA5>EMA21, 그리고5일 로그비율 수익>0. 역방향은 자산을 바꿔 대조.\n- G 금 약세: GLD종가<EMA10, 5일 로그수익<0.\n- S 급락: 5일 로그수익/(과거63일 일별 로그수익 표준편차×√5)<−1. G와 별개로 비교.\n- B 반등/바닥힌트: BRK종가>EMA10, 5일수익>0, 최근5일 최저종가가 직전5일 최저종가보다 높음. 종가 바닥의 대용치이며 실제 스윙 저점을 확정하는 조건이 아니다.\n- F 일중차이: h일 평균 log(C/O)가 BRK양수·GLD음수이며, BRK평균CLV>GLD평균CLV. CLV=(2C−H−L)/(H−L). h=5가 기본, 1·3일은 후속 민감도. 거래량이나 주문 흐름으로 매수세를 직접 검증한 것은 아니다.\n\n'
    s+='R/G/B/F를 모두 요구하거나 일부를 제거하는 대조 실험, 급락 조건, 다수결,3일확인,절반배분,역방향까지20개 정책을 비교했다. 기본5일 결과를 본 뒤 추가한1·3일 확인 및 준비추적 실험은 사후 후속 가설임을 protocol.json에 구분했다. 기간과 임계값을 넓게 최적화하지 않았다.\n\n'
    s+='## 결합과 보유 규칙\n\n기존 공격/방어 진입시점은 유지한다. 정상 방어2/3/4에서 기존이 금을 선택했을 때만 BRK로 일부/전량 전환한다. 기존 Cross/D25현금 예산은 유지하고 투자된 방어 예산만 바꾼다. state1강제잠금은 그대로 둔다.\n\n전환 후에는 상대강도가3일 연속 역전하거나 새 보유자산 자체가 약해지면 기존 배분으로 돌아간다. 공격재진입·기존현금대피·원래방어선택변경은 그대로 따른다. 후보에 따라서 양쪽약세 시 추가 현금 대피를 비교했다. 목표판정은 종가이며 실제 매매는 다음거래일·밴드·대기주문·수수료 영향을 받는다.\n\n'
    s+='준비추적(`armed`)은 공격구간에도 가상의 방어후보를 추적하지만 실제 공격비중은 변경하지 않는다. 10/2는공격상태, 10/12부터방어였다. 준비추적후보는10/12 BRK목표를만들어다음날10/13시가에실행가능했고, 방어진입후에만힌트를확인한weak_flow는10/13목표→10/14시가순서였다. 실제주문을낸것이아닌모의계산이다.\n\n'
    fields=[('model','정책',str),('cagr','연복리',lambda x:f'{x:.2%}'),('mdd','최대낙폭',lambda x:f'{x:.2%}'),('trade_days','매매일',lambda x:str(int(x)))]
    q=m[(m.period=='actual_BITO')&(m.window=='full')&(m['mode']=='next_open')&(m.slippage==0)]
    s+='## 실제구간 전체 결과\n\n2021-10-20~2026-10-20,달러,다음시가,편도수수료0.1%,현금이자/분배금/자기금융/12.5%p밴드. 미래 기대수익률이 아니다.\n\n'+table(q,fields)+'\n'
    s+='## 유망 후보의 체결·비용 한계\n\n'
    q=m[(m.period.isin(['actual_BITO','common_2020']))&(m.window=='full')&m.model.isin(['baseline','weak_flow_armed'])]
    s+=table(q,[('period','자료',str),('model','정책',str),('mode','체결',str),('slippage','추가슬리피지',lambda x:f'{x:.2%}'),('delay','지연거래일',lambda x:str(int(x))),('cagr','연복리',lambda x:f'{x:.2%}'),('mdd','최대낙폭',lambda x:f'{x:.2%}')])+'\n'
    s+='common_2020은 OHLC모두가준비된2020-01-31~2026-10-20,미국종가시각BTC를상장전BITO대용으로쓴합성구간이다. 2015부터는OHLC가없어F를쓰는후보는비교에서제외했다. 빈OHLC를추정해채우지않았다. 전구간세금·환전·시장충격·장중낙폭제외.\n\n'
    s+='## 기존 실패창과의 연관성\n\n기존평가창의시작일에만각힌트를측정한진단이다. 고정최대21일자산비교의사후잘못선택여부이며, 실제새정책의독립매매승률이아니다. 미래의오답여부를현재조건에넣지않았다.\n\n'
    assoc=pd.read_csv(OUT/'feature_associations.csv')
    s+=table(assoc,[('asset','원래자산',str),('wrong','대안이더좋았음',str),('hint','힌트',str),('n','표본',lambda x:str(int(x))),('frequency','시작일힌트빈도',lambda x:f'{x:.1%}')])+'\n'
    s+='예컨대GLD선택의약세G는실패10창중70%,기존선택이맞은19창중68.4%로거의차이가없다. F5는실패10창중50%,맞은16창중37.5%로차이가있으나표본이작고기간범위도다르다. 이것은힌트가나왔을때실패할확률이나검증된예측정확도가아니다.\n\n'
    s+='## 장·단기 선택기\n\n같은실제거래정책의가상비용후월별로그자산증분으로연1회선택했다. 과거24개월이상,전체과거와최근36개월두방식을비교했다. 현재연도이후자료는사용하지않았다. 실제구간에서는승인할과거양수성과가없어두선택기모두기존을유지했다. 따라서현재사후1위후보를사전에고르는방법까지확립했다고말할수없다.\n\n'
    s+='## 다음 판단\n\n주요진전은가격비율만보던연구에서보유자산약세와일중움직임차이를분리하고,공격기간에도다음방어자산을미리추적할수있음을확인한것이다. 운영교체는보류하고대표후보weak_flow_armed를기존과동일자료로모의비교할연구대상으로남긴다. 현재선택이맞던기간의기회손실과비용민감도를계속기록해야한다. 새기준을계속추가해과거승자를만드는탐색은여기서중단했다.\n\n'
    s+='기존모델도과거탐색을거쳐선택됐다. 모든자료가이미열람된상태이며후속가설까지포함하므로독립적인미사용검증이나통계적유의성을주장하지않는다. 수학적으로측정가능한특징이있어도미래실패를항상구별하는공통법칙이있다는보장은없다.\n\n'
    s+='## 재현자료와 검사\n\nprotocol.json:후보/조건/추가가설단계,metrics.csv:전조건,october_timeline.csv:10월힌트와비중,first_october_signal.csv:최초BRK목표일,failure_features.csv:사후실패진단,feature_associations.csv:빈도,router_log.csv:선택과학습마지막일,selected_annual.csv:연도별,manifest.json:코드/입력해시.\n\n완전한OHLC행의범위일관성,과거절단,미래가격변조후과거불변,공격목표동일,비중제약,기존NAV재현,선택기과거월사용검사통과. 원본BRK OHLC의10/21은결측이나주실험10/20종료이후여서그전결과에영향없다. 결측을채워매수세힌트를만들지않았다.\n\n'
    s+='참고: [Fidelity의 A/D 설명](https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/accumulation-distribution)은일중종가위치와갭변화가다른신호를줄수있음을설명한다. 본연구는거래량을곱한A/D를구현한것이아니며CLV와시가대비종가를대용특징으로썼다. [Lo·Mamaysky·Wang](https://www.nber.org/papers/w7613)은차트패턴을계산가능한규칙으로정의해검증하는방법론참고다. 이문헌이본후보의효과를입증하지는않는다.\n\n운영모델·앱·배포·주문기능변경없음.\n'
    (OUT/'details.md').write_text(s,encoding='utf-8')
    brief='''# 차트 힌트와 기존 방어 로직의 결합 연구

2026-11-05. 장기 수익 우선. 연구용이며 운영 모델은 변경하지 않았다.

## 이번에 확인한 진전

사용자가 제안한 상대강도 전환, 금 추세 약화, 일중 움직임 차이는 수학적으로 측정할 수 있었다. 이 세 조건을 5일 기준으로 확인하고 **공격 구간에서도 다음 방어 후보를 관찰하는 정책**이 이번 후보군의 기본 실제 구간에서 가장 높은 수익을 냈다.

공격 비중을 미리 버크셔로 바꾼 것은 아니다. 실제 방어 진입 시점은 기존과 동일하게 유지했다. 새로운 후보의 연복리는 49.26%, 기존은 47.63%였다. 그러나 체결 지연과 장기 비교에서는 기존보다 낮아 정식 승격 근거는 부족하다.

## 세 힌트를 어떻게 측정했나

| 힌트 | 계산 기준 |
|---|---|
| 상대강도 전환 | BRK/GLD 비율의 EMA5가 EMA21 위이며 5일 비율 수익도 양수 |
| 금 추세 약화 | 금 종가가 EMA10 아래이고 5일 수익이 음수 |
| 일중 움직임 차이 | 5일 평균 시가 대비 종가 수익이 BRK는 양수·금은 음수이며, BRK의 일중 범위 내 종가 위치가 더 높음 |

종가 위치는 `CLV = (2×종가 − 고가 − 저가) / (고가 − 저가)`로 측정했다. 일봉의 대용 특징이며 실제 매수 주문 흐름이나 장중 가격의 움직인 순서를 입증하지 않는다.

추가로 변동성 대비 급락, 과거 저점의 상승, 3일 확인, 절반 배분과 역방향도 비교했다. 하루·3일·5일 확인과 공격 중 준비 추적은 후속 민감도 실험으로 구분했다. 총 20개 정책을 검토했으며, 이번 결과에 맞춰 기간을 무제한 탐색하지 않았다.

## 10월 2일 사례

- 버크셔: 시가 500.10 → 종가 502.65. 금: 시가 384.45 → 종가 380.14.
- 10월 2일에는 상대강도와 금 약세 힌트가 있었다. 하루의 일중 움직임 차이도 보였다.
- 5일 평균의 세 조건은 10월 6일 함께 확인됐다. 종가 기준 저점 상승 대용치는 7일 확인됐다.
- 기존 모델은 10월 2일에 공격 상태였고 12일부터 방어 상태였다.
- 준비 추적 후보는 12일 버크셔 목표를 만들고 **13일 시가부터 실행 가능한 모의 경로**가 됐다. 방어 진입 뒤에만 힌트를 확인한 후보는 13일 목표 → 14일 시가 순서였다.

10월 2일 당일 시가에 매수하는 결과로 소급 계산하지 않았다. 공격 구간에서 실제 보유 비중을 바꾸려면 공격/방어 전환 자체를 따로 연구해야 한다.

## 기본 결과와 한계

최근 실제 구간은 2021-10-20~2026-10-20, 달러, 다음 거래일 시가, 편도 수수료 0.1% 기준이다. 기존 현금 보호·공격 전환을 유지하고 투자된 방어 예산만 변경했다. 새 보유 자산 자체가 약해지거나 상대강도가 3일 연속 역전되면 철회한다.

| 비교 조건 | 기존 연복리 | 준비 추적 후보 연복리 |
|---|---:|---:|
| 실제 구간·다음 시가 | 47.63% | 49.26% |
| 추가 슬리피지 0.3% | 39.24% | 40.11% |
| 다음 종가 체결 | 53.12% | 52.55% |
| 3거래일 지연＋추가 0.3% | 31.71% | 29.21% |
| 2020년 이후 공통 합성 구간·다음 종가 | 71.96% | 67.82% |

기본 실제 구간의 최대낙폭은 둘 다 −17.25%였다. 마지막 행은 상장 전 BITO를 BTC 대체 가격으로 만든 합성 자료이며, 실제 구간의 절대 성과와 직접 비교하면 안 된다. OHLC는 2020년부터여서 일중 힌트 후보를 2015년까지 소급한 성과는 제시하지 않았다.

## 기존 실패 사례의 공통점인가

단일 힌트만으로는 강하게 구별되지 않았다. 금 선택 실패 10개 평가창에서 금 약세 힌트는 70%, 기존 선택이 맞았던 19개 창에서는 68.4%였다. 일중 차이 힌트는 각각 50%(10개), 37.5%(16개)였지만 표본이 작고 관측 기간도 다르다. 이는 힌트 발생 시 실패할 확률이 아니라, 사후 분류한 창에서 관측한 빈도다.

동일한 거래정책의 과거 비용 후 월별 수익으로 기존/단기를 고르는 선택기도 비교했다. 실제 구간에서는 충분한 과거 우위를 확인하지 못해 기존을 유지했다. 따라서 이 후보를 사전에 승인할 선택 방법까지 확립한 결과는 아니다.

## 판단

대표 관찰 후보는 **상대강도＋금 약세＋5일 일중 차이＋방어 후보 준비 추적**으로 고정한다. 현재로서는 연구 후보이며 실운영에 적용하지 않는다. 최근 사례를 본 뒤 설계한 사후 연구이고, 기존 모델도 과거 최적화로 선택됐으므로 이번 비교를 미래 우위나 독립 검증으로 주장하지 않는다.

새 자료에서도 비용 후 수익 개선이 유지되는지, 기존의 좋은 선택을 얼마나 훼손하는지, 체결 지연에 취약한 이유를 함께 평가해야 한다. 수학적 특징이 존재하더라도 미래의 잘못된 선택을 항상 구별하는 법칙이 있다는 보장은 없다.

## 자료

- [상세 정의·전체 결과·출처](details.md)
- [전체 백테스트 지표](metrics.csv)
- [10월 날짜별 힌트와 목표 비중](october_timeline.csv)
- [기존 실패 평가창의 특징](failure_features.csv)
- [특징 빈도](feature_associations.csv)
- [선택기 로그](router_log.csv)
- [프로토콜](protocol.json) / [검증·입력 해시](manifest.json)

검사: 완전한 OHLC 행의 고가·저가 범위, 과거 절단, 미래 가격 변조 후 과거 불변, 공격 목표 동일, 비중 제약, 기존 실제 NAV 재현, 선택기의 과거 월 사용을 확인했다. 원본 결측 OHLC를 추정해 힌트를 만들지 않았다.

방법론 참고: [Fidelity A/D 설명](https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/accumulation-distribution), [Lo·Mamaysky·Wang의 차트 패턴 계산·검증 연구](https://www.nber.org/papers/w7613). 이 자료들은 본 후보의 성과를 입증하지 않는다.
'''
    (OUT/'report.md').write_text(brief,encoding='utf-8')
    print(pd.DataFrame(first).to_string(index=False));print('Saved report.md')

if __name__=='__main__':main()
