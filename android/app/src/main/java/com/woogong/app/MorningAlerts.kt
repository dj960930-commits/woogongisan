package com.woogong.app

import android.app.*
import android.content.*
import android.os.Build
import androidx.work.*
import java.time.Instant

internal object MorningAlerts {
 private val lock=Any()
 private fun calendar(c:Context)=CloseCalendar.read(c.assets.open("market-calendar.json").bufferedReader().use{it.readText()})
 fun exactAllowed(c:Context)=Build.VERSION.SDK_INT<31||c.getSystemService(AlarmManager::class.java).canScheduleExactAlarms()
 private fun pending(c:Context)=PendingIntent.getBroadcast(c,3664,Intent(c,MorningAlarmReceiver::class.java).setAction("com.woogong.app.CLOSE_CHECK"),PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
 fun schedule(c:Context){
  val manager=c.getSystemService(AlarmManager::class.java);val operation=pending(c)
  if(!CloseAlerts.enabled(c)){manager.cancel(operation);return}
  val event=AlertSchedule.next(Instant.now(),calendar(c));val next=event.at.toEpochMilli()
  try{
   if(Build.VERSION.SDK_INT<31||manager.canScheduleExactAlarms())manager.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP,next,operation)
   else manager.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP,next,operation)
  }catch(_:SecurityException){manager.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP,next,operation)}
  Data.prefs(c).edit().putLong("morning_next_at",next).apply()
 }
 fun deliver(c:Context,now:Instant=Instant.now())=synchronized(lock){
  if(!CloseAlerts.enabled(c)||!CloseAlerts.allowed(c))return@synchronized
  val calendar=calendar(c);val prefs=Data.prefs(c)
  val delivered=prefs.getStringSet("alert_events_delivered",emptySet())!!.toMutableSet()
  val events=AlertSchedule.due(now,calendar).filter{it.key !in delivered}
  for(event in events){
  val day=event.day
  val s=Data.load(c,"snapshot");val h=Data.load(c,"status");val expected=calendar.expected(now)
  val fresh=MorningPolicy.fresh(s,h,expected,now)
  if(event.kind=="close_check"){delivered+=event.key;continue}
  val title:String;val body:String
  if(fresh&&event.kind=="close_deadline"){
   CloseAlerts.onSynced(c,s,h)
   if(prefs.getString("close_alert_last",null)!=CloseAlertPolicy.identity(s,h,now))continue
  }else{
   when{
    event.kind=="calendar_unknown"->{title="우공이산 · 거래 일정 확인";body="거래 일정을 갱신해 주세요."}
    event.kind=="holiday_eve"->{title="내일 미국장 휴장";body="$day · 새 장 마감 신호는 없습니다."}
    event.kind=="holiday_today"->{title="오늘 미국장 휴장";body="$day · 최근 배분을 확인해 주세요."}
    else->{title="장 마감 결과 확인 지연";body="장 종료 후 20분이 지났습니다. 결과를 계속 확인하고 준비되면 바로 알려드릴게요."}
   }
   val id=when(event.kind){"holiday_eve"->3663;"holiday_today"->3665;else->3661}
   if(!CloseAlerts.post(c,id,title,body))continue
  }
  delivered+=event.key
  prefs.edit().putString("morning_last_day",day.toString()).putString("morning_last_at",now.toString()).apply()
  }
  prefs.edit().putStringSet("alert_events_delivered",delivered.sortedBy{it.substringAfter(':')}.takeLast(100).toSet()).apply()
 }
 fun enqueueModel(c:Context){
  WorkManager.getInstance(c).enqueueUniqueWork("close-model-refresh",ExistingWorkPolicy.REPLACE,OneTimeWorkRequestBuilder<ModelSyncWorker>().setBackoffCriteria(BackoffPolicy.LINEAR,30,java.util.concurrent.TimeUnit.SECONDS).setExpedited(OutOfQuotaPolicy.RUN_AS_NON_EXPEDITED_WORK_REQUEST).build())
 }
}
class MorningAlarmReceiver:BroadcastReceiver(){
 override fun onReceive(c:Context,intent:Intent){
  MorningAlerts.schedule(c)
  try{MorningAlerts.deliver(c)}catch(_:Exception){}
  MorningAlerts.enqueueModel(c)
 }
}
class ModelSyncWorker(c:Context,p:WorkerParameters):Worker(c,p){
 override fun doWork():Result = if(ModelRefresh.run(applicationContext))Result.success() else Result.retry()
}
internal object ModelRefresh {
 fun run(c:Context):Boolean {
  try{MorningAlerts.deliver(c)}catch(_:Exception){}
  if(Data.url(c).isBlank())return true
  return try{
   Data.sync(c);WoogongWidget.updateAll(c)
   Data.prefs(c).edit().putString("model_check_at",Instant.now().toString()).apply()
   !Data.stale(Data.load(c,"snapshot"),Data.load(c,"status"))
  }catch(_:Exception){
   Data.prefs(c).edit().putString("sync_error","갱신 실패 · 이전 기준일을 확인하세요").apply();WoogongWidget.updateAll(c);false
  }
 }
}
