package com.woogong.app

import androidx.compose.runtime.*
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import org.json.JSONObject

@Composable internal fun PriceOutlook(s:JSONObject){
 val outlook=s.optJSONObject("price_outlook")?:return
 val assets=outlook.optJSONArray("assets")?:return
 if(assets.length()==0)return
 var selected by remember{mutableIntStateOf(0)}
 val a=assets.getJSONObject(selected.coerceAtMost(assets.length()-1));val windows=a.getJSONArray("windows")
 if(windows.length()==0)return
 val price=a.getDouble("close");val middle=windows.getJSONObject(if(windows.length()>1)1 else 0)
 val primary=MaterialTheme.colorScheme.primary
 Panel{
  Text("가격 흐름 미리보기",fontWeight=FontWeight.Bold)
  Row(horizontalArrangement=Arrangement.spacedBy(6.dp)){
   for(i in 0 until assets.length())FilterChip(selected=selected==i,onClick={selected=i},label={Text(assets.getJSONObject(i).getString("symbol").replace("BRK.B","버크셔"))})
  }
  Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween){
   Text("약 1개월 뒤 중앙 경로",fontSize=12.sp,color=MaterialTheme.colorScheme.onSurfaceVariant)
   Text("%+.1f%%".format((middle.getDouble("median")/price-1)*100),fontWeight=FontWeight.Bold,color=primary)
  }
  val horizons=listOf(0)+(0 until windows.length()).map{windows.getJSONObject(it).getInt("sessions")}
  val lower=listOf(price)+(0 until windows.length()).map{windows.getJSONObject(it).getDouble("lower")}
  val upper=listOf(price)+(0 until windows.length()).map{windows.getJSONObject(it).getDouble("upper")}
  val median=listOf(price)+(0 until windows.length()).map{windows.getJSONObject(it).getDouble("median")}
  Canvas(Modifier.fillMaxWidth().height(130.dp)){
   val lo=lower.min();val span=(upper.max()-lo).coerceAtLeast(.01)
   fun x(i:Int)=size.width*horizons[i]/horizons.last().toFloat()
   fun y(v:Double)=size.height*(1-((v-lo)/span).toFloat())
   val band=Path().apply{moveTo(x(0),y(lower[0]));for(i in 1 until lower.size)lineTo(x(i),y(lower[i]));for(i in upper.indices.reversed())lineTo(x(i),y(upper[i]));close()}
   drawPath(band,primary.copy(alpha=.13f))
   drawLine(primary.copy(alpha=.2f),Offset(0f,y(price)),Offset(size.width,y(price)),1f)
   val path=Path().apply{moveTo(x(0),y(median[0]));for(i in 1 until median.size)lineTo(x(i),y(median[i]))}
   drawPath(path,primary,style=Stroke(3.dp.toPx()))
  }
  Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween){Text("현재 ${usd(price)}",fontSize=11.sp);Text("3개월",fontSize=11.sp)}
  Text("선은 중앙 경로, 음영은 과거에 관측된 변동 범위예요.",fontSize=12.sp,color=MaterialTheme.colorScheme.onSurfaceVariant)
 }
}
