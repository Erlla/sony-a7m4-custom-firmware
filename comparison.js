const st = document.currentScript.dataset.st;
const previewRow = document.createElement('tr');
previewRow.className = 'comparison-row';
previewRow.id = 'st-comparison';
previewRow.innerHTML = `
  <td colspan="5">
    <div class="comparison-stage">
      <div class="comparison-frame">
        <img class="comparison-before" alt="同一张 RAW 的原厂 ST 预览" decoding="async" draggable="false">
        <img class="comparison-after" alt="" draggable="false">
        <img class="comparison-reference" alt="" draggable="false" hidden>
        <div class="comparison-labels" aria-hidden="true"><span class="comparison-st-label">ST · 标准</span><span class="comparison-name"></span><span class="comparison-reference-label" hidden></span></div>
        <div class="comparison-seam" aria-hidden="true"><span></span></div>
        <div class="comparison-seam comparison-seam-right" aria-hidden="true" hidden><span></span></div>
        <input class="comparison-range" type="range" min="0" max="100" value="50" aria-label="ST 画面所占比例" aria-valuetext="ST 50%">
        <input class="comparison-range comparison-range-right" type="range" min="0" max="100" value="67" aria-label="M4 与参考图分界" hidden>
      </div>
      <div class="comparison-caption"><span class="comparison-credit">M4 模拟器</span><span class="comparison-status" aria-live="polite">拖动滑杆比较同一区域</span></div>
    </div>
  </td>`;

const frame = previewRow.querySelector('.comparison-frame');
const before = previewRow.querySelector('.comparison-before');
const after = previewRow.querySelector('.comparison-after');
const reference = previewRow.querySelector('.comparison-reference');
const range = previewRow.querySelector('.comparison-range');
const rightRange = previewRow.querySelector('.comparison-range-right');
const rightSeam = previewRow.querySelector('.comparison-seam-right');
const leftLabel = previewRow.querySelector('.comparison-st-label');
const middleLabel = previewRow.querySelector('.comparison-name');
const rightLabel = previewRow.querySelector('.comparison-reference-label');
const credit = previewRow.querySelector('.comparison-credit');
const status = previewRow.querySelector('.comparison-status');
let active;
let singleSplit = 50;
let dragRange;

function updateSplits(changed) {
  const triple = frame.classList.contains('is-triple');
  if (triple && Number(range.value) > Number(rightRange.value)) {
    if (changed === rightRange) rightRange.value = range.value;
    else range.value = rightRange.value;
  }
  const left = Number(range.value);
  const right = Number(rightRange.value);
  frame.style.setProperty('--split', left + '%');
  frame.style.setProperty('--split-right', right + '%');
  range.setAttribute('aria-valuetext', 'ST ' + left + '%');
  rightRange.setAttribute('aria-valuetext', '参考图 ' + (100 - right) + '%');
  if (!triple) singleSplit = left;
  leftLabel.hidden = triple && left < 16;
  middleLabel.hidden = triple && right - left < 18;
  rightLabel.hidden = !triple || right > 81;
}

range.addEventListener('input', () => updateSplits(range));
rightRange.addEventListener('input', () => updateSplits(rightRange));

function pointerPercent(event) {
  const rect = frame.getBoundingClientRect();
  return Math.round(100 * (event.clientX - rect.left) / rect.width);
}

frame.addEventListener('pointerdown', event => {
  if (!frame.classList.contains('is-triple') || range.disabled || event.button !== 0 || dragRange) return;
  const position = pointerPercent(event);
  const seam = event.target.closest('.comparison-seam');
  const rightIsCloser = Math.abs(position - Number(rightRange.value)) < Math.abs(position - Number(range.value));
  dragRange = (seam === rightSeam || (!seam && rightIsCloser)) ? rightRange : range;
  frame.setPointerCapture(event.pointerId);
  dragRange.focus({preventScroll: true});
  if (!seam) {
    dragRange.value = position;
    updateSplits(dragRange);
  }
});
frame.addEventListener('pointermove', event => {
  if (!dragRange || !frame.hasPointerCapture(event.pointerId)) return;
  dragRange.value = pointerPercent(event);
  updateSplits(dragRange);
});
frame.addEventListener('lostpointercapture', () => { dragRange = null; });

