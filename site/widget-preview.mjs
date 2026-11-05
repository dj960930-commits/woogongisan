import {windowFor,graph,series,percent,periods} from './performance.mjs?v=200';
let data=null,period='1m';
const selected=new Map();
const variants=[['compact','요약 · 3×2','작은 공간에서도 세 수익률을 또렷하게.'],['graph','그래프 · 5×2','세 개의 흐름을 한눈에.'],['detail','상세 · 5×3','그래프와 모델 목표, 상대 성과까지.']];
function render(){
 document.getElementById('periods').innerHTML=Object.entries(periods).map(([k,label])=>`<button class="button" data-period="${k}" aria-pressed="${k===period}">${label}</button>`).join('');
 document.getElementById('gallery').innerHTML=variants.map(([variant,title,description])=>{
  const p=selected.get(variant)||period,w=windowFor(data,p);
  const allocation=Object.entries(data?.target||{}).filter(([,v])=>v>0).map(([k,v])=>`${k} ${(v*100).toFixed(0)}%`).join(' · ');
  return `<section class="sample"><h2>${title}</h2><p class="caption">${description}</p><div class="widget ${variant}"><div class="widget-head"><strong>우공이산</strong><button class="period-button" data-cycle="${variant}" aria-label="${title} 기간 변경">${periods[p]} ↻</button></div><div class="widget-chart">${graph(w,true)}</div><div class="widget-values">${series.map(([k,label])=>`<div style="color:var(--series-${k})"><span>${label}</span><strong>${w?percent(w.returns[k]):'—'}</strong></div>`).join('')}</div>${variant==='detail'?`<div class="widget-detail">모델 목표 ${allocation||'앱에서 확인'}<br>${w?'TQQQ 대비 '+((w.returns.model-w.returns.tqqq)*100).toFixed(2)+'%p':'자료 갱신 대기'}</div>`:''}<div class="widget-date">${w?w.end+' · USD · 모의':'비교 자료 갱신 대기'}</div></div></section>`;
 }).join('');
}
document.addEventListener('click',e=>{
 const b=e.target.closest('button');if(!b)return;
 if(b.dataset.period){period=b.dataset.period;selected.clear();render();}
 if(b.dataset.cycle){const keys=Object.keys(periods),p=selected.get(b.dataset.cycle)||period;selected.set(b.dataset.cycle,keys[(keys.indexOf(p)+1)%keys.length]);render();}
 if(b.dataset.theme){if(b.dataset.theme==='system')delete document.documentElement.dataset.theme;else document.documentElement.dataset.theme=b.dataset.theme;document.querySelectorAll('[data-theme]').forEach(x=>{if(x.tagName==='BUTTON')x.setAttribute('aria-pressed',x===b)});}
});
try{const r=await fetch('snapshot.json',{cache:'no-store'});if(!r.ok)throw Error('fetch');data=await r.json();render();}catch{document.getElementById('gallery').textContent='비교 자료를 확인할 수 없습니다.';}
