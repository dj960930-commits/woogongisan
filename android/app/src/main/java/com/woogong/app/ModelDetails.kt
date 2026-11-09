package com.woogong.app

import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.material3.*
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.platform.LocalContext
import android.content.Intent
import android.net.Uri
import org.json.JSONObject

@Composable internal fun ModelDetails(s:JSONObject,onBack:()->Unit){
 val context=LocalContext.current
 TextButton(onClick=onBack){Text("← 설정으로")}
 StrategyGuide()
 TextButton(onClick={context.startActivity(Intent(Intent.ACTION_VIEW,Uri.parse(BuildConfig.SIGNAL_BASE_URL.trimEnd('/')+"/investment-lab.html")))}){Text("내 투자 조건 비교 ↗")}
 Text("표시 중인 신호의 판단 근거",style=MaterialTheme.typography.titleMedium,fontWeight=FontWeight.Bold)
 val reasons=s.optJSONArray("reasons")
 if(reasons!=null)for(i in 0 until reasons.length()){
  val r=reasons.getJSONObject(i)
  Panel{Text(r.getString("title"),fontWeight=FontWeight.Bold);Text(r.getString("description"))}
 }
 Panel{
  Text("수익률 계산 기준",fontWeight=FontWeight.Bold)
  Text(s.optJSONObject("performance")?.optString("basis")?:"USD · 당일 확정 종가 후 동일 가격 체결 가정")
  Text("최종 종가를 확인한 뒤 같은 가격에 거래했다고 가정한 모델 계산입니다. 실제 계좌의 체결·수익률과는 다릅니다.")
  Text(s.optString("research_note"))
 }
 val forecast=s.optJSONObject("price_outlook")
 if(forecast!=null)Panel{Text("가격 흐름 그래프 읽기",fontWeight=FontWeight.Bold);Text(forecast.optString("method"));Text(forecast.optString("limitation"))}
 val loan=s.optJSONObject("loan_timing")
 if(loan!=null&&loan.optBoolean("supported"))Panel{
  Text("신규 차입 신호 조건",fontWeight=FontWeight.Bold)
  Text(loan.optString("entry_rule"));Text(loan.optString("exit_rule"));Text(loan.optString("risk"))
  Text("은행 부채·금리·상환 여력은 직접 확인해야 합니다. 이 신호가 자동 대출이나 주문 증액을 실행하지는 않습니다.")
 }
 Panel{Text("추가 성과 자료",fontWeight=FontWeight.Bold);Text("새 방어 사례와 파동의 진행 기록, 가격 전망 비교 결과를 확인해요.")
  TextButton(onClick={context.startActivity(Intent(Intent.ACTION_VIEW,Uri.parse(BuildConfig.SIGNAL_BASE_URL.trimEnd('/')+"/research-validation.html")))}){Text("검증 기록 보기 ↗")}}
}

@Composable private fun StrategyGuide(){
 val context=LocalContext.current
 val guide=remember(context){
  JSONObject(context.assets.open("strategy-guide.json").bufferedReader(Charsets.UTF_8).use{it.readText()})
 }
 var expanded by remember{mutableStateOf(-1)}
 Text(guide.getString("title"),style=MaterialTheme.typography.headlineSmall,fontWeight=FontWeight.Bold)
 Text(guide.getString("intro"),color=MaterialTheme.colorScheme.onSurfaceVariant)
 val rules=guide.getJSONArray("rules")
 for(index in 0 until rules.length()){
  val rule=rules.getJSONObject(index)
  Panel{
   Text("${index+1}. ${rule.getString("title")}",fontWeight=FontWeight.Bold)
   Text(rule.getString("summary"))
   TextButton(onClick={expanded=if(expanded==index)-1 else index}){
    Text(if(expanded==index)"설명 접기" else "규칙·예시·백테스트 보기")
   }
   if(expanded==index){
    for((label,key) in listOf("어떻게 판단하나요?" to "rule","예시" to "example",
      "어떤 실험을 했나요?" to "study","현재 적용하는 방식" to "decision")){
     Text(label,fontWeight=FontWeight.Bold)
     Text(rule.getString(key))
    }
    TextButton(onClick={
     val url=BuildConfig.SIGNAL_BASE_URL.trimEnd('/')+"/strategy-guide.html#rule-"+(index+1)
     context.startActivity(Intent(Intent.ACTION_VIEW,Uri.parse(url)))
    }){Text("관련 실험 원본 보기 ↗")}
   }
  }
 }
 Panel{
  Text("전체 전략의 백테스트",fontWeight=FontWeight.Bold)
  Text(guide.getString("result"))
  Text(guide.getString("basis"),color=MaterialTheme.colorScheme.onSurfaceVariant)
 }
}
