package com.woogong.app

import android.content.Context
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.time.Instant

object Data {
 fun prefs(c:Context)=c.getSharedPreferences("woogong",Context.MODE_PRIVATE)
 fun load(c:Context,name:String):JSONObject {
  val cached=prefs(c).getString(name,null)
  return JSONObject(cached?:c.assets.open("$name.json").bufferedReader().use{it.readText()})
 }
 fun url(c:Context):String {
  val stored=prefs(c).getString("url",BuildConfig.SIGNAL_BASE_URL)!!.trimEnd('/')
  if(stored in setOf("https://eastgenie0909-cell.github.io/woogongisan","https://github.com/eastgenie0909-cell/woogongisan")){
   prefs(c).edit().putString("url",BuildConfig.SIGNAL_BASE_URL).apply();return BuildConfig.SIGNAL_BASE_URL
  }
  return stored
 }
 private fun identity(a:JSONObject)=ModelIdentity(a.optInt("schema_version"),a.optString("model_id"),a.optString("model_fingerprint"))
 fun sameModel(a:JSONObject,b:JSONObject):Boolean = identity(a).matches(identity(b))
 fun stale(s:JSONObject,status:JSONObject):Boolean = try {
  !sameModel(s,status) || s.optString("market_date")!=status.optString("market_date") || s.optString("mode")!="live" || status.optString("state")!="ready" || Instant.now().isAfter(Instant.parse(s.getString("valid_until")))
 } catch(e:Exception){true}
 fun sync(c:Context) {
  val previous=try{load(c,"snapshot")}catch(_:Exception){null}
  val base=SignalEndpoint.normalize(url(c))
  val requestTime=System.currentTimeMillis()
  fun fetch(name:String,optional:Boolean=false):String? {
   val connection=URL("$base/$name.json?check=$requestTime").openConnection() as HttpURLConnection
   try {
    connection.connectTimeout=15000;connection.readTimeout=20000;connection.useCaches=false;connection.setRequestProperty("Cache-Control","no-cache")
    if(optional&&connection.responseCode==404)return null
    require(connection.responseCode==200){"연결 오류 ${connection.responseCode}"}
    return connection.inputStream.bufferedReader().use{it.readText()}
   } finally {connection.disconnect()}
  }
  val bundle=fetch("bundle",true)?.let{SignalBundle.read(it)}
  fun get(name:String):String = if(bundle!=null)bundle.getJSONObject("$name.json").toString() else fetch(name)!!
  // Parse and validate the complete pair before atomically replacing cache.
  val state=get("status");val snap=get("snapshot");val obj=JSONObject(snap)
  val manifest=JSONObject(get("model"));val health=JSONObject(state)
  require(sameModel(obj,manifest) && sameModel(obj,health)){"모델 버전이 섞여 있습니다. 다시 갱신하세요"}
  require(obj.getDouble("rebalance_band")>0 && obj.getDouble("rebalance_band")<=1)
  val weights=obj.getJSONObject("target");var sum=0.0
  require(weights.keys().asSequence().toSet()==setOf("TQQQ","SOXL","BITO","BRK.B","GLD","CASH")){"지원하지 않는 자산 구성입니다"}
  weights.keys().forEach{val w=weights.getDouble(it);require(w.isFinite()&&w>=-1e-10);sum+=w}
  require(kotlin.math.abs(sum-1)<1e-8);JSONObject(state)
  if(health.optString("state")=="ready")require(obj.getString("market_date")==health.getString("market_date"))
  val edit=prefs(c).edit().putString("snapshot",snap).putString("status",state).putString("sync_error","").putString("model_check_at",Instant.now().toString())
  // Persist each received live publication; model/date revisions remain separate.
  if(obj.optString("mode")=="live"&&health.optString("state")=="ready"){
   val digest=java.security.MessageDigest.getInstance("SHA-256").digest(snap.toByteArray()).joinToString(""){"%02x".format(it)}
   val directory=java.io.File(c.filesDir,"model-history").apply{mkdirs()}
   val file=java.io.File(directory,"$digest.json")
   if(!file.exists())file.writeText(snap)
  }
  edit.apply()
  // Notify from the validated core pair before optional history downloads or account work.
  try{CloseAlerts.onSynced(c,obj,health,previous)}catch(_:Exception){}
  val historyEdit=prefs(c).edit()
  for(name in listOf("backtest","extended_backtest")){
   try{val back=get(name);if(sameModel(obj,JSONObject(back)))historyEdit.putString(name,back) else historyEdit.remove(name)}catch(_:Exception){}
  }
  historyEdit.apply()
  try{PortfolioStore.recordDaily(c,obj,health);prefs(c).edit().remove("portfolio_error").apply()}
  catch(_:Exception){prefs(c).edit().putString("portfolio_error","자산 기록을 저장하지 못했습니다. 내 자산에서 잔고를 확인하세요.").apply()}

 }
 fun allocation(s:JSONObject):String {
  val w=s.getJSONObject("target")
  return w.keys().asSequence().filter{w.optDouble(it)>0.0001}.joinToString(" · "){"$it ${"%.1f".format(w.optDouble(it)*100)}%"}
 }
}
