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
  val next=MorningPolicy.next(Instant.now(),calendar(c)).toEpochMilli()
  try{
   if(Build.VERSION.SDK_INT<31||manager.canScheduleExactAlarms())manager.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP,next,operation)
   else manager.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP,next,operation)
  }catch(_:SecurityException){manager.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP,next,operation)}
  Data.prefs(c).edit().putLong("morning_next_at",next).apply()
 }
 fun deliver(c:Context,now:Instant=Instant.now())=synchronized(lock){
  if(!CloseAlerts.enabled(c)||!CloseAlerts.allowed(c))return@synchronized
  val calendar=calendar(c);val day=MorningPolicy.dueDay(now,calendar)?:return@synchronized
  val key=day.toString();val prefs=Data.prefs(c)
  if(prefs.getString("morning_last_day",null)==key)return@synchronized
  val s=Data.load(c,"snapshot");val h=Data.load(c,"status");val expected=calendar.expected(now)
  val fresh=MorningPolicy.fresh(s,h,expected,now)
  val closed=calendar.known(day)&&calendar.session(day)==null
  val title:String;val body:String
  if(fresh&&!closed){
   CloseAlerts.onSynced(c,s,h)
   if(prefs.getString("close_alert_last",null)!=CloseAlertPolicy.identity(s,h,now))return@synchronized
  }else{
   when{
    !calendar.known(day)->{title="우공이산 · 거래일 확인 필요";body="거래 일정 갱신이 필요합니다. 앱에서 최신 결과를 확인하세요."}
    closed->{title="우공이산 · 미국장 휴장";body=if(fresh)"최신 종가 $expected · 모델 목표 ${Data.allocation(s)}" else "휴장일입니다. 저장된 결과 ${s.optString("market_date")} · 최신 자료 확인 필요"}
    else->{title="우공이산 · 장 마감 결과 대기";body="미국장 $day 종료 · 서버의 확정 종가 계산을 확인 중입니다. 새 결과가 준비되면 알려드립니다."}
   }
   if(!CloseAlerts.post(c,3661,title,body))return@synchronized
  }
  prefs.edit().putString("morning_last_day",key).putString("morning_last_at",now.toString()).apply()
 }
 fun enqueueModel(c:Context){
  WorkManager.getInstance(c).enqueueUniqueWork("close-model-refresh",ExistingWorkPolicy.REPLACE,OneTimeWorkRequestBuilder<ModelSyncWorker>().setBackoffCriteria(BackoffPolicy.LINEAR,30,java.util.concurrent.TimeUnit.SECONDS).setExpedited(OutOfQuotaPolicy.RUN_AS_NON_EXPEDITED_WORK_REQUEST).build())
 }
}
class MorningAlarmReceiver:BroadcastReceiver(){
 override fun onReceive(c:Context,intent:Intent){
  MorningAlerts.schedule(c)
  if(intent.action=="com.woogong.app.CLOSE_CHECK"){
   try{MorningAlerts.deliver(c)}catch(_:Exception){}
   MorningAlerts.enqueueModel(c)
  }
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
