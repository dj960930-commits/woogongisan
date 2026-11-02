import assert from 'node:assert/strict';
import worker,{dueSession,isPublished,activeRun,run} from '../workers/close-scheduler/worker.mjs';

const instant=s=>Date.parse(s);
const now=instant('2026-11-02T21:05:00Z');
const expected=dueSession(now);
assert.equal(expected.date,'2026-11-02');
assert.equal(dueSession(now-1),null);
assert.equal(dueSession(instant('2026-11-01T21:05:00Z')),null); // Sunday, Korean Monday.
assert.equal(dueSession(instant('2026-11-26T21:05:00Z')),null); // Thanksgiving.
assert.equal(dueSession(instant('2026-11-27T18:05:00Z')).date,'2026-11-27'); // Early close.
assert.equal(dueSession(instant('2026-10-30T20:05:00Z')).date,'2026-10-30'); // DST.
assert.equal(dueSession(instant('2026-11-02T22:30:01Z')),null);
const status={schema_version:1,state:'ready',market_date:expected.date,data_contract_id:'audited-mixed-close-v1',model_fingerprint:'a'.repeat(64),updated_at:'2026-11-02T21:05:00Z'};
assert.ok(isPublished(status,expected,now));
for(const patch of [{state:'error'},{market_date:'2026-10-30'},{updated_at:'2026-11-02T20:59:59Z'},{model_fingerprint:'invalid'}])assert.equal(isPublished({...status,...patch},expected,now),false);
assert.ok(activeRun([{status:'queued',created_at:'2026-11-02T21:04:00Z'}],now));
assert.equal(activeRun([{status:'in_progress',created_at:'2026-11-02T20:40:00Z'}],now),false);

const token='test-token-never-log';
function fake({published=status,runs=[],runsStatus=200,dispatchStatus=204}={}){
 const calls=[];
 const fetcher=async(url,options)=>{
  calls.push({url,options});assert.ok(!url.includes(token));
  if(url.includes('/status.json?close=')){assert.equal(options.headers.Authorization,undefined);return Response.json(published);}
  assert.ok(url.startsWith('https://api.github.com/repos/dj960930-commits/woogongisan/'));
  assert.equal(options.headers.Authorization,'Bearer '+token);
  assert.equal(options.redirect,'error');
  if(url.includes('/runs?'))return Response.json({workflow_runs:runs},{status:runsStatus});
  assert.equal(options.method,'POST');
  assert.deepEqual(JSON.parse(options.body),{ref:'main',inputs:{external_close_date:'2026-11-02'}});
  return new Response(null,{status:dispatchStatus});
 };
 return {calls,fetcher};
}
{
 const f=fake();assert.equal((await run(now,{GITHUB_TOKEN:token},f.fetcher)).state,'already_published');assert.equal(f.calls.length,1);
}
{
 const f=fake({published:{...status,market_date:'2026-10-30'}});
 assert.equal((await run(now,{GITHUB_TOKEN:token},f.fetcher)).state,'dispatched');assert.equal(f.calls.length,3);
}
{
 const f=fake({published:{state:'error'},runs:[{status:'in_progress',created_at:'2026-11-02T21:04:00Z'}]});
 assert.equal((await run(now,{GITHUB_TOKEN:token},f.fetcher)).state,'calculation_active');assert.equal(f.calls.length,2);
}
{
 const f=fake();assert.equal((await run(instant('2026-11-01T21:05:00Z'),{},f.fetcher)).state,'outside_window');assert.equal(f.calls.length,0);
 await assert.rejects(()=>run(now,{},f.fetcher),/missing_github_token/);
}
for(const failure of [{runsStatus:403},{dispatchStatus:403}]){
 const f=fake({published:{state:'error'},...failure});await assert.rejects(()=>run(now,{GITHUB_TOKEN:token},f.fetcher),/github_.*_http_403/);
}
assert.equal((await worker.fetch(new Request('https://example.test/trigger',{method:'POST'}))).status,404);
console.log('Free close scheduler: calendar, publication, deduplication, dispatch, permission failures and private-route checks passed');
