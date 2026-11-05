"""Expose aggregate research tables without account data or runtime secrets."""
from pathlib import Path
from html import escape
import shutil
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]

def main():
    src=ROOT/'release/long-close-2010';out=ROOT/'site/research';out.mkdir(exist_ok=True)
    for name in ['metrics.csv','annual.csv']:shutil.copy2(src/name,out/('v2-'+name))
    f=pd.read_csv(src/'metrics.csv');annual=pd.read_csv(src/'annual.csv')
    names={'baseline':'기존 V1.3-D','user_v1_latch':'제시한 5·20일 조건·유지형','fixed_entry_only':'우공이산 v2 · EMA5/21 진입 개입','monthly_entrygate':'월별 승인안'}
    body=''
    for case,title in [('conditional_2010_btc_drag-0.053388','2010-02-11~2026-11-04 · BTC 대용 실험'),('actual_BITO','2021-10-20~2026-11-04 · 실제 BITO 가격 구간')]:
        selected=f[(f['case']==case)&(f['mode']=='same_close')&(f.slippage==0)&f.model.isin(names)]
        body+=f'<section class="card"><h2>{escape(title)}</h2><div style="overflow:auto"><table><thead><tr><th>규칙</th><th>연복리</th><th>최대낙폭</th></tr></thead><tbody>'
        for r in selected.itertuples():body+=f'<tr><td>{escape(names[r.model])}</td><td>{r.cagr*100:.2f}%</td><td>{r.mdd*100:.2f}%</td></tr>'
        body+='</tbody></table></div><details><summary>연도별 결과</summary><div style="overflow:auto"><table><thead><tr><th>연도</th><th>기존</th><th>v2</th></tr></thead><tbody>'
        pv=annual[(annual['case']==case)&(annual['mode']=='same_close')].pivot(index='year',columns='model',values='return_')
        for y,r in pv.iterrows():body+=f'<tr><td>{y}</td><td>{r.baseline*100:+.2f}%</td><td>{r.fixed_entry_only*100:+.2f}%</td></tr>'
        body+='</tbody></table></div></details></section>'
    html='''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>우공이산 v2 · 규칙과 검증</title><link rel="stylesheet" href="style.css?v=200"><style>main{max-width:960px;margin:auto;padding:32px 20px}.card{margin:24px 0}table{width:100%;border-collapse:collapse;white-space:nowrap}th,td{text-align:left;padding:14px 10px;border-bottom:1px solid var(--border,#8884)}summary{cursor:pointer;padding:20px 0}p{line-height:1.8}</style></head><body><main><a href="./">← 대시보드</a><div class="eyebrow" style="margin-top:32px">WOOGONGISAN V2 / 2.0</div><h1>장기 기준으로 고른, 방어 진입 보조.</h1><p>기존 공격·현금 방어는 유지하고, 금을 고르려던 방어 진입일에만 단기 EMA5/21과 장기 우세 약화를 확인해 버크셔를 선택합니다. 월별 승인 필터는 사용하지 않습니다.</p><section class="card"><h2>종가 체결은 비교용 가정입니다.</h2><p>당일 최종 종가를 확인한 뒤 애프터장에서 같은 정규장 종가로 전량 거래했다고 가정합니다. 새 자산에 당일 수익을 소급 반영하지 않습니다. 실제 애프터장 가격·체결 보장은 아닙니다. 편도 비용 0.1%, USD·무차입·세전이며 세금·환전·시장충격은 제외했습니다.</p><p>2010년 표는 동결 신호 가격과 전날 UTC BTC 종가 대용에 연 로그 -5.3388% 드래그를 적용한 조건부 실험입니다. 미상장 BITO의 실제 운용 수익이 아닙니다. 2010년은 2월 11일부터, 2026년은 11월 4일까지입니다. 최신 구간은 당시 저장 종가를 연결한 연구 장부이며 독립 미래 검증이 아닙니다.</p></section>'''+body+'''<section class="card"><h2>개선의 한계도 함께 봅니다.</h2><p>v2의 장기 개선은 2026년에 집중됐습니다. 2025년 말까지 장기 누적 자산은 기존보다 약 1.77% 적었습니다. 2026년 사례를 본 뒤 고른 규칙이므로 이 표를 미래 수익 보장이나 전역 최적의 증명으로 해석할 수 없습니다. 월별 승인안은 학습 시작일에 따라 결과가 달라 제외했습니다.</p><p>앱의 동결 성과는 10월 20일 종료 자료로 별도 재현하며, 온라인 운영 그래프와 가격 기준이 다를 수 있습니다. 각 화면에 실제 계산 기준을 표시합니다. 모델 신호는 제공하지만 실주문·자동 차입은 활성화하지 않습니다.</p><p><a href="research/v2-metrics.csv">체결 방식·추가 비용 전체 지표 CSV</a> · <a href="research/v2-annual.csv">연도별 CSV</a> · <a href="install.html">앱 2.0 설치</a></p></section></main></body></html>'''
    (ROOT/'site/v2.html').write_text(html,encoding='utf-8')
    p=ROOT/'site/install.html';s=p.read_text(encoding='utf-8');needle='<h1>우공이산 2.0을 만나보세요.</h1>'
    s=s.replace(needle,needle+'<p><a href="v2.html">v2 확정 규칙과 2010년부터의 백테스트 →</a></p>')
    p.write_text(s,encoding='utf-8')
    print('Published aggregate research page and2 CSVs')

if __name__=='__main__':main()
