package com.woogong.app

import org.json.JSONObject

/** Parse one published generation; never fill a missing document from another. */
internal object SignalBundle {
 fun read(raw:String):JSONObject {
  val bundle=JSONObject(raw)
  require(bundle.getInt("schema_version")==1)
  require(bundle.getString("generation").matches(Regex("[a-f0-9]{32}")))
  val docs=bundle.getJSONObject("documents")
  for(name in listOf("model.json","snapshot.json","status.json"))docs.getJSONObject(name)
  require(docs.getJSONObject("snapshot.json").getString("market_date")==bundle.getString("market_date"))
  return docs
 }
}
