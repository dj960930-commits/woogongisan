"""Report the exact user-proposed entry without threshold re-fitting."""
import json
import numpy as np
import pandas as pd
from research_user_v1 import ROOT,OUT,RAW

LABELS={'baseline':'기존','v1_daily':'V1 조건 유지 중에만 전환','v1_sticky':'V1 단기 역전까지 유지','v1_armed':'V1 공격 중 준비 추적',
 'v1_symmetric':'V1 양방향 전환','v1_clp':'V1＋종가 위치','v1_confirm2':'V1 2일 확인',
 'drop_r5':'5일 상대강도 제거','drop_r20':'20일 상대강도 제거','drop_ratio_ma':'비율 10일선 제거',
 'drop_gold_ma':'금 10일선 이탈 제거','drop_brk_ma':'BRK 5일선 안정화 제거','v1_cash_proxy':'V1＋현금 대용 적격성','frozen2024_router':'2024년까지 선택 후 고정'}

def table(frame,fields):
    lines=['| '+' | '.join(t for k,t,fn in fields)+' |','|'+'|'.join(['---']*len(fields))+'|']
    for _,r in frame.iterrows():lines.append('| '+' | '.join(fn(r[k]) for k,t,fn in fields)+' |')
    return '\n'.join(lines)+'\n'

