package com.woogong.app

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.AccountBalanceWallet
import androidx.compose.material.icons.outlined.Home
import androidx.compose.material.icons.outlined.Refresh
import androidx.compose.material.icons.outlined.Settings
import androidx.compose.material.icons.outlined.ShowChart
import androidx.compose.material.icons.outlined.Timeline
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.imageResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

private data class AppTab(val id: Int, val label: String, val icon: ImageVector)
private val tabs = listOf(
    AppTab(0, "오늘", Icons.Outlined.Home),
    AppTab(1, "내 자산", Icons.Outlined.AccountBalanceWallet),
    AppTab(3, "성과", Icons.Outlined.ShowChart),
    AppTab(5, "파동", Icons.Outlined.Timeline),
    AppTab(4, "설정", Icons.Outlined.Settings)
)

@Composable internal fun AppHeader(tab: Int, version: String, busy: Boolean, refresh: () -> Unit) {
    val scheme = MaterialTheme.colorScheme
    val title = if (tab == 0) "우공이산" else tabs.firstOrNull { it.id == tab }?.label ?: "설정"
    val art = ImageBitmap.imageResource(R.drawable.woogong_icon_art)
    Surface(color = scheme.background) {
        Row(
            Modifier.fillMaxWidth().statusBarsPadding().padding(start = 16.dp, end = 8.dp),
            horizontalArrangement = Arrangement.spacedBy(9.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Canvas(Modifier.size(28.dp).clip(RoundedCornerShape(8.dp))) {
                drawImage(art, srcOffset = IntOffset(200, 155), srcSize = IntSize(900, 900),
                    dstSize = IntSize(size.width.toInt(), size.height.toInt()))
            }
            Text(title, Modifier.weight(1f), maxLines = 1, overflow = TextOverflow.Ellipsis,
                fontSize = 23.sp, fontWeight = FontWeight.Bold, letterSpacing = (-.65).sp)
            if (tab == 0 && version.isNotBlank()) {
                Surface(shape = RoundedCornerShape(6.dp), color = scheme.surfaceVariant,
                    contentColor = scheme.onSurfaceVariant) {
                    Text(version, Modifier.padding(horizontal = 7.dp, vertical = 3.dp),
                        fontSize = 10.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
                }
            }
            if (tab == 0) {
                IconButton(onClick = refresh, enabled = !busy) {
                    if (busy) CircularProgressIndicator(Modifier.size(19.dp), strokeWidth = 2.dp)
                    else Icon(Icons.Outlined.Refresh, "최신 결과 확인", tint = scheme.primary)
                }
            } else Spacer(Modifier.height(48.dp))
        }
    }
}

@Composable internal fun AppTabBar(selected: Int, onSelect: (Int) -> Unit) {
    val scheme = MaterialTheme.colorScheme
    Surface(color = scheme.surface) {
        Column {
            HorizontalDivider(thickness = .5.dp, color = scheme.outlineVariant)
            Row(
                Modifier.fillMaxWidth().navigationBarsPadding().padding(horizontal = 5.dp).selectableGroup()
            ) {
                tabs.forEach { tab ->
                    val active = tab.id == selected || (tab.id == 4 && selected == 2)
                    val tint = if (active) scheme.primary else scheme.onSurfaceVariant
                    Column(
                        Modifier.weight(1f).heightIn(min = 54.dp)
                            .selectable(selected = active, role = Role.Tab, onClick = { onSelect(tab.id) })
                            .padding(horizontal = 2.dp, vertical = 5.dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.Center
                    ) {
                        Surface(
                            color = if (active) scheme.primaryContainer else scheme.surface,
                            shape = RoundedCornerShape(8.dp)
                        ) {
                            Icon(tab.icon, contentDescription = null, tint = tint,
                                modifier = Modifier.padding(horizontal = 10.dp, vertical = 2.dp).size(19.dp))
                        }
                        Text(tab.label, color = tint, fontSize = 10.sp, lineHeight = 13.sp,
                            fontWeight = if (active) FontWeight.SemiBold else FontWeight.Medium,
                            maxLines = 1, overflow = TextOverflow.Ellipsis)
                    }
                }
            }
        }
    }
}

@Composable internal fun Panel(content: @Composable ColumnScope.() -> Unit) {
    val scheme = MaterialTheme.colorScheme
    Card(
        Modifier.fillMaxWidth(), shape = RoundedCornerShape(18.dp),
        colors = CardDefaults.cardColors(containerColor = scheme.surface),
        border = BorderStroke(.5.dp, scheme.outlineVariant)
    ) {
        Column(Modifier.padding(horizontal = 14.dp, vertical = 12.dp),
            verticalArrangement = Arrangement.spacedBy(7.dp), content = content)
    }
}
