package com.woogong.app

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyStore
import java.security.MessageDigest
import java.time.Instant
import java.util.UUID
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec
import org.json.JSONArray
import org.json.JSONObject

// A separate vault and cache: manual portfolios and private execution servers stay separate.
internal object MeritzAccount {
 private const val ALIAS="woogong-meritz-device"
 private const val KEY="meritz_credentials_v1"
 private const val CACHE="meritz_account_v1"
 private val lock=Any()
 private val networkLock=Any()
 private fun key():SecretKey {
  val store=KeyStore.getInstance("AndroidKeyStore").apply{load(null)}
  (store.getKey(ALIAS,null) as? SecretKey)?.let{return it}
  return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,"AndroidKeyStore").apply{init(KeyGenParameterSpec.Builder(ALIAS,KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT).setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build())}.generateKey()
 }
 private fun encrypt(value:String):String {val cipher=Cipher.getInstance("AES/GCM/NoPadding");cipher.init(Cipher.ENCRYPT_MODE,key());return Base64.encodeToString(cipher.iv+cipher.doFinal(value.toByteArray(Charsets.UTF_8)),Base64.NO_WRAP)}
 private fun decrypt(value:String):String {val b=Base64.decode(value,Base64.NO_WRAP);require(b.size>12);val cipher=Cipher.getInstance("AES/GCM/NoPadding");cipher.init(Cipher.DECRYPT_MODE,key(),GCMParameterSpec(128,b.copyOfRange(0,12)));return cipher.doFinal(b.copyOfRange(12,b.size)).toString(Charsets.UTF_8)}
 private fun accountId(appKey:String)=MessageDigest.getInstance("SHA-256").digest(appKey.toByteArray()).take(8).joinToString(""){"%02x".format(it)}
 fun connected(c:Context)=Data.prefs(c).contains(KEY)
 fun failed(c:Context)=Data.prefs(c).getBoolean("meritz_sync_failed",false)
 fun cached(c:Context):JSONObject?=synchronized(lock){try{Data.prefs(c).getString(CACHE,null)?.let{JSONObject(decrypt(it))}}catch(_:Exception){null}}
 fun connect(c:Context,appKey:String,secret:String){
  val k=MeritzRoutes.credential(appKey);val s=MeritzRoutes.credential(secret)
  synchronized(lock){
   val credentials=JSONObject().put("key",k).put("secret",s).put("mac",UUID.randomUUID().toString().replace("-","").take(12).uppercase())
   val oldId=cached(c)?.optJSONObject("account")?.optString("account_id")
   val keepHistory=oldId==accountId(k)
   val edit=Data.prefs(c).edit().putString(KEY,encrypt(credentials.toString())).putBoolean("meritz_sync_failed",true)
   if(!keepHistory)edit.remove(CACHE)
   check(edit.commit())
  }
  WoogongWidget.updateAll(c)
 }
 fun disconnect(c:Context){synchronized(lock){Data.prefs(c).edit().remove(KEY).remove(CACHE).remove("meritz_sync_failed").commit()};WoogongWidget.updateAll(c)}
 fun sync(c:Context):JSONObject=synchronized(networkLock){
  var captured:String?=null
  try{
   val auth=synchronized(lock){captured=Data.prefs(c).getString(KEY,null);JSONObject(decrypt(captured?:error("메리츠 계좌를 먼저 연결하세요")))}
   val client=MeritzClient()
   if(auth.optLong("expires")<=Instant.now().epochSecond){val (token,expires)=client.authenticate(auth.getString("key"),auth.getString("secret"));auth.put("token",token).put("expires",expires)}
   val account=client.snapshot(auth.getString("token"),auth.getString("mac"))
   account.put("account_id",accountId(auth.getString("key")))
   synchronized(lock){
    require(Data.prefs(c).getString(KEY,null)==captured){"연결 정보가 변경되었습니다. 다시 조회하세요."}
    val old=cached(c);val history=old?.optJSONArray("history")?:JSONArray();val day=PortfolioStore.today();val updated=JSONArray()
    for(i in 0 until history.length()){val mark=history.getJSONObject(i);if(mark.getString("day")!=day)updated.put(mark)}
    updated.put(JSONObject().put("day",day).put("total_krw",account.getDouble("total_krw")).put("as_of",account.getString("as_of")))
    val trimmed=JSONArray();for(i in maxOf(0,updated.length()-730) until updated.length())trimmed.put(updated.getJSONObject(i))
    val result=JSONObject().put("account",account).put("history",trimmed)
    check(Data.prefs(c).edit().putString(KEY,encrypt(auth.toString())).putString(CACHE,encrypt(result.toString())).putBoolean("meritz_sync_failed",false).commit())
    WoogongWidget.updateAll(c);result
   }
  }catch(e:Exception){
   synchronized(lock){if(Data.prefs(c).getString(KEY,null)==captured){
    val edit=Data.prefs(c).edit().putBoolean("meritz_sync_failed",true)
    if(e.message?.let{it.contains("EGW00121")||it.contains("EGW00123")}==true){
     try{val auth=JSONObject(decrypt(captured!!));auth.remove("token");auth.remove("expires");edit.putString(KEY,encrypt(auth.toString()))}catch(_:Exception){}
    }
    edit.apply()
   }}
   WoogongWidget.updateAll(c)
   // Network and parsing exceptions can contain request details. Display only controlled messages.
   throw IllegalStateException(if(e is IllegalArgumentException||e is IllegalStateException)e.message?.takeIf{it.startsWith("메리츠")||it.startsWith("잔고")||it.startsWith("연결 정보")||it.startsWith("지원하지") }?:"메리츠 응답 확인이 필요합니다" else "메리츠에 접속하지 못했습니다. 통신 상태와 API 사용 권한을 확인하세요.")
  }
 }
}
