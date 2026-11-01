package com.woogong.app

import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class SignalBundleTest {
 private fun bundle()=JSONObject().put("schema_version",1).put("generation","a".repeat(32)).put("market_date","2026-10-30")
  .put("documents",JSONObject().put("snapshot.json",JSONObject().put("market_date","2026-10-30"))
   .put("status.json",JSONObject().put("state","ready")).put("model.json",JSONObject()))
 @Test fun readsOnePublishedGeneration(){val docs=SignalBundle.read(bundle().toString());assertEquals("2026-10-30",docs.getJSONObject("snapshot.json").getString("market_date"))}
 @Test fun rejectsMissingCoreDocument(){val b=bundle();b.getJSONObject("documents").remove("model.json");assertTrue(runCatching{SignalBundle.read(b.toString())}.isFailure)}
 @Test fun rejectsUnknownOrMalformedContract(){for(b in listOf(bundle().put("schema_version",2),bundle().put("generation","invalid"))){assertTrue(runCatching{SignalBundle.read(b.toString())}.isFailure)}}
 @Test fun rejectsMixedMarketDates(){val b=bundle().put("market_date","2026-11-02");assertTrue(runCatching{SignalBundle.read(b.toString())}.isFailure)}
 @Test fun allowsErrorStatusWithPreviousGenerationWithoutFillingHistory(){val b=bundle();b.getJSONObject("documents").getJSONObject("status.json").put("state","error");val docs=SignalBundle.read(b.toString());assertEquals("error",docs.getJSONObject("status.json").getString("state"));assertFalse(docs.has("backtest.json"))}
}
