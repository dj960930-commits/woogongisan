"""Per-device outbox: call only AFTER the Pages deployment succeeds."""
from pathlib import Path
import json,os,hashlib
from pipeline import ROOT,SITE,write
def main():
 status=json.loads((SITE/'status.json').read_text(encoding='utf-8'))
 if status.get('state') not in ['ready','error']:return
 data=json.loads((SITE/'snapshot.json').read_text(encoding='utf-8'))
 failure=status.get('state')=='error'
 if failure:data={'version':status.get('version','우공')+' 오류','market_date':status.get('expected_date','확인 필요'),'state_label':'종가 자료 확인 중 · 새 신호를 사용하지 마세요','model_fingerprint':status.get('model_fingerprint','')}
 if not failure and (data.get('model_fingerprint')!=status.get('model_fingerprint') or data.get('market_date')!=status.get('market_date')):raise ValueError('게시 결과 모델 불일치')
 tokens=json.loads(os.environ.get('FCM_TOKENS') or '[]');raw=os.environ.get('FIREBASE_SERVICE_ACCOUNT_JSON','')
 if not tokens or not raw:print('push: not configured');return
 import firebase_admin
 from firebase_admin import credentials,messaging
 firebase_admin.initialize_app(credentials.Certificate(json.loads(raw)))
 out=Path(os.environ.get('WOOGONG_OUTBOX_DIR',str(ROOT/'runtime')));out.mkdir(parents=True,exist_ok=True);file=out/'delivery.json'
 done=json.loads(file.read_text(encoding='utf-8')) if file.exists() else {};failures=0
 for token in tokens:
  key=data.get('model_fingerprint',data['version'])+':'+data['market_date']+':'+hashlib.sha256(token.encode()).hexdigest()
  if key in done:continue
  try:
   messaging.send(messaging.Message(data={'title':'우공이산 · '+data['version'].removeprefix('우공 ')+' · '+data['market_date'],'body':data['state_label']+' · 목표 비중을 확인하세요','refresh':'1'},android=messaging.AndroidConfig(priority='high'),token=token))
   done[key]=True;write(file,done)
  except Exception:failures+=1
 print('push failures:',failures)
 if failures:raise SystemExit(1)
if __name__=='__main__':main()

