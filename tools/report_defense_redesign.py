"""Summarize both stages, diagnose October using separately labelled prices."""
import json,hashlib
import numpy as np
import pandas as pd
from research_defense_redesign import ROOT,OUT,combine,replay
from research_defense_growth_stage2 import combine as growth_combine

LABELS=dict(baseline='기존',cash='방어 전량 현금',static50='금·BRK 절반 고정',dual63='63일 현금초과 승자',dual126='126일 현금초과 승자',
    dual_ensemble='63·126일 승자 혼합',momentum_blend='21·63·126일 초과모멘텀 승자',breadth='기간별 적격 비중',breadth_slow='장기 기간별 적격 비중',
    sma_breadth='기간별 이동평균 적격 비중',invvol_trend='추세 적격·변동성 배분',breadth_entry3='기간별 적격·3일 진입 확인',
    prior_sma63='장기 선호+SMA63 필터',prior_sma126='장기 선호+SMA126 필터',prior_weak63='장기 선호+63일 약세 탈락',prior_weak126='장기 선호+126일 약세 탈락',
    sticky_weak63='63일 약세 시에만 교체',sticky_weak126='126일 약세 시에만 교체',legacy_guard63='기존 보호+63일 자체 약세 대피',legacy_guard126='기존 보호+126일 자체 약세 대피')

def md(df,fields):
    rows=['| '+' | '.join(f[1] for f in fields)+' |','|'+'|'.join(['---']*len(fields))+'|']
    for _,r in df.iterrows():rows.append('| '+' | '.join(fn(r[k]) for k,title,fn in fields)+' |')
    return '\n'.join(rows)+'\n'

