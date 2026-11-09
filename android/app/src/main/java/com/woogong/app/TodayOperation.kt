package com.woogong.app

import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import org.json.JSONObject

internal fun operationReason(snapshot: JSONObject): String {
    val reasons = snapshot.optJSONArray("reasons") ?: return "시장 상태에 따른 목표 배분입니다."
    val state = snapshot.optInt("state", -1)
    val titles = if (state == 0) listOf("공격 비중과 현금", "상대강도")
        else listOf("긴급 재대피", "Cross5 · GLD21", "D25 방어 현금", "방어 선택", "상태 우선순위")
    for (title in titles) for (index in 0 until reasons.length()) {
        val reason = reasons.optJSONObject(index) ?: continue
        if (reason.optString("title") == title && reason.optBoolean("active"))
            return reason.optString("description")
    }
    return "시장 상태에 따른 목표 배분입니다."
}

internal fun signalLabel(snapshot: JSONObject, stale: Boolean, changed: Boolean): String {
    val status = when {
        stale -> "저장 자료"
        changed -> "배분 변경 확인"
        else -> "확인할 변경 없음"
    }
    return snapshot.optString("state_label", "신호 대기") + " · " + status
}

@Composable internal fun TodayOperation(snapshot: JSONObject, stale: Boolean, onReview: () -> Unit) {
    val context = LocalContext.current
    val changed = AllocationChange.pending(context) != null
    Panel {
        Text("오늘의 운용", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
        Text(signalLabel(snapshot, stale, changed))
        Text("기준 거래일 ${snapshot.optString("market_date", "—")}", color = MaterialTheme.colorScheme.onSurfaceVariant)
        snapshot.optJSONObject("target")?.let { Text(AllocationChange.display(it), fontWeight = FontWeight.Bold) }
        Text(operationReason(snapshot), style = MaterialTheme.typography.bodySmall)
        if (changed && !stale) TextButton(onClick = onReview) { Text("변경 전·후 보기 →") }
    }
}

@Composable internal fun WidgetBackgroundSettings() {
    val context = LocalContext.current
    val prefs = Data.prefs(context)
    var selected by androidx.compose.runtime.remember {
        androidx.compose.runtime.mutableStateOf(prefs.getString("widget_background_choice", "system"))
    }
    Panel {
        Text("위젯 배경", fontWeight = FontWeight.Bold)
        Text("선택하면 홈 화면의 우공이산 위젯에 바로 적용됩니다. 투명은 시스템 테마에 맞춰 글자색을 고릅니다.")
        listOf("system" to "시스템", "white" to "화이트", "black" to "블랙", "transparent" to "투명").forEach { (key, label) ->
            FilterChip(selected = selected == key, onClick = {
                selected = key
                prefs.edit().putString("widget_background_choice", key).apply()
                WoogongWidget.updateAll(context)
            }, label = { Text(label) })
        }
    }
}