function closePreview() {
  if (!active) return;
  active.setAttribute('aria-expanded', 'false');
  active.removeAttribute('aria-controls');
  dragRange = null;
  previewRow.remove();
  active = null;
}

for (const download of document.querySelectorAll('#all a[download][data-preview]')) {
  const key = download.getAttribute('href').split('/').at(-1).replace(/\.json$/, '');
  const referenceUrl = download.dataset.reference;
  const triple = Boolean(referenceUrl);
  const isFuji = download.dataset.referenceRenderer === 'fuji';
  const row = download.closest('tr');
  const name = row.querySelector('th').firstChild.textContent.trim();
  const button = document.createElement('button');
  button.className = 'comparison-toggle';
  button.type = 'button';
  button.textContent = triple ? '三图对比' : 'ST 对比';
  button.dataset.preview = key;
  button.setAttribute('aria-label', name + (triple ? ' 与 ST、参考图三图对比' : ' 与 ST 对比'));
  button.setAttribute('aria-expanded', 'false');
  const controls = document.createElement('div');
  controls.className = 'comparison-actions';
  const files = document.createElement('span');
  files.className = 'comparison-files';
  const cell = download.closest('td');
  files.append(...cell.querySelectorAll('a[download]'));
  controls.append(button, files);
  cell.append(controls);

  button.addEventListener('click', async () => {
    const wasOpen = active === button;
    closePreview();
    if (wasOpen) return;
    active = button;
    button.setAttribute('aria-expanded', 'true');
    button.setAttribute('aria-controls', previewRow.id);
    const wasTriple = frame.classList.contains('is-triple');
    frame.classList.toggle('is-triple', triple);
    if (triple && !wasTriple) {
      range.value = 33;
      rightRange.value = 67;
    } else if (!triple && wasTriple) range.value = singleSplit;
    range.setAttribute('aria-label', triple ? 'ST 与 M4 分界' : 'ST 画面所占比例');
    rightSeam.hidden = rightRange.hidden = !triple;
    before.src = st;
    after.hidden = true;
    reference.hidden = true;
    range.disabled = rightRange.disabled = true;
    after.alt = name + ' 的 M4 模拟器预览';
    after.src = download.dataset.preview;
    if (triple) {
      const renderer = isFuji ? '富士 RAW FILE CONVERTER EX' : 'Lightroom Classic · Cobalt';
      reference.alt = name + ' 的参考图，由 ' + renderer + ' 导出';
      reference.src = referenceUrl;
      rightLabel.textContent = isFuji ? (key === 'classic-neg' ? '富士 · CN' : '富士软件') : 'LR · Cobalt';
      credit.textContent = isFuji
        ? '富士参考图由同一张索尼 RAW 转为富士 RAF 后，在 RAW FILE CONVERTER EX 中显影导出。'
        : '参考图使用训练时的 Cobalt 配置，在 Lightroom Classic 中从同一张索尼 RAW 显影导出。';
    } else credit.textContent = 'M4 模拟器';
    middleLabel.textContent = triple ? 'M4 · ' + (key === 'classic-neg' ? 'CN' : name) : name;
    updateSplits();
    status.textContent = '正在加载对比图';
    row.after(previewRow);
    try {
      const images = triple ? [before, after, reference] : [before, after];
      await Promise.all(images.map(image => image.decode()));
      if (active !== button) return;
      after.hidden = false;
      reference.hidden = !triple;
      range.disabled = false;
      rightRange.disabled = !triple;
      status.textContent = triple ? '拖动两根滑杆比较同一区域' : '拖动滑杆比较同一区域';
    } catch {
      if (active === button) status.textContent = '对比图加载失败，请收起后重试';
    }
  });
}

function closeWhenFiltered() {
  if (active?.closest('.group').hidden) closePreview();
}

document.querySelector('nav[aria-label="按品牌筛选"]').addEventListener('click', closeWhenFiltered);
window.addEventListener('hashchange', closeWhenFiltered);
window.addEventListener('popstate', closeWhenFiltered);

const initial = new URLSearchParams(location.search).get('preview');
const demo = [...document.querySelectorAll('.comparison-toggle')].find(button => button.dataset.preview === initial);
if (demo && !demo.closest('.group').hidden) {
  demo.click();
  demo.closest('tr').scrollIntoView({block: 'start'});
}
