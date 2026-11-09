const host = document.querySelector('#guide');
function add(parent, tag, text, className) {
  const item = document.createElement(tag);
  item.textContent = text;
  if (className) item.className = className;
  parent.append(item);
  return item;
}

try {
  const response = await fetch(new URL('strategy-guide.json', import.meta.url));
  if (!response.ok) throw new Error('Guide unavailable');
  const guide = await response.json();
  host.replaceChildren();
  add(host, 'p', guide.intro);
  const labels = [['rule', '어떻게 판단하나요?'], ['example', '예시'],
    ['study', '어떤 실험을 했나요?'], ['decision', '현재 적용하는 방식']];
  guide.rules.forEach((rule, index) => {
    const card = add(host, 'details', '', 'card');
    card.id = "rule-" + (index + 1);
    if (location.hash === "#" + card.id) { card.open = true; requestAnimationFrame(() => card.scrollIntoView()); }
    add(card, 'summary', (index + 1) + '. ' + rule.title);
    add(card, 'p', rule.summary);
    for (const [key, title] of labels) {
      add(card, 'h2', title);
      add(card, 'p', rule[key]);
    }
    const evidence = [null, "bito-weighted-reduction", "defense-36912", "methodology-full", "methodology-full"][index];
    const link = add(card, "a", "관련 실험 원본 보기 ↗");
    link.href = evidence ? "research/" + evidence + ".csv" : "research-validation.html";
  });
  const results = add(host, 'section', '', 'card');
  add(results, 'h2', '전체 전략의 백테스트');
  add(results, 'p', guide.result);
  add(results, 'p', guide.basis, 'hint');
  const history = add(results, 'a', '이전 모델 연구와 검증 기록 ↗');
  history.href = 'research-validation.html';
} catch {
  host.textContent = '전략 가이드를 열 수 없습니다. 페이지를 새로고침해 주세요.';
}
