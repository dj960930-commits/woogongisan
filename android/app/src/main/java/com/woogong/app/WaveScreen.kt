package com.woogong.app

import android.util.AtomicFile
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject

private val intervals = linkedMapOf("4h" to "4시간봉", "1d" to "일봉", "1w" to "주봉", "1mo" to "월봉")
private val ranges = linkedMapOf(1 to "1개월", 3 to "3개월", 6 to "6개월", 12 to "1년", 36 to "3년", 0 to "전체")
private val korea = ZoneId.of("Asia/Seoul")
private val timeLabel = DateTimeFormatter.ofPattern("MM-dd HH:mm").withZone(korea)
private val waveCacheLock = Any()
private data class Bar(val date:String, val end:Instant, val open:Double, val high:Double, val low:Double,
                       val close:Double, val minutes:Int)
private data class Pivot(val index:Int, val confirmation:Int, val kind:String)
private fun price(value:Double) = "$" + "%,.2f".format(value)

private fun readFeed(bytes:ByteArray):JSONObject = JSONObject(bytes.toString(Charsets.UTF_8)).also {
    require(it.getInt("schema_version") == 1 && it.getJSONObject("symbols").length() > 0)
    Instant.parse(it.getString("generated_at"))
}

@Composable internal fun WaveScreen() {
    val context = LocalContext.current
    val cache = remember { AtomicFile(File(context.filesDir, "waves-v1.json")) }
    var feed by remember { mutableStateOf<JSONObject?>(null) }
    var symbol by rememberSaveable { mutableStateOf("QQQ") }
    var interval by rememberSaveable { mutableStateOf("1d") }
    var months by rememberSaveable { mutableIntStateOf(6) }
    var request by remember { mutableIntStateOf(0) }
    var loading by remember { mutableStateOf(true) }
    var failed by remember { mutableStateOf(false) }
    var menu by remember { mutableStateOf(false) }

    LaunchedEffect(request) {
        loading = true
        failed = false
        val stored = withContext(Dispatchers.IO) {
            val saved = synchronized(waveCacheLock) {
                runCatching { readFeed(cache.readFully()) }.getOrNull()
            }
            val bundled = runCatching { context.assets.open("waves.json").use { readFeed(it.readBytes()) } }.getOrNull()
            listOfNotNull(saved, bundled).maxByOrNull { Instant.parse(it.getString("generated_at")) }
        }
        feed = stored
        val online = withContext(Dispatchers.IO) {
            runCatching {
                val connection = URL(BuildConfig.SIGNAL_BASE_URL.trimEnd('/') + "/waves.json").openConnection() as HttpURLConnection
                try {
                    connection.connectTimeout = 7000
                    connection.readTimeout = 9000
                    connection.useCaches = false
                    require(connection.responseCode == 200)
                    val bytes = connection.inputStream.use { stream ->
                        val result = java.io.ByteArrayOutputStream()
                        val buffer = ByteArray(8192)
                        while (true) {
                            val count = stream.read(buffer)
                            if (count < 0) break
                            require(result.size() + count <= 3_000_000)
                            result.write(buffer, 0, count)
                        }
                        result.toByteArray()
                    }
                    val value = readFeed(bytes)
                    require(stored == null || Instant.parse(value.getString("generated_at")) >=
                        Instant.parse(stored.getString("generated_at")))
                    synchronized(waveCacheLock) {
                        val existing = runCatching { readFeed(cache.readFully()) }.getOrNull()
                        if (existing != null && Instant.parse(existing.getString("generated_at")) >
                            Instant.parse(value.getString("generated_at"))) {
                            existing
                        } else {
                            val output = cache.startWrite()
                            try {
                                output.write(bytes)
                                cache.finishWrite(output)
                            } catch (error: Exception) {
                                cache.failWrite(output)
                                throw error
                            }
                            value
                        }
                    }
                } finally {
                    connection.disconnect()
                }
            }.getOrNull()
        }
        if (online != null) feed = online else failed = true
        loading = false
    }

    Text("파동 분석", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
    val symbols = feed?.optJSONObject("symbols")
    Panel {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Box {
                OutlinedButton(onClick = { menu = true }, enabled = symbols != null) { Text("$symbol ▾") }
                DropdownMenu(expanded = menu, onDismissRequest = { menu = false }) {
                    symbols?.keys()?.asSequence()?.forEach { name ->
                        DropdownMenuItem(text = { Text(name) }, onClick = { symbol = name; menu = false })
                    }
                }
            }
            TextButton(onClick = { request++ }, enabled = !loading) {
                Text(if (loading) "확인 중" else "새로고침")
            }
        }
        Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            intervals.forEach { (key, label) ->
                FilterChip(selected = interval == key, onClick = { interval = key }, label = { Text(label) })
            }
        }
        Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            ranges.forEach { (value, label) ->
                FilterChip(selected = months == value, onClick = { months = value }, label = { Text(label) })
            }
        }
    }

    val series = symbols?.optJSONObject(symbol)?.optJSONObject("series")?.optJSONObject(interval)
    if (series == null) {
        Panel { Text(if (loading) "차트 자료를 불러오는 중입니다." else "이 종목의 봉 자료를 확인할 수 없습니다.") }
        return
    }
    val bars = remember(series) {
        val rows = series.getJSONArray("bars")
        (0 until rows.length()).map {
            val row = rows.getJSONArray(it)
            Bar(row.getString(0), Instant.parse(row.getString(1)), row.getDouble(2),
                row.getDouble(3), row.getDouble(4), row.getDouble(5), row.optInt(6, 0))
        }
    }
    val points = remember(series) {
        val rows = series.getJSONArray("pivots")
        (0 until rows.length()).map {
            val point = rows.getJSONArray(it)
            Pivot(point.getInt(0), point.getInt(1), point.getString(2))
        }
    }
    val last = bars.last()
    val cutoff = if (months == 0) bars.first().end else last.end.atZone(korea).minusMonths(months.toLong()).toInstant()
    val first = bars.indexOfFirst { it.end >= cutoff }.coerceIn(0, bars.lastIndex - 1)
    val scenario = series.optJSONObject("scenario")
    val analysis = series.optJSONObject("analysis")
    Panel {
        Text("$symbol · ${intervals.getValue(interval)}", fontWeight = FontWeight.Bold)
        val date = if (interval == "4h") timeLabel.format(last.end) + " KST" else last.date
        Text("완료 $date" + if (failed || series.optBoolean("cached")) " · 저장 자료" else "", fontSize = 12.sp)
        WaveChart(bars, first, points, scenario, analysis)
        Text("실제 봉 ${bars[first].date} ~ ${last.date}", fontSize = 11.sp)
        Text("회색 · 이전 파동   골드 · 현재 움직임   점선 · 예상 경로", fontSize = 11.sp)
        Text(if (analysis != null) "점선 · 시간 표본이 충분한 경로   가로 띠 · 과거 소요 시간 범위"
            else "점선의 가로 간격은 보기 쉽게 배치했어요.", fontSize = 11.sp)
        if (interval == "4h" && symbol != "BTC/USD") {
            Text("정규장 마지막 봉은 짧을 수 있습니다. 봉을 눌러 길이를 확인하세요.", fontSize = 11.sp)
        }
    }
    if (analysis != null) WaveResearchExplanation(analysis, bars)
    WaveExplanation(bars, points, scenario)
}

