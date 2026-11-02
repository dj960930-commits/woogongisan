const root=document.querySelector('#outlook'),select=document.querySelector('#history');
const text=(parent,tag,value)=>{const e=document.createElement(tag);e.textContent=value;parent.append(e);return e;};
const usd=v=>new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(v);
let latest,index=[];
async function load(url){const r=await fetch(url,{cache:'no-store'});if(!r.ok)throw Error('자료 조회 실패');return r.json();}
function render(s){root.replaceChildren();const f=s.price_outlook;if(!f?.assets){text(root,'p','이 발표에는 가격 예상 자료가 없습니다.');return;}
 text(root,'h2',`${f.as_of} 기준 예상`);text(root,'p',f.method);text(root,'p',f.limitation);
 for(const a of f.assets){const card=text(root,'section','');card.className='card';text(card,'h2',`${a.symbol} · 기준 ${usd(a.close)}`);
 for(const w of a.windows){text(card,'h3',`${w.sessions}거래일 후 · ${w.target_date}`);text(card,'p',`중앙 ${usd(w.median)} · 과거 분포 범위 ${usd(w.lower)} ~ ${usd(w.upper)}`);const e=w.evaluation;if(e.origins)text(card,'p',`과거 순차검증 ${e.origins}회 · 중앙 예상 오차 ${(100*e.mae_return).toFixed(1)}%p / 가격유지 기준 ${(100*e.unchanged_mae_return).toFixed(1)}%p · 과거 범위 포함 ${(100*e.historical_coverage).toFixed(0)}%`);
 const actual=index.filter(x=>x.market_date===w.target_date).at(-1);if(actual)load('history/'+actual.file).then(v=>{const price=v.raw_close?.[a.symbol];if(Number.isFinite(price))text(card,'p',`실제 ${w.target_date}: ${usd(price)} · 중앙 예상 대비 ${((price/w.median-1)*100).toFixed(2)}%`);}).catch(()=>{});
 }} }
try{[latest,index]=await Promise.all([load('snapshot.json'),load('history/index.json').catch(()=>[])]);for(const row of [...index].reverse()){if(!/^[a-zA-Z0-9.-]+\.json$/.test(row.file))continue;const o=document.createElement('option');o.value=row.file;o.textContent=`${row.market_date} · ${row.version} · ${row.generated_at||''}`;select.append(o);}render(latest);}catch{root.textContent='자료를 불러오지 못했습니다. 잠시 후 다시 확인하세요.';}
select.onchange=async()=>{try{render(select.value?await load('history/'+select.value):latest);}catch{root.textContent='과거 자료 조회 실패';}};
