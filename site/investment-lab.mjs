export function project(points, key, initial, monthly, fee) {
  let paid = initial;
  let value = initial * (1 - fee);
  for (let i = 1; i < points.length; i++) {
    const previous = points[i - 1], current = points[i];
    value *= (1 + current[key]) / (1 + previous[key]);
    if (current.date.slice(0, 7) !== previous.date.slice(0, 7)) {
      paid += monthly;
      value += monthly * (1 - fee);
    }
  }
  return { paid, value, profit: value - paid };
}

if (typeof document !== 'undefined') {
  const form = document.querySelector('#inputs');
  const result = document.querySelector('#results');
  const usd = new Intl.NumberFormat('ko', { style: 'currency', currency: 'USD' });
  try {
    const response = await fetch('snapshot.json');
    if (!response.ok) throw new Error();
    const snapshot = await response.json();
    const points = snapshot.performance.windows.all.points;
    if (points.length < 2) throw new Error();
    form.elements.start.min = form.elements.start.value = points[0].date;
    form.elements.start.max = points.at(-2).date;
    document.querySelector('#basis').textContent = snapshot.performance.basis;
    function render() {
      const inputs = new FormData(form);
      const selected = points.filter(point => point.date >= inputs.get('start'));
      if (selected.length < 2) return;
      result.replaceChildren();
      const period = document.createElement('p');
      period.textContent = selected[0].date + ' ~ ' + selected.at(-1).date;
      result.append(period);
      for (const [key, name] of [['model', snapshot.version], ['tqqq', 'TQQQ'], ['brkb', '버크셔 B']]) {
        const { paid, value, profit } = project(selected, key, +inputs.get('initial'), +inputs.get('monthly'), +inputs.get('fee') / 100);
        const card = document.createElement('p');
        card.className = 'card';
        card.textContent = name + ' · 총 납입액 ' + usd.format(paid) + ' · 최종 평가액 ' + usd.format(value) + ' · 투자손익 ' + usd.format(profit);
        result.append(card);
      }
    }
    form.addEventListener('submit', event => { event.preventDefault(); render(); });
    render();
  } catch {
    result.textContent = '비교에 필요한 일별 성과를 불러올 수 없습니다.';
  }
}
