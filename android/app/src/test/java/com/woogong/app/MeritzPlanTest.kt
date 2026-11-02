package com.woogong.app
import org.junit.Assert.*
import org.junit.Test
import org.json.JSONObject
import java.time.Instant

class MeritzPlanTest {
 private val now=Instant.parse("2026-11-02T00:00:00Z")
 private fun account()=JSONObject("""{"as_of":"2026-11-02T00:00:00Z","loans_krw":0,"cash_krw":300000,"currencies":[{"currency":"USD","amount":1000,"fx":1400}],"positions":[{"symbol":"TQQQ.OQ","kind":"해외주식","quantity":2}]}""")
 private fun snapshot()=JSONObject("""{"market_date":"2026-10-30","raw_close":{"TQQQ":50}}""")
 @Test fun usesBrokerQuantityAndUsdCashWithoutSpendingKrw(){
  val a=MeritzPlanAdapter.account(account(),snapshot(),now)
  assertEquals(2.0,a.positions.single().quantity,0.0);assertEquals("TQQQ",a.positions.single().symbol)
  val weights=(PortfolioEngine.symbols+"CASH").associateWith{if(it=="TQQQ")1.0 else 0.0}
  assertEquals(1100.0,PortfolioEngine.plan(a,weights).budget,0.0);assertFalse(a.capitalKnown)
 }
 @Test fun staleDebtUnknownHoldingsAndMissingFxBlockPlans(){
  val variants=listOf(account().put("as_of","2026-11-01T20:00:00Z"),account().put("loans_krw",1),account().apply{getJSONArray("positions").getJSONObject(0).put("symbol","UNKNOWN")},account().apply{getJSONArray("currencies").getJSONObject(0).put("fx",0)})
  variants.forEach{a->assertTrue(runCatching{MeritzPlanAdapter.account(a,snapshot(),now)}.isFailure)}
 }
}
