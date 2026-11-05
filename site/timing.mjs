const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function timingAvailable(t,available=false,now=Date.now()){
 const until=Date.parse(t?.valid_until);
 return Boolean(available&&t?.supported&&Number.isFinite(now)&&Number.isFinite(until)&&now<until);
}
export function refreshTimingCards(root,t,available=false,date='—',now=Date.now()){
 const valid=timingAvailable(t,available,now);
 for(const card of root.querySelectorAll('[data-loan-timing]')){
  card.style.borderLeftColor=valid&&t.phase==='entry'?'#7964d9':'#b4b8c8';
  card.querySelector('[data-timing-label]').textContent=valid?t.label:'판정 보류 · 최신 검증 신호 필요';
  card.querySelector('[data-timing-date]').textContent='기준 '+date+(!valid&&t?.label?' · 과거 상태: '+t.label:'');
 }
}
export function timingCard(t,available=false,date='—'){
 const valid=timingAvailable(t,available);
 return `<section class="card" data-loan-timing><h2>신규 차입 신호</h2><h3 data-timing-label>${esc(valid?t.label:'최신 결과 확인 중')}</h3><p class="caption" data-timing-date>기준 ${esc(date)}</p></section>`;
}
export function timingDetails(t){return `<h3>신규 차입 신호 조건</h3><p>${esc(t?.entry_rule||'방어에서 공격으로 전환하는 날을 확인합니다.')}</p><p>${esc(t?.exit_rule||'공격 종료 시 차입분 정리를 검토합니다.')}</p><p>${esc(t?.checks||'은행 부채·금리·상환 여력은 직접 확인해야 합니다.')}</p><p>${esc(t?.risk||'자동 차입이나 주문 증액을 실행하지 않습니다.')}</p>`;}
