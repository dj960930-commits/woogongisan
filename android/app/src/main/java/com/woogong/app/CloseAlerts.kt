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
 fun allowed(c:Context):Boolean {
  if(android.os.Build.VERSION.SDK_INT>=33&&ContextCompat.checkSelfPermission(c,Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED)return false
  return NotificationManagerCompat.from(c).areNotificationsEnabled()&&c.getSystemService(NotificationManager::class.java).getNotificationChannel("close")?.importance!=NotificationManager.IMPORTANCE_NONE
 }
 internal fun post(c:Context,id:Int,title:String,body:String):Boolean {
  if(android.os.Build.VERSION.SDK_INT>=33&&ContextCompat.checkSelfPermission(c,Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED)return false
  val intent=PendingIntent.getActivity(c,0,Intent(c,MainActivity::class.java),PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
  val notification=NotificationCompat.Builder(c,"close").setSmallIcon(R.drawable.ic_notification).setContentTitle(title)
   .setContentText(body).setStyle(NotificationCompat.BigTextStyle().bigText(body)).setAutoCancel(true).setContentIntent(intent).build()
  return try{NotificationManagerCompat.from(c).notify(id,notification);true}catch(_:SecurityException){false}
 }
 fun onSynced(c:Context,snapshot:JSONObject,health:JSONObject)=synchronized(lock){
  val identity=CloseAlertPolicy.identity(snapshot,health)
  if(!CloseAlertPolicy.shouldNotify(identity,Data.prefs(c).getString("close_alert_last",null),enabled(c),allowed(c)))return@synchronized
  // Only public model data goes into the notification. Account/key details stay private.
  if(!post(c,3661,"우공이산 · ${snapshot.optString("market_date")} 장 마감",snapshot.optString("state_label")+" · "+Data.allocation(snapshot)))return@synchronized
  check(Data.prefs(c).edit().putString("close_alert_last",identity).putString("close_alert_last_at",Instant.now().toString()).commit())
 }
 fun test(c:Context):Boolean {
  if(!allowed(c))return false
  return post(c,3662,"우공이산 · 알림 테스트","알림을 받을 수 있습니다. 새 장 마감 결과를 확인하면 이 기기에서 알려드립니다.")
  // Test does not consume the real model/date identity.
 }
}
