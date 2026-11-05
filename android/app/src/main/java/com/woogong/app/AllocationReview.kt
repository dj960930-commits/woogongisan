package com.woogong.app

import androidx.compose.runtime.*
import androidx.compose.material3.*
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import org.json.JSONObject

@Composable internal fun AllocationPopup(s:JSONObject,stale:Boolean,request:Int){
 val c=LocalContext.current
 var pending by remember{mutableStateOf(AllocationChange.pending(c))}
 var dismissed by remember{mutableStateOf("")}
 DisposableEffect(Unit){
  val prefs=Data.prefs(c)
  val listener=android.content.SharedPreferences.OnSharedPreferenceChangeListener{_,key->if(key=="allocation_pending")pending=AllocationChange.pending(c)}
  prefs.registerOnSharedPreferenceChangeListener(listener)
  onDispose{prefs.unregisterOnSharedPreferenceChangeListener(listener)}
 }
 LaunchedEffect(request){dismissed="";pending=AllocationChange.pending(c)}
 val p=pending;val key=p?.optString("key")?:""
 if(!stale&&p!=null&&key!=dismissed){
  AlertDialog(onDismissRequest={dismissed=key},title={Text("자산 배분이 바뀌었어요",fontWeight=FontWeight.Bold)},
   text={androidx.compose.foundation.layout.Column{
    Text("변경 전",color=MaterialTheme.colorScheme.onSurfaceVariant)
    Text(AllocationChange.display(p.getJSONObject("before")))
    Text("현재 목표",color=MaterialTheme.colorScheme.primary,fontWeight=FontWeight.Bold)
    Text(AllocationChange.display(s.getJSONObject("target")),fontWeight=FontWeight.Bold)
    Text("내 자산에서 현재 보유와 필요한 수량을 확인하세요.")
   }},confirmButton={TextButton(onClick={AllocationChange.acknowledge(c,s);pending=null}){Text("확인했어요")}},
   dismissButton={TextButton(onClick={dismissed=key}){Text("나중에")}})
 }
}