@Composable private fun WaveResearchExplanation(analysis:JSONObject, bars:List<Bar>) {
    val patterns = analysis.getJSONArray("patterns")
    val shock = analysis.getJSONObject("shock")
    var expanded by rememberSaveable { mutableStateOf(false) }
    Panel {
        Text("파형 해설", fontWeight = FontWeight.Bold)
        if (patterns.length() > 0) {
            val main = patterns.getJSONObject(0)
            val end = main.getInt("end")
            val direction = if (main.getInt("direction") > 0) "상승" else "하락"
            Text(if (main.optBoolean("developing")) "현재는 $direction 방향의 ${main.getString("name")} 외형이 진행 중인 후보예요."
                else "최근 확인된 구조는 $direction 방향의 ${main.getString("name")} 후보예요.")
            Text("${bars[main.getInt("start")].date} ~ ${bars[end].date} 구간을 짚었습니다.", fontSize = 12.sp)
            val move = Performance.percent(bars.last().close / bars[end].close - 1)
            Text(if (main.optBoolean("developing")) "물음표는 현재 봉까지의 진행 지점이에요. 다음 전환점에서 파형을 다시 확인합니다."
                else "그 끝점 이후 ${bars.lastIndex - end}개 봉, 종가는 $move 움직였어요.", fontSize = 12.sp)
        } else {
            Text("최근 전환점 배열에서 ABC·추진파·복합 조정에 맞는 외형 후보가 아직 잡히지 않았어요. 아래 가격 범위로 현재 흐름을 봅니다.")
        }
        val change = Performance.percent(shock.getDouble("change"))
        Text(if (shock.getBoolean("rapid_drop")) {
            "마지막 봉은 $change. 직전 ${shock.getInt("lookback")}개 봉의 움직임과 비교해 급락으로 분류했어요."
        } else {
            "마지막 봉 $change · 최근 변동 폭 기준 급락 조건은 채우지 않았어요."
        }, fontSize = 12.sp)
        TextButton(onClick = { expanded = !expanded }) { Text(if (expanded) "근거 접기" else "파형 근거·대안 보기") }
        if (expanded) {
            for (i in 0 until patterns.length()) {
                val item = patterns.getJSONObject(i)
                Text("${if (i == 0) "기본" else "대안"} · ${item.getString("name")}", fontWeight = FontWeight.SemiBold)
                val labels = item.getJSONArray("labels")
                val positions = (0 until labels.length()).map {
                    val point = labels.getJSONObject(it)
                    "${point.getString("label")} ${price(bars[point.getInt("index")].close)}"
                }
                Text(positions.joinToString(" → "), fontSize = 12.sp)
                Text(item.getString("evidence"), fontSize = 12.sp)
                val durations = item.getJSONArray("durations")
                Text("각 구간 ${(0 until durations.length()).joinToString("·") { durations.getInt(it).toString() }}개 봉",
                    fontSize = 11.sp)
                Text(if (item.getBoolean("subdivision_verified")) "가격 외형과 한 단계 작은 파동의 구성 조건이 맞았어요."
                    else "가격 외형이 맞는 후보예요. 내부 파동 구성은 추가 확인이 필요해요.", fontSize = 11.sp)
            }
            Text("ABC는 세 움직임의 조정, W–X–Y는 두 조정을 X파가 연결한 구조예요. 세 조정이 연결되면 W–X–Y–X–Z로 표기해요.",
                fontSize = 11.sp)
            Text("급락은 직전 최대 60개 봉의 로그수익률 평균보다 2표준편차 이상 낮은 음수 수익률로 분류해요.",
                fontSize = 11.sp)
        }
    }
    Panel {
        Text("앞으로 볼 두 경로", fontWeight = FontWeight.Bold)
        val paths = analysis.getJSONArray("paths")
        for (i in 0 until paths.length()) {
            val path = paths.getJSONObject(i)
            val up = path.getString("direction") == "up"
            val trigger = price(path.getDouble("trigger"))
            val target = if (path.isNull("target")) null else price(path.getDouble("target"))
            val invalidation = price(path.getDouble("invalidation"))
            val direction = if (up) "상승" else "하락"
            val side = if (up) "위" else "아래"
            Text("${if (i == 0) "기본" else "반대"} · $direction", fontWeight = FontWeight.SemiBold)
            Text(if (target != null) "종가가 $trigger ${side}에 있을 때 $target 쪽을 봐요. 반대 기준선은 ${invalidation}입니다."
                else "종가가 $trigger ${side}에 머무는지 봐요. 가격 폭으로 계산한 추가 목표는 유효 범위를 벗어나 보류합니다.",
                fontSize = 12.sp)
            val method = if (path.getString("method") == "first_leg_1.618") "첫 파동의 1.618배 연장 가격" else "최근 전환점 가격 폭을 돌파 방향으로 더한 기준 가격"
            Text(method, fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            val clock = path.getJSONObject("timing")
            if (clock.getString("status") == "estimated") {
                val formatter = DateTimeFormatter.ofPattern("yy.MM.dd HH:mm").withZone(korea)
                val from = formatter.format(Instant.parse(clock.getString("lower_at")))
                val until = formatter.format(Instant.parse(clock.getString("upper_at")))
                Text("남은 ${clock.getInt("lower")}~${clock.getInt("upper")}개 봉 · $from ~ $until KST", fontSize = 12.sp)
                Text("같은 방향의 완료 파동 ${clock.getInt("samples")}개에서 현재까지의 경과 봉 수를 뺀 사분위 범위예요. 가격 도달과 시간 종료는 따로 확인해요.",
                    fontSize = 11.sp)
            } else if (clock.getString("status") == "waiting_turn") {
                Text("반대 방향의 시작 전환점이 확인되면 시간 범위를 계산해요.", fontSize = 11.sp)
            } else {
                Text("시간 추정 보류 · 같은 방향·현재 경과 시간 조건의 표본 ${clock.getInt("samples")}개",
                    fontSize = 11.sp)
            }
        }
        if (paths.length() == 0) Text("상단·하단 가격 폭이 잡히면 두 방향의 경로를 비교합니다.", fontSize = 12.sp)
        if (!analysis.isNull("rejection")) Text("기존 연장 후보 · ${analysis.getString("rejection")}", fontSize = 11.sp)
    }
}

@Composable private fun WaveChart(bars:List<Bar>, first:Int, pivots:List<Pivot>, scenario:JSONObject?, analysis:JSONObject?) {
    val accent = MaterialTheme.colorScheme.primary
    val up = MaterialTheme.colorScheme.tertiary
    val muted = MaterialTheme.colorScheme.onSurfaceVariant
    val red = MaterialTheme.colorScheme.error
    val show = bars.subList(first, bars.size)
    val target = scenario?.getDouble("target")
    val invalid = scenario?.getDouble("invalidation")
    val trigger = scenario?.getDouble("trigger")
    val pathRows = analysis?.optJSONArray("paths")
    val timedPaths = (0 until (pathRows?.length() ?: 0)).map { pathRows!!.getJSONObject(it) }
        .filter { !it.isNull("target") && it.getJSONObject("timing").optString("status") == "estimated" }
    val projectedPrices = timedPaths.flatMap { listOf(it.getDouble("target"), it.getDouble("invalidation"), it.getDouble("trigger")) }
    val minimum = minOf(show.minOf { it.low }, projectedPrices.minOrNull() ?: target ?: Double.MAX_VALUE, invalid ?: Double.MAX_VALUE, trigger ?: Double.MAX_VALUE)
    val maximum = maxOf(show.maxOf { it.high }, projectedPrices.maxOrNull() ?: target ?: 0.0, invalid ?: 0.0, trigger ?: 0.0)
    var inspected by remember(bars, first) { mutableIntStateOf(bars.lastIndex) }
    val selected = bars[inspected]
    val legacyProjection = analysis == null && target != null && invalid != null && trigger != null
    val hasProjection = timedPaths.isNotEmpty() || legacyProjection
    val futureSlots = maxOf(timedPaths.maxOfOrNull { it.getJSONObject("timing").getInt("upper") } ?: 0,
        if (hasProjection) ((bars.lastIndex - first) * 2 / 3).coerceAtLeast(1) else 0)
    val historyFraction = (bars.lastIndex - first).toFloat() / (bars.lastIndex - first + futureSlots)
    Canvas(Modifier.fillMaxWidth().height(235.dp).pointerInput(bars, first, historyFraction) {
        detectTapGestures { offset ->
            val axis = 56.dp.toPx()
            val historyWidth = (size.width - axis - 6.dp.toPx()).coerceAtLeast(1f) * historyFraction
            if (offset.x > axis + historyWidth) return@detectTapGestures
            val position = ((offset.x - axis) / historyWidth).coerceIn(0f, 1f)
            inspected = first + (position * (bars.lastIndex - first) + .5f).toInt()
        }
    }) {
        val left = 56.dp.toPx()
        val right = left + (size.width - left - 6.dp.toPx()) * historyFraction
        val top = if (hasProjection) 27.dp.toPx() else 10.dp.toPx()
        val bottom = size.height - if (analysis != null) 24.dp.toPx() else 10.dp.toPx()
        val span = (maximum - minimum).coerceAtLeast(.001)
        fun y(p:Double) = top + (bottom - top) * (1 - (p - minimum) / span).toFloat()
        fun x(index:Int) = left + (right - left) * (index - first) / (bars.lastIndex - first)
        val paint = android.graphics.Paint(android.graphics.Paint.ANTI_ALIAS_FLAG).apply {
            color = muted.toArgb()
            textSize = 10.sp.toPx()
        }
        if (hasProjection) {
            drawRect(accent.copy(alpha = .07f), topLeft = Offset(right, 0f),
                size = Size(size.width - right, size.height))
            drawLine(muted.copy(alpha = .30f), Offset(right, 0f), Offset(right, bottom))
            val label = if (analysis != null) "예상 시간 범위" else "예상 구간"
            val labelX = right + (size.width - right - paint.measureText(label)) / 2
            drawContext.canvas.nativeCanvas.drawText(label, labelX, 14.dp.toPx(), paint)
        }
        for (step in 0..4) {
            val value = minimum + span * step / 4
            drawLine(muted.copy(alpha = .17f), Offset(left, y(value)), Offset(size.width, y(value)))
            drawContext.canvas.nativeCanvas.drawText("%,.1f".format(value), 0f, y(value) + 3.dp.toPx(), paint)
        }
        val candleWidth = ((right - left) / show.size * .55f).coerceIn(1f, 9.dp.toPx())
        show.forEachIndexed { index, bar ->
            val at = x(index + first)
            val color = (if (bar.close >= bar.open) up else red).copy(alpha = .53f)
            drawLine(color, Offset(at, y(bar.high)), Offset(at, y(bar.low)), 1f)
            val openY = y(bar.open)
            val closeY = y(bar.close)
            drawLine(color, Offset(at, openY), Offset(at, if (closeY == openY) closeY + 1 else closeY), candleWidth)
        }
        pivots.filter { it.index >= first }.zipWithNext().forEach { (a, b) ->
            drawLine(muted, Offset(x(a.index), y(bars[a.index].close)), Offset(x(b.index), y(bars[b.index].close)), 2.dp.toPx())
        }
        pivots.lastOrNull()?.takeIf { it.index >= first }?.let { point ->
            drawLine(accent, Offset(x(point.index), y(bars[point.index].close)), Offset(right, y(bars.last().close)), 2.dp.toPx())
        }
        scenario?.optJSONArray("anchors")?.let { anchors ->
            for (i in 0 until anchors.length()) {
                val index = anchors.getInt(i)
                if (index >= first) drawContext.canvas.nativeCanvas.drawText("P$i", x(index), y(bars[index].close) - 4.dp.toPx(), paint)
            }
        }
        analysis?.optJSONArray("patterns")?.optJSONObject(0)?.optJSONArray("labels")?.let { labels ->
            for (i in 0 until labels.length()) {
                val label = labels.getJSONObject(i)
                val index = label.getInt("index")
                if (index >= first) drawContext.canvas.nativeCanvas.drawText(
                    label.getString("label"), x(index), y(bars[index].close) - 13.dp.toPx(), paint)
            }
        }
        timedPaths.forEach { path ->
            val clock = path.getJSONObject("timing")
            val color = if (path == pathRows?.optJSONObject(0)) accent else up
            val goalY = y(path.getDouble("target"))
            val dash = PathEffect.dashPathEffect(floatArrayOf(9f, 6f))
            val middleX = x(bars.lastIndex + clock.getInt("median"))
            val lowX = x(bars.lastIndex + clock.getInt("lower"))
            val highX = x(bars.lastIndex + clock.getInt("upper"))
            drawLine(color.copy(alpha = .25f), Offset(lowX, goalY), Offset(highX, goalY), 9.dp.toPx())
            drawLine(color, Offset(right, y(bars.last().close)), Offset(middleX, goalY), 2.dp.toPx(), pathEffect = dash)
            drawCircle(color, 3.dp.toPx(), Offset(middleX, goalY))
            drawLine(color.copy(alpha = .45f), Offset(right, y(path.getDouble("invalidation"))),
                Offset(highX, y(path.getDouble("invalidation"))), pathEffect = dash)
        }
        if (analysis != null) {
            val currentLabel = bars.last().date.substring(5)
            drawContext.canvas.nativeCanvas.drawText(currentLabel, right - paint.measureText(currentLabel),
                size.height - 2.dp.toPx(), paint)
            val latestClock = timedPaths.maxByOrNull { it.getJSONObject("timing").getInt("upper") }?.getJSONObject("timing")
            if (latestClock != null) {
                val label = timeLabel.format(Instant.parse(latestClock.getString("upper_at"))).substring(0, 5)
                val at = x(bars.lastIndex + latestClock.getInt("upper"))
                drawContext.canvas.nativeCanvas.drawText(label, (at - paint.measureText(label)).coerceAtLeast(right),
                    size.height - 2.dp.toPx(), paint)
            }
        }
        if (legacyProjection && target != null && invalid != null && trigger != null) {
            val dash = PathEffect.dashPathEffect(floatArrayOf(9f, 6f))
            val end = size.width - 5.dp.toPx()
            val start = Offset(right, y(bars.last().close))
            val goal = Offset(end, y(target))
            if (scenario?.optBoolean("triggered") == true) {
                drawLine(accent, start, goal, 2.dp.toPx(), pathEffect = dash)
            } else {
                val checkpoint = Offset(right + (end - right) * .38f, y(trigger))
                drawLine(accent, start, checkpoint, 2.dp.toPx(), pathEffect = dash)
                drawLine(accent, checkpoint, goal, 2.dp.toPx(), pathEffect = dash)
            }
            drawCircle(accent, radius = 3.dp.toPx(), center = goal)
            drawLine(red.copy(alpha = .7f), Offset(right, y(invalid)), Offset(end, y(invalid)), pathEffect = dash)
        }
        if (!hasProjection || inspected != bars.lastIndex) {
            drawLine(muted.copy(alpha = .55f), Offset(x(inspected), top), Offset(x(inspected), bottom))
        }
    }
    Text("${selected.date} · 종가 ${price(selected.close)}" +
        if (selected.minutes > 0) " · ${timeLabel.format(selected.end)} KST · ${selected.minutes}분" else "", fontSize = 11.sp)
}

@Composable private fun WaveExplanation(bars:List<Bar>, points:List<Pivot>, scenario:JSONObject?) {
    val pivot = points.lastOrNull()
    Panel {
        Text("지금 보는 그림", fontWeight = FontWeight.Bold)
        if (scenario == null) {
            WaveRangeReadout(bars, points)
        } else {
            val up = scenario.getString("direction") == "up"
            val direction = if (up) "상승" else "하락"
            val trigger = price(scenario.getDouble("trigger"))
            val target = price(scenario.getDouble("target"))
            val invalidation = price(scenario.getDouble("invalidation"))
            val triggerSide = if (up) "위" else "아래"
            val breach = if (up) "저가가 $invalidation 이하로 내려오면" else "고가가 $invalidation 이상으로 올라가면"
            val triggered = scenario.getBoolean("triggered")

            Text(if (triggered) {
                "종가가 $trigger ${triggerSide}에 있어요. 지금은 $direction 흐름이 한 번 더 이어지는 그림을 먼저 봅니다."
            } else {
                "$direction 쪽으로 한 번 더 뻗을 수 있는 자리예요. 먼저 $trigger ${triggerSide}에서 봉이 마감되는지 봅니다."
            })
            Text(if (triggered) "다음으로 볼 가격 · $target" else "확인 조건을 채우면 볼 가격 · $target",
                fontWeight = FontWeight.SemiBold)
            Text("$breach 이 그림은 접고, 새 고점과 저점부터 다시 봅니다.", fontSize = 12.sp)
        }
    }
    if (pivot != null) {
        Panel {
            Text("차트에서 짚은 자리", fontWeight = FontWeight.Bold)
            if (scenario != null) {
                val anchors = scenario.getJSONArray("anchors")
                val start = price(bars[anchors.getInt(0)].close)
                val turn = price(bars[anchors.getInt(1)].close)
                val pullback = price(bars[anchors.getInt(2)].close)
                val retracement = "%.0f%%".format(scenario.getDouble("retracement") * 100)
                Text("P0 $start → P1 $turn, 여기까지가 첫 움직임이에요. P2 ${pullback}까지 첫 움직임의 ${retracement}만큼 되돌렸습니다.", fontSize = 12.sp)
                Text("점선 끝은 P2에서 첫 움직임의 1.618배를 같은 방향으로 적용한 가격입니다.", fontSize = 12.sp)
            } else {
                val prior = points.getOrNull(points.lastIndex - 1)
                if (prior != null) Text("이전 파동 · ${price(bars[prior.index].close)} → ${price(bars[pivot.index].close)}", fontSize = 12.sp)
            }
            fun label(bar: Bar) = if (bar.minutes > 0) timeLabel.format(bar.end) + " KST" else bar.date
            Text("마지막 전환점 ${label(bars[pivot.index])} · 확인 ${label(bars[pivot.confirmation])}",
                fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable private fun WaveRangeReadout(bars:List<Bar>, points:List<Pivot>) {
    val close = bars.last().close
    val latest = points.lastOrNull()?.let { bars[it.index].close }
    val prior = points.getOrNull(points.lastIndex - 1)?.let { bars[it.index].close }
    val recent = bars.subList((bars.lastIndex - 20).coerceAtLeast(0), bars.lastIndex)
    val pivotRange = if (latest != null && prior != null && latest != prior) {
        minOf(latest, prior)..maxOf(latest, prior)
    } else {
        null
    }
    val lower = pivotRange?.start ?: recent.minOf { it.close }
    val upper = pivotRange?.endInclusive ?: recent.maxOf { it.close }
    val lowLabel = price(lower)
    val highLabel = price(upper)
    val closeLabel = price(close)

    Text(when {
        close > upper -> "종가 $closeLabel. 윗선 $highLabel 위까지 올라왔어요."
        close < lower -> "종가 $closeLabel. 아랫선 $lowLabel 아래까지 내려왔어요."
        close == upper && close == lower -> "종가 $closeLabel. 기준 가격과 같아요."
        close == upper -> "종가 $closeLabel. 윗선에 닿았어요."
        close == lower -> "종가 $closeLabel. 아랫선에 닿았어요."
        else -> "종가 $closeLabel. $lowLabel ~ $highLabel 사이에 있어요."
    })
    if (latest != null && latest > 0.0) {
        val move = Performance.percent(close / latest - 1)
        Text("마지막 전환점 ${price(latest)} 대비 $move", fontSize = 12.sp)
    }
    val basis = if (pivotRange != null) "최근 두 전환점의 종가" else "직전 ${recent.size}개 봉의 종가 범위"
    Text("다음에 볼 가격 · $basis 기준", fontWeight = FontWeight.SemiBold, fontSize = 12.sp)
    Text(if (close > upper) {
        "종가가 $highLabel 위를 지키면 돌파 유지, 그 아래로 돌아오면 돌파 실패 가능성을 봐요."
    } else if (close < lower) {
        "종가가 $lowLabel 아래에 머물면 이탈 유지, 그 위로 돌아오면 범위 회복을 봐요."
    } else {
        "종가가 $highLabel 위로 마감하면 상방 돌파, $lowLabel 아래로 마감하면 하방 이탈을 봐요."
    }, fontSize = 12.sp)
}
