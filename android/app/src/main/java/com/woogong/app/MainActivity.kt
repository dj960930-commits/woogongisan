package com.woogong.app

import android.Manifest
import android.os.Bundle
import androidx.activity.enableEdgeToEdge
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.sp
import androidx.compose.ui.graphics.Path
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
 override fun onNewIntent(intent:android.content.Intent){super.onNewIntent(intent);resumeTick++}
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
  var reviewRequest by remember{mutableIntStateOf(0)}
  val clockTick by produceState(0L){while(true){delay(1000);value=value+1}}
  LaunchedEffect(resumeTick){snap=Data.load(this@MainActivity,"snapshot");status=Data.load(this@MainActivity,"status");back=Data.load(this@MainActivity,"backtest");if(MeritzAccount.connected(this@MainActivity))try{withContext(Dispatchers.IO){MeritzAccount.sync(this@MainActivity)}}catch(_:Exception){}}
  val stale=remember(clockTick,snap,status,error){Data.stale(snap,status)||error.isNotEmpty()||Data.prefs(this@MainActivity).getString("sync_error","")!!.isNotEmpty()}
  AllocationPopup(snap,stale,resumeTick+reviewRequest)
  Scaffold(
   modifier=Modifier.windowInsetsPadding(WindowInsets.safeDrawing.only(WindowInsetsSides.Horizontal)),
   containerColor=MaterialTheme.colorScheme.background,
   topBar={AppHeader(tab,snap.optString("version").removePrefix("우공이산 ").removePrefix("우공 "),busy,::refresh)},
   bottomBar={AppTabBar(tab){tab=it}}
  ){padding->
   Column(Modifier.padding(padding).consumeWindowInsets(padding).fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal=14.dp),verticalArrangement=Arrangement.spacedBy(9.dp)){
    if(stale && tab in setOf(2,3))Text("저장 자료 · ${snap.optString("market_date")}",color=Gold,fontSize=12.sp)
    if(error.isNotEmpty() && tab in setOf(0,4))Text(error,color=MaterialTheme.colorScheme.error)
    when(tab){
     0->{
      ReturnsHome(snap,stale){reviewRequest++}
     }
     1->{
      var assetView by remember{mutableIntStateOf(0)}
      Row(horizontalArrangement=Arrangement.spacedBy(5.dp)){
       FilterChip(selected=assetView==0,onClick={assetView=0},label={Text("메리츠 계좌")})
       FilterChip(selected=assetView==1,onClick={assetView=1},label={Text("수동 기록")})
       FilterChip(selected=assetView==2,onClick={assetView=2},label={Text("운용 센터")})
      }
      when(assetView){0->MeritzScreen(snap,status);1->PortfolioScreen(snap,status,resumeTick);else->TradingScreen()}
     }
     2->{ModelDetails(snap){tab=4}}
     3->{PerformanceScreen(snap,back)}
     5->{WaveScreen()}
     4->{
      var connectionExpanded by remember{mutableStateOf(false)}
      Panel{Text("모델 설명과 주의사항",fontWeight=FontWeight.Bold);TextButton(onClick={tab=2}){Text("규칙·계산 기준 보기")};TextButton(onClick={connectionExpanded=!connectionExpanded}){Text(if(connectionExpanded)"연결 설정 접기" else "모델 연결 설정")}}
      Text(snap.optString("version"),color=MaterialTheme.colorScheme.onSurfaceVariant)
      var base by remember{mutableStateOf(Data.url(this@MainActivity))}
      if(connectionExpanded)Panel{Text("모델 결과 연결",fontWeight=FontWeight.Bold);Text("메리츠 계좌는 내 자산 → 메리츠 계좌에서 연결합니다. 이 주소는 우공 모델의 계산 결과를 받는 곳입니다.",fontSize=12.sp);OutlinedTextField(base,{base=it},label={Text("모델 결과 HTTPS 주소")},modifier=Modifier.fillMaxWidth(),singleLine=true);Button(onClick={try{base=SignalEndpoint.normalize(base);Data.prefs(this@MainActivity).edit().putString("url",base).apply();refresh()}catch(e:Exception){error=e.message?:"주소를 확인하세요"}}){Text("저장하고 결과 확인")};TextButton(onClick={base=BuildConfig.SIGNAL_BASE_URL;Data.prefs(this@MainActivity).edit().putString("url",base).apply();refresh()}){Text("우공이산 기본 주소로 복구")};Text(if(Data.prefs(this@MainActivity).getString("sync_error","").isNullOrEmpty())"표시 자료: ${status.optString("market_date")} · ${if(status.optString("state")=="ready")"계산 완료" else "과거 미리보기 / 자동 계산 미연결"}" else "결과 서버 연결을 다시 확인하세요",fontSize=11.sp)}
      CloseAlertSettings(resumeTick)
      Panel{Text("위젯 컬렉션",fontWeight=FontWeight.Bold);Text("홈 화면을 길게 누르고 위젯 → 우공이산에서 선택하세요.\n요약 3×2 · 그래프 5×2 · 상세 5×3\n위젯의 기간 버튼으로 기간을 바꿀 수 있습니다. 크기가 작아지면 요약형으로 자동 전환되며 시스템 화면 모드도 따라갑니다.");Text("화면 테마 · 시스템 설정 사용",color=MaterialTheme.colorScheme.onSurfaceVariant,fontSize=12.sp)}
     }
    };Spacer(Modifier.height(10.dp))
   }
  }
 }
}
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

