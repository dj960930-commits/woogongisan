package com.woogong.app

import java.time.*
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class MorningPolicyTest {
 private val calendar=CloseCalendar(LocalDate.parse("2026-10-01"),LocalDate.parse("2026-12-01"),listOf(
  CloseSession(LocalDate.parse("2026-10-29"),Instant.parse("2026-10-29T20:00:00Z")),
  CloseSession(LocalDate.parse("2026-10-30"),Instant.parse("2026-10-30T20:00:00Z")),
  CloseSession(LocalDate.parse("2026-11-02"),Instant.parse("2026-11-02T21:00:00Z")),
  CloseSession(LocalDate.parse("2026-11-27"),Instant.parse("2026-11-27T18:00:00Z"))))
 @Test fun dstChangesKoreanCheckHour(){
  assertEquals(5,MorningPolicy.due(LocalDate.parse("2026-10-30"),calendar).atZone(MorningPolicy.korea).hour)
  assertEquals(6,MorningPolicy.due(LocalDate.parse("2026-11-02"),calendar).atZone(MorningPolicy.korea).hour)
 }
 @Test fun earlyCloseIsNotDelayedUntilRegularClose(){
  assertEquals(Instant.parse("2026-11-27T18:05:00Z"),MorningPolicy.due(LocalDate.parse("2026-11-27"),calendar))
 }
 @Test fun koreanMondayUsesLatestFridayAndStillHasDailyCheck(){
  val monday=Instant.parse("2026-11-01T21:05:00Z")
  assertEquals(LocalDate.parse("2026-10-30"),calendar.expected(monday))
  assertEquals(LocalDate.parse("2026-11-01"),MorningPolicy.dueDay(monday,calendar))
  assertNull(calendar.session(LocalDate.parse("2026-11-01")))
 }
 @Test fun nextAlarmIsFutureAcrossDstWeekend(){
  val now=Instant.parse("2026-10-31T20:05:00Z")
  assertEquals(Instant.parse("2026-11-01T21:05:00Z"),MorningPolicy.next(now,calendar))
 }
 @Test fun noEarlyOrVeryLateDailyBrief(){
  assertNull(MorningPolicy.dueDay(Instant.parse("2026-11-02T21:04:59Z"),calendar))
  assertNotNull(MorningPolicy.dueDay(Instant.parse("2026-11-02T21:05:00Z"),calendar))
  assertNull(MorningPolicy.dueDay(Instant.parse("2026-11-03T03:05:00Z"),calendar))
 }
 @Test fun previousResultCannotBePresentedAsNewClose(){
  val now=Instant.parse("2026-11-02T21:05:00Z")
  val s=JSONObject().put("schema_version",1).put("model_id","woogong-1.3-d").put("model_fingerprint","a".repeat(64)).put("mode","live").put("market_date","2026-10-30").put("valid_until","2026-11-05T21:05:00Z")
  val h=JSONObject(s.toString()).put("state","ready")
  assertFalse(MorningPolicy.fresh(s,h,calendar.expected(now),now))
  s.put("market_date","2026-11-02");h.put("market_date","2026-11-02")
  assertTrue(MorningPolicy.fresh(s,h,calendar.expected(now),now))
  h.put("state","error");assertFalse(MorningPolicy.fresh(s,h,calendar.expected(now),now))
 }
 @Test fun unknownCalendarRangeIsNotCalledAHoliday(){
  assertFalse(calendar.known(LocalDate.parse("2031-01-01")))
 }
}
