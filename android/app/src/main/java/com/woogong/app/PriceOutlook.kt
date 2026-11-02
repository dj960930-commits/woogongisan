package com.woogong.app

import androidx.compose.runtime.Composable
import androidx.compose.material3.Text
import androidx.compose.ui.text.font.FontWeight
import org.json.JSONObject

@Composable internal fun PriceOutlook(s:JSONObject){
 val outlook=s.optJSONObject("price_outlook")?:return
 val assets=outlook.optJSONArray("assets")?:return
 Panel{
  Text("앞으로의 가격 · 과거 분포 시나리오",fontWeight=FontWeight.Bold)
  Text("기준 ${outlook.optString("as_of")} · USD · 현재 최신 가격은 갱신 후 확인하세요")
  for(i in 0 until assets.length()){
   val a=assets.getJSONObject(i);Text("${a.getString("symbol")} · 기준 ${usd(a.getDouble("close"))}",fontWeight=FontWeight.Bold)
   val windows=a.getJSONArray("windows")
   for(j in 0 until windows.length()){
    val w=windows.getJSONObject(j)
    Text("${w.getInt("sessions")}거래일 후 · ${w.getString("target_date")}\n중앙 ${usd(w.getDouble("median"))} · 범위 ${usd(w.getDouble("lower"))} ~ ${usd(w.getDouble("upper"))}")
    val e=w.getJSONObject("evaluation")
    if(e.optInt("origins")>0)Text("과거 순차검증 ${e.getInt("origins")}회 · 중앙 오차 ${"%.1f".format(e.getDouble("mae_return")*100)}%p / 가격유지 기준 ${"%.1f".format(e.getDouble("unchanged_mae_return")*100)}%p")
   }
  }
  Text(outlook.optString("method"));Text(outlook.optString("limitation"))
 }
}
