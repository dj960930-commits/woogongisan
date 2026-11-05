package com.woogong.app

import android.content.Context
import androidx.compose.runtime.*
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import org.json.JSONObject

object ReturnsSummary {
 fun percent(total:Double,capital:Double):Double?=if(total.isFinite()&&total>=0&&capital.isFinite()&&capital>0)((total/capital-1)*100).takeIf{it.isFinite()} else null
 fun read(c:Context):Pair<String,String> {
  if(MeritzAccount.connected(c))return try{
   val a=MeritzAccount.cached(c)?.optJSONObject("account")?:return "—" to "메리츠 계좌 조회 대기"
   val positions=a.getJSONArray("positions");var cost=0.0;var profit=0.0
   for(i in 0 until positions.length()){val p=positions.getJSONObject(i);cost+=p.getDouble("cost_krw");profit+=p.getDouble("profit_krw")}
   val percentage=if(cost>0)100*profit/cost else null
   val old=MeritzAccount.failed(c)||WidgetSummary.expired(java.time.Instant.parse(a.getString("as_of")),java.time.Instant.now())
   (percentage?.takeIf{it.isFinite()}?.let{"%+.2f%%".format(it)}?:"—") to "보유 종목 평가 · ${a.getString("as_of")}${if(old)" · 갱신 필요" else ""}"
  }catch(_:Exception){"—" to "메리츠 계좌 갱신 필요"}
  if(TradingConnection.url(c).isNotBlank())return "—" to "연결 계좌 · 순투입금 확인 필요"
  return try{
   val a=PortfolioStore.read(c).account?:return "—" to "내 자산에서 원금·잔고 등록"
   val v=PortfolioEngine.value(a);val r=if(a.capitalKnown)percent(v.totalKrw,a.capitalKrw) else null
   (r?.let{"%+.2f%%".format(it)}?:"—") to "수동 기록 · 가격 ${a.priceDate} / 환율 ${a.fxDate}"
  }catch(_:Exception){"—" to "원금·잔고 확인 필요"}
 }
}

@Composable internal fun ReturnsHome(s:JSONObject,stale:Boolean,onReview:()->Unit={}){
 val c=LocalContext.current
 var period by remember{mutableStateOf(Data.prefs(c).getString("performance_period","1m")?:"1m")}
 val window = Performance.read(s, period)
 val scheme = MaterialTheme.colorScheme
 val colors = PerformanceColors
 Panel {
  Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween,
   verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
   Text("시장 비교", style = MaterialTheme.typography.titleMedium)
   Text("USD · 세전", style = MaterialTheme.typography.bodySmall, color = scheme.onSurfaceVariant)
  }
  if (window != null) {
   Text(Performance.percent(window.last.model), color = scheme.onSurface,
    style = MaterialTheme.typography.headlineSmall.copy(fontSize=36.sp,lineHeight=42.sp,
      letterSpacing=(-1.4).sp,fontFeatureSettings="tnum"))
  }
  Surface(color = scheme.surfaceVariant, shape = RoundedCornerShape(10.dp)) {
   Row(Modifier.fillMaxWidth().padding(2.dp)) {
    Performance.periods.forEach { (key, label) ->
     val selected = period == key
     TextButton(modifier = Modifier.weight(1f), shape = RoundedCornerShape(8.dp),
      colors = ButtonDefaults.textButtonColors(
       containerColor = if (selected) scheme.surface else Color.Transparent,
       contentColor = if (selected) scheme.primary else scheme.onSurfaceVariant),
      contentPadding = PaddingValues(horizontal = 1.dp),
      onClick = {
       period = key
       Data.prefs(c).edit().putString("performance_period", key).apply()
       WoogongWidget.updateAll(c)
      }) {
      Text(label, fontSize=11.sp, fontWeight = if (selected) FontWeight.SemiBold else FontWeight.Medium)
     }
    }
   }
  }
  if (window == null) {
   Text("상단 새로고침으로 비교 자료를 확인하세요.", style = MaterialTheme.typography.bodySmall)
  } else {
   PerformanceChart(window)
   HorizontalDivider(thickness = .5.dp, color = scheme.outlineVariant)
   Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(5.dp)) {
    val summary = listOf("우공이산" to window.last.model, "TQQQ" to window.last.tqqq, "버크셔 B" to window.last.brkb)
    summary.forEachIndexed { index, (name, value) ->
     Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(1.dp)) {
      Text(name, color = colors[index], fontSize = 11.sp, fontWeight = FontWeight.Medium)
      Text(Performance.percent(value), fontSize = 13.sp, fontWeight = FontWeight.SemiBold,
       style = androidx.compose.ui.text.TextStyle(fontFeatureSettings="tnum"))
     }
    }
   }
  }
 }
 Panel {
  Text("오늘의 배분", style = MaterialTheme.typography.titleMedium)
  Text(Data.allocation(s),fontSize=20.sp,fontWeight=FontWeight.SemiBold)
  Text("${s.optString("market_date")} 미국 종가 · ${if(stale)"저장 자료" else "갱신 완료"}",
   fontSize=11.sp,color=if(stale)Gold else scheme.onSurfaceVariant)
 }
 if(AllocationChange.pending(c)!=null&&!stale)Panel{Text("확인할 배분 변경이 있어요",fontWeight=FontWeight.Bold);TextButton(onClick=onReview){Text("변경 전·후 보기")}}
 PriceOutlook(s)
 LoanTiming(s.optJSONObject("loan_timing"),!stale,s.optString("market_date"),s.optString("valid_until"))
}
