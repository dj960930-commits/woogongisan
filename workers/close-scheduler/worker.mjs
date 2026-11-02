import {sessions, coverageEnd} from './calendar.mjs';

const ROOT='https://api.github.com/repos/eastgenie0909-cell/woogongisan';
const STATUS='https://eastgenie0909-cell.github.io/woogongisan/status.json';
const ACTIVE=new Set(['queued','in_progress','waiting','pending','requested']);

export function dueSession(now, rows=sessions){
 if(!Number.isFinite(now))throw Error('invalid_clock');
 let lo=0,hi=rows.length-1,index=-1;
 while(lo<=hi){const mid=(lo+hi)>>1;if(rows[mid][0]+300000<=now){index=mid;lo=mid+1;}else hi=mid-1;}
 if(index<0||now>rows[index][0]+90*60000)return null;
 return {close:rows[index][0],date:rows[index][1]};
}

export function isPublished(status, expected, now){
 return status?.schema_version===1&&status.state==='ready'&&status.market_date===expected.date
  &&status.data_contract_id==='audited-mixed-close-v1'
  &&/^[a-f0-9]{64}$/.test(status.model_fingerprint||'')
  &&Number.isFinite(Date.parse(status.updated_at))
  &&Date.parse(status.updated_at)>=expected.close+300000&&Date.parse(status.updated_at)<=now+300000;
}

export function activeRun(runs,now){
 return runs.some(run=>ACTIVE.has(run.status)&&Number.isFinite(Date.parse(run.created_at))
  &&Date.parse(run.created_at)<=now+300000&&now-Date.parse(run.created_at)<20*60000);
}

export async function run(now,env,fetcher=fetch){
 const expected=dueSession(now);
 if(!expected)return {state:now>Date.parse(coverageEnd+'T23:59:59Z')?'calendar_expired':'outside_window',configured:Boolean(env.GITHUB_TOKEN)};
 if(!env.GITHUB_TOKEN)throw Error('missing_github_token');
 let status=null;
 try{
  const response=await fetcher(STATUS+'?close='+expected.date+'&check='+Math.floor(now/300000),{headers:{'Cache-Control':'no-cache'},redirect:'error',signal:AbortSignal.timeout(15000)});
  if(response.ok)status=await response.json();
 }catch{ /* A temporarily unavailable public page must not suppress calculation. */ }
 if(isPublished(status,expected,now))return {state:'already_published',date:expected.date};
 const headers={'Authorization':'Bearer '+env.GITHUB_TOKEN,'Accept':'application/vnd.github+json',
  'User-Agent':'Woogongisan-free-close-scheduler','X-GitHub-Api-Version':'2022-11-28'};
 const existing=await fetcher(ROOT+'/actions/workflows/daily.yml/runs?per_page=5',
  {headers,redirect:'error',signal:AbortSignal.timeout(15000)});
 if(!existing.ok)throw Error('github_runs_http_'+existing.status);
 const data=await existing.json();
 if(!Array.isArray(data.workflow_runs))throw Error('invalid_runs_response');
 if(activeRun(data.workflow_runs,now))return {state:'calculation_active',date:expected.date};
 const response=await fetcher(ROOT+'/actions/workflows/daily.yml/dispatches',{
  method:'POST',headers:{...headers,'Content-Type':'application/json'},redirect:'error',
  body:JSON.stringify({ref:'main',inputs:{external_close_date:expected.date}}),signal:AbortSignal.timeout(15000)});
 if(response.status!==204)throw Error('github_dispatch_http_'+response.status);
 return {state:'dispatched',date:expected.date};
}

export default {
 async scheduled(controller,env,ctx){
  ctx.waitUntil((async()=>{
   try{console.log(JSON.stringify(await run(controller.scheduledTime,env)));}
   catch(error){
    // Never log request headers, tokens, upstream bodies, or arbitrary errors.
    const message=String(error?.message||'');
    const code=/^(missing_github_token|invalid_clock|invalid_runs_response|github_(runs|dispatch)_http_\d{3})$/.test(message)?message:'request_failed';
    console.error(JSON.stringify({state:'failed',code}));throw Error(code);
   }
  })());
 },
 fetch(){return new Response('Not found',{status:404,headers:{'Cache-Control':'no-store'}});}
};
