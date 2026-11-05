package com.woogong.app

import androidx.compose.runtime.*
import androidx.compose.material3.TextButton
import androidx.compose.material3.Text
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp
import org.json.JSONObject
import java.time.Instant
import kotlinx.coroutines.delay

internal fun timingFresh(available:Boolean,supported:Boolean,until:String,now:Instant=Instant.now()):Boolean=try{available&&supported&&now.isBefore(Instant.parse(until))}catch(_:Exception){false}

@Composable internal fun LoanTiming(t:JSONObject?,available:Boolean,date:String,validUntil:String=t?.optString("valid_until")?:""){
 val now by produceState(Instant.now()){while(true){delay(1000);value=Instant.now()}}
 val fresh=timingFresh(available,t?.optBoolean("supported")==true,validUntil,now)
 Panel{
  Text("신규 차입 신호",fontWeight=FontWeight.Bold,color=Mint)
  Text(if(fresh)when(t!!.optString("phase")){"entry"->"신규 차입 검토";"hold"->"공격 배분 유지";"exit"->"차입분 정리 검토";else->"신규 차입 대기"} else "최신 결과 확인 중",fontSize=19.sp,fontWeight=FontWeight.Bold)
  Text("기준 $date",fontSize=11.sp)
 }
}
