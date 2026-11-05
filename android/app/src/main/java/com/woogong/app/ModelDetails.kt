package com.woogong.app

import androidx.compose.runtime.Composable
import androidx.compose.material3.*
import androidx.compose.ui.text.font.FontWeight
import org.json.JSONObject

@Composable internal fun ModelDetails(s:JSONObject,onBack:()->Unit){
 TextButton(onClick=onBack){Text("← 설정으로")}
 Text("모델 설명과 주의사항",style=MaterialTheme.typography.headlineSmall,fontWeight=FontWeight.Bold)
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
 if(loan!=null)Panel{
  Text("신규 차입 신호 조건",fontWeight=FontWeight.Bold)
  Text(loan.optString("entry_rule"));Text(loan.optString("exit_rule"));Text(loan.optString("risk"))
  Text("은행 부채·금리·상환 여력은 직접 확인해야 합니다. 이 신호가 자동 대출이나 주문 증액을 실행하지는 않습니다.")
 }
 Panel{Text("추가 성과 자료",fontWeight=FontWeight.Bold);Text("장기 대용 자료와 비용·체결 방식별 결과는 설치 안내의 v2 연구 결과에서 볼 수 있어요.")}
}
