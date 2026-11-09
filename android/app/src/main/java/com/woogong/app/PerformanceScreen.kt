package com.woogong.app

import androidx.compose.runtime.*
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import org.json.JSONArray
import org.json.JSONObject

@Composable internal fun PerformanceScreen(s:JSONObject,basic:JSONObject){
 val c=LocalContext.current
 val ext=Data.prefs(c).getString("extended_backtest",null)?.let{try{JSONObject(it)}catch(_:Exception){null}}
 var recent by remember{mutableStateOf(true)}
 Text("모델 성과",style=MaterialTheme.typography.headlineSmall,fontWeight=FontWeight.Bold)
 Row(horizontalArrangement=Arrangement.spacedBy(8.dp)){
  FilterChip(selected=recent,onClick={recent=true},enabled=ext!=null,label={Text("최신까지")})
  FilterChip(selected=!recent,onClick={recent=false},label={Text("출시 기준")})
 }
 val b=if(recent&&ext!=null)ext else basic
 if(!Data.sameModel(s,b)){Text("현재 모델의 성과를 불러오는 중입니다.");return}
 Text(if(recent&&ext!=null)"최근 종가까지 이어서 계산한 결과" else "출시 때 기준으로 삼은 기간의 결과",fontSize=12.sp,color=MaterialTheme.colorScheme.onSurfaceVariant)
 Panel{
  Text("${b.getString("data_end")}까지",fontSize=12.sp,color=MaterialTheme.colorScheme.onSurfaceVariant)
  Text("연평균 성장 ${"%.1f".format(b.getDouble("cagr")*100)}%",fontSize=24.sp,fontWeight=FontWeight.Bold)
  Text("매년 일정하게 올랐다는 뜻은 아니에요. 복리로 환산한 평균입니다.",fontSize=12.sp,color=MaterialTheme.colorScheme.onSurfaceVariant)
  HistoryChart(b.getJSONArray("curve"),"nav")
 }
 basic.optJSONObject("execution_review")?.takeIf{Data.sameModel(s,basic)}?.let{review->
  val selected=review.getJSONObject("selected")
  Panel{
   Text("체결을 다음 시가로 늦추면",fontWeight=FontWeight.Bold)
   Text("${review.getString("start")} ~ ${review.getString("end")}",fontSize=11.sp)
   Text("연복리 %.2f%% · 최대낙폭 %.2f%%".format(selected.getDouble("cagr")*100,selected.getDouble("mdd")*100),fontSize=14.sp,fontWeight=FontWeight.SemiBold)
   Text("수익 대비 낙폭 지표(Calmar) %.2f".format(selected.getDouble("calmar")),fontSize=12.sp)
   Text("다음 거래일 시가 체결 · 편도 비용 0.1% · USD·세전",fontSize=11.sp,color=MaterialTheme.colorScheme.onSurfaceVariant)
  }
 }
 Panel{
  Text("최고점에서 얼마나 내려갔나요?",fontWeight=FontWeight.Bold)
  Text("최대 ${"%.1f".format(-b.getDouble("mdd")*100)}% 하락",fontSize=24.sp,fontWeight=FontWeight.Bold)
  Text("최고 자산이 1,000만원이었다면 약 ${"%,.0f".format(1000*(1+b.getDouble("mdd")))}만원까지 줄었던 구간입니다.",fontSize=13.sp)
  HistoryChart(b.getJSONArray("curve"),"drawdown")
  Text("이 정도 하락을 견딜 수 있는지 투자 금액을 정할 때 참고하세요.",fontSize=12.sp,color=MaterialTheme.colorScheme.onSurfaceVariant)
 }
}

@Composable private fun HistoryChart(data:JSONArray,key:String){
 val color=MaterialTheme.colorScheme.primary;val muted=MaterialTheme.colorScheme.onSurfaceVariant
 if(data.length()<2)return
 val values=(0 until data.length()).map{data.getJSONObject(it).getDouble(key)-(if(key=="nav")1 else 0)}
 Canvas(Modifier.fillMaxWidth().height(160.dp)){
  val left=46.dp.toPx();val bottom=size.height-8.dp.toPx();val lo=minOf(0.0,values.min());val hi=maxOf(0.0,values.max());val span=(hi-lo).coerceAtLeast(.01)
  fun x(i:Int)=left+(size.width-left)*i/(values.size-1)
  fun y(v:Double)=8.dp.toPx()+(bottom-8.dp.toPx())*(1-((v-lo)/span).toFloat())
  val paint=android.graphics.Paint(android.graphics.Paint.ANTI_ALIAS_FLAG).apply{this.color=muted.toArgb();textSize=10.sp.toPx()}
  for(v in listOf(lo,(lo+hi)/2,hi)){
   drawLine(muted.copy(alpha=.15f),Offset(left,y(v)),Offset(size.width,y(v)),1f)
   drawContext.canvas.nativeCanvas.drawText("%.0f%%".format(v*100),0f,y(v)+4.dp.toPx(),paint)
  }
  val path=Path().apply{moveTo(x(0),y(values[0]));for(i in 1 until values.size)lineTo(x(i),y(values[i]))}
  drawPath(path,color,style=Stroke(2.5.dp.toPx()))
 }
}
