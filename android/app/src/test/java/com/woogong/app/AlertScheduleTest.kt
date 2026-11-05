package com.woogong.app

import org.junit.Test
import org.junit.Assert.*
import java.time.*

class AlertScheduleTest {
 private val start=LocalDate.parse("2026-11-23")
 private val calendar=CloseCalendar(start,LocalDate.parse("2026-12-01"),listOf(
  CloseSession(start,Instant.parse("2026-11-23T21:00:00Z")),
  CloseSession(start.plusDays(1),Instant.parse("2026-11-24T21:00:00Z")),
  CloseSession(start.plusDays(2),Instant.parse("2026-11-25T21:00:00Z")),
  CloseSession(start.plusDays(4),Instant.parse("2026-11-27T18:00:00Z"))))
 @Test fun exactDeadlineFollowsEarlyClose(){
  val e=AlertSchedule.events(Instant.parse("2026-11-27T17:00:00Z"),calendar)
  assertEquals(Instant.parse("2026-11-27T18:20:00Z"),e.first{it.kind=="close_deadline"&&it.day.toString()=="2026-11-27"}.at)
  assertEquals(Instant.parse("2026-11-27T18:05:00Z"),e.first{it.kind=="close_check"&&it.day.toString()=="2026-11-27"}.at)
 }
 @Test fun holidaysUseUsualKoreanMorningOnPreviousAndActualDate(){
  val e=AlertSchedule.events(Instant.parse("2026-11-25T00:00:00Z"),calendar).filter{it.day.toString()=="2026-11-26"}
  assertEquals(Instant.parse("2026-11-24T21:20:00Z"),e.first{it.kind=="holiday_eve"}.at)
  assertEquals(Instant.parse("2026-11-25T21:20:00Z"),e.first{it.kind=="holiday_today"}.at)
 }
 @Test fun nextKeepsTwentyMinuteDeadlineAfterFirstCheck(){
  val next=AlertSchedule.next(Instant.parse("2026-11-23T21:06:00Z"),calendar)
  assertEquals("close_deadline",next.kind)
  assertEquals(Instant.parse("2026-11-23T21:20:00Z"),next.at)
 }
 @Test fun summerHolidayUsesFiveTwentyInKorea(){
  val day=LocalDate.parse("2026-07-03")
  val summer=CloseCalendar(day.minusDays(2),day.plusDays(1),listOf(CloseSession(day.minusDays(1),Instant.parse("2026-07-02T17:00:00Z"))))
  val e=AlertSchedule.events(Instant.parse("2026-07-02T00:00:00Z"),summer).first{it.kind=="holiday_today"&&it.day==day}
  assertEquals(5,e.at.atZone(MorningPolicy.korea).hour)
  assertEquals(20,e.at.atZone(MorningPolicy.korea).minute)
 }
}
