export const periods={'1m':'1개월','3m':'3개월','1y':'1년',all:'전체'};
export const series=[['model','우공이산','#75dfc5'],['tqqq','TQQQ','#8caaff'],['brkb','버크셔 B','#e5bb70']];
export const percent=v=>(v>=0?'+':'')+(v*100).toFixed(2)+'%';
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function windowFor(snapshot,period='1m'){
 const p=snapshot?.performance,w=p?.windows?.[period];
 if(!p?.available||p.version!=='model-tqqq-brkb-v1'||p.currency!=='USD'||p.market_date!==snapshot.market_date||!w||!Array.isArray(w.points)||w.points.length<2)return null;
 if(w.start!==w.points[0].date||w.end!==w.points.at(-1).date||w.end!==snapshot.market_date)return null;
 for(let i=0;i<w.points.length;i++){
  const row=w.points[i];if(!/^\d{4}-\d{2}-\d{2}$/.test(row.date)||(i&&row.date<=w.points[i-1].date))return null;
  if(series.some(([k])=>!Number.isFinite(row[k])||row[k]<-1))return null;
 }
 if(series.some(([k])=>Math.abs(w.points[0][k])>1e-10||!Number.isFinite(w.returns[k])||Math.abs(w.returns[k]-w.points.at(-1)[k])>1e-10))return null;
 return w;
}
export function graph(w,compact=false){
 if(!w)return '<p style="color:#a2b5c9">비교 자료 갱신 대기 · 최신 결과를 확인하세요.</p>';
 const width=720,height=compact?160:270,left=compact?85:72,top=14,bottom=height-24;
 const values=w.points.flatMap(p=>series.map(([k])=>p[k]));const low=Math.min(0,...values),high=Math.max(0,...values),span=Math.max(.01,high-low);
 const y=v=>top+(bottom-top)*(1-(v-low)/span),x=i=>left+(width-left-10)*i/(w.points.length-1);
 const axes=[low,low+span/2,low+span].map(v=>`<path d="M${left} ${y(v)}H${width}" stroke="var(--chart-grid,#304153)" stroke-dasharray="4 6"/><text x="0" y="${y(v)+4}" fill="var(--muted,#a2b5c9)" font-size="${compact?19:14}">${(v*100).toFixed(1)}%</text>`).join('');
 return `<svg viewBox="0 0 ${width} ${height}" style="width:100%;display:block" role="img" aria-label="우공이산 모델, TQQQ, 버크셔 B 동일 기간 수익률 비교">${axes}<path d="M${left} ${y(0)}H${width}" stroke="#66778a"/>${series.map(([k,,color],i)=>`<polyline points="${w.points.map((r,i)=>`${x(i)},${y(r[k])}`).join(' ')}" fill="none" stroke="var(--series-${k},${color})" stroke-width="${i?2.4:3.6}" stroke-linejoin="round" stroke-linecap="round"/>`).join('')}<text x="${left}" y="${height-2}" fill="var(--muted,#a2b5c9)" font-size="14">${esc(w.start)}</text><text x="${width}" y="${height-2}" text-anchor="end" fill="var(--muted,#a2b5c9)" font-size="14">${esc(w.end)}</text></svg>`;
}
export function card(snapshot,period='1m'){
 const w=windowFor(snapshot,period);
 return `<section class="card performance-card"><div class="eyebrow">MODEL / BENCHMARK</div><h2>우공이산, 시장과 나란히</h2><div class="performance-periods">${Object.entries(periods).map(([k,v])=>`<button class="${period===k?'selected':''}" data-action="performance-period" data-value="${k}" aria-pressed="${period===k}">${v}</button>`).join('')}</div><div class="performance-hero"><span>● 우공이산 모델</span><strong>${w?percent(w.returns.model):'—'}</strong><small>선택 기간의 누적 수익률</small></div>${graph(w)}<div class="performance-benchmarks">${series.slice(1).map(([k,label])=>`<div style="color:var(--series-${k})"><span>● ${label}</span><strong>${w?percent(w.returns[k]):'—'}</strong></div>`).join('')}</div><p class="caption">동일 기간 시작 0% · USD · 세전<br>${esc(snapshot?.performance?.basis||'계산 기준 확인 필요')}</p></section>`;
}
