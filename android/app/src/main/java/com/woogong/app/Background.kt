package com.woogong.app

import android.Manifest
import android.app.*
import android.appwidget.AppWidgetManager
import android.content.*
import android.content.pm.PackageManager
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import androidx.work.*
import com.google.firebase.FirebaseApp
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import java.util.concurrent.TimeUnit

class WoogongApp:Application(){
 override fun onConfigurationChanged(config:android.content.res.Configuration){super.onConfigurationChanged(config);WoogongWidget.updateAll(this)}
 override fun onCreate(){super.onCreate()
  getSystemService(NotificationManager::class.java).createNotificationChannel(NotificationChannel("close","장 마감 결과",NotificationManager.IMPORTANCE_DEFAULT))
  getSystemService(NotificationManager::class.java).createNotificationChannel(NotificationChannel("allocation_changes_v1","목표 배분 변경",NotificationManager.IMPORTANCE_HIGH).apply{enableVibration(true);description="자산 배분이 크게 바뀐 날 소리와 상단 알림으로 안내합니다."})
  MorningAlerts.schedule(this)
  WorkManager.getInstance(this).enqueueUniquePeriodicWork("fallback-sync",ExistingPeriodicWorkPolicy.UPDATE,PeriodicWorkRequestBuilder<SyncWorker>(15,TimeUnit.MINUTES).setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build()).build())
 }
}
class SyncWorker(c:Context,p:WorkerParameters):Worker(c,p){
 override fun doWork():Result {
  val modelReady=ModelRefresh.run(applicationContext)
  var tradingFailed=false
  if(MeritzAccount.connected(applicationContext)){
   try{MeritzAccount.sync(applicationContext)}catch(_:Exception){tradingFailed=true}
  }
  if(TradingConnection.url(applicationContext).isNotBlank()){
   try{TradingConnection.call(applicationContext,"status")}catch(_:Exception){tradingFailed=true}
  }
  WoogongWidget.updateAll(applicationContext)
  if(Data.url(applicationContext).isBlank()){
   return try{PortfolioStore.recordDaily(applicationContext);if(tradingFailed)Result.retry() else Result.success()}catch(_:Exception){Result.retry()}
  }
  return if(!modelReady||tradingFailed)Result.retry() else Result.success()
 }
}
class PushService:FirebaseMessagingService(){
 override fun onNewToken(token:String){Data.prefs(this).edit().putString("fcm_token",token).apply()}
 override fun onMessageReceived(message:RemoteMessage){
  // FCM is an optional wake-up. Worker and manual refresh use the same validated,
  // persistent model/date deduplication path, so push + polling cannot alert twice.
  MorningAlerts.enqueueModel(this)
 }
}
