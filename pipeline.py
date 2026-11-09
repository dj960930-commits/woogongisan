"""GitHub Actions job: validate complete EOD, publish derived snapshot, push."""
from pathlib import Path
from datetime import datetime,timedelta,timezone
import argparse,hashlib,json,os,time
import numpy as np,pandas as pd
import pandas_market_calendars as calendars
import httpx
from engine import evaluate,ASSETS
from models.registry import load_model
ROOT=Path(__file__).parent;SITE=Path(os.environ.get('WOOGONG_SITE_DIR',str(ROOT/'site')))
def write(path,value):
 tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False,allow_nan=False),encoding='utf-8');tmp.replace(path)
def session(now):
 schedule=calendars.get_calendar('NYSE').schedule(start_date=(now-timedelta(days=10)).date(),end_date=now.date())
 done=schedule[schedule.market_close<=pd.Timestamp(now)-pd.Timedelta(minutes=5)]
 return None if done.empty else (done.index[-1],done.market_close.iloc[-1])
def fetch(expected):
 from market_data import fetch as public_fetch
 return public_fetch(expected,ROOT)
def latest_backtest(p,targets,model=None,return_daily=False):
 model=model or load_model()
 if model.profile.get('performance_execution')=='same_close_reference':
  return close_reference_backtest(p,targets,model,return_daily)
 ix=p.loc['2021-10-20':].index;prices=p.reindex(ix)[['TQQQ','BRK.B','GLD','SOXL','BITO']]
 if prices.isna().any().any():raise ValueError('BITO 확장 백테스트 가격 누락')
 cls=np.column_stack([prices.TQQQ,prices['BRK.B'],prices.GLD,np.ones(len(ix)),prices.SOXL,prices.BITO]);tar=targets.reindex(ix).to_numpy()
 held=np.array([0.,0,0,1.,0,0]);nav=[1.];value=1.;goal=tar[0];request=True;rate=np.array([.001,.001,.001,0,.001,.001]);trades=0
 for i in range(1,len(ix)):
  mark=held*cls[i]/cls[i-1];value*=mark.sum();held=mark/mark.sum()
  if request:
   lo,hi=0.,1.
   for _ in range(55):
    x=(lo+hi)/2
    if x+np.dot(abs(x*goal-held),rate)>1:hi=x
    else:lo=x
   value*=(lo+hi)/2;held=goal.copy();trades+=1
  goal=tar[i];request=np.max(abs(goal-held))>=model.band;nav.append(value)
 v=np.array(nav);dd=v/np.maximum.accumulate(v)-1;cg=v[-1]**(365.25/(ix[-1]-ix[0]).days)-1
 result={**model.metadata(),'data_end':str(ix[-1].date()),'kind':'extended_EOD_audited_price_basis','label':'최신 확장 · 원본 혼합 가격기준 · 다음 종가 · 편도0.1% · 현금금리0 · 세전','cagr':cg,'mdd':float(dd.min()),'calmar':cg/-dd.min(),'trades':trades,'curve':[{'date':str(ix[i].date()),'nav':float(v[i]),'drawdown':float(dd[i])} for i in list(range(0,len(ix)-1,5))+[len(ix)-1]]}
 if return_daily:result['_daily_nav']=pd.Series(v,index=ix)
 return result

