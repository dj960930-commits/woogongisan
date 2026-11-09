package com.woogong.app

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.time.Instant

@Composable internal fun MeritzScreen(snap:JSONObject,status:JSONObject){
 val c=LocalContext.current;val scope=rememberCoroutineScope()
 var data by remember{mutableStateOf(MeritzAccount.cached(c))};var settings by remember{mutableStateOf(!MeritzAccount.connected(c))}
 var appKey by remember{mutableStateOf("")};var secret by remember{mutableStateOf("")};var busy by remember{mutableStateOf(false)};var message by remember{mutableStateOf("")}
 var continueHistory by remember{mutableStateOf(false)};var restoreKey by remember{mutableStateOf<String?>(null)}
 fun refresh(){if(busy)return;scope.launch{busy=true;message="";try{data=withContext(Dispatchers.IO){MeritzAccount.sync(c)}}catch(e:Exception){message=e.message?:"메리츠 조회 실패"}finally{busy=false}}}
 LaunchedEffect(Unit){if(MeritzAccount.connected(c))refresh()}
 DisposableEffect(Unit){
  val prefs=Data.prefs(c)
  val listener=android.content.SharedPreferences.OnSharedPreferenceChangeListener{_,key->if(key=="meritz_account_v1"||key=="meritz_sync_failed")data=MeritzAccount.cached(c)}
  prefs.registerOnSharedPreferenceChangeListener(listener)
  onDispose{prefs.unregisterOnSharedPreferenceChangeListener(listener)}
 }
 Text("내 메리츠 자산",fontSize=25.sp,fontWeight=FontWeight.Bold)
 Text("메리츠 Open API에서 잔고와 평가액을 자동으로 가져옵니다.",fontSize=12.sp)
 if(message.isNotEmpty())Panel{Text(message,color=MaterialTheme.colorScheme.error)}
 if(settings)Panel{
  Text("메리츠 계좌 연결",fontWeight=FontWeight.Bold)
  Text("발급받은 App Key와 App Secret을 입력하세요. 앱이 메리츠에 직접 인증하며, 키와 계좌 기록은 이 휴대폰에서 암호화해 보관합니다. 잔고·평가액만 조회합니다.",fontSize=12.sp)
  OutlinedTextField(appKey,{appKey=it},label={Text("메리츠 App Key")},visualTransformation=PasswordVisualTransformation(),singleLine=true,modifier=Modifier.fillMaxWidth())
  OutlinedTextField(secret,{secret=it},label={Text("메리츠 App Secret")},visualTransformation=PasswordVisualTransformation(),singleLine=true,modifier=Modifier.fillMaxWidth())
  if(data?.optJSONObject("account")!=null)Row(verticalAlignment=androidx.compose.ui.Alignment.CenterVertically){
   Checkbox(checked=continueHistory,onCheckedChange={continueHistory=it})
   Text("새 키도 같은 계좌라면 기존 일별 기록 이어쓰기",fontSize=12.sp)
  }
  Button(enabled=!busy,onClick={try{MeritzAccount.connect(c,appKey,secret,continueHistory);appKey="";secret="";continueHistory=false;data=null;settings=false;refresh()}catch(e:Exception){message=e.message?:"키를 확인하세요"}},modifier=Modifier.fillMaxWidth()){Text("암호화 저장하고 메리츠 연결")}
  Text("PC에서 입력했던 키는 저장하지 않아 휴대폰에서 한 번 입력해야 합니다. 계좌번호·잔고·주식 수량은 입력하지 않습니다.",fontSize=11.sp)
 }
 val a=data?.optJSONObject("account")
 if(a==null){Panel{Text(if(busy)"메리츠 자산을 불러오고 있습니다…" else "연결하면 보유 종목·현금·평가액이 표시됩니다.")}}
 else {
  val stale=MeritzAccount.failed(c)||try{WidgetSummary.expired(Instant.parse(a.getString("as_of")),Instant.now())}catch(_:Exception){true}
  Panel{
   Text("메리츠 계좌 평가액",fontWeight=FontWeight.Bold)
   Text(won(a.getDouble("total_krw")),fontSize=29.sp,fontWeight=FontWeight.Bold)
   Text("메리츠 API가 반환한 총자산 · 외화 현금 포함",fontSize=11.sp)
   Text("조회 ${a.getString("as_of")}${if(stale)" · 이전 잔고 / 갱신 필요" else " · 연결됨"}",fontSize=10.sp,color=if(stale)Gold else Mint)
   Text("원화 예수금 ${won(a.getDouble("cash_krw"))}\n외화 예수금 원화환산 ${won(a.getDouble("foreign_cash_krw"))}\n유가증권 평가 ${won(a.getDouble("securities_krw"))}",fontSize=12.sp)
   if(a.getDouble("loans_krw")!=0.0)Text("증권사 대출 ${won(a.getDouble("loans_krw"))}",color=Gold)
   val cash=a.getJSONArray("currencies");for(i in 0 until cash.length()){val row=cash.getJSONObject(i);Text("${row.getString("currency")} 현금 ${"%,.2f".format(row.getDouble("amount"))}",fontSize=12.sp)}
   Button(enabled=!busy,onClick={refresh()},modifier=Modifier.fillMaxWidth()){Text(if(busy)"조회 중…" else "메리츠 자산 새로고침")}
  }
  Panel{
   Text("보유 주식",fontWeight=FontWeight.Bold);val positions=a.getJSONArray("positions")
   if(positions.length()==0)Text("조회된 보유 종목이 없습니다.")
   for(i in 0 until positions.length()){
    val p=positions.getJSONObject(i);Text("${p.getString("name")} · ${p.getString("symbol")}",fontWeight=FontWeight.Bold)
    Text("${"%,.6f".format(p.getDouble("quantity")).trimEnd('0').trimEnd('.')}주 · ${p.getString("kind")}",fontSize=11.sp)
    Text("${won(p.getDouble("value_krw"))} · 평가손익 ${won(p.getDouble("profit_krw"))}",fontSize=12.sp)
    HorizontalDivider()
   }
  }
  MeritzPlan(a,snap,status,stale)
  Panel{
   Text("일별 자산",fontWeight=FontWeight.Bold);val history=data!!.getJSONArray("history")
   Text("하루 한 건씩 자동 기록합니다. 증감에는 입출금이 포함되며 투자 수익률과 다릅니다.",fontSize=11.sp)
   if(history.length()>1){val latest=history.getJSONObject(history.length()-1);val previous=history.getJSONObject(history.length()-2);Text("이전 기록 대비 ${won(latest.getDouble("total_krw")-previous.getDouble("total_krw"))}",fontWeight=FontWeight.Bold)}
   for(i in history.length()-1 downTo maxOf(0,history.length()-7)){val row=history.getJSONObject(i);Text("${row.getString("day")} · ${won(row.getDouble("total_krw"))}",fontSize=12.sp)}
  }
 }
 val archives=MeritzAccount.archives(c)
 if(a!=null&&archives.isNotEmpty())Panel{
  Text("보관된 이전 기록",fontWeight=FontWeight.Bold)
  Text("같은 계좌의 기록만 현재 기록에 이어 붙이세요.",fontSize=11.sp)
  archives.forEach{(key,archive)->
   val history=archive.optJSONArray("history");val last=if(history!=null&&history.length()>0)history.optJSONObject(history.length()-1) else null
   TextButton(onClick={restoreKey=key}){Text("기록 "+key.takeLast(4)+" · "+(last?.optString("day")?:"날짜 없음")+" 이어쓰기")}
  }
 }
 restoreKey?.let{key->AlertDialog(onDismissRequest={restoreKey=null},title={Text("같은 계좌의 기록인가요?")},
  text={Text("확인하면 보관된 기록을 현재 계좌의 일별 기록과 합칩니다. 같은 날짜는 현재 기록을 사용합니다.")},
  confirmButton={TextButton(onClick={try{MeritzAccount.restoreHistory(c,key);data=MeritzAccount.cached(c);message="이전 기록을 이어 붙였습니다."}catch(_:Exception){message="이전 기록을 불러오지 못했습니다."};restoreKey=null}){Text("같은 계좌 · 이어쓰기")}},
  dismissButton={TextButton(onClick={restoreKey=null}){Text("취소")}})}
 if(MeritzAccount.connected(c))TextButton(enabled=!busy,onClick={settings=!settings}){Text(if(settings)"연결 설정 접기" else "메리츠 연결 관리")}
 if(settings&&MeritzAccount.connected(c))TextButton(enabled=!busy,onClick={MeritzAccount.disconnect(c);data=null;appKey="";secret="";message="이 휴대폰의 메리츠 키와 계좌 기록을 삭제했습니다."}){Text("연결 해제 · 기기 기록 삭제")}
}