def main():
    a=pd.read_csv(OUT/'metrics.csv');bdir=ROOT/'release/defense-growth-stage2';b=pd.read_csv(bdir/'metrics.csv')
    # Update metadata after adding explicit builder-source hashing; no score edits.
    for directory,source in [(OUT,'research_defense_redesign.py'),(bdir,'research_defense_growth_stage2.py')]:
        path=directory/'manifest.json';m=json.loads(path.read_text(encoding='utf-8'))
        for f in [ROOT/'tools'/source,ROOT/'tools/research_defense_redesign.py',ROOT/'tools/research_defense_whipsaw.py']:
            m['hashes'][str(f)]=hashlib.sha256(f.read_bytes()).hexdigest()
        path.write_text(json.dumps(m,indent=2),encoding='utf-8')
        f=pd.read_csv(directory/'metrics.csv');f.loc[f.mdd.abs()<1e-12,'calmar']=np.nan;f.to_csv(directory/'metrics.csv',index=False)
    # October only: same frozen prefix with anchored extended closes. Carry the
    # latest observed cash rate where unavailable. No claim of actual execution.
    frozen=pd.read_csv(ROOT/'data/equities.csv',index_col=0,parse_dates=True)
    recent=pd.read_csv(ROOT/'runtime/outlook-input.csv',index_col=0,parse_dates=True)
    np.testing.assert_allclose(recent.reindex(frozen.index).to_numpy(),frozen.to_numpy(),equal_nan=True,atol=1e-10,rtol=1e-10)
    recent.cash_return=recent.cash_return.ffill()
    btc=pd.read_csv(ROOT/'data/btc.csv',parse_dates=['date_utc']).set_index('date_utc').close
    t,ind=combine(recent,btc);gt,_=growth_combine(recent,btc);t.update(gt)
    ix=recent.loc['2026-09-30':].index;attack=ind.state.reindex(ix).eq(0).to_numpy()
    names=list(t);arr=np.stack([t[n].reindex(ix).to_numpy() for n in names]);arr[:,attack,:]=0;arr[:,attack,3]=1
    prices=np.ones((len(ix),6));prices[:,1:3]=recent.loc[ix,['BRK.B','GLD']].to_numpy()
    nav,tr,turn,fees=replay(arr,prices,prices,recent.cash_return.reindex(ix).to_numpy(),np.zeros_like(prices),'next_close',0,1)
    diagnosis=[]
    for k,name in enumerate(names):
        diagnosis.append(dict(model=name,return_=nav[k,-1]/nav[k,0]-1,trade_days=int(tr[k].sum()),
            brk_target=float(t[name].loc[ix[-1],'BRK.B']),gold_target=float(t[name].loc[ix[-1],'GLD']),cash_target=float(t[name].loc[ix[-1],'CASH'])))
    d=pd.DataFrame(diagnosis);d.to_csv(OUT/'recent_october_diagnostic.csv',index=False)
    (OUT/'recent_diagnostic_assumptions.json').write_text(json.dumps(dict(
        start=str(ix[0].date()),end=str(ix[-1].date()),source='runtime/outlook-input.csv anchored close extension',
        cash_rate='last known observed cash_return carried forward for missing appended dates',
        calculation='defense sleeve only; cash outside defense; next close; 0.1% per side; no market-open data',
        caveat='recent diagnosis after viewing outcome, not independent validation; BTC values absent after frozen cutoff do not affect defense entry states and October BRK-up blocks original Cross',
        source_sha256=hashlib.sha256((ROOT/'runtime/outlook-input.csv').read_bytes()).hexdigest()),indent=2),encoding='utf-8')
    combined=pd.concat([a.assign(stage=1),b[b.model!='baseline'].assign(stage=2)])
    nominal=combined[(combined.period=='actual_BITO')&(combined.scope=='portfolio')&(combined.window=='full')&(combined['mode']=='next_open')&(combined.slippage==0)&(combined.delay==1)&~combined.cash_zero]
    fields=[('model','候補',lambda x:LABELS[x]),('cagr','전체 연복리',lambda x:f'{x:.2%}'),('mdd','전체 최대낙폭',lambda x:f'{x:.2%}'),('trade_days','매매일 수',lambda x:str(int(x)))]
    s='# 우공이산 방어 배분 재설계 연구 — 2026-11-05\n\n'
    s+='## 결론\n\n사용자 우선순위는 **손실 변동을 감수하고 장기 수익 우선**이다. 기존의 약점은 실제로 확인됐다. 다만 새 구조 1차 11개와 수익 보존형 2차 8개(기존 대조군 별도)를 시험한 결과, 기본 실제 BITO 구간에서 기존보다 높은 전체 연복리를 낸 후보는 없었다. 손실 축소 후보는 있지만 장기 수익을 희생했다. 따라서 **새 정식 방어 정책으로 승격하지 않는다.**\n\n'
    s+='이 결과가 기존이 미래에도 최선이라는 증거는 아니다. 기존 모델도 과거 탐색을 거쳐 선택됐고 모든 비교 기간을 이미 봤다. 19개 대안 중 과거 승자를 고르는 작업 자체에 선택 편향이 있다. 여러 기간·비용 시나리오도 서로 독립된 표본은 아니다. 최근 10월에 맞는 규칙을 계속 추가해 승자를 만들지 않고 여기서 탐색을 중단했다.\n\n'
    s+='## 최근 실패의 원인\n\n동결 자료와 연결된 10/30 가격에서, 실제 방어 진입일 **10/12→10/30 BRK +4.81%, GLD −6.90%**였다. 이것은 두 자산의 가격 변화이며 계좌 실현수익이 아니다. 10/1~10/9는 공격 구간이므로 그 이전 BRK 상승을 방어 기회손실로 세지 않는다.\n\n'
    s+='1. GLD/BRK EMA84/378은 장기 상대우위만 보고 금 자체의 최근 하락을 탈락 사유로 삼지 않는다.\n2. Cross 현금 대피는 BRK와 GLD가 모두 하락해야 하므로 금만 하락·BRK 상승 시 작동하지 않는다.\n3. D25 현금25%는 QQQ<SMA200에 묶여 있어 보유 방어자산의 약세와 불일치할 수 있다.\n4. 휩소 잠금 state1은 BRK를 강제하므로 일반 방어 배분과 일관되지 않다.\n\n'
    s+='## 새로운 구조\n\n공격/방어 전환 신호는 고정하고, 방어 상태1/2/3/4 모두에서 **BRK·GLD·현금을 평가하는 별도 배분 모듈**을 연구했다. 현금은 `cash_return` 누적 지수이며 각 자산 모멘텀은 현금 대비 초과수익으로 계산한다. 현금보다 열세면 매수 의무가 없다. 새 완전교체안에는 기존 Cross/D25를 중첩하지 않는다. 기존 보호에 자체 약세 대피만 추가한 2차 대조군은 별도 표시했다.\n\n'
    s+='- 승자 선택형: 63/126일 초과수익 상위 자산, 모두 음수면 현금. 두 기간 혼합과 21/63/126 연율 로그초과수익 평균도 비교.\n- 단계 배분형: 자산마다 최대50% 예산. 21/63/126일 중 현금보다 나은 기간 수에 따라 0/16.7/33.3/50%를 배정하고 잔여 현금. 장기기간·이동평균·3일 진입확인 변형을 비교.\n- 변동성 배분형: SMA126 위이면서 현금초과63일 양수인 자산만 inverse-vol63 배정, 자산당 최대2/3, 남는 비중 현금.\n- 수익 보존형(사용자 답변 이후 2차): 장기 선호는 유지하되 선택 자산 자체가 SMA63/126 아래이며 21일 현금초과수익도 음수면 대체 적격자 또는 현금. 복귀형/보유 지속형/기존 보호 유지 대조군을 분리.\n\n'
    s+='## 실제 BITO 구간 기본 비교\n\n2021-10-20~2026-10-20, 달러 기준, 종가 신호 다음 시가 체결, 편도 수수료0.1%, 현금이자·분배금·자기금융·12.5%p 밴드. 세금·환전·시장충격 제외. 과거 연복리는 미래 기대수익률이 아니다.\n\n'+md(nominal,fields)+'\n'
    sleeve=combined[(combined.period=='actual_BITO')&(combined.scope=='defense_sleeve')&(combined.window=='full')&(combined['mode']=='next_open')&(combined.slippage==0)&(combined.delay==1)&~combined.cash_zero]
    s+='## 방어 자체를 보면\n\n전체 낙폭은 공격 구간 BTC 손실 등에 가려질 수 있다. 아래 장부는 비방어일에 현금으로 대기하며, 방어 신호 때만 후보를 매매한다. 따라서 이 연복리는 방어일만의 연율 수익이 아니고 전체 달력 기간의 방어 전용 장부 연복리다.\n\n'
    s+=md(sleeve[sleeve.model.isin(['baseline','cash','breadth','breadth_entry3','invvol_trend','sticky_weak126'])],fields)+'\n'
    s+='단계 배분+3일 확인은 기본 방어 낙폭을 16.80→10.30%로 줄였지만 전체 연복리는47.63→40.75%로 낮췄다. 수익 우선 선택에는 부합하지 않는다. 2026-06-05~09-01 방어 구간 진단에서 기존+7.10% 대비 해당 후보−0.74%로 상승 기회도 놓쳤다. 최근 10월 개선만 보여주면 이 손실을 감추게 된다.\n\n'
    s+='## 장기·체결 비용 점검\n\n'
    long=combined[(combined.period=='long_synthetic')&(combined.scope=='portfolio')&(combined.window=='full')&(combined.slippage==0)&(combined.delay==1)]
    s+='2015-07-01~2026-10-20, 상장 전 BITO는 미국 종가 시각 BTC 대용에 사후 추정 로그비용−5.3388%/년을 적용한 합성 경로다. 다음 종가 체결. 실제 구간과 절대 수익률을 직접 비교하지 않는다.\n\n'+md(long[long.model.isin(['baseline','breadth_entry3','dual63','sticky_weak126','legacy_guard126'])],fields)+'\n'
    s+='2012 확장도 재계산했다. 이는 동결 주식 신호가격·전날 UTC BTC 가격을 실행 대용으로 쓰는 조건부 실험이며 실제 당시 BITO 거래가 아니다. 본격 시가 원장과 합쳐 단일 실적을 만들지 않았다.\n\n'
    selected=combined[(combined.scope=='portfolio')&(combined.period=='actual_BITO')&(combined.window=='full')&(combined.model.isin(['baseline','breadth_entry3','sticky_weak126','legacy_guard126']))]
    s+=md(selected,[('model','후보',lambda x:LABELS[x]),('mode','체결',str),('slippage','추가 슬리피지',lambda x:f'{x:.2%}'),('delay','거래일 지연',lambda x:str(int(x))),('cash_zero','현금금리0 가정',str),('cagr','연복리',lambda x:f'{x:.2%}'),('mdd','최대낙폭',lambda x:f'{x:.2%}')])+'\n'
    s+='## 10월 재현은 별도 진단\n\n9/30~10/30, 비방어일 현금인 장부, 다음 종가·수수료0.1%. 원래 연구 가격의 고정 prefix와 연결된 확장 가격을 썼다. 10/21 이후 누락 현금금리는 마지막 관측 금리를 유지한 가정이다. 실제 체결 기록이 아니며 연구 후보를 고르기 위한 미사용 검증도 아니다.\n\n'
    s+=md(d[d.model.isin(['baseline','cash','dual63','breadth_entry3','sticky_weak126','legacy_guard126'])],[('model','후보',lambda x:LABELS[x]),('return_','방어 장부 진단 수익',lambda x:f'{x:.2%}'),('brk_target','10/30 BRK 목표',lambda x:f'{x:.1%}'),('gold_target','GLD 목표',lambda x:f'{x:.1%}'),('cash_target','현금 목표',lambda x:f'{x:.1%}')])+'\n'
    s+='## 적용 제안\n\n1. 방어 배분 모듈을 별도 인터페이스로 분리하는 방향은 유지한다. 입력은 가격·현금수익·기존 방어상태, 출력은 BRK/GLD/CASH 비중·선택이유·탈락조건으로 통일한다. 모델 교체가 쉬워지고 원인을 추적할 수 있다. 이번 작업은 연구 모듈만 작성했다.\n2. 장기 수익 우선인 현재 목적에서는 새 후보로 운영 교체하지 않는다. 저위험 후보를 수익 개선안처럼 포장하지 않는다.\n3. 최근 구간에서 판단하고 싶은 경우, 정상 장기 선호와 자산 자체 추세·현금 대비 수익을 함께 보여주는 진단 카드가 유용하다. 추세와 금리 비교는 확률적 판단 보조이며 앞으로 가장 오를 자산을 보장하지 않는다.\n4. 향후 새 자료에 정책·비용·탈락조건을 사전 고정해 모의 기록한다. 기존 모델도 과거 최적화 편향이 있으므로 지금 과거 우위만으로 영구 확정하지 않는다. 현 연구에선 강건하게 우월한 교체 규칙을 도출하지 못했다.\n\n'
    s+='## 검증과 자료\n\n- 기존 목표2,843일 일치, 실제·장기 기본 NAV 일치, 공격 목표 불변, 2016/2023 구간 절단과 미래 가격 변조 검사 통과. 별도 읽기 감사도 수행했다.\n- 모든 새 정책은 가격 당일 종가까지 사용하며 주문은 그 다음 거래일이다. 즉시 탈락은 목표 판정이며 실제 체결에는 밴드·대기 주문·지연 영향이 있다.\n- episodes.csv는 연속 방어 신호 구간의 동일 NAV 슬라이스이고 독립 매매 승률이 아니다.\n- 순수 현금 장부의 낙폭이0이면 Calmar는 정의되지 않아 빈값으로 표시한다.\n- 각 폴더 metrics.csv: 전체·방어 장부/날짜분할/체결비용; annual.csv: 연도별; episodes.csv: 방어 구간; allocation_coverage.csv: 목표 현금 활용; manifest.json: 입력·코드 해시. 2021·2026 등 경계 연도는 부분 기간이다.\n- 1차 protocol.json과 2차 protocol.json은 구분해 보관했다. 후보는 총19개+기존 대조군이며 후속 가설은 1차 결과와 사용자 목적을 확인한 뒤 추가됐다는 한계가 있다.\n\n'
    s+='방법론 참고: [Time Series Momentum 원 논문 안내](https://www.aqr.com/Insights/Research/Journal-Article/Time-Series-Momentum), [Faber의 추세 기반 자산배분](https://mebfaber.com/2009/02/19/a-quantitative-approach-to-tactical-asset-allocation-updated/). 이 연구들은 가설의 배경이며 본 후보의 성과를 입증하지 않는다.\n'
    (OUT/'report.md').write_text(s.replace('候補','후보'),encoding='utf-8')
    print(d[d.model.isin(['baseline','dual63','breadth_entry3','sticky_weak126','legacy_guard126'])].to_string(index=False))
    print('Saved',OUT/'report.md')

if __name__=='__main__':main()
