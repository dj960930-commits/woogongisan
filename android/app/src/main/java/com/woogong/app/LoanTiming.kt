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
 var expanded by remember{mutableStateOf(false)}
 val now by produceState(Instant.now()){while(true){delay(1000);value=Instant.now()}}
 val fresh=timingFresh(available,t?.optBoolean("supported")==true,validUntil,now)
 Panel{
  Text("공격 전환 · 연구 신호",fontWeight=FontWeight.Bold,color=Mint)
  Text(if(fresh)t!!.optString("label") else "판정 보류 · 최신 검증 신호 필요",fontSize=19.sp,fontWeight=FontWeight.Bold)
  Text("기준 $date",fontSize=11.sp)
  TextButton(onClick={expanded=!expanded}){Text(if(expanded)"신호 설명 접기" else "신호 조건·차입 유의사항")}
  if(expanded){
  Text(t?.optString("entry_rule")?:"방어 → 공격 전환 첫 확정 종가에 진입 조건 확인")
  Text(t?.optString("exit_rule")?:"공격 종료 시 차입분 매도·상환 검토. 완제 전 재차입 금지.",fontSize=12.sp)
  Text("마통 한도 전액 사용이나 현금 0%를 뜻하지 않습니다. 은행 부채·금리·상환 여력은 미확인입니다.",fontSize=12.sp,color=Gold)
  Text("연구 기본안 17회 중 6회 손실. 이전 시기 대용 최악 -17.38%는 손실 상한이 아닙니다. 자동 차입·주문 증액과 연결되지 않습니다.",fontSize=11.sp)
  }
 }
}
