package com.woogong.app

import android.Manifest
import android.content.ClipData
import android.content.ClipboardManager
import android.os.Bundle
import androidx.activity.enableEdgeToEdge
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Brush
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.unit.sp
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.google.firebase.FirebaseApp
import com.google.firebase.messaging.FirebaseMessaging
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.coroutines.delay
import org.json.JSONArray
import org.json.JSONObject

class MainActivity:ComponentActivity(){
 private var resumeTick by mutableIntStateOf(0)
 override fun onResume(){super.onResume();resumeTick++;MorningAlerts.schedule(this)}
 private val permission=registerForActivityResult(ActivityResultContracts.RequestPermission()){}
 override fun onCreate(savedInstanceState:Bundle?){super.onCreate(savedInstanceState)
  enableEdgeToEdge()
  if(android.os.Build.VERSION.SDK_INT>=33)permission.launch(Manifest.permission.POST_NOTIFICATIONS)
  if(FirebaseApp.getApps(this).isNotEmpty())FirebaseMessaging.getInstance().token.addOnSuccessListener{Data.prefs(this).edit().putString("fcm_token",it).apply()}
  setContent{WoogongTheme { App() }}
 }
 @Composable fun App(){
  var tab by remember{mutableIntStateOf(0)};var snap by remember{mutableStateOf(Data.load(this,"snapshot"))};var status by remember{mutableStateOf(Data.load(this,"status"))}
  var back by remember{mutableStateOf(Data.load(this,"backtest"))};var busy by remember{mutableStateOf(false)};var error by remember{mutableStateOf("")};val scope=rememberCoroutineScope()
  DisposableEffect(Unit){
   val prefs=Data.prefs(this@MainActivity)
   val listener=android.content.SharedPreferences.OnSharedPreferenceChangeListener{_,key->
    if(key in setOf("snapshot","status","backtest","sync_error")){
     snap=Data.load(this@MainActivity,"snapshot");status=Data.load(this@MainActivity,"status");back=Data.load(this@MainActivity,"backtest")
    }
   }
   prefs.registerOnSharedPreferenceChangeListener(listener)
   onDispose{prefs.unregisterOnSharedPreferenceChangeListener(listener)}
  }
  fun refresh(){scope.launch{busy=true;error="";try{withContext(Dispatchers.IO){Data.sync(this@MainActivity)};snap=Data.load(this@MainActivity,"snapshot");status=Data.load(this@MainActivity,"status");back=Data.load(this@MainActivity,"backtest");WoogongWidget.updateAll(this@MainActivity)}catch(e:Exception){error=e.message?:"갱신 실패"}finally{busy=false}}}
  LaunchedEffect(Unit){if(Data.url(this@MainActivity).isNotBlank())refresh()}
  val clockTick by produceState(0L){while(true){delay(1000);value=value+1}}
  LaunchedEffect(resumeTick){snap=Data.load(this@MainActivity,"snapshot");status=Data.load(this@MainActivity,"status");back=Data.load(this@MainActivity,"backtest");if(MeritzAccount.connected(this@MainActivity))try{withContext(Dispatchers.IO){MeritzAccount.sync(this@MainActivity)}}catch(_:Exception){}}
  val stale=remember(clockTick,snap,status,error){Data.stale(snap,status)||error.isNotEmpty()||Data.prefs(this@MainActivity).getString("sync_error","")!!.isNotEmpty()}
  val icons=listOf(Icons.Outlined.Home,Icons.Outlined.AccountBalanceWallet,Icons.Outlined.Lightbulb,Icons.Outlined.ShowChart,Icons.Outlined.Settings)
  Scaffold(modifier=Modifier.windowInsetsPadding(WindowInsets.safeDrawing.only(WindowInsetsSides.Horizontal)),containerColor=MaterialTheme.colorScheme.background,
   topBar={Row(Modifier.fillMaxWidth().statusBarsPadding().padding(horizontal=24.dp,vertical=18.dp),horizontalArrangement=Arrangement.SpaceBetween,verticalAlignment=Alignment.CenterVertically){
    Column(Modifier.weight(1f)){Text("우공이산",maxLines=1,overflow=TextOverflow.Ellipsis,fontSize=25.sp,fontWeight=FontWeight.ExtraBold,letterSpacing=(-1).sp);Text("차분하게, 더 멀리",fontSize=11.sp,color=MaterialTheme.colorScheme.onSurfaceVariant)}
    Surface(color=MaterialTheme.colorScheme.primaryContainer,shape=RoundedCornerShape(12.dp)){Text(snap.optString("version").removePrefix("우공 "),Modifier.padding(12.dp,8.dp),fontSize=10.sp,color=MaterialTheme.colorScheme.onPrimaryContainer,fontWeight=FontWeight.Bold)}
   }},bottomBar={NavigationBar(containerColor=MaterialTheme.colorScheme.surface,tonalElevation=0.dp){listOf("오늘","내 자산","이유","성과","설정").forEachIndexed{i,label->NavigationBarItem(selected=tab==i,onClick={tab=i},icon={Icon(icons[i],contentDescription=label)},label={Text(label,fontSize=11.sp)},colors=NavigationBarItemDefaults.colors(selectedIconColor=Mint,selectedTextColor=Mint,indicatorColor=MaterialTheme.colorScheme.primaryContainer,unselectedIconColor=MaterialTheme.colorScheme.onSurfaceVariant,unselectedTextColor=MaterialTheme.colorScheme.onSurfaceVariant))}}}){padding->
   Column(Modifier.padding(padding).consumeWindowInsets(padding).fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal=20.dp),verticalArrangement=Arrangement.spacedBy(14.dp)){
    if(stale&&tab!=1)Panel{Text(if(snap.optString("mode")!="live")"과거 자료 미리보기" else "새 종가 갱신 대기",color=Gold,fontWeight=FontWeight.Bold);Text("기준일 ${snap.optString("market_date")} · 현재 매매 신호로 사용하지 마세요.")}
    if(error.isNotEmpty())Text(error,color=MaterialTheme.colorScheme.error)
    when(tab){
     0->{
      ReturnsHome(snap,stale)
      Button(onClick={refresh()},enabled=!busy,modifier=Modifier.fillMaxWidth()){Text(if(busy)"확인 중…" else "최신 결과 확인")}
     }
     1->{
      var assetView by remember{mutableIntStateOf(0)}
      Row(horizontalArrangement=Arrangement.spacedBy(8.dp)){
       FilterChip(selected=assetView==0,onClick={assetView=0},label={Text("메리츠 계좌")})
       FilterChip(selected=assetView==1,onClick={assetView=1},label={Text("수동 기록")})
       FilterChip(selected=assetView==2,onClick={assetView=2},label={Text("운용 센터")})
      }
      when(assetView){0->MeritzScreen(snap,status);1->PortfolioScreen(snap,status,resumeTick);else->TradingScreen()}
     }
     2->{
      Text("왜 이 목표인가요?",style=MaterialTheme.typography.headlineSmall,fontWeight=FontWeight.Bold)
      Text("실제로 적용된 규칙과 숫자를 보여드립니다.")
      val reasons=snap.getJSONArray("reasons")
      for(i in 0 until reasons.length()){val reason=reasons.getJSONObject(i);Panel{Text(reason.getString("title"),color=if(reason.optBoolean("active"))Mint else Gold,fontWeight=FontWeight.Bold);Text(reason.getString("description"))}}
      Panel{Text("방어자산의 상대 흐름",fontWeight=FontWeight.Bold);Text("GLD / BRK.B · EMA84와 EMA378");Lines(snap.getJSONObject("charts").getJSONArray("defense"),listOf("defense_ratio","defense_fast","defense_slow"))}
      Panel{Text("QQQ 고점 대비 낙폭",fontWeight=FontWeight.Bold);Lines(snap.getJSONObject("charts").getJSONArray("drawdown"),listOf("qqq_drawdown"));Text("급락 상태는 25일 고점 대비 -6%에서 시작합니다. 해제에는 별도 회복·장기 추세 조건이 필요합니다.")}
     }
     3->{
      Text("과거 성과",style=MaterialTheme.typography.headlineSmall,fontWeight=FontWeight.Bold)
      var extended by remember{mutableStateOf(false)}
      val ext=Data.prefs(this@MainActivity).getString("extended_backtest",null)
      Row{FilterChip(selected=!extended,onClick={extended=false},label={Text("동결 검증")});Spacer(Modifier.width(8.dp));FilterChip(selected=extended,onClick={extended=true},label={Text("최신 확장")},enabled=ext!=null)}
      val b=if(extended&&ext!=null)JSONObject(ext) else back
      if(Data.sameModel(snap,b)){
      Panel{Text(b.getString("label"),color=Mint);Text("종료 ${b.getString("data_end")}");Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween){Metric("연복리",b.getDouble("cagr"));Metric("최대 낙폭",b.getDouble("mdd"));Column{Text("CAGR/MDD");Text("%.2f".format(b.getDouble("calmar")),fontWeight=FontWeight.Bold)}};Lines(b.getJSONArray("curve"),listOf("nav"))}
      Panel{Text("낙폭의 깊이",fontWeight=FontWeight.Bold);Lines(b.getJSONArray("curve"),listOf("drawdown"));Text("거래일 종가 기준입니다. 장중 낙폭·실제 세금·환율·정수주 체결은 포함하지 않습니다.")}
      if(!extended)Panel{Text("장기 합성은 별도 참고",fontWeight=FontWeight.Bold);Text(b.optString("synthetic_label")+" · CAGR %.2f%%".format(b.optDouble("synthetic_cagr")*100))}
      Panel{Text(snap.optString("approval"),fontWeight=FontWeight.Bold);Text(snap.optString("research_note"))}
      if(!extended){Panel{Text("비용·체결 민감도",fontWeight=FontWeight.Bold);val cases=back.getJSONArray("scenarios");for(i in 0 until cases.length()){val row=cases.getJSONObject(i);val timing=when(row.getString("mode")){"next_open"->"다음 시가";"same_close_reference"->"당일 종가 가격 가정";else->"다음 종가"};Text("${if(row.optString("period")=="long_synthetic")"2015~ BTC 대용" else "실제 BITO"} · $timing · 추가 비용 ${"%.1f".format(row.getDouble("slippage")*100)}% · 체결 ${"%.0f".format(row.getDouble("fill")*100)}%\nCAGR ${"%.2f".format(row.getDouble("cagr")*100)}% / MDD ${"%.2f".format(row.getDouble("mdd")*100)}% / 비율 ${"%.2f".format(row.getDouble("calmar"))}",style=MaterialTheme.typography.bodySmall)}}}
      }else Panel{Text("선택 모델의 백테스트 갱신 대기",fontWeight=FontWeight.Bold);Text("현재 목표와 같은 버전의 결과가 준비되면 표시합니다.")}
     }
     4->{
      Panel{Text("현재 모델",fontWeight=FontWeight.Bold);Text(snap.optString("version"));Text(snap.optString("approval"));Text("모델 변경은 서버 설정에서 반영되며, 보유량은 휴대폰에 유지됩니다.")}
      var base by remember{mutableStateOf(Data.url(this@MainActivity))}
      Panel{Text("모델 결과 연결",fontWeight=FontWeight.Bold);Text("메리츠 계좌는 내 자산 → 메리츠 계좌에서 연결합니다. 이 주소는 우공 모델의 계산 결과를 받는 곳입니다.",fontSize=12.sp);OutlinedTextField(base,{base=it},label={Text("모델 결과 HTTPS 주소")},modifier=Modifier.fillMaxWidth(),singleLine=true);Button(onClick={try{base=SignalEndpoint.normalize(base);Data.prefs(this@MainActivity).edit().putString("url",base).apply();refresh()}catch(e:Exception){error=e.message?:"주소를 확인하세요"}}){Text("저장하고 결과 확인")};TextButton(onClick={base=BuildConfig.SIGNAL_BASE_URL;Data.prefs(this@MainActivity).edit().putString("url",base).apply();refresh()}){Text("우공이산 기본 주소로 복구")};Text(if(Data.prefs(this@MainActivity).getString("sync_error","").isNullOrEmpty())"표시 자료: ${status.optString("market_date")} · ${if(status.optString("state")=="ready")"계산 완료" else "과거 미리보기 / 자동 계산 미연결"}" else "결과 서버 연결을 다시 확인하세요",fontSize=11.sp)}
      CloseAlertSettings(resumeTick)
      Panel{Text("위젯 컬렉션",fontWeight=FontWeight.Bold);Text("홈 화면을 길게 누르고 위젯 → 우공이산에서 선택하세요.\n요약 3×2 · 그래프 5×2 · 상세 5×3\n위젯의 기간 버튼으로 기간을 바꿀 수 있습니다. 크기가 작아지면 요약형으로 자동 전환되며 시스템 화면 모드도 따라갑니다.");Text("화면 테마 · 시스템 설정 사용",color=MaterialTheme.colorScheme.onSurfaceVariant,fontSize=12.sp)}
     }
    };Spacer(Modifier.height(18.dp))
   }
  }
 }
}
@Composable internal fun Panel(content:@Composable ColumnScope.()->Unit){Card(Modifier.fillMaxWidth(),shape=RoundedCornerShape(24.dp),colors=CardDefaults.cardColors(containerColor=MaterialTheme.colorScheme.surface)){Column(Modifier.padding(20.dp),verticalArrangement=Arrangement.spacedBy(9.dp),content=content)}}
@Composable private fun Metric(title:String,value:Double){Column{Text(title);Text("%.2f%%".format(value*100),fontWeight=FontWeight.Bold)}}
@Composable internal fun Lines(data:JSONArray,keys:List<String>){
 val lineColors=listOf(Mint,Gold,MaterialTheme.colorScheme.onSurfaceVariant)
 Canvas(Modifier.fillMaxWidth().height(160.dp).padding(vertical=12.dp)){
  if(data.length()<2)return@Canvas
  val values=(0 until data.length()).flatMap{i->keys.map{data.getJSONObject(i).getDouble(it)}};val lo=values.min();val range=(values.max()-lo).coerceAtLeast(1e-9)
  for((index,key) in keys.withIndex()){
   val path=Path();for(i in 0 until data.length()){val x=size.width*i/(data.length()-1);val y=size.height*(1-((data.getJSONObject(i).getDouble(key)-lo)/range).toFloat());if(i==0)path.moveTo(x,y)else path.lineTo(x,y)}
   drawPath(path,lineColors[index%3],style=androidx.compose.ui.graphics.drawscope.Stroke(width=if(index==0)3f else 2f))
  }
  drawLine(Color(0xffdfe6e5),Offset(0f,size.height),Offset(size.width,size.height),1f)
 }
}

