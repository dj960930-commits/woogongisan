package com.woogong.app

import android.content.Context
import androidx.compose.runtime.*
import androidx.compose.foundation.background
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

@Composable internal fun ReturnsHome(s:JSONObject,stale:Boolean){
 val c=LocalContext.current
 var period by remember{mutableStateOf(Data.prefs(c).getString("performance_period","1m")?:"1m")}
 val window=Performance.read(s,period);val scheme=MaterialTheme.colorScheme;val colors=PerformanceColors
 Card(Modifier.fillMaxWidth(),shape=RoundedCornerShape(28.dp),colors=CardDefaults.cardColors(containerColor=scheme.surface)){
  Column(Modifier.padding(22.dp),verticalArrangement=Arrangement.spacedBy(16.dp)){
   Text("MODEL / BENCHMARK",fontSize=10.sp,letterSpacing=2.sp,color=scheme.onSurfaceVariant,fontWeight=FontWeight.SemiBold)
   Text("우공이산, 시장과 나란히",fontSize=22.sp,fontWeight=FontWeight.Bold,letterSpacing=(-0.6).sp)
   Surface(color=scheme.background,shape=RoundedCornerShape(14.dp)){
    Row(Modifier.fillMaxWidth().padding(3.dp)){
     Performance.periods.forEach{(key,label)->TextButton(modifier=Modifier.weight(1f),shape=RoundedCornerShape(11.dp),colors=ButtonDefaults.textButtonColors(containerColor=if(period==key)scheme.primaryContainer else Color.Transparent),contentPadding=PaddingValues(horizontal=0.dp),onClick={period=key;Data.prefs(c).edit().putString("performance_period",key).apply();WoogongWidget.updateAll(c)}){Text(label,color=if(period==key)scheme.onPrimaryContainer else scheme.onSurfaceVariant,fontSize=12.sp,fontWeight=if(period==key)FontWeight.Bold else FontWeight.Normal)}}
    }
   }
   if(window==null){Text("비교 자료를 불러오는 중입니다. 최신 결과 확인을 눌러주세요.",fontSize=13.sp,color=scheme.onSurfaceVariant)}
   else {
    Column(verticalArrangement=Arrangement.spacedBy(5.dp)){
     Text("● 우공이산 모델",fontSize=12.sp,color=colors[0],fontWeight=FontWeight.SemiBold)
     Text(Performance.percent(window.last.model),fontSize=38.sp,fontWeight=FontWeight.Bold,letterSpacing=(-1.5).sp,color=scheme.onSurface)
     Text("선택 기간의 누적 수익률",fontSize=11.sp,color=scheme.onSurfaceVariant)
    }
    PerformanceChart(window)
    listOf("TQQQ" to window.last.tqqq,"버크셔 B" to window.last.brkb).forEachIndexed{i,(name,value)->
     Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween){Text("● $name",fontSize=13.sp,color=colors[i+1]);Text(Performance.percent(value),fontSize=17.sp,fontWeight=FontWeight.SemiBold,color=colors[i+1])}
    }
    HorizontalDivider(color=scheme.outlineVariant)
    Text("동일 기간 시작 0% · USD · 세전",fontSize=11.sp,color=scheme.onSurfaceVariant)
    Text(s.optJSONObject("performance")?.optString("basis")?.takeIf{it.isNotBlank()}?:"계산 기준을 확인해 주세요.",fontSize=10.sp,color=scheme.onSurfaceVariant,lineHeight=16.sp)
   }
  }
 }
 Panel{
  Text("오늘의 모델",fontSize=12.sp,color=scheme.onSurfaceVariant)
  Text(Data.allocation(s),fontSize=23.sp,fontWeight=FontWeight.Bold)
  Text("${s.optString("market_date")} 미국 종가 · ${if(stale)"갱신 대기" else "갱신 완료"}",fontSize=11.sp,color=if(stale)Gold else scheme.onSurfaceVariant)
 }
 PriceOutlook(s)
 LoanTiming(s.optJSONObject("loan_timing"),!stale,s.optString("market_date"),s.optString("valid_until"))
}
