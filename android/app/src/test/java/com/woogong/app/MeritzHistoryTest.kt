package com.woogong.app

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class MeritzHistoryTest {
 private fun row(day:String,value:Int)=JSONObject().put("day",day).put("total_krw",value)

 @Test fun currentRecordWinsOnDuplicateDayAndDaysAreSorted(){
  val old=JSONArray().put(row("2026-01-02",2)).put(row("2026-01-01",1))
  val current=JSONArray().put(row("2026-01-02",9)).put(row("2026-01-03",3))
  val merged=MeritzHistory.merge(old,current)
  assertEquals(3,merged.length())
  assertEquals("2026-01-01",merged.getJSONObject(0).getString("day"))
  assertEquals(9,merged.getJSONObject(1).getInt("total_krw"))
  assertEquals("2026-01-03",merged.getJSONObject(2).getString("day"))
 }

 @Test fun mergeKeepsOnlyMostRecent730Days(){
  val rows=JSONArray()
  val start=java.time.LocalDate.parse("2020-01-01")
  for(i in 0..730)rows.put(row(start.plusDays(i.toLong()).toString(),i))
  val merged=MeritzHistory.merge(rows,JSONArray())
  assertEquals(730,merged.length())
  assertEquals(start.plusDays(1).toString(),merged.getJSONObject(0).getString("day"))
 }
}
