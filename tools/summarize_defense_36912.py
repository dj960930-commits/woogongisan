"""Render the fixed defense selection experiment without modifying production."""
import hashlib
import json
from pathlib import Path
import pandas as pd
from tools.research_defense_36912 import OUT

LABELS={'v21':'현행 V2.1','w4321_long':'4:3:2:1 가중 선택',
        'w4321_cash':'4:3:2:1 + 현금','w4321_hybrid':'4:3:2:1 + 단기 전환',
        'w4321_hybrid_cash':'4:3:2:1 + 단기 전환 + 현금'}
PRIMARY=list(LABELS)

def table(df,columns):
    headings={'name':'전략','period':'자료','start':'시작','end':'종료','final':'자산 배수',
              'cagr':'CAGR','mdd':'MDD','calmar':'Calmar','trade_days':'거래일 수',
              'total_return':'누적수익','mode':'체결','extra':'추가 편도비용','year':'연도','return_':'연 수익'}
    lines=['| '+' | '.join(headings.get(c,c) for c in columns)+' |',
           '| '+' | '.join('---' for _ in columns)+' |']
    for _,row in df.iterrows():
        values=[]
        for c in columns:
            v=row[c]
            if c=='name': text=LABELS.get(v,v)
            elif c in ['cagr','mdd','total_return','return_','extra']: text=f'{v*100:.2f}%'
            elif c in ['final','calmar']: text=f'{v:.2f}'
            else: text=str(v)
            values.append(text)
        lines.append('| '+' | '.join(values)+' |')
    return lines

