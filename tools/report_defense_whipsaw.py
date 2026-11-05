"""Create a reviewable report from offline results; no live-model writes."""
from pathlib import Path
import os
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'release/whipsaw-research'
NAMES = {
    'baseline': '기존 V1.3-D', 'confirm2': '선택 전환 2일 확인',
    'confirm3': '선택 전환 3일 확인', 'confirm5': '선택 전환 5일 확인',
    'hysteresis025': 'EMA 상대비율 ±0.25% 완충',
    'hysteresis050': 'EMA 상대비율 ±0.50% 완충',
    'minimum_hold5': '선택기 상태 5일 유지',
    'forced_selector': '잠금에도 현재 방어 선택',
    'forced_keep_defense': '잠금에도 마지막 정상 방어 선택 기억',
    'forced_mix50': '잠금 중 금·버크셔 50:50',
    'forced_cash': '잠금 중 현금 100%',
    'forced_mix_confirm2': '잠금 50:50 + 선택 전환 2일 확인',
    'cross_in_lock': '기존 버크셔 잠금 + 잠금에도 Cross',
    'selector_cross_in_lock': '선택형 잠금 + 잠금에도 Cross',
}


def table(frame, fields):
    lines = ['| ' + ' | '.join(title for key,title,fmt in fields) + ' |',
             '| ' + ' | '.join('---' for _ in fields) + ' |']
    for _, row in frame.iterrows():
        lines.append('| ' + ' | '.join(fmt(row[key]) for key,title,fmt in fields) + ' |')
    return '\n'.join(lines)