def main():
    m=pd.read_csv(OUT/'metrics.csv');e=pd.read_csv(OUT/'override_windows.csv');f=pd.read_csv(OUT/'case_signals.csv',index_col=0,parse_dates=True)
    p=pd.read_csv(ROOT/'data/equities.csv',index_col=0,parse_dates=True)
    row=f.loc['2026-10-02'];case=[]
    for key,title in [('r5','비율 5일 수익'),('r20','비율 20일 수익'),('ratio_ma','비율 SMA10 대비'),('gold_ma','GLD SMA10 대비'),('brk_ma','BRK SMA5 대비')]:
        case.append(dict(metric=title,value=row['gold_'+key+'_value'],passed=bool(row['gold_'+key])))
    pd.DataFrame(case).to_csv(OUT/'october2_reproduction.csv',index=False)
    s='''# 제안 V1의 정확한 재현과 과거 검증

2026-11-05. 사용자가 제시한 다섯 임계값을 그대로 고정했다. 새 임계값을 탐색하지 않았다. 이번 결과는 운영 모델에 적용하지 않았다.

## 결과

10월 2일의 가격·지표와 V1 신호는 재현됐다. 그러나 그 날짜를 설명하는 것과 여러 시기에서 기존 모델을 개선하는 것은 달랐다. 기본 실제 구간에서 원안 계열과 조건 제거 후보 모두 기존보다 연복리가 낮았다. 2008~2024년 독립 방어자산 실험에서도 기존 EMA84/378 선택을 넘지 못했다.

## 10월 2일 수치 재현

'''
    s+=table(pd.DataFrame(case),[('metric','지표',str),('value','계산값',lambda x:f'{x:+.3%}'),('passed','조건 통과',lambda x:'예' if x else '아니오')])+'\n'
    s+='5일과 20일 수익은 각각 9월25일·9월3일 종가 대비다. 12개월 가격수익도 2025-10-02와 비교하면 BRK +1.36%, GLD +7.15%로 재현된다. 252거래일 수익과 달력상 같은 날짜의 12개월 수익은 다르다. 기존 앱의 실제 선택 기준은 12개월 가격수익 순위가 아니라 GLD/BRK 비율 EMA84/378이다.\n\n'
    s+='|자산|시가|고가|저가|종가|CLP|\n|---|---:|---:|---:|---:|---:|\n'
    for sym,ticker in [('BRK.B','BRK-B'),('GLD','GLD')]:
        z=pd.read_csv(RAW/f'{ticker}_prices.csv',index_col=0,parse_dates=True).loc['2026-10-02']
        s+=f'|{sym}|{z.open:.2f}|{z.high:.2f}|{z.low:.2f}|{z.close:.2f}|{(z.close-z.low)/(z.high-z.low):.1%}|\n'
    s+='\nCLP=(CLV+1)/2다. 앞선 연구의 CLV를0~1로 바꾼 같은 가격 위치 정보다. 일봉만으로 실제 주문 흐름이나 저가가 발생한 시각은 확인하지 못한다.\n\n'
    s+='''## 원안에 빠진 보유·복귀 규칙을 분리

원안 코드는 진입만 정의한다. 이를 임의의 하나의 종료 정책으로 확정하지 않고 다음을 비교했다.

- **매일 조건형:** 다섯 조건이 사라지면 기존 배분으로 돌아간다. 원안의 ‘기존 보유 유지’와 동일하다고 간주하지 않은 대조군이다.
- **단기 역전 유지형:** 진입 후 BRK를 유지하다 비율 5일 수익이0 이하이며 비율이 SMA10 아래일 때 복귀한다.
- **준비 추적형:** 같은 유지·철회 판단을 공격 중에도 관찰하되 공격 비중은 그대로 둔다. 실제 전환은 정상 방어 진입 뒤에만 가능하다.
- **양방향형:** 반대 방향의 동일한 다섯 조건으로 전환한다. 실제 상태·기존 선택이 달라지면 그에 맞춰 초기화한다.
- **보조 조건:** CLP가 대체 자산은50% 초과·현재 자산은50% 미만, 또는 원안이2일 연속 충족될 때만 진입한다.

기존 Cross/D25 현금은 유지하고 투자된 방어 예산만 변경했다. 공격 재진입과 state1 잠금은 기존대로다. 10/2는 공격 상태였으므로 앱에서 그날 금을 팔아 다음날 BRK를 사는 경로로 소급하지 않았다. 독립 방어 실험과 앱 실험을 구분한다.

실제 방어 진입일10/12에는 5일 비율 수익+1.95%, 20일 비율 수익+3.33%, GLD의 SMA10 대비+0.31%로 원안 조건이 성립하지 않았다. 따라서 공격 중 신호를 기록하지 않는 원안은 이 날짜에 전환하지 않는다. 준비 추적형을 별도로 시험한 이유다.

## 앱 전체 전략에 결합한 결과

2021-10-20~2026-10-20, 달러, 종가 신호 다음 거래일 시가 체결, 편도 수수료0.1%, 분배금·현금이자·자기금융·12.5%p 밴드. 세금·환전·시장충격 제외.

'''
    fields=[('model','정책',lambda x:LABELS[x]),('cagr','연복리',lambda x:f'{x:.2%}'),('mdd','최대낙폭',lambda x:f'{x:.2%}'),('trade_days','매매일',lambda x:str(int(x)))]
    q=m[(m['case']=='app_actual')&(m['mode']=='next_open')&(m.slippage==0)&(m.window=='full')]
    s+=table(q,fields)+'\n'
    s+='5일 상대강도나 비율 SMA10 조건을 뺀 후보는 이 장부에서 유지형과 같은 결과였다. 따라서 조건 다섯 개가 모두 독립적인 정보를 추가했다고 해석하면 안 된다. 다만 모든 날짜에서 논리적으로 중복이라는 뜻은 아니다. 20일 상대강도 제거 등은 성과를 더 악화시켰다.\n\n'
    s+='## 바로 앞선 반례: 9월 15일\n\n'
    z=f.loc['2026-09-15'];counter=pd.DataFrame([dict(metric=title,value=z['gold_'+key+'_value']) for key,title in [('r5','비율 5일 수익'),('r20','비율 20일 수익'),('ratio_ma','비율 SMA10 대비'),('gold_ma','GLD SMA10 대비'),('brk_ma','BRK SMA5 대비')]])
    s+=table(counter,[('metric','지표',str),('value','값',lambda x:f'{x:+.2%}')])+'\n'
    s+='이날도 다섯 조건이 모두 충족됐다. 유지형 목표 전환 창의 다음 종가 비교(9/16→9/18, 가상 왕복 편도0.1%)는 BRK −2.13%, GLD +2.20%였다. **같은 조건이 금의 하락 지속뿐 아니라 금의 반등 직전에도 나타났다.** 이는 앱 전체 원장의 실현 매매손익과 동일한 지표는 아니며, 진입 신호가 항상 지속적인 상대강세를 뜻하지 않는 가까운 반례다.\n\n'
    s+='## 2008년까지 확장한 별도 방어자산 실험\n\n공격자산 없이 GLD/BRK만 배분한다. 대조군은 두 자산 비율 EMA84/378이며 지표 준비 자료는2004년부터 사용했다. 실제 평가는2008년부터다. 종가 가격 대용, 다음 종가 체결·편도0.1%를 사용했다. TQQQ·SOXL·BITO가 존재하지 않던 시기의 앱 전체 실적으로 제시하지 않는다.\n\n'
    sd=m[(m['case']=='standalone2008')&(m['mode']=='next_close')&(m.slippage==0)&(m.delay==1)&m.model.isin(['baseline','v1_daily','v1_sticky','v1_armed','v1_symmetric','v1_confirm2','v1_cash_proxy'])]
    s+=table(sd,[('model','정책',lambda x:LABELS[x]),('window','구간',str),('cagr','연복리',lambda x:f'{x:.2%}'),('mdd','최대낙폭',lambda x:f'{x:.2%}')])+'\n'
    s+='through2024는2008~2024, 2025on은2025~2026-10-20이다. 해당 날짜들을 이미 검토했으므로 완전한 미사용 검증은 아니다. OHLC가2020년부터여서 종가 위치 보조 후보는2008 비교에서 제외했다. 결측을 추정해 넣지 않았다.\n\n'
    s+='## 과거로 고른 뒤 2025년부터 적용하면\n\n각 자료/실행 방식 안에서2024년까지의 실제 정책 장부 로그수익으로 기존과 후보를 비교하고, 가장 높았던 정책을2025년부터 고정 적용했다. 학습 이전 기간은 기존을 유지하고, 채택 시점의 거래비용은 새 원장에서 반영했다.\n\n'
    picks=pd.read_csv(OUT/'frozen_selections.csv');s+=table(picks,[('case','실험',str),('pick','2024년 선택',lambda x:LABELS[x]),('train_end','학습 종료',str)])+'\n'
    cq=m[(m['case']=='app_actual')&(m['mode']=='next_open')&(m.slippage==0)&(m.window=='2025on')&m.model.isin(['baseline','frozen2024_router'])]
    s+=table(cq,fields)+'\n'
    s+='앱 실제 자료에서는 현금 대용 적격성 정책이 학습 기간에 유리했지만2025년 이후에는 낮아졌다. 독립2008 장기 자료와 앱 합성 장기 자료에서는 기존이 선택됐다. 모든 기간과 자산 체계에서 같은 후보를 고르는 데 성공한 결과가 아니다.\n\n'
    s+='## BIL과 현금 대용\n\n선택 예정 자산의20일 수익이 현금 금리보다 낮으면 다른 적격 자산, 둘 다 낮으면 현금으로 대기하는 별도 후보를 계산했다. 이것은 BIL ETF의 실제 보유 수익이 아니다. BIL 가격 조회는 연결 서비스의 이용 한도로 실패했고, 분배금 포함 총수익 자료를 확보하지 못했다. BIL의 실제 가격·분배금·거래비용 없이 현금 금리 결과를 BIL 실적으로 표기하지 않았다.\n\n'
    s+='[BIL 운용사 자료](https://www.ssga.com/us/en/individual/etfs/state-street-spdr-bloomberg-1-3-month-t-bill-etf-bil)는1~3개월 미국 국채 지수 추종과 월 분배를 설명한다. 단순 가격 수익만으로 총수익을 대체하지 않는다.\n\n'
    s+='## 판정과 다음 방향\n\n원안의 수치는 맞았지만, 같은 형태가 금의 반등 직전에도 발생했다. 다음 구분 과제는 상대강도 상승 자체보다 **그 상승이 계속되는 경우와 일시적인 과매도 반등인 경우의 차이**다. 이 반례를 본 뒤 즉석에서 임계값을 더 붙여 통과시키지는 않았다.\n\n'
    s+='현재는 제안 V1의 운영 반영을 권하지 않는다. 2025~2026을 이미 봤고 임계값도10/2 이후에 제안됐으므로 날짜를 분리하는 것만으로 과최적화가 사라지지 않는다. 기존 모델 역시 과거 선택 편향이 있다. 과거 우위가 미래 우위를 보장하지 않는다. 가격 신호와 보유 정책을 함께 고정한 다음 새 데이터에서 비용 후 성과를 관측해야 한다.\n\n'
    s+='## 검증·재현\n\n2020/2024 앱 절단 일치, 독립 방어2008 실험의2024 절단 일치, 미래 가격 변조 후 과거 불변, 10/2 원안 신호 통과, 공격 목표 불변, 비중 제약, 기존 실제 NAV 재현을 확인했다. 미래의 실패 여부로 거래를 켜지 않았다.\n\n'
    s+='[전체 지표](metrics.csv)에는 추가 슬리피지0.3%·3일 지연·실제 구간 다음 종가도 있다. [신호 원본](case_signals.csv), [전환 목표 창](override_windows.csv), [학습 후 선택](frozen_selections.csv), [프로토콜](protocol.json), [해시·검증](manifest.json). 전환 목표 창은 실제 체결 거래나 독립 승률과 다르다.\n\n'
    s+='선행 연구 점검: 공격 중 준비 후보의 철회 판정도 매일 갱신하도록 정리했다. 대표 weak_flow_armed의 기존49.26%는 동일했고, 대조 all_hints_armed는48.07→47.99%로 재계산됐다. 선행 상세 결과 파일도 갱신했다. 운영 모델에 영향은 없다.\n'
    (OUT/'report.md').write_text(s,encoding='utf-8')
    print('Saved report.md and october2_reproduction.csv')

if __name__=='__main__':main()
