package com.woogong.app

import android.Manifest
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import java.time.Instant
import org.json.JSONObject

internal object CloseAlertPolicy {
 fun identity(snapshot:JSONObject,health:JSONObject,now:Instant=Instant.now()):String? {
  if(!Data.sameModel(snapshot,health)||snapshot.optString("mode")!="live"||health.optString("state")!="ready")return null
  val date=snapshot.optString("market_date");val fingerprint=snapshot.optString("model_fingerprint")
  if(!PortfolioEngine.validDate(date)||health.optString("market_date")!=date||!fingerprint.matches(Regex("[a-f0-9]{64}")))return null
  val validUntil=try{Instant.parse(snapshot.getString("valid_until"))}catch(_:Exception){return null}
  if(!now.isBefore(validUntil))return null
  return "$fingerprint:$date"
 }
 fun shouldNotify(identity:String?,last:String?,enabled:Boolean,allowed:Boolean)=identity!=null&&identity!=last&&enabled&&allowed
}

internal object CloseAlerts {
 private val lock=Any()
 fun enabled(c:Context)=Data.prefs(c).getBoolean("close_alerts_enabled",true)
 fun enable(c:Context,value:Boolean){Data.prefs(c).edit().putBoolean("close_alerts_enabled",value).apply();MorningAlerts.schedule(c)}
 fun allowed(c:Context,channel:String="close"):Boolean {
  if(android.os.Build.VERSION.SDK_INT>=33&&ContextCompat.checkSelfPermission(c,Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED)return false
  return NotificationManagerCompat.from(c).areNotificationsEnabled()&&c.getSystemService(NotificationManager::class.java).getNotificationChannel(channel)?.importance!=NotificationManager.IMPORTANCE_NONE
 }
 internal fun post(c:Context,id:Int,title:String,body:String,important:Boolean=false):Boolean {
  if(android.os.Build.VERSION.SDK_INT>=33&&ContextCompat.checkSelfPermission(c,Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED)return false
  val channel=if(important)"allocation_changes_v1" else "close"
  if(!allowed(c,channel))return false
  val intent=PendingIntent.getActivity(c,id,Intent(c,MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP),PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
  val notification=NotificationCompat.Builder(c,channel).setSmallIcon(R.drawable.ic_notification).setContentTitle(title)
   .setPriority(if(important)NotificationCompat.PRIORITY_HIGH else NotificationCompat.PRIORITY_DEFAULT)
   .setCategory(if(important)NotificationCompat.CATEGORY_RECOMMENDATION else NotificationCompat.CATEGORY_STATUS)
   .setContentText(body).setStyle(NotificationCompat.BigTextStyle().bigText(body)).setAutoCancel(true).setContentIntent(intent).build()
  return try{NotificationManagerCompat.from(c).notify(id,notification);true}catch(_:SecurityException){false}
 }
 fun onSynced(c:Context,snapshot:JSONObject,health:JSONObject,previous:JSONObject?=null)=synchronized(lock){
  val identity=CloseAlertPolicy.identity(snapshot,health)?:return@synchronized
  if(!enabled(c))return@synchronized
  val prefs=Data.prefs(c)
  val reference=try{prefs.getString("allocation_reference",null)?.let{JSONObject(it)}?:previous}catch(_:Exception){previous}
  if(AllocationChange.changed(reference,snapshot)){
   val key=identity+":"+AllocationChange.signature(snapshot)
   val change=JSONObject().put("key",key).put("date",snapshot.getString("market_date"))
    .put("before",reference!!.getJSONObject("target")).put("after",snapshot.getJSONObject("target"))
   prefs.edit().putString("allocation_pending",change.toString()).apply()
   if(prefs.getString("allocation_alert_last",null)!=key&&post(c,3666,"배분 변경 · 확인이 필요해요",AllocationChange.display(change.getJSONObject("before"))+" → "+AllocationChange.display(change.getJSONObject("after")),true)){
    prefs.edit().putString("allocation_alert_last",key).putString("allocation_reference",AllocationChange.reference(snapshot).toString())
     .putString("close_alert_last",identity).putString("close_alert_last_at",Instant.now().toString()).apply()
   }
   return@synchronized
  }
  if(prefs.getString("allocation_reference",null)==null||reference==null||reference.optString("mode")!="live")prefs.edit().putString("allocation_reference",AllocationChange.reference(snapshot).toString()).apply()
  if(!CloseAlertPolicy.shouldNotify(identity,Data.prefs(c).getString("close_alert_last",null),enabled(c),allowed(c)))return@synchronized
  // Only public model data goes into the notification. Account/key details stay private.
  if(!post(c,3661,"오늘의 배분 · ${snapshot.optString("market_date")}",AllocationChange.display(snapshot.getJSONObject("target"))))return@synchronized
  check(Data.prefs(c).edit().putString("close_alert_last",identity).putString("close_alert_last_at",Instant.now().toString()).commit())
 }
 fun test(c:Context):Boolean {
  if(!allowed(c,"allocation_changes_v1"))return false
  return post(c,3662,"배분 변경 알림 테스트","이 알림처럼 변경 내용을 소리와 상단 알림으로 안내합니다.",true)
  // Test does not consume the real model/date identity.
 }
}
