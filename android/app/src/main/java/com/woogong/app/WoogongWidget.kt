package com.woogong.app

import android.app.PendingIntent
import android.appwidget.*
import android.content.*
import android.content.res.Configuration
import android.graphics.*
import android.os.Bundle
import android.widget.RemoteViews

open class WoogongWidget:AppWidgetProvider(){
 override fun onUpdate(c:Context,m:AppWidgetManager,ids:IntArray){ids.forEach{update(c,m,it)}}
 override fun onAppWidgetOptionsChanged(c:Context,m:AppWidgetManager,id:Int,options:Bundle){update(c,m,id)}
 override fun onDeleted(c:Context,ids:IntArray){Data.prefs(c).edit().apply{ids.forEach{remove("widget_period_$it")}}.apply()}
 override fun onReceive(c:Context,intent:Intent){
  if(intent.action==PERIOD_ACTION){
   val id=intent.getIntExtra(AppWidgetManager.EXTRA_APPWIDGET_ID,AppWidgetManager.INVALID_APPWIDGET_ID)
   val m=AppWidgetManager.getInstance(c)
   if(m.getAppWidgetInfo(id)?.provider?.packageName==c.packageName){
    val p=Data.prefs(c);val key="widget_period_$id";val old=p.getString(key,p.getString("performance_period","1m"))?:"1m"
    p.edit().putString(key,WidgetPresentation.nextPeriod(old)).apply();update(c,m,id)
   }
  }else super.onReceive(c,intent)
 }
 companion object {
  private const val PERIOD_ACTION="com.woogong.app.WIDGET_PERIOD"
  fun updateAll(c:Context){val m=AppWidgetManager.getInstance(c);listOf(WoogongWidget::class.java,WoogongCompactWidget::class.java,WoogongDetailWidget::class.java,WoogongSignalWidget::class.java).forEach{type->m.getAppWidgetIds(ComponentName(c,type)).forEach{update(c,m,it)}}}
  fun update(c:Context,m:AppWidgetManager,id:Int){
   val info=m.getAppWidgetInfo(id)?:return
   val options=m.getAppWidgetOptions(id)
   val preferred=when(info.provider.className){WoogongCompactWidget::class.java.name->WidgetPresentation.Layout.COMPACT;WoogongDetailWidget::class.java.name->WidgetPresentation.Layout.DETAIL;else->WidgetPresentation.Layout.GRAPH}
   val defaultWidth=if(preferred==WidgetPresentation.Layout.COMPACT)210 else 340
   val defaultHeight=if(preferred==WidgetPresentation.Layout.DETAIL)250 else 130
   // Choose a layout that fits both reported orientations; never assume a launcher grid cell size.
   val width=options.getInt(AppWidgetManager.OPTION_APPWIDGET_MIN_WIDTH,defaultWidth)
   val height=options.getInt(AppWidgetManager.OPTION_APPWIDGET_MIN_HEIGHT,defaultHeight)
   val layout=WidgetPresentation.layout(width,height,c.resources.configuration.fontScale,preferred)
   val s=Data.load(c,"snapshot");val status=Data.load(c,"status");val prefs=Data.prefs(c)
   val stale=Data.stale(s,status)||!prefs.getString("sync_error","").isNullOrEmpty()
   val background=prefs.getString("widget_background_choice","system")
   val systemDark=c.resources.configuration.uiMode and Configuration.UI_MODE_NIGHT_MASK==Configuration.UI_MODE_NIGHT_YES
   val dark=when(background){"black"->true;"white"->false;else->systemDark}
   val ink=if(dark)Color.WHITE else Color.rgb(24,29,40)
   val muted=if(dark)Color.rgb(185,194,211) else Color.rgb(85,94,113)
   val colors=seriesColors(dark)
   fun applyBackground(view:RemoteViews){
    val fill=when(background){"white"->Color.WHITE;"black"->Color.BLACK;"transparent"->Color.TRANSPARENT;else->if(dark)Color.rgb(32,38,57) else Color.WHITE}
    view.setInt(R.id.widget_root,"setBackgroundColor",fill)
   }
   if(info.provider.className==WoogongSignalWidget::class.java.name){
    val view=RemoteViews(c.packageName,R.layout.widget_signal)
    applyBackground(view)
    if(background=="system")view.setInt(R.id.widget_root,"setBackgroundColor",if(dark)Color.rgb(32,38,57) else Color.WHITE)
    view.setTextColor(R.id.signal_title,colors[0])
    view.setTextColor(R.id.signal_state,ink)
    view.setTextColor(R.id.signal_date,muted)
    view.setTextViewText(R.id.signal_state,signalLabel(s,stale,AllocationChange.pending(c)!=null))
    view.setTextViewText(R.id.signal_date,"기준 거래일 "+s.optString("market_date","—"))
    val open=PendingIntent.getActivity(c,id,Intent(c,MainActivity::class.java),PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
    view.setOnClickPendingIntent(R.id.widget_root,open)
    m.updateAppWidget(id,view)
    return
   }
   val period=prefs.getString("widget_period_$id",prefs.getString("performance_period","1m"))?:"1m"
   val window=Performance.read(s,period)
   val resource=when(layout){WidgetPresentation.Layout.COMPACT->R.layout.widget_compact;WidgetPresentation.Layout.DETAIL->R.layout.widget_detail;else->R.layout.widget}
   val v=RemoteViews(c.packageName,resource)
   applyBackground(v)
   v.setTextColor(R.id.title,ink)
   v.setTextColor(R.id.state,muted)
   v.setTextColor(R.id.period,ink)
   v.setInt(R.id.period,"setBackgroundColor",Color.TRANSPARENT)
   listOf(R.id.legend_model to R.id.account,R.id.legend_tqqq to R.id.weights,R.id.legend_brkb to R.id.loan).forEachIndexed{index,(label,value)->
    v.setTextColor(label,colors[index])
    v.setTextColor(value,colors[index])
   }
   if(layout==WidgetPresentation.Layout.DETAIL)v.setTextColor(R.id.detail,ink)
   v.setTextViewText(R.id.title,"우공이산")
   v.setTextViewText(R.id.period,(Performance.periods[period]?:"1개월")+" ↻")
   v.setTextViewText(R.id.account,window?.let{Performance.percent(it.last.model)}?:"—")
   v.setTextViewText(R.id.weights,window?.let{Performance.percent(it.last.tqqq)}?:"—")
   v.setTextViewText(R.id.loan,window?.let{Performance.percent(it.last.brkb)}?:"—")
   v.setTextViewText(R.id.state,if(window==null)"비교 자료 갱신 대기 · 앱에서 확인" else "${window.end} · USD · 모의${if(stale)" · 갱신 대기" else ""}")
   if(layout==WidgetPresentation.Layout.DETAIL){
    val gap=window?.let{"TQQQ 대비 %+.2f%%p".format((it.last.model-it.last.tqqq)*100)}?:"비교 자료 갱신 대기"
    v.setTextViewText(R.id.detail,"모델 목표  ${Data.allocation(s)}\n$gap")
   }

   v.setImageViewBitmap(R.id.chart,chart(window,dark,layout==WidgetPresentation.Layout.COMPACT,WidgetPresentation.chartPixels(width,height,layout)))
   val open=PendingIntent.getActivity(c,id,Intent(c,MainActivity::class.java),PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
   v.setOnClickPendingIntent(R.id.widget_root,open)
   val cycle=Intent(PERIOD_ACTION).setComponent(info.provider).putExtra(AppWidgetManager.EXTRA_APPWIDGET_ID,id)
   v.setOnClickPendingIntent(R.id.period,PendingIntent.getBroadcast(c,id,cycle,PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT))
   m.updateAppWidget(id,v)
  }
  private fun seriesColors(dark:Boolean)=if(dark)listOf(Color.rgb(234,200,122),Color.rgb(174,185,234),Color.rgb(139,196,185)) else listOf(Color.rgb(118,85,22),Color.rgb(77,91,157),Color.rgb(50,109,100))
  internal fun chart(window:PerformanceWindow?,dark:Boolean=true,compact:Boolean=false,pixelHeight:Int=240):Bitmap {
   val bitmap=Bitmap.createBitmap(800,pixelHeight,Bitmap.Config.ARGB_8888);val canvas=Canvas(bitmap)
   val muted=if(dark)Color.rgb(165,174,194) else Color.rgb(104,112,134)
   val grid=if(dark)Color.rgb(48,57,75) else Color.rgb(224,228,239)
   val paint=Paint(Paint.ANTI_ALIAS_FLAG).apply{color=muted;textSize=24f}
   if(window==null){canvas.drawText("비교 자료 갱신 대기",18f,pixelHeight/2f+paint.textSize/3,paint);return bitmap}
   val labels=listOf(window.low,window.low+window.span/2,window.low+window.span)
   val left=if(compact)8f else labels.maxOf{paint.measureText("%+.1f%%".format(it*100))}+18f
   val top=14f;val right=790f;val height=(pixelHeight-28).toFloat()
   fun y(v:Double)=top+height*(1-((v-window.low)/window.span).toFloat())
   for(value in labels){
    val yy=y(value)
    if(!compact){paint.color=muted;canvas.drawText("%+.1f%%".format(value*100),0f,yy+7f,paint)}
    paint.color=grid;paint.strokeWidth=1.5f;canvas.drawLine(left,yy,right,yy,paint)
   }
   paint.color=muted;paint.alpha=100;canvas.drawLine(left,y(0.0),right,y(0.0),paint);paint.alpha=255
   val colors=seriesColors(dark)
   listOf("model","tqqq","brkb").forEachIndexed{index,key->
    val path=Path();window.points.forEachIndexed{i,p->val xx=left+(right-left)*i/(window.points.size-1);if(i==0)path.moveTo(xx,y(p.value(key))) else path.lineTo(xx,y(p.value(key)))}
    val line=Paint(Paint.ANTI_ALIAS_FLAG).apply{color=colors[index];strokeWidth=if(index==0)5.5f else 3.5f;style=Paint.Style.STROKE;strokeJoin=Paint.Join.ROUND;strokeCap=Paint.Cap.ROUND}
    canvas.drawPath(path,line)
   }
   return bitmap
  }
 }
}
class WoogongCompactWidget:WoogongWidget()
class WoogongDetailWidget:WoogongWidget()

class WoogongSignalWidget:WoogongWidget()
