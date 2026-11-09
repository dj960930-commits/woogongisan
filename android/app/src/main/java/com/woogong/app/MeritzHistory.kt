package com.woogong.app

import org.json.JSONArray

/** Merge only after the user confirms that both histories belong to the same account. */
internal object MeritzHistory {
 fun merge(older:JSONArray,current:JSONArray):JSONArray {
  val days=sortedMapOf<String,org.json.JSONObject>()
  for(rows in listOf(older,current))for(i in 0 until rows.length()){
   val row=rows.getJSONObject(i)
   val day=row.getString("day")
   require(day.matches(Regex("\\d{4}-\\d{2}-\\d{2}")))
   days[day]=row
  }
  val result=JSONArray()
  days.values.toList().takeLast(730).forEach{result.put(it)}
  return result
 }
}