def input_fingerprint(p,btc,model):
 def digest(value):
  if value is None:return None
  series=value.astype(float)
  return hashlib.sha256(pd.util.hash_pandas_object(series,index=True).values.tobytes()).hexdigest()
 parts={
  'equities_and_cash':digest(p),
  'bitcoin':digest(btc),
  'model_id':model.id,
  'model_fingerprint':model.fingerprint,
  'first_date':str(p.index.min().date()) if len(p) else None,
  'last_date':str(p.index.max().date()) if len(p) else None,
  'input_contract':'equities+btc+cash_returns'
 }
 return hashlib.sha256(json.dumps(parts,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def close_reference_backtest(p,targets,model,return_daily=False):
 from models.performance import replay
 ix=p.loc['2021-10-20':].index
 cls=np.column_stack([p.loc[ix,'TQQQ'],p.loc[ix,'BRK.B'],p.loc[ix,'GLD'],np.ones(len(ix)),p.loc[ix,'SOXL'],p.loc[ix,'BITO']])
 cash=p.loc[ix,'cash_return'] if 'cash_return' in p else pd.Series(np.nan,index=ix)
 rf=cash.fillna(0).to_numpy()
 v,tr,_,_=replay(targets.reindex(ix).to_numpy(),cls,rf,band=model.band)
 dd=v/np.maximum.accumulate(np.r_[1.,v])[1:]-1
 cg=v[-1]**(365.25/(ix[-1]-ix[0]).days)-1
 basis='모델: 원본 혼합 가격기준·당일 확정 종가 후 동일 종가 체결 가정·편도0.1%·보관 현금수익(미확인일 0) / USD·세전'
 result={**model.metadata(),'data_end':str(ix[-1].date()),'kind':'extended_EOD_same_close_reference',
  'execution':'same_close_reference','basis':basis,'cash_zero_fallback_sessions':int(cash.isna().sum()),'label':'최신 확장 · 당일 종가 가격 체결 가정 · 실제 애프터장 체결 보장 아님',
  'cagr':float(cg),'mdd':float(dd.min()),'calmar':float(cg/-dd.min()) if dd.min()<0 else 0.,'trades':int(tr.sum()),
  'curve':[{'date':str(ix[i].date()),'nav':float(v[i]),'drawdown':float(dd[i])} for i in list(range(0,len(ix)-1,5))+[len(ix)-1]]}
 if return_daily:
  daily=pd.Series(v,index=ix);daily.attrs['basis']=basis;result['_daily_nav']=daily
 return result
def snapshot(p,btc,mode,raw=None,model=None):
 model=model or load_model()
 t,ind=evaluate(p,btc,model);last=ind.iloc[-1];day=t.index[-1];target=t.iloc[-1].to_dict();state=int(last.state)
 labels={0:'위험자산 배분',1:'반복 전환 제한',2:'상대강도 방어',3:'급락 방어',4:'상대지수 낙폭 방어'}
 def series(columns):return [{'date':str(i.date()),**{c:float(row[c]) for c in columns}} for i,row in ind.tail(180).iterrows() if all(np.isfinite(row[c]) for c in columns)]
 reasons=[{'title':'상대강도','value':float(last.gap),'threshold':-.005,'description':f'보정 상대지수 EMA20/45 로그 차이 {last.gap:.3%}. 진입은 0 초과, 이탈은 -0.5% 미만.','active':bool(last.bull)},
 {'title':'급락 상태','value':float(last.qqq_drawdown),'threshold':-.06,'description':f'QQQ 25일 고점 대비 {last.qqq_drawdown:.2%}. -6%에서 급락 상태 진입.','active':bool(last.crash)},
 {'title':'방어 선택','value':float(last.defense_fast-last.defense_slow),'threshold':0,'description':f'GLD/BRK.B EMA84 {last.defense_fast:.4f}, EMA378 {last.defense_slow:.4f}. '+('금 선택.' if last.defense_fast>last.defense_slow else '버크셔 선택.'),'active':state!=0},
 {'title':'상태 우선순위','value':state,'threshold':None,'description':labels[state]+(' 상태이므로 BRK.B로 제한합니다.' if state==1 else ' 상태를 목표 비중에 반영했습니다.'),'active':True}]
 state_label=labels[state]
 if 'defense_entry_active' in last:
  active=bool(last.defense_entry_active)
  reasons[2]['description']+=' v2는 방어 진입 때 단기 EMA5/21과 장기 우세 약화를 확인합니다. '+('BRK.B 보조 선택 적용 중.' if active else '현재 장기 선택 유지.')
  if active:state_label+=' · v2 단기 상대강도 버크셔 선택'
 if 'cross_cash' in ind:
  c=model.profile['cross'];d=model.profile['defense']
  if bool(last.cross_cash):state_label='Cross 동반 하락 · 달러 현금 대피'
  elif bool(last.defensive_cash):state_label+=f" · 방어 몫 {d['cash_fraction']:.0%} 현금"
  reasons.extend([
   {'title':'Cross5 · GLD21','value':int(last.cross_cash),'threshold':None,'description':f"방어 상태에서 위험자산 {c['riskmin']}종 이상과 BRK.B·GLD 동반 하락, 선택 방어자산 {c['look']}일 수익률 {c['loss']:.0%} 이하를 확인합니다. GLD 선택 시 {c['gold']}일 수익률도 음수여야 합니다. 최소 {c['minhold']}일·최대 {c['maxhold']}일 대피, 재진입 대기 {c['cooldown']}일. 현재 "+('현금 대피 중.' if last.cross_cash else '대피 미적용.'),'active':bool(last.cross_cash)},
   {'title':'D25 방어 현금','value':float(last.cash_fraction),'threshold':d['cash_fraction'],'description':f"QQQ 종가 {p.QQQ.iloc[-1]:.2f} / SMA{d['qqq_sma']} {last.qqq_sma:.2f}. 약세 시 BRK.B·GLD 방어 몫의 {d['cash_fraction']:.0%}를 달러 현금으로 이동합니다. 강제 BRK.B 상태에도 적용. 현재 "+('적용.' if last.defensive_cash else '미적용.'),'active':bool(last.defensive_cash)}])
 if 'allocation' in model.profile:
  allocation=model.profile['allocation']
  reasons.append({'title':'공격 비중과 현금','value':float(target['TQQQ']+target['SOXL']),
   'threshold':allocation['lever_cap'],
   'description':f"TQQQ+SOXL 목표 비중은 최대 {allocation['lever_cap']:.0%}, SOXL은 최대 {allocation['soxl_cap']:.0%}. 제한으로 남는 비중은 달러 현금으로 보유합니다. BTC에는 원래 모멘텀 비중만 배분하며 최소 비중은 없습니다. 재조정 기준과 가격 변동 때문에 실제 보유 비중은 목표 상한을 넘을 수 있습니다.",
   'active':state==0})
 data={**model.metadata(),'market_date':str(day.date()),'generated_at':datetime.now(timezone.utc).isoformat(),'mode':mode,'state':state,'state_label':state_label,
  'target':{k:float(v) for k,v in target.items()},'account_connected':False,'reasons':reasons,
 'indicators':{k:float(last[k]) for k in ['beta','hedge','gap','qqq_drawdown','defense_fast','defense_slow']},'charts':{'relative':series(['relative','relative_fast','relative_slow']),'defense':series(['defense_ratio','defense_fast','defense_slow']),'drawdown':series(['qqq_drawdown'])},'raw_close':raw or {},'data_fingerprint':input_fingerprint(p,btc,model)}
 future=calendars.get_calendar('NYSE').schedule(start_date=(day+pd.Timedelta(days=1)).date(),end_date=(day+pd.Timedelta(days=10)).date())
 data['valid_until']=(future.market_close.iloc[0]+pd.Timedelta(minutes=5)).isoformat()
 from trading.timing import timing
 data['loan_timing']=timing(state,int(ind.iloc[-2].state) if len(ind)>1 else None,model.fingerprint)
 return data,t
def push(data):
 tokens=json.loads(os.environ.get('FCM_TOKENS') or '[]');credentials_json=os.environ.get('FIREBASE_SERVICE_ACCOUNT_JSON','')
 if not tokens or not credentials_json:return {'configured':False,'sent':0,'failed':len(tokens)}
 import firebase_admin
 from firebase_admin import credentials,messaging
 if not firebase_admin._apps:firebase_admin.initialize_app(credentials.Certificate(json.loads(credentials_json)))
 sent=0
 for token in tokens:
  # Android immediately displays a visible notification, then syncs widget data.
  title='우공이산 · '+data['version'].removeprefix('우공 ')+' · '+data.get('market_date','데이터 확인')
  body=data.get('state_label','데이터 오류: 새 신호를 사용하지 마세요')
  message=messaging.Message(data={'title':title,'body':body,'market_date':data.get('market_date',''),'refresh':'1'},android=messaging.AndroidConfig(priority='high',ttl=timedelta(hours=3)),token=token)
  try:messaging.send(message);sent+=1
  except Exception:pass
 return {'configured':True,'sent':sent,'failed':len(tokens)-sent}
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--live',action='store_true');parser.add_argument('--demo',action='store_true');parser.add_argument('--force-refresh',action='store_true');args=parser.parse_args()
 if not args.live and not args.demo:parser.error('choose --live or --demo')
 SITE.mkdir(exist_ok=True);now=datetime.now(timezone.utc);model=load_model()
 if args.demo:
  p=pd.read_csv(ROOT/'data/equities.csv',index_col=0,parse_dates=True);btc=pd.read_csv(ROOT/'data/btc.csv',parse_dates=['date_utc']).set_index('date_utc').close
  data,t=snapshot(p,btc,'historical_demo',model=model);write(SITE/'snapshot.json',data);write(SITE/'model.json',model.metadata());write(SITE/'status.json',{**model.metadata(),'state':'demo','market_date':data['market_date'],'message':'2026-10-20 기준 과거 검증 자료. 현재 매매 신호가 아닙니다.'});return
 found=session(now)
 if found is None:return
 expected,close=found
 existing=json.loads((SITE/'snapshot.json').read_text(encoding='utf-8')) if (SITE/'snapshot.json').exists() else {}
 health=json.loads((SITE/'status.json').read_text(encoding='utf-8')) if (SITE/'status.json').exists() else {}
 if not args.force_refresh and existing.get('performance',{}).get('version')=='model-tqqq-brkb-v1' and existing.get('data_contract_id')=='audited-mixed-close-v1' and existing.get('market_date')==str(expected.date()) and existing.get('mode')=='live' and existing.get('model_fingerprint')==model.fingerprint and health.get('state')=='ready' and health.get('model_fingerprint')==model.fingerprint:return
 try:
  p,btc,raw=fetch(expected);data,t=snapshot(p,btc,'live',raw,model)
  data.update(data_contract_id='audited-mixed-close-v1',data_sources={'equities':'Yahoo Finance','btc':'Bitstamp'},price_basis={'QQQ':'close','TQQQ':'close','BRK.B':'close','GLD':'close','SOXL':'adjclose','BITO':'adjclose'})
  if data['market_date']!=str(expected.date()):raise ValueError('계산 기준일 불일치')
  proof=ROOT/'runtime/market-data-validation.json'
  if proof.exists():
   validation=json.loads(proof.read_text(encoding='utf-8'))
   if validation.get('expected_date')==data['market_date']:write(SITE/'data-validation.json',validation)
  evidence=ROOT/'models/evidence'/f'{model.id}.backtest.json'
  if evidence.exists():
   archived=json.loads(evidence.read_text(encoding='utf-8'))
   if archived.get('model_fingerprint')==model.fingerprint:write(SITE/'backtest.json',archived)
  extension=latest_backtest(p,t,model,return_daily=True)
  nav=extension.pop('_daily_nav')
  from comparison import build as build_comparison
  try:
   data['performance']=build_comparison(nav,json.loads((ROOT/'runtime/benchmark-prices.json').read_text(encoding='utf-8')))
  except (ValueError,KeyError,OSError):
   data['performance']={'available':False,'message':'비교 자료 갱신 대기'}
  from price_outlook import build as price_outlook
  try:
   data['price_outlook']=price_outlook(p,raw) if all(k in raw for k in ('TQQQ','BRK.B','GLD')) else {'available':False}
  except (ValueError,KeyError,IndexError):
   data['price_outlook']={'available':False,'message':'가격 시나리오 자료 확인 중'}
  write(SITE/'extended_backtest.json',extension);write(SITE/'snapshot.json',data);write(SITE/'model.json',model.metadata())
  write(SITE/'status.json',{**model.metadata(),'state':'ready','market_date':data['market_date'],'message':'원본 가격기준 대조 · 확정 종가 계산 완료','data_contract_id':'audited-mixed-close-v1','data_sources':data['data_sources'],'updated_at':now.isoformat()})
 except Exception as exc:
  # Preserve the last valid snapshot and visibly mark it unavailable/stale.
  write(SITE/'status.json',{**model.metadata(),'state':'error','expected_date':str(expected.date()),'message':'종가 자료 확인 중. 이전 목표를 새 신호로 사용하지 마세요.','error_type':type(exc).__name__,'updated_at':now.isoformat()})
  print('data unavailable:',type(exc).__name__);return
 # Forward-only research archive. A failure here must never block the live signal.
 if model.id!='woogong-1.3-d':
  try:
   from shadow_journal import append as append_shadow
   archive=SITE/'shadow-journal.json'
   journal=json.loads(archive.read_text(encoding='utf-8')) if archive.exists() else {}
   baseline=load_model('woogong-1.3-d');base_targets,_=baseline.evaluate(p,btc)
   journal=append_shadow(journal,data,p.iloc[-1],[(model,t.iloc[-1]),(baseline,base_targets.iloc[-1])])
   write(archive,journal)
   from tools.score_shadow_journal import summarize as summarize_shadow
   write(SITE/'shadow-report.json',summarize_shadow(journal))
  except Exception as shadow_error:
   print('shadow journal unavailable:',type(shadow_error).__name__)
 # Deployment workflow sends only after publication succeeds.
 print('snapshot prepared',data['market_date'])
if __name__=='__main__':main()
