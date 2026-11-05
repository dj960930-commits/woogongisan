package com.woogong.app

import java.time.*

internal data class AlertEvent(val kind:String,val day:LocalDate,val at:Instant){
 val key get()="$kind:$day"
}
internal object AlertSchedule {
 fun events(now:Instant,calendar:CloseCalendar):List<AlertEvent>{
  val koreaDay=now.atZone(MorningPolicy.korea).toLocalDate()
  val nyDay=now.atZone(MorningPolicy.ny).toLocalDate()
  val list=mutableListOf<AlertEvent>()
  for(offset in -2L..5L){
   val day=nyDay.plusDays(offset)
   calendar.session(day)?.let{
    list+=AlertEvent("close_check",day,it.close.plusSeconds(300))
    list+=AlertEvent("close_deadline",day,it.close.plusSeconds(1200))
   }
  }
  for(offset in -1L..5L){
   val holiday=koreaDay.plusDays(offset)
   // Holiday messages use the regular close+20 morning clock, including DST.
   val time=holiday.atTime(16,20).atZone(MorningPolicy.ny).withZoneSameInstant(MorningPolicy.korea).toLocalTime()
   fun morning(day:LocalDate)=day.atTime(time).atZone(MorningPolicy.korea).toInstant()
   if(calendar.known(holiday)&&calendar.session(holiday)==null){
    list+=AlertEvent("holiday_eve",holiday,morning(holiday.minusDays(1)))
    list+=AlertEvent("holiday_today",holiday,morning(holiday))
   }else if(!calendar.known(holiday))list+=AlertEvent("calendar_unknown",holiday,morning(holiday))
  }
  return list.distinctBy{it.key}.sortedBy{it.at}
 }
 fun next(now:Instant,calendar:CloseCalendar)=events(now,calendar).first{it.at>now}
 fun due(now:Instant,calendar:CloseCalendar)=events(now,calendar).filter{it.at<=now&&now<it.at.plusSeconds(if(it.kind.startsWith("holiday"))7200 else 1800)}
}
