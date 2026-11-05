"""Publish fixed-rule long-history and execution comparison tables."""
import json
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'release/long-close-2010'
LONG='conditional_2010_btc_drag-0.053388'
LABELS={'baseline':'기존 V1.3-D','user_v1_latch':'사용자 5·20일 조건 + 전환 후 유지',
    'monthly_entrygate':'EMA5/21 + 월별 승인','monthly_entrygate_closed3':'월별 승인 + 종료 사례 3건 필요',
    'fixed_entry_only':'EMA5/21 방어 진입 개입, 승인 필터 없음'}

def table(frame,fields):
    lines=['| '+' | '.join(label for key,label in fields)+' |','|'+'|'.join(['---']*len(fields))+'|']
    for _,r in frame.iterrows():
        row=[]
        for key,label in fields:
            x=r[key]
            row.append(LABELS.get(x,x) if key=='model' else f'{x*100:+.2f}%' if key in ['cagr','mdd','return_'] else str(x))
        lines.append('| '+' | '.join(row)+' |')
    return '\n'.join(lines)

def main():
    f=pd.read_csv(OUT/'metrics.csv');annual=pd.read_csv(OUT/'annual.csv')
    fields=[('model','규칙'),('cagr','연복리 수익률'),('mdd','최대낙폭')]
    text='# 2010년까지 확장한 백테스트와 종가 체결 가정\n\n'
    text+='**이번 결과는 당일 확정 종가 신호를 보고, 애프터장에서 그 정규장 종가와 동일한 가격으로 전량 체결했다고 가정한 실험이다. 이전 답변은 다음 거래일 시가 체결이었다. 기존 앱 실행 정책을 바꾼 것은 아니다.**\n\n'
    text+='종가 확정 뒤 거래하므로 새로 산 자산의 당일 상승을 소급 반영하지 않는다. 기존 자산으로 당일 수익을 평가한 뒤 거래하고 수수료를 차감하며, 새 비중은 다음 구간부터 수익에 반영한다.\n\n'
    text+='이것은 종가에 체결된다는 가격 가정이지 실제 애프터장 체결 검증이 아니다. 시간외 가격은 정규장 종가와 다를 수 있고 주문이 미체결될 수 있다. [SEC 시간외 거래 안내](https://www.sec.gov/about/reports-publications/investorpubsafterhourshtm). 실제 장마감 동시호가 주문은 최종 종가를 확인하기 전에 제출해야 하므로 그 방식과도 구분한다.\n\n'
    text+='## 1. 규칙과 비용\n\n'
    text+='- 기존: V1.3-D의 공격/방어 판단, 강제 상태, Cross 및 현금 규칙 보존.\n'
    text+='- 사용자 조건: 상대강도 5일 >2%, 20일 >5%, 비율 10일 평균 대비 >1%, GLD 10일 평균 대비 <-1%, BRK 5일 평균 위. 정상 방어에서 기존이 GLD를 선택할 때 BRK로 변경. 앞선 10월 답변과 동일하게 전환 후 유지하며 공격/강제 상태 또는 기존 GLD 선택 종료 때 해제한다. 반대 방향 조건이 완성되지 않아 임의의 대칭 청산 규칙을 추가하지 않았다. 이 결과는 이 유지 방식에 한정된다.\n'
    text+='- EMA5/21 개입: 장기 GLD 우세가 약해지고 단기 BRK 우세인 공격→방어 진입일에만 BRK 개입. 단기 GLD 복귀나 기존 위험 규칙이 개입하면 해제한다.\n'
    text+='- 월별 승인: 최소 24개 완료 월의 기존 대비 평균 순 로그 초과성과가 양수일 때만 개입 승인. 각 체결 기준에 맞춰 전문가 장부를 따로 계산하고, 개입 진입 당시 승인을 종료까지 고정한다. 장기 자료와 실제 BITO 기간은 승인 학습 이력이 다르다.\n'
    text+='- 달러, 무차입, 세전. 편도 0.1% 비용, 비중 차이 12.5%p 재조정 밴드, 관측된 현금 이자. 추가 편도 0.3% 비용 민감도도 제공. 세금·환전·시장충격·부분체결은 미반영.\n\n'
    text+='## 2. 2010-02-11~2026-11-04 조건부 대용 실험\n\n'
    text+='TQQQ의 보관 가격이 시작되는 2월 11일부터다. 2010년 1월을 포함한 연간 결과가 아니다. 주식은 동결된 신호용 가격 이력을 사용하며, 전 종목 분배금 재투자 체결 장부로 독립 검증된 자료는 아니다. BITO 대신 전체 기간에 전날 UTC BTC 종가 대용을 사용한다. BTC 자료는 2011-08-18부터 있으며, 자료와 준비기간이 부족할 때 원래 모델의 위험배분 준비 조건에 따라 BTC/SOXL 배분이 0인지 검사했다. 미상장 ETF 수익을 만들어 넣지 않았다.\n\n'
    text+='아래 중심 시나리오는 BTC 대용에 연 로그 -5.3388% 드래그를 적용한다. 이 드래그는 사후 관측 추정치이고 2010년 당시 알 수 있던 비용이 아니다. 정확한 BITO 과거 성과나 실현 가능한 연 수익으로 해석할 수 없다.\n\n'
    text+=table(f[(f['case']==LONG)&(f['mode']=='same_close')&(f.slippage==0)],fields)+'\n\n'
    text+='**중요:** 월별 승인안이 기존과 같은 이유는 개선 효과가 없다고 가정했기 때문이 아니다. 2010년부터 누적한 과거 초과성과가 2026년 10월까지 승인 문턱을 넘지 못했다. 11월에 승인이 나더라도 이미 진행 중인 개입에는 중간 합류하지 않는다. 실제 BITO 기간만 학습한 승인안과 다른 경로다.\n\n'
    text+='대용 드래그를 0%/-10%로 바꾸면 기존 연복리는 67.86%/65.43%, 승인 없는 EMA 개입은 69.25%/66.80%다. 장기 대용 자료에서 최대낙폭은 약 -41%이며 최근 5년의 낙폭으로 장기 손실을 제한할 수 없다.\n\n'
    text+='## 3. 실제 BITO 가격 장부: 2021-10-20~2026-11-04\n\n'
    text+='10월 20일까지 검증 보관된 실제 ETF 수정가격·분배금 비용 장부를 사용하고, 이후 위험자산 노출 및 추가 시가 체결이 없는 방어 구간만 저장된 BRK/GLD 종가로 연장했다. 최신 자료는 독립적인 시세 재조회에 성공한 자료가 아니다.\n\n'
    text+=table(f[(f['case']=='actual_BITO')&(f['mode']=='same_close')&(f.slippage==0)],fields)+'\n\n'
    text+='월별 승인에 종료 사례 3건을 요구하면 실제 BITO 구간에서도 개입이 승인되지 않아 기존과 같다. 완화된 승인안의 10월 진입 당시 종료된 모의 개입은 한 건뿐이었다.\n\n'
    text+='## 4. 체결 가정과 비용 민감도\n\n'
    for case,title in [(LONG,'2010 장기 대용'),('actual_BITO','실제 BITO 구간')]:
        text+='### '+title+'\n\n'
        s=f[(f['case']==case)&f.model.isin(['baseline','user_v1_latch','monthly_entrygate','fixed_entry_only'])].copy()
        s['execution']=s['mode'].map({'same_close':'당일 종가 가격 가정','next_close':'다음 거래일 종가','next_open':'다음 거래일 시가'})
        s['extra_cost']=s.slippage.map({0.:'없음',.003:'편도 +0.3%'})
        text+=table(s,[('execution','체결 기준'),('extra_cost','추가 비용'),*fields])+'\n\n'
    text+='각 체결 기준은 승인 학습도 해당 체결 기준의 순수익으로 계산했다. 따라서 서로 다른 체결 방식의 승인 날짜가 반드시 같지는 않다. 장기 대용에는 검증된 시가 이력이 없어 다음 시가 결과를 만들지 않았다.\n\n'
    text+='## 5. 연도별 수익률: 당일 종가 가격 가정\n\n'
    text+='2010년은 2월 11일부터, 2026년은 11월 4일까지. 첫해는 초기 자금 대비, 이후는 전년 말 대비이며 전 기간을 계속 운용한 경로다.\n\n'
    for case,title in [(LONG,'2010 장기 대용'),('actual_BITO','실제 BITO 구간')]:
        text+='### '+title+'\n\n'
        s=annual[(annual['case']==case)&(annual['mode']=='same_close')]
        pv=s.pivot(index='year',columns='model',values='return_')
        text+='| 연도 | 기존 | 사용자 조건 | EMA 개입·무승인 | EMA 개입·월별 승인 |\n|---|---:|---:|---:|---:|\n'
        for y,r in pv.iterrows():text+=f"| {y} | {r.baseline*100:+.2f}% | {r.user_v1_latch*100:+.2f}% | {r.fixed_entry_only*100:+.2f}% | {r.monthly_entrygate*100:+.2f}% |\n"
        text+='\n'
    text+='## 6. 판단\n\n'
    text+='사용자 조건과 유지 규칙의 조합은 2020년과 2025년 등에서 기존보다 낮은 수익을 보여 최근 10월의 성공을 장기 개선으로 일반화할 수 없다. 승인 없는 EMA5/21 진입 개입은 장기 전체 수익을 높였지만, 2025년 말까지 누적 최종 자산은 기존보다 약 1.77% 낮았고 전체 개선은 최근 2026년에 집중됐다. 장기에서 항상 우월한 규칙을 찾았다고 결론낼 수 없다.\n\n'
    text+='월별 승인 방식은 학습 시작일에 민감하다. 2021년부터 학습한 개선이 2010년부터의 학습에서도 반복된다고 볼 수 없다. 규칙은 2026년 사례를 본 뒤 구성했으므로 이번 전 기간은 사후 재검사 자료이며 독립 표본외 검증이 아니다. 앱 모델 승격·자동 주문·체결 정책 변경은 하지 않았다.\n\n'
    text+='## 7. 검증과 파일\n\n'
    audit=json.loads((OUT/'audit.json').read_text(encoding='utf-8'))
    text+=f"당일 종가 장부 {len(audit['checks'])}개를 별도 달러 장부와 대조했다. 2014/2024 자료 절단 시 과거 목표 비중 불변, 당일 상승의 소급 수익 방지, 기존 다음 시가 장부와의 일치, 미관측 자산 노출 0 검사도 통과했다. 이는 체결 가능성이나 미래 성과를 검증한 것은 아니다.\n\n"
    text+='metrics.csv: 전체 지표 / annual.csv: 연도별 / nav_*.csv: 일별 자산 / monthly_approval.csv: 월별 승인 근거 / audit.json: 자료 가정·검증·해시. 연구 코드: tools/research_2010_close_execution.py.\n'
    (OUT/'report.md').write_text(text,encoding='utf-8')
    print('Wrote',OUT/'report.md')

if __name__=='__main__':main()
