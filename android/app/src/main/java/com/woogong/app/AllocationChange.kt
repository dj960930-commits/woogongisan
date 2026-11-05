package com.woogong.app

import android.content.Context
import org.json.JSONObject
import kotlin.math.abs

internal object AllocationChange {
 val symbols=listOf("TQQQ","BRK.B","GLD","CASH","SOXL","BITO")
 fun signature(s:JSONObject):String = symbols.joinToString("|"){s.getJSONObject("target").getDouble(it).toString()}
 fun reference(s:JSONObject)=JSONObject().put("mode",s.optString("mode")).put("market_date",s.optString("market_date"))
  .put("model_fingerprint",s.optString("model_fingerprint")).put("target",s.getJSONObject("target"))
 fun changed(before:JSONObject?,after:JSONObject):Boolean=try{
  before!=null&&before.optString("mode")=="live"&&before.optString("market_date")<=after.getString("market_date")&&
   symbols.maxOf{abs(before.getJSONObject("target").getDouble(it)-after.getJSONObject("target").getDouble(it))}>=after.getDouble("rebalance_band")-1e-9
 }catch(_:Exception){false}
 fun pending(c:Context):JSONObject?=try{Data.prefs(c).getString("allocation_pending",null)?.let{JSONObject(it)}}catch(_:Exception){null}
 fun acknowledge(c:Context,s:JSONObject){Data.prefs(c).edit().remove("allocation_pending").putString("allocation_reference",reference(s).toString()).apply();androidx.core.app.NotificationManagerCompat.from(c).cancel(3666)}
 fun display(target:JSONObject)=symbols.filter{target.optDouble(it)>.0001}.joinToString(" · "){
  "${if(it=="CASH")"현금" else if(it=="BRK.B")"버크셔" else it} ${"%.0f".format(target.getDouble(it)*100)}%"
 }
}
