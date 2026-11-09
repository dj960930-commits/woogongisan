"""Earlier historical checks. No fitting, live model changes, or deployment."""
import json, hashlib
import numpy as np
import pandas as pd
from research_defense_whipsaw import ROOT, AUDIT, targets, replay, metrics

OUT=ROOT/'release/model-research/studies/whipsaw-earlier'
CONFIGS=[dict(name='baseline'),dict(name='confirm3',confirm=3),dict(name='confirm5',confirm=5),
         dict(name='forced_selector',forced='selector'),dict(name='forced_mix50',forced='mix'),dict(name='forced_cash',forced='cash')]

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    p=pd.read_csv(ROOT/'data/equities.csv',index_col=0,parse_dates=True)
    btc=pd.read_csv(ROOT/'data/btc.csv',parse_dates=['date_utc']).set_index('date_utc').close
    ts={c['name']:targets(p,btc,c)[0] for c in CONFIGS}
    # Check a much earlier boundary as well as the previous study's boundary.
    for c in CONFIGS:
        cut='2016-12-30'
        np.testing.assert_allclose(ts[c['name']].loc[:cut],targets(p.loc[:cut],btc.loc[:cut],c)[0],atol=1e-12,rtol=0)
    a=np.load(AUDIT/'inputs_long_synthetic.npz')
    audited=(pd.DatetimeIndex(a['dates']),a['op'],a['cl'],a['rf'],a['div'])
    # Conditional extension: signal-price closes and previous calendar day's
    # UTC BTC close, NOT NY-close BTC marks or pre-inception BITO observations.
    ix=p.index[(p.index>='2012-01-01')&(p.index<='2026-10-20')]
    px=p.reindex(ix)[['TQQQ','BRK.B','GLD','SOXL']].copy()
    px['CASH']=1.;px['BITO']=btc.shift(1).reindex(ix)
    px=px[['TQQQ','BRK.B','GLD','CASH','SOXL','BITO']]
    assert np.isfinite(px).all().all() and (px>0).all().all(), 'Missing inputs; do not drop dates'
    rows=[];annual=[];events=[]
    cases=[('audited_2015_proxy',audited,None)]
    for drag in (0.,-.05338828097800662,-.10):
        close=px.to_numpy(copy=True)
        close[:,5]*=np.exp(drag*(ix-ix[0]).days.to_numpy()/365.25)
        cases.append(('conditional_2012_UTC_proxy',(ix,close,close,p.cash_return.reindex(ix).to_numpy(),np.zeros_like(close)),drag))
    for source,(dates,op,cl,rf,div),drag in cases:
        arr=np.stack([t.reindex(dates).to_numpy() for t in ts.values()]);assert np.isfinite(arr).all()
        for slip in (0.,.003):
            nav,tr,turn,fee=replay(arr,op,cl,rf,div,'next_close',slip,1)
            if source=='audited_2015_proxy' and slip==0:
                old=pd.read_csv(ROOT/'release/model-research/studies/whipsaw-research/nav_long_synthetic_next_close.csv',index_col=0,parse_dates=True)
                np.testing.assert_allclose(nav.T,old[list(ts)].to_numpy(),atol=1e-9,rtol=1e-10)
            windows=[('full',dates[0],dates[-1]),('before_BITO',dates[0],pd.Timestamp('2021-10-19')),
                     ('2015_2019',pd.Timestamp('2015-07-01'),pd.Timestamp('2019-12-31')),
                     ('covid_2020',pd.Timestamp('2020-01-01'),pd.Timestamp('2020-12-31'))]
            if source.startswith('conditional'):
                windows.append(('2012_2014',pd.Timestamp('2012-01-01'),pd.Timestamp('2014-12-31')))
            for k,name in enumerate(ts):
                for window,start,end in windows:
                    pos=np.flatnonzero((dates>=start)&(dates<=end));lo=max(0,pos[0]-1);hi=pos[-1]+1
                    rows.append(dict(source=source,drag=drag,slippage=slip,model=name,window=window,start=str(dates[lo].date()),end=str(dates[hi-1].date()),
                        total_return=float(nav[k,hi-1]/nav[k,lo]-1),**metrics(nav[k,lo:hi],dates[lo:hi],tr[k,lo:hi],turn[k,lo:hi],fee[k,lo:hi])))
                if slip==0:
                    for y in sorted(set(dates.year)):
                        pos=np.flatnonzero(dates.year==y);lo=max(0,pos[0]-1);hi=pos[-1]+1;v=nav[k,lo:hi]
                        annual.append(dict(source=source,drag=drag,model=name,year=y,return_=v[-1]/v[0]-1,mdd=(v/np.maximum.accumulate(v)-1).min()))
            if slip==0:
                pd.DataFrame(nav.T,index=dates,columns=list(ts)).to_csv(OUT/f'nav_{source}_{drag}.csv')
    # Defense signal history extends to 2010, but no fabricated 6-asset NAV.
    t=ts['baseline'];ind=targets(p,btc,CONFIGS[0])[1]
    for i in range(1,len(t)):
        if t.GLD.iloc[i-1]>0 and t['BRK.B'].iloc[i]>0 and t['BRK.B'].iloc[i-1]<1e-9 and t.GLD.iloc[i]<1e-9:
            events.append(dict(date=str(t.index[i].date()),state=int(ind.state.iloc[i]),kind='forced_lock' if ind.state.iloc[i]==1 else 'normal_selector'))
    result=pd.DataFrame(rows);result.to_csv(OUT/'metrics.csv',index=False)
    pd.DataFrame(annual).to_csv(OUT/'annual.csv',index=False);pd.DataFrame(events).to_csv(OUT/'gold_to_brk_signals.csv',index=False)
    manifest=dict(candidates=CONFIGS,checks=['2015 cached ledger NAV parity','all candidates prefix at 2016-12-30','no missing dates dropped'],
        files={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in (ROOT/'data/equities.csv',ROOT/'data/btc.csv',AUDIT/'inputs_long_synthetic.npz')},
        caveats=['2012 conditional uses frozen signal-price closes as execution proxies','BTC previous-calendar-day UTC price is not US-close mark',
                 'BITO absent before inception; proxy drag is scenario, not observed history','-0.053388 drag estimated retrospectively from 2021-2026; not independent validation',
                 '2015 cached BTC marks use US-close aligned price proxies','All data already viewed; no independent out-of-sample claim'])
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    shown=result[(result.slippage==0)&(result.window.isin(['full','before_BITO','2012_2014']))]
    print(shown[['source','drag','model','window','cagr','mdd']].to_string(index=False))
    report='# 우공이산 휩소 — 과거 확장 검증\n\n'
    report+='2015-07-01부터의 보관 장부 재현과 2012-01-03부터의 조건부 실험을 분리했다. 두 자료는 가격 기준이 달라 절대 수익률을 직접 비교하지 않는다. 운영 모델 변경 없음.\n\n'
    for source,drag in [('audited_2015_proxy',None),('conditional_2012_UTC_proxy',-.05338828097800662)]:
        report+=f'## {source}\n\n'
        report+='| 구간 | 후보 | 시작 | 종료 | 연복리 | 최대낙폭 |\n|---|---|---|---|---:|---:|\n'
        subset=shown[(shown.source==source)&(shown.drag.isna() if drag is None else np.isclose(shown.drag.fillna(1),drag))]
        for r in subset.itertuples():report+=f'| {r.window} | {r.model} | {r.start} | {r.end} | {r.cagr:.2%} | {r.mdd:.2%} |\n'
        report+='\n'
    report+='## 판단\n\n'
    report+='3일 확인은 2015 이후 소폭 개선하지만, 2012~2014에서는 기존보다 수익률이 낮다. 5일 확인도 이전 구간에서는 열세여서 항상 개선되는 규칙은 아니다. 강제 잠금 변경안의 장기 성과도 기존보다 낮다. 운영 교체 근거가 충분하지 않다는 판단을 유지한다.\n\n'
    report+='2012 확장 중간 비용 시나리오의 최대낙폭은 약 -43.47%이며, 2013-12-05 고점~2013-12-19 저점에 발생했다. 최근 실제 BITO 구간의 -17.25%가 장기 손실 상한이라는 해석은 성립하지 않는다. 대체 가격 실험이라 당시 실현 손실로 단정하지 않는다.\n\n'
    report+='## 한계와 가정\n\n'
    report+='- 편도 수수료 0.1%, 다음 거래일 종가, 12.5%p 밴드, 현금 이자. 추가 슬리피지 0.3%도 계산했다. 세금·환전·시장충격 제외.\n'
    report+='- 2015 보관 장부는 미국 종가 시각 BTC 가격 대용에 연 로그 -5.3388% 보정을 적용한 합성 BITO다.\n'
    report+='- 2012 확장은 주식 신호용 동결 종가와 전날 UTC BTC 종가를 실행 대용으로 사용한다. 정확한 동시각 체결 검증이 아니다. BTC 대용에 연 로그 비용 0%, -5.3388%, -10%를 각각 적용했다. 가운데 비용은 사후 추정치다.\n'
    report+='- 상장 전 BITO 기록은 없고 2000년에는 BTC·TQQQ·SOXL도 없었다. 닷컴·금융위기 당시의 현재 6자산 전략 실제 성과로 확장하지 않는다. 별도 과거 조건부 재현 자료는 있어도 이번 후보의 검증 결과로 대체하지 않는다.\n'
    report+='- 미래값을 써서 과거 신호를 바꾸지 않았다. 2016 절단 검사와 2015 보관 NAV 일치 검사 통과. 과거는 모두 재검사 자료이며 미래 기대수익률이나 독립 검증 증거가 아니다.\n\n'
    report+='전체 비용·구간 지표: metrics.csv / 연도별: annual.csv / 2010 이후 전환 신호: gold_to_brk_signals.csv / 해시·가정: manifest.json\n'
    (OUT/'report.md').write_text(report,encoding='utf-8')
    print('PASS earlier prefix, cached NAV parity, complete data; results:',OUT)

if __name__=='__main__':main()
