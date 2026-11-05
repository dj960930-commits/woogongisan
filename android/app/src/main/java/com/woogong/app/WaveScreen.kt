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
    Panel {
        Text("$symbol · ${intervals.getValue(interval)}", fontWeight = FontWeight.Bold)
        val date = if (interval == "4h") timeLabel.format(last.end) + " KST" else last.date
        Text("완료 $date" + if (failed || series.optBoolean("cached")) " · 저장 자료" else "", fontSize = 12.sp)
        WaveChart(bars, first, points, scenario)
        Text("실제 봉 ${bars[first].date} ~ ${last.date}", fontSize = 11.sp)
        Text("회색 · 이전 파동   골드 · 현재 움직임   점선 · 예상 경로", fontSize = 11.sp)
        if (interval == "4h" && symbol != "BTC/USD") {
            Text("정규장 마지막 봉은 짧을 수 있습니다. 봉을 눌러 길이를 확인하세요.", fontSize = 11.sp)
        }
    }
    WaveExplanation(bars, points, series.getDouble("threshold"), scenario)
}

@Composable private fun WaveChart(bars:List<Bar>, first:Int, pivots:List<Pivot>, scenario:JSONObject?) {
    val accent = MaterialTheme.colorScheme.primary
    val up = MaterialTheme.colorScheme.tertiary
    val muted = MaterialTheme.colorScheme.onSurfaceVariant
    val red = MaterialTheme.colorScheme.error
    val show = bars.subList(first, bars.size)
    val target = scenario?.getDouble("target")
    val invalid = scenario?.getDouble("invalidation")
    val trigger = scenario?.getDouble("trigger")
    val minimum = minOf(show.minOf { it.low }, target ?: Double.MAX_VALUE, invalid ?: Double.MAX_VALUE, trigger ?: Double.MAX_VALUE)
    val maximum = maxOf(show.maxOf { it.high }, target ?: 0.0, invalid ?: 0.0, trigger ?: 0.0)
    var inspected by remember(bars, first) { mutableIntStateOf(bars.lastIndex) }
    val selected = bars[inspected]
    val hasProjection = target != null && invalid != null && trigger != null
    val historyFraction = if (hasProjection) .60f else 1f
    Canvas(Modifier.fillMaxWidth().height(235.dp).pointerInput(bars, first, historyFraction) {
        detectTapGestures { offset ->
            val axis = 56.dp.toPx()
            val historyWidth = (size.width - axis).coerceAtLeast(1f) * historyFraction
            if (offset.x > axis + historyWidth) return@detectTapGestures
            val position = ((offset.x - axis) / historyWidth).coerceIn(0f, 1f)
            inspected = first + (position * (bars.lastIndex - first) + .5f).toInt()
        }
    }) {
        val left = 56.dp.toPx()
        val right = left + (size.width - left) * historyFraction
        val top = if (hasProjection) 27.dp.toPx() else 10.dp.toPx()
        val bottom = size.height - 10.dp.toPx()
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
            val label = "예상 구간"
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
        if (target != null && invalid != null && trigger != null) {
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

@Composable private fun WaveExplanation(bars:List<Bar>, points:List<Pivot>, threshold:Double, scenario:JSONObject?) {
    val pivot = points.lastOrNull()
    Panel {
        Text("이전·현재 파동", fontWeight = FontWeight.Bold)
        if (pivot == null) {
            Text("이 봉에서 확인된 전환점이 아직 없습니다.")
        } else {
            val prior = points.getOrNull(points.lastIndex - 1)
            if (prior != null) Text("이전 · ${bars[prior.index].date} ${price(bars[prior.index].close)} → " +
                "${bars[pivot.index].date} ${price(bars[pivot.index].close)}")
            Text("현재 · 마지막 전환점 이후 ${if (pivot.kind == "L") "반등" else "하락"} 구간")
            val detected = bars[pivot.index]
            val confirmed = bars[pivot.confirmation]
            fun label(bar: Bar) = if (bar.minutes > 0) timeLabel.format(bar.end) + " KST" else bar.date
            Text("전환점 ${label(detected)} · 확인 ${label(confirmed)}", fontSize = 12.sp)
        }
    }
    Panel {
        Text("예상 파동과 근거", fontWeight = FontWeight.Bold)
        if (scenario == null) {
            Text("관찰 대기 · 최근 세 전환점에서 유효한 연장 조건을 찾지 못했습니다.")
        } else {
            val up = scenario.getString("direction") == "up"
            val direction = if (up) "상승" else "하락"
            val action = if (up) "돌파" else "이탈"
            Text("$direction 연장 후보 · ${if (scenario.optBoolean("triggered")) "종가 기준 확인선 통과" else "확인선 대기"}")
            Text("P0→P1 첫 파동 · P1→P2 되돌림 · P2 이후 다음 파동 후보", fontSize = 12.sp)
            Text("확인선 ${price(scenario.getDouble("trigger"))} $action 시 · 연장 기준 ${price(scenario.getDouble("target"))}")
            Text("해석이 깨지는 가격 ${price(scenario.getDouble("invalidation"))}")
            Text("첫 움직임을 %.0f%% 되돌린 뒤 같은 방향으로 전환했습니다. 연장 기준은 첫 파동 길이의 1.618배입니다."
                .format(scenario.getDouble("retracement") * 100), fontSize = 12.sp)
        }
        Text("종가가 극점에서 %.1f%% 반대로 움직이면 전환점을 확인합니다. 점선은 조건부 가격 경로이며, 가로 간격은 보기 쉽게 배치했습니다."
            .format(threshold * 100), fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}
