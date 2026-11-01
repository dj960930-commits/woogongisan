package com.woogong.app

import java.time.*
import org.json.JSONObject

internal data class CloseSession(val date:LocalDate,val close:Instant)
internal class CloseCalendar(val start:LocalDate,val end:LocalDate,val sessions:List<CloseSession>){
 fun known(day:LocalDate)=!day.isBefore(start)&&!day.isAfter(end)
 fun session(day:LocalDate)=sessions.find{it.date==day}
 fun expected(now:Instant)=sessions.lastOrNull{!it.close.isAfter(now)}?.date
 companion object{
  fun read(raw:String):CloseCalendar {
   val o=JSONObject(raw);val rows=o.getJSONArray("sessions")
   val sessions=(0 until rows.length()).map{val r=rows.getJSONObject(it);CloseSession(LocalDate.parse(r.getString("date")),Instant.parse(r.getString("close")))}
   require(sessions.isNotEmpty()&&sessions.zipWithNext().all{(a,b)->a.date<b.date&&a.close<b.close})
   return CloseCalendar(LocalDate.parse(o.getString("start")),LocalDate.parse(o.getString("end")),sessions)
  }
 }
}
internal object MorningPolicy {
 val ny:ZoneId=ZoneId.of("America/New_York")
 val korea:ZoneId=ZoneId.of("Asia/Seoul")
 fun due(day:LocalDate,calendar:CloseCalendar):Instant =
  (calendar.session(day)?.close?:day.atTime(16,0).atZone(ny).toInstant()).plusSeconds(300)
 fun next(now:Instant,calendar:CloseCalendar):Instant {
  val day=now.atZone(ny).toLocalDate()
  return (0L..3L).map{due(day.plusDays(it),calendar)}.first{it>now}
 }
 fun dueDay(now:Instant,calendar:CloseCalendar):LocalDate? {
  val day=now.atZone(ny).toLocalDate();val due=due(day,calendar)
  return day.takeIf{!now.isBefore(due)&&now<due.plusSeconds(6*3600)}
 }
 fun fresh(s:JSONObject,h:JSONObject,expected:LocalDate?,now:Instant):Boolean =
  expected!=null&&s.optString("market_date")==expected.toString()&&CloseAlertPolicy.identity(s,h,now)!=null
}
