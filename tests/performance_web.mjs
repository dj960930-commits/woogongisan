import assert from 'node:assert/strict';
import {windowFor,graph,card,basisDetails} from '../site/performance.mjs';
const points=[{date:'2026-09-25',model:0,tqqq:0,brkb:0},{date:'2026-10-27',model:-.08,tqqq:-.1,brkb:.07}];
const snapshot={market_date:'2026-10-27',performance:{available:true,version:'model-tqqq-brkb-v1',currency:'USD',market_date:'2026-10-27',windows:{'1m':{start:points[0].date,end:points[1].date,points,returns:{model:-.08,tqqq:-.1,brkb:.07}}}}};
const w=windowFor(snapshot);assert.ok(w);assert.match(graph(w),/버크셔 B/);assert.equal((graph(w).match(/<polyline /g)||[]).length,3);assert.match(card(snapshot),/-8.00%/);assert.doesNotMatch(card(snapshot),/내 계좌/);
for(const alter of [s=>s.performance.currency='KRW',s=>s.performance.market_date='2026-10-26',s=>s.performance.windows['1m'].points[0].model=.01,s=>s.performance.windows['1m'].returns.tqqq=.9]){const s=structuredClone(snapshot);alter(s);assert.equal(windowFor(s),null);}
console.log('Performance web comparison: 9 checks passed');
snapshot.performance.basis='당일 확정 종가 후 동일 가격 체결 가정 <script>';
assert.match(basisDetails(snapshot),/당일 확정 종가 후 동일 가격 체결 가정/);
assert.doesNotMatch(card(snapshot),/당일 확정 종가 후 동일 가격 체결 가정/);
assert.doesNotMatch(basisDetails(snapshot),/<script>/);
console.log('V2 execution-basis rendering and escaping passed');
