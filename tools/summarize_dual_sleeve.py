"""Render the saved dual-sleeve results without rerunning or selecting parameters."""
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"release/model-research/studies/dual-sleeve-study"
LABELS={"v21":"현행 V2.1", "v21_residual63":"② 잔여분 모멘텀",
        "hybrid_raw":"① 50:50 기본", "hybrid_raw_residual63":"①+② 결합",
        "hybrid_short":"50:50 단기형", "hybrid_vol":"50:50 변동성 보정",
        "absolute_only":"절대 모멘텀만", "relative_only":"상대강도만",
        "hybrid_short_residual63":"단기형+잔여분", "hybrid_vol_residual63":"변동성 보정+잔여분",
        "hybrid_no_relative_gate":"상대강도에 현금조건 없음"}
MAIN=["v21","v21_residual63","hybrid_raw","hybrid_raw_residual63","hybrid_short"]


def table(frame, keys):
    headings={"name":"전략","total_return":"누적수익","cagr":"CAGR","mdd":"MDD","calmar":"Calmar",
              "final":"최종 자산 배수","trade_days":"거래일 수","mode":"체결","extra":"추가 편도비용",
              "start":"시작","end":"종료"}
    lines=["| "+" | ".join(headings.get(k,k) for k in keys)+" |",
           "| "+" | ".join("---" for _ in keys)+" |"]
    for _,row in frame.iterrows():
        values=[]
        for key in keys:
            value=row[key]
            if key=="name": value=LABELS.get(value,value)
            elif key in ("total_return","cagr","mdd","extra"): value=f"{value*100:,.2f}%"
            elif key in ("final","calmar"): value=f"{value:,.2f}"
            elif key=="trade_days": value=str(int(value))
            elif key=="mode": value="같은 종가 가격 가정" if value=="same_close_reference" else "다음 종가"
            values.append(str(value))
        lines.append("| "+" | ".join(values)+" |")
    return "\n".join(lines)