def main():
    data = pd.read_csv(OUT / 'metrics.csv')
    stage2 = pd.read_csv(ROOT / 'release/whipsaw-research-stage2/metrics.csv')
    primary = data[(data.period=='actual_BITO') & (data['mode']=='next_open') &
                   (data.slippage==0) & (data.delay==1) & (data.window=='full')]
    f = [('model','후보',lambda x:NAMES[x]),('cagr','연복리 수익률',lambda x:f'{x:.2%}'),
         ('mdd','최대낙폭',lambda x:f'{x:.2%}'),('trade_days','매매일 수',lambda x:str(int(x))),
         ('turnover_year','연간 매매대금 / 자산',lambda x:f'{x:.2f}배')]
    control = stage2[(stage2.period=='actual_BITO') & (stage2['mode']=='next_open') &
                     (stage2.slippage==0) & (stage2.delay==1) & (stage2.window=='full')]
    stress = data[(data.model.isin(['baseline','confirm3'])) & (data.window=='full')].pivot(
        index=['period','mode','slippage','delay'], columns='model', values='cagr').reset_index()
    split = data[(data.model.isin(['baseline','confirm3','confirm5','forced_selector','forced_cash'])) &
                 (data.period=='actual_BITO') & (data['mode']=='next_open') &
                 (data.slippage==0) & (data.delay==1) & (data.window!='full')]
    diag = pd.read_csv(OUT/'diagnostics.csv')
    text = '''# 우공이산 방어자산 휩소 점검 — 2026-11-05

## 판단

금→버크셔→금의 8거래일 왕복은 실제 규칙에서 확인된다. 원인은 보통의 금/버크셔 추세 교차보다 **휩소 방지 잠금이 버크셔를 강제로 지정**하는 데 있다. 그러나 이 규칙을 제거하거나 금을 유지한 대안은 낙폭 또는 다른 시기의 성과가 나빠졌다. **운영 모델 변경을 정당화할 강건한 개선은 확인하지 못했다.**

추가 검증의 대표 후보는 **정상 방어자산 전환 3일 확인**이다. 5일보다 지연이 짧고 시험한 체결·비용 조건에서 모두 성과가 개선됐다. 다만 최근 실제 ETF 구간의 개선은 2024년 말 한 국면에 집중되며, 문제의 강제 왕복 3건은 그대로다. 이를 휩소의 완전한 해결책이나 새 정식 모델로 승격하면 안 된다.

## 무엇이 휩소였나

| 신호 날짜 | 원인 | 이후 경로 |
| --- | --- | --- |
| 2024-11-27 | 정상 방어 선택기 BRK 전환 | 12/03 위험자산 재진입으로 종료. 즉시 금 복귀 왕복은 아님 |
| 2025-01-21 | 8일 강제 BRK 잠금 | 01/31 GLD 복귀 |
| 2025-12-02 | 8일 강제 BRK 잠금 | 12/12 GLD 복귀 |
| 2026-06-15 | 8일 강제 BRK 잠금 | 06/26 GLD 복귀 |

원래 잠금은 12거래일 안에서 공격 상태가 두 번 바뀌면 8거래일 동안 작동한다. 이때 정상 GLD/BRK 선택을 무시하고 BRK로 이동한다. 위 3건은 모두 정확히 8거래일의 목표 왕복이다. 5거래일 이내 직접 왕복은 없었다.

앞서 제시한 ‘4건 모두 BRK 개별 보유수익이 음수’는 동일한 현상 4회나 전략 승률을 뜻하지 않는다. 특히 2026년 6월에는 BRK 손실이 작았지만 GLD 하락은 훨씬 컸으므로, 손실 거래를 없애는 것만으로 개선을 판단할 수 없다.

## 비교 방법

- 실제 BITO 거래 가능 구간: 2021-10-20~2026-10-20. 달러 기준 전체 포트폴리오 장부.
- 종가로 신호를 만들고 다음 거래일 시가 체결. 고정 수수료 편도 0.10%, 현금 이자, 분배금, 자기금융 제약, 12.5%p 리밸런싱 밴드를 반영했다. 아래의 매매일은 실제 모의장부에 체결이 발생한 날 수다.
- 추가 슬리피지 0.10%·0.30%, 다음 종가 체결, 2·3거래일 체결 지연도 비교했다. 미체결 주문은 원래 장부처럼 예정 목표를 유지한다.
- 방어 선택을 바꾼 경우 Cross 현금 대피와 D25 현금 비중을 다시 계산했다. 공격자산 선택, 위험 신호, 8일 잠금 발생 조건은 그대로다.
- 장기 점검은 2015년 시작의 합성 BITO 대용 자료이며 다음 종가 체결만 사용한다. 실제 BITO 상장 전 실적처럼 해석하면 안 된다.
- 주가·BTC 고정 원본, 모델 지문은 manifest.json에 기록했다. 세금·환전·시장충격·개인별 체결 차이는 반영하지 않았다.

검증: 기존 목표 2,843거래일 일치, 기존 다음 시가 장부 NAV 일치, 모든 후보의 과거 구간 절단 및 미래 가격 변조 후 과거 신호 불변 검사를 통과했다. 독립 읽기 검토 두 건에서도 비교를 무효화할 인과성·체결 오류는 발견되지 않았다.

## 1차: 미리 정의한 12개 대안

'''
    text += table(primary, f)
    text += '''

수수료가 포함된 과거 시뮬레이션이다. 이 연복리 수익률은 미래 기대수익률이 아니다. ‘최대낙폭’은 손실의 절댓값이 작을수록 좋으며 표에는 음수로 표기했다. 매매대금은 현금을 제외한 매수·매도 금액을 모두 합산하므로 왕복 시 두 번 센다.

해석:

- **현재 방어 선택 유지**는 거래일 78→72일로 줄지만 MDD가 −17.25→−18.71%로 악화한다. 마지막 정상 방어 선택을 기억하는 후보도 이 구간에서는 같으며, 실제 직전 보유자산을 기억하는 규칙은 아니다.
- **금·BRK 절반 배분**은 직접 전량 왕복의 크기를 줄이지만 실제 거래일은 증가하고, 기본 수익률과 장기 합성 성과가 낮아졌다. 전량 왕복 수가 0이 되는 것은 MIX 분류의 결과이므로 ‘휩소를 제거했다’고 해석하지 않는다.
- **현금 잠금**은 기본 체결에서 개선되지만 다음 종가 체결과 장기 합성에서는 열세다.
- **3일 확인**은 순수 방어 선택기의 방향이 3거래일 연속 같을 때 변경한다. 확인 중에는 이전 선택을 유지하며, 위험자산 청산·급락 방어·현금 대피는 지연시키지 않는다. 확인 횟수는 공격자산 보유 중에도 갱신한다.
- **선택기 상태 5일 유지**는 실제 보유 5일을 보장하는 규칙이 아니다. 이번 자료에서는 기존과 같아 효과를 확인하지 못했다.
- ±0.25/0.50%는 GLD나 BRK 가격 변동이 아니라 EMA84/EMA378 비율의 로그 차이 완충값이다. 장기 합성에서 기존보다 나빠졌다.

## 날짜로 나누어 보면

이미 살펴본 과거를 나눈 재검사다. 독립 미사용 검증 자료가 아니다.

'''
    text += table(split, [('model','후보',lambda x:NAMES[x]),('window','기간',lambda x:'2021~2023' if x=='development' else '2024~2026.10'),
                         ('cagr','연복리',lambda x:f'{x:.2%}'),('mdd','최대낙폭',lambda x:f'{x:.2%}')])
    text += '''

3일 확인과 5일 확인의 실제 자료 상대성과 변화는 **2024년 11~12월의 양방향 전환**에 전부 집중됐다. 다른 시기의 상대성과 변화는 없다. 2021년 10월 이전 장기 합성 구간의 상대 NAV는 3일 확인 +1.31%, 5일 확인 −0.41%였다. 5일 확인이 최근 숫자에서 가장 높다는 이유만으로 고르는 것은 적절하지 않다.

## 체결·비용 민감도: 기존 vs 3일 확인

'''
    text += table(stress,[('period','자료',lambda x:'실제 BITO' if x=='actual_BITO' else '장기 합성'),
                          ('mode','체결',lambda x:'시가' if x=='next_open' else '종가'),
                          ('slippage','추가 슬리피지',lambda x:f'{x:.2%}'),('delay','지연 거래일',lambda x:str(int(x))),
                          ('baseline','기존 연복리',lambda x:f'{x:.2%}'),('confirm3','3일 확인 연복리',lambda x:f'{x:.2%}')])
    text += '''

8조건 모두 3일 확인의 연복리가 높고 최대낙폭은 수치 오차 범위에서 같다. 하지만 동일한 과거 사건을 다른 체결 조건으로 반복 계산한 것이므로 독립된 성공 사례 8개가 아니다. 기본 매매일은 78→79일이다. 강제 GLD→BRK→GLD 왕복 3건도 유지돼, 거래 감소나 핵심 휩소 해결을 입증한 것은 아니다.

## 2차: 잠금에도 Cross 현금 보호를 적용한다면

1차 결과를 확인한 뒤 추가한 구조 가설이다. 원래 Cross는 정상 방어 상태에만 적용되므로 버그 수정으로 단정하지 않았다. 잠금 자산 선택과 Cross 적용 범위를 2×2로 분리했다. 기준과 선택형은 대조군으로 다시 계산했다.

'''
    text += table(control, f)
    text += '''

선택형 잠금에 같은 현금 보호를 추가해도 최대낙폭은 더 커졌다. 이 조합을 채택하지 않는다. 결과에 맞춰 필터를 더 붙이는 탐색은 여기서 중단한다.

## 실행 제안

1. **정식 모델은 유지한다.** 강제 BRK 잠금의 왕복을 줄이는 변경이 전체 성과·낙폭에서도 우월하다는 근거는 아직 없다.
2. **3일 확인을 별도 모의운용 후보로 고정한다.** 5일 확인은 민감도 대조군으로만 남긴다. 새 날짜의 종가, 선택 이유, 모의 다음 시가 체결, 비용, 낙폭과 두 자산 상대성과를 기록한다. 새 국면·새 사건이 충분히 쌓이기 전에는 승격하지 않는다.
3. 앱에서는 **‘정상 상대강도 전환’과 ‘8일 휩소 방어 잠금’**을 구별하고, 잠금의 남은 거래일과 다음 종료 조건을 표시하는 개선이 유용하다. 강제 방어 배정을 새로운 장기 상승 신호로 오해하는 것을 줄일 수 있다. 이 보고서에서는 UI도 변경하지 않았다.
4. 앞으로의 승격 판단은 휩소 왕복 감소뿐 아니라 전체 NAV, 최대낙폭, 비용, 불리한 사건에서의 손실을 함께 본다. 기간이 지나거나 신호가 한 번 맞았다는 이유만으로 자동 승격하지 않는다.

본 작업은 분석 도구와 결과물만 작성했다. 운영 프로필·파라미터·앱·자동매매·배포 파일은 변경하지 않았다.

## 재현 자료

- research_defense_whipsaw.py: 1차 12후보, 전체 장부·인과성 검사.
- research_whipsaw_stage2.py: 2차 가설 2×2 대조 실험.
- summarize_defense_whipsaw.py: 연도별 수익률·직접 왕복·상대성과 변화일.
- metrics.csv: 전체 지표와 체결 조건.
- diagnostics.csv / rapid_roundtrips.csv: 목표 기준 직접 방어 왕복. 실제 체결 왕복·비용후 손실 건수와 동일한 지표는 아니다.
- annual_returns.csv: 연도별 수익률. 2021·2026은 부분 연도다.
- manifest.json: 고정 입력 해시와 검증 목록.

여러 대안을 같은 과거에 맞출수록 과최적화 위험이 커진다는 방법론 참고: [Bailey 외, The Probability of Backtest Overfitting](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf). 이 보고서는 PBO를 추정하거나 통계적 유의성을 주장하지 않는다.
'''
    (OUT/'report.md').write_text(text, encoding='utf-8')
    os.environ['MPLCONFIGDIR'] = str(OUT/'.mplcache')
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        plt.rcParams.update({'font.family':'Malgun Gothic','axes.unicode_minus':False})
        nav = pd.read_csv(OUT/'nav_actual_BITO_next_open.csv',index_col=0,parse_dates=True)
        fig, axes = plt.subplots(2,1,figsize=(11,7),sharex=True,constrained_layout=True)
        colors={'baseline':'#64748b','confirm3':'#0284c7','forced_selector':'#d97706'}
        for name in colors:
            if name!='baseline':
                axes[0].plot(nav.index, (nav[name]/nav.baseline-1)*100, label=NAMES[name],color=colors[name],linewidth=1.8)
            v=nav[name]
            axes[1].plot(nav.index,(v/v.cummax()-1)*100,label=NAMES[name],color=colors[name],linewidth=1.6)
        axes[0].axhline(0,color='#94a3b8',linewidth=.7)
        axes[0].set_title('개선은 일부 과거 국면에 집중 — 정식 변경 근거는 부족',loc='left',fontsize=15,pad=15)
        axes[0].set_ylabel('기존 대비 상대 자산 (%)');axes[0].legend(loc='upper left',frameon=False)
        axes[1].set_ylabel('고점 대비 낙폭 (%)');axes[1].legend(loc='lower left',frameon=False,ncol=3)
        for ax in axes:
            ax.grid(axis='y',alpha=.2);ax.spines[['top','right']].set_visible(False)
        fig.supxlabel('2021-10-20~2026-10-20 · 달러 · 다음 시가 · 편도 수수료 0.10% · 과거 시뮬레이션')
        fig.savefig(OUT/'comparison.png',dpi=150)
        plt.close(fig)
        print('Saved report.md and comparison.png')
    except ImportError:
        print('Saved report.md (plot dependency unavailable)')


if __name__=='__main__':
    main()
