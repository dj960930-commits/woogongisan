package com.woogong.app

import android.content.Intent
import android.net.Uri
import android.os.Build
import java.time.Instant
import java.time.format.DateTimeFormatter
import android.provider.Settings
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

@Composable internal fun CloseAlertSettings(resumeTick:Int){
 val c=LocalContext.current
 var enabled by remember{mutableStateOf(CloseAlerts.enabled(c))}
 var allowed by remember{mutableStateOf(CloseAlerts.allowed(c))}
 var exact by remember{mutableStateOf(MorningAlerts.exactAllowed(c))}
 var message by remember{mutableStateOf("")}
 LaunchedEffect(resumeTick){allowed=CloseAlerts.allowed(c);exact=MorningAlerts.exactAllowed(c);MorningAlerts.schedule(c)}
 Panel{
  Text("장 마감·휴장일 알림",fontWeight=FontWeight.Bold)
  Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween){Text("매일 장 마감 확인");Switch(checked=enabled,onCheckedChange={enabled=it;CloseAlerts.enable(c,it)})}
  Text(if(!enabled)"앱 알림 꺼짐" else if(allowed)"휴대폰 알림 허용됨" else "휴대폰에서 우공이산 알림을 허용해주세요.",color=if(enabled&&allowed)Mint else Gold)
  Text("미국장 마감 5분 뒤 확인을 시작하고, 새 확정 종가 결과가 게시되면 알립니다. 조기 폐장·서머타임을 반영하며 휴장일에도 최신 결과를 안내합니다. 서버가 아직 계산 중이면 대기 상태를 표시합니다.",fontSize=12.sp)
  Text(if(exact)"장 마감 확인 시간 예약 가능" else "정확한 확인 시간 허용 필요 · 현재는 지연 가능한 예약",color=if(exact)Mint else Gold,fontSize=12.sp)
  if(Build.VERSION.SDK_INT>=31&&!exact)TextButton(onClick={c.startActivity(Intent(Settings.ACTION_REQUEST_SCHEDULE_EXACT_ALARM,Uri.parse("package:"+c.packageName)))}){Text("알람 및 리마인더 허용하기")}
  Text("결과 게시까지의 시간과 기기 절전·통신에 따라 결과 알림은 늦어질 수 있습니다. 보조 조회는 약 15분 간격입니다. 현재 배포에는 Firebase 서버 푸시 연결이 없습니다.",fontSize=11.sp)
  fun localTime(raw:String?)=try{Instant.parse(raw).atZone(MorningPolicy.korea).format(DateTimeFormatter.ofPattern("MM-dd HH:mm:ss"))+" (한국시간)"}catch(_:Exception){"기록 없음"}
  val next=Data.prefs(c).getLong("morning_next_at",0)
  if(enabled&&next>0)Text("다음 확인 예약: "+localTime(Instant.ofEpochMilli(next).toString()),fontSize=11.sp)
  Text("최근 모델 조회: "+localTime(Data.prefs(c).getString("model_check_at",null)),fontSize=11.sp)
  Button(enabled=enabled,onClick={allowed=CloseAlerts.allowed(c);message=if(CloseAlerts.test(c))"테스트 알림을 보냈습니다. 알림창에서 확인하세요." else "휴대폰 알림 설정을 열어 우공이산 알림과 ‘장 마감 결과’ 채널을 허용하세요."}){Text("알림 테스트")}
  TextButton(onClick={c.startActivity(Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE,c.packageName))}){Text("휴대폰 알림 설정 열기")}
  val last=Data.prefs(c).getString("close_alert_last_at",null)
  Text(last?.let{"최근 새 결과 알림: "+localTime(it)}?:"아직 새 결과 알림 기록이 없습니다.",fontSize=11.sp)
  if(message.isNotEmpty())Text(message,fontSize=12.sp)
 }
}