def main():
    m=pd.read_csv(OUT/'metrics.csv'); s=pd.read_csv(OUT/'segments.csv')
    a=pd.read_csv(OUT/'annual.csv'); d=pd.read_csv(OUT/'defense_only.csv')
    base=m[m['mode'].eq('same_close_reference') & m.extra.eq(0)]
    lines=['# 방어자산 선택 36912 검토','',
      '2026-11-09 작성. 자료 종료 2026-10-20. 운영 V2.1은 변경하지 않았다. 현행1개와 신규12개를 비교했으며 이번 후보는 현행을 대체할 근거가 부족했다.','',
      '## 비교 규칙','',
      '- 공격/방어 진입, 공격 배분, 강제 버크셔(state1), 기존 전액 현금 신호 및 현금 유보 비중을 고정했다. 일반 방어(state2/3/4)에서 기존 투자 예산의 BRK.B/GLD 선택만 바꿨다. 기존 현금 오버레이는 원래 선택에 기초한 값을 동결해 선택 효과를 분리했다.',
      '- 63·126·189·252거래일 현금 초과 단순수익률의 가중평균. 가중치는 4:3:2:1, 12:4:2:1, 동일가중. 높은 점수 자산 선택, 정확한 동점과 준비기간에는 기존 선택 유지.',
      '- 현금형: 선택된 자산의 현금 초과 점수가 0 이하이면 해당 방어 예산도 현금으로 전환. 단기 전환을 사용한 경우에도 이 절대 필터를 마지막에 적용한다.',
      '- 단기형: 반대 자산/현재 가중 선택 자산의 가격비율이 5·21일 전보다 높고, 비율>SMA10, 반대 자산>SMA5 조건이 3종가 연속이면 그 자산을 선택한다. BRK.B↔GLD 대칭. 당일 OHLC 확인 조건이나 특정 10월 수치를 맞춘 임계값은 사용하지 않았다.',
      '- 기본 편도비용0.1%, 추가 편도0.3% 민감도, 12.5%p 재조정. USD·세전. 동일종가 참조와 다음 종가 비교. 실제 BITO 구간은 모든 후보 QQQ비중0이므로 검증된 6자산 시가 자료로 다음 시가도 계산했다.','',
      '## 실제 BITO 구간 2021-10-20~2026-10-20','']
    actual=base[base.period.eq('actual_BITO')]
    lines+=table(actual[actual.name.isin(PRIMARY)],['name','final','cagr','mdd','calmar','trade_days'])
    lines+=['','## 모든 가중치·규칙 조합','']+table(actual,['name','final','cagr','mdd','calmar'])
    for period in ['long_synthetic','long2010_drag-0.053388']:
        x=base[base.period.eq(period)&base.name.isin(PRIMARY)]
        lines+=['','## '+('2015-07-01~2026-10-20 BTC 대용' if period=='long_synthetic' else '2010-02-11~2026-10-20 BTC 대용·연간 로그 추적비용5.3388%'),'']
        lines+=table(x,['name','final','cagr','mdd','calmar'])
    lines+=['','## 구간별 새 현금에서 시작','']
    lines+=table(s[s.name.isin(PRIMARY)],['period','name','start','end','total_return','cagr','mdd'])
    lines+=['','## 체결·비용 민감도 · 실제 BITO 구간','']
    lines+=table(m[m.period.eq('actual_BITO')&m.name.isin(PRIMARY)],['name','mode','extra','cagr','mdd','calmar'])
    lines+=['','## 방어만 따로 운용한 진단 포트폴리오','',
      '일반 방어 기간만 원래의 방어 예산을 투자하고 나머지 기간은 현금으로 대기한다. 현금 대기수익 및 진입·청산 비용을 포함한다. 전체 전략의 수익 기여도나 방어일만의 연율 수익률이 아니다.','']
    lines+=table(d[d.name.isin(PRIMARY)],['period','name','total_return','cagr','mdd','trade_days'])
    lines+=['','## 연도별 · 전체 기간 연속 운용','']
    lines+=table(a[a.period.isin(['actual_BITO','long2010_drag-0.053388'])&a.name.isin(PRIMARY)],['period','name','year','return_'])
    lines+=['','## 해석과 범위','',
      '4:3:2:1 단순 대체는 최근 CAGR45.75%, MDD-30.70%로 현행59.49%, -18.83%보다 낮았다. 현금 필터는 신규안 내부에서는 개선됐으나 현행을 넘지 못했다. 단기 전환은 거래일을124→150으로 늘리고 수익률을 더 낮췄다.',
      '2022년 연속운용 수익률은 현행+7.42%, 가중 선택-13.26%, 현금형-1.67%, 단기형-14.28%였다. 한 사례의 조기 전환 개선으로 전체 우위를 추정할 수 없다.',
      '2010 확장의 전체 MDD가 모두 약-41.15%로 같아도 성과가 같은 것은 아니다. 방어 변경으로 CAGR64.31%가 가중 선택57.68%, 현금형59.31%로 낮아졌다. 분리 방어 진단에서도 현행보다 낮았다.',
      '실제 BITO 구간의 다음 시가에서도 현행 CAGR54.44%·MDD-16.68%에 비해 가중 선택42.09%·-28.46%, 현금형44.65%·-22.86%로 열세였다. 이번 후보 운영 미채택.',
      '현재 V2.1의 2026-10-02는 공격 상태다. 방어 선택만 바꾼 이 실험으로 그날 방어 진입을 만들지는 않는다. 과거에 논의한 다른 모델의 방어 진입 사례와 구분해야 한다.',
      '긴 자료는 BTC 대용·상장 전 혼합 자료로 ETF 실운용 성과가 아니며 각 기간은 중첩된다. 기존에 살펴본 자료를 다시 연구한 것으로 독립 미래 검증이 아니다. 특정 가중 모멘텀의 모든 구현이 불리하다는 결론도 아니다.',
      '검사: 비중 합계·유한/비음수·공격 자산 동일·강제버크셔 및 원래 전액현금 유지·비현금형 현금 유지·기간절단·미래가격변경·기존 장부일치 통과. 단위테스트3개 통과.','']
    (OUT/'REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
    p=OUT/'protocol.json'; meta=json.loads(p.read_text(encoding='utf-8'))
    meta['next_open']='Actual BITO only; verified canonical six-asset openings; QQQ zero for every candidate.'
    for file in ['tools/research_defense_36912.py','tools/summarize_defense_36912.py','tests/test_defense_36912_research.py']:
        meta['source_hashes'][file]=hashlib.sha256((OUT.parents[1]/file).read_bytes()).hexdigest()
    p.write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    print(OUT/'REPORT.md')

if __name__=='__main__':
    main()
