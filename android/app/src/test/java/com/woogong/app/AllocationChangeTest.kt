package com.woogong.app

import org.json.JSONObject
import org.junit.Test
import org.junit.Assert.*

class AllocationChangeTest {
 private fun s(brk:Double,gold:Double,mode:String="live")=JSONObject().put("mode",mode).put("market_date","2026-11-04").put("rebalance_band",.125)
  .put("target",JSONObject().put("TQQQ",0).put("SOXL",0).put("BITO",0).put("CASH",0).put("BRK.B",brk).put("GLD",gold))
 @Test fun switchIsImportantButSmallDailyChangeIsNot(){
  assertTrue(AllocationChange.changed(s(0.0,1.0),s(1.0,0.0)))
  assertFalse(AllocationChange.changed(s(.5,.5),s(.55,.45)))
  assertTrue(AllocationChange.changed(s(.5,.5),s(.65,.35)))
 }
 @Test fun noInventedChangeOnFirstOfflineSeed(){
  assertFalse(AllocationChange.changed(null,s(1.0,0.0)))
  assertFalse(AllocationChange.changed(s(0.0,1.0,"historical_demo"),s(1.0,0.0)))
 }
 @Test fun canonicalSignatureDoesNotDependOnObjectOrder(){
  val a=s(1.0,0.0);val b=JSONObject(a.toString())
  b.put("generated_at","different")
  assertEquals(AllocationChange.signature(a),AllocationChange.signature(b))
 }
}