def main():
    f=pd.read_csv(OUT/"metrics.csv");s=pd.read_csv(OUT/"segments.csv");a=pd.read_csv(OUT/"annual.csv")
    primary=f[f.name.isin(MAIN)&f["mode"].eq("same_close_reference")&f.extra.eq(0)]
    lines=["# 50:50·잔여분 모멘텀 연구", "",
           "2026-11-09. 운영 모델 V2.1은 변경하지 않았다. 단기형은 최근 구간에서 수익이 개선됐지만 장기와 비용 조건에서 일관된 우위를 보이지 않아 현행을 유지한다.",
           "",
           "## 규칙",
           "",
           "- ① 50:50 기본: TQQQ·SOXL·BITO·QQQ·GLD·BRK.B 중 63·126거래일 현금 초과 로그수익률 평균이 양수인 자산에 절반을 균등배분하고, 나머지 절반은 같은 점수 상위2개에 균등배분한다. 없으면 현금이다.",
           "- ② 잔여분: 레버리지 상한 때문에 새로 생긴 현금만 BITO(BTC 신호)·QQQ·GLD의 63일 로그수익률 상위1개에 배분한다. 모두 음수이면 현금이다.",
           "- ①+②: 두 절반을 합쳐 비중 제한을 적용한 뒤 제한으로 생긴 현금을 ②로 배분한다.",
           "- 단기형은 21·63일, 변동성 보정형은 각 기간 수익률을 같은 기간 일간 변동성×기간 제곱근으로 나눠 순위를 정한다. 별도 민감도 후보이며 사후 최적 기간이라고 보지 않는다.",
           "- 합산 후 SOXL40%, TQQQ+SOXL70% 상한. 일반 제한 잔여분은 현금. 기존 방어 구간과 12.5%p 재조정 기준은 동일하다.",
           "",
           "## 가격·체결과 자료 범위", "",
           "기본 편도 비용0.1%, USD·세전. 표의 같은 종가는 확정 종가 확인 후 그 가격에 거래한다는 참조 가정이다. 다음 종가와 추가 편도비용0.3%도 계산했다.",
           "BITO 신호는 전날 완료 UTC BTC 종가를 사용한다. 실제 BITO와 SOXL 성과는 보관된 수정 가격 장부, QQQ는 기존 신호용 종가 기준이다. QQQ 시가 자료가 없어 다음 시가 결과는 만들지 않았다.",
           "2010 구간은 상장 전 BITO를 BTC로 대체한다. 연간 로그 추적비용0/5.3388%/10%를 적용하며 실제 ETF 운용실적으로 보지 않는다. 초기 BTC·ETF 자료가 없으면 해당 자산을 보유하지 않는다.",
           "2010와2015 대용 및 실제BITO 구간은 서로 중첩된다. 이미 살펴본 과거의 탐색으로 독립 미래 검증이 아니다.",
           ""]
    for period,title in [
        ("actual_BITO","실제 BITO 구간 · 2021-10-20~2026-10-20"),
        ("long_synthetic","2015-07-01~2026-10-20 · 보관 BTC 대용"),
        ("long2010_drag-0.053388","2010-02-11~2026-10-20 · BTC 대용·연간 로그 추적비용5.34%")]:
        lines+=["## "+title,"",table(primary[primary.period.eq(period)],["name","final","total_return","cagr","mdd","calmar","trade_days"]),""]
    lines+=["## 독립 시작 구간", "",
            "각 구간은 이전 가격으로 신호를 계산하되, 구간 첫날 현금1로 새 장부를 시작한다. 구간별 수익은 연간 연속 운용 수익과 다를 수 있다.",""]
    for period,start,end in s[["period","start","end"]].drop_duplicates().itertuples(index=False,name=None):
        label="실제BITO" if period=="actual_BITO" else "2010 BTC대용"
        rows=s[s.period.eq(period)&s.start.eq(start)&s.end.eq(end)&s.name.isin(MAIN)]
        lines+=["### "+label+" "+start+"~"+end,"",table(rows,["name","total_return","cagr","mdd","calmar"]),""]
    lines+=["## 연도별 연속 운용 수익 · 2010 BTC대용·추적비용5.34%","",
            "2010과2026은 일부 기간이다. 다른 연도는 각 연말 평가액을 전년말 평가액과 비교한다.","",
            "| 연도 | "+" | ".join(LABELS[k] for k in MAIN)+" |",
            "| --- | "+" | ".join("---" for _ in MAIN)+" |"]
    pivot=a[a.period.eq("long2010_drag-0.053388")].pivot(index="year",columns="name",values="return_")
    for year,row in pivot.iterrows():
        lines.append("| "+str(year)+("*" if year in (2010,2026) else "")+" | "+" | ".join(f"{row[k]*100:+.2f}%" for k in MAIN)+" |")
    lines+=["","## 실제 BITO 구간 · 비용·체결 민감도","",
            table(f[f.period.eq("actual_BITO")&f.name.isin(MAIN)],["name","mode","extra","final","cagr","mdd","trade_days"]),"",
            "## 해석","",
            "기본50:50은 최근 수익률과 MDD가 모두 현행보다 나빴다. 장기에서는 낙폭을 줄였지만 큰 수익 감소가 동반됐다.",
            "단기형은 최근 최종자산10.934배로 현행10.318배를 앞섰지만, 추가편도비용0.3%에서는7.669배 대7.704배로 역전됐다. 거래일 수도127회 대91회였다.",
            "잔여분모멘텀도 최근10.445배 대10.318배의 소폭 우위가 추가비용에서는7.683배 대7.704배로 사라졌다. 따라서 지금 운영 규칙을 바꿀 근거는 약하다.",
            "절대와상대 두 절반의 공격일 위험자산 비중 중복은 평균47.4%였다. 같은 가격 추세를 활용하므로 독립적인 두 수익원이 아니다.",
            "",
            "## 재현·검사","",
            "python tools/research_dual_sleeve.py",
            "python tools/summarize_dual_sleeve.py",
            "python -m pytest tests/test_dual_sleeve_research.py -q",
            "",
            "비중합1·전체상한·방어비중동일·기간절단·미래가격변경·기존V2.1장부일치 검사를 수행했다. protocol.json에 입력 지문과 가정을 보관한다."]
    (OUT/"REPORT.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    print(OUT/"REPORT.md")


if __name__=="__main__":
    main()
