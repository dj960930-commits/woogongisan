package com.woogong.app

import androidx.compose.runtime.Composable
import androidx.compose.material3.Text
import androidx.compose.ui.text.font.FontWeight
import org.json.JSONObject
import java.time.Instant
import java.time.ZoneId

internal object MeritzPlanAdapter {
 fun account(a:JSONObject,s:JSONObject,now:Instant=Instant.now()):Account {
  require(!WidgetSummary.expired(Instant.parse(a.getString("as_of")),now)){"최신 메리츠 잔고를 조회하세요"}
  require(a.getDouble("loans_krw")==0.0){"대출 잔고가 있어 운용예산 확인이 필요합니다"}
  val currencies=a.getJSONArray("currencies")
  val usdRows=(0 until currencies.length()).map{currencies.getJSONObject(it)}.filter{it.getString("currency")=="USD"}
  require(usdRows.size==1){"달러 잔고와 환율을 확인할 수 없습니다"}
  val usd=usdRows.single();val fx=usd.getDouble("fx");val cash=usd.getDouble("amount")
  require(fx.isFinite()&&fx>0&&cash.isFinite()&&cash>=0){"달러 예수금 확인이 필요합니다"}
  val prices=s.getJSONObject("raw_close");val rows=a.getJSONArray("positions")
  val positions=(0 until rows.length()).map{i->
   val row=rows.getJSONObject(i);val symbol=row.getString("symbol").trim().uppercase().replace(Regex("\\.(OQ|N|P)$"), "").let{if(it=="BRK/B"||it=="BRKB")"BRK.B" else it}
   require(row.getString("kind").startsWith("해외주식")&&symbol in PortfolioEngine.symbols){"전략 외 종목 또는 종목코드 확인이 필요합니다: $symbol"}
   Position(symbol,row.getDouble("quantity"),price=prices.getDouble(symbol))
  }
  val day=now.atZone(ZoneId.of("Asia/Seoul")).toLocalDate().toString()
  return Account(positions=positions,cashUsd=cash,cashKrw=a.getDouble("cash_krw"),fx=fx,
   priceDate=s.getString("market_date"),fxDate=day,confirmedDate=day,capitalKnown=false)
 }
}

@Composable internal fun MeritzPlan(a:JSONObject,s:JSONObject,status:JSONObject,accountStale:Boolean){
 Panel{
  Text("내 계좌 기준 목표 수량",fontWeight=FontWeight.Bold)
  if(accountStale||Data.stale(s,status))Text("최신 계좌와 모델 결과를 확인한 뒤 수량을 계산합니다.")
  else {
   val result=runCatching{
    val account=MeritzPlanAdapter.account(a,s)
    val target=s.getJSONObject("target");val weights=target.keys().asSequence().associateWith{target.getDouble(it)}
    PortfolioEngine.plan(account,weights)
   }
   val plan=result.getOrNull()
   if(plan==null)Text(result.exceptionOrNull()?.message?:"운용예산을 확인하세요")
   else {
    Text("${s.getString("market_date")} 확정 종가 · 달러 운용예산 ${usd(plan.budget)}")
    plan.rows.filter{it.current>0||it.targetWeight>0}.forEach{r->
     Text("${r.symbol} · 현재 ${r.current}주 → ${r.after}주 · "+when{r.buy>0->"${r.buy}주 매수";r.sell>0->"${r.sell}주 매도";else->"유지"})
    }
    Text("계획 후 달러 현금 ${usd(plan.cashAfter)} · 목표 유보 ${usd(plan.desiredCash)}")
    Text("잔고 수량·달러 예수금과 모델 종가를 이용한 참고 계산입니다. 원화는 자동 환전하지 않습니다. 매도 대금 사용을 가정하며 실제 주문가능금액·미체결 주문·현재 호가를 확인해야 합니다. 주문은 전송하지 않습니다.")
   }
  }
 }
}
