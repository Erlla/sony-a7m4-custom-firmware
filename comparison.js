const st = document.currentScript.dataset.st;
const filterExposure = document.currentScript.dataset.filterEv;
const previewRow = document.createElement('tr');
previewRow.className = 'comparison-row';
previewRow.id = 'st-comparison';
previewRow.innerHTML = `
  <td colspan="5">
    <div class="comparison-stage">
      <div class="comparison-frame">
        <img class="comparison-before" alt="同一张 RAW 的原厂 ST 预览" decoding="async" draggable="false">
        <img class="comparison-after" alt="" draggable="false">
        <div class="comparison-labels" aria-hidden="true"><span>ST · 标准</span><span class="comparison-name"></span></div>
        <div class="comparison-seam" aria-hidden="true"><span></span></div>
        <input class="comparison-range" type="range" min="0" max="100" value="50" aria-label="ST 画面所占比例" aria-valuetext="ST 50%">
      </div>
      <div class="comparison-caption"><span class="comparison-credit"></span><span class="comparison-status" aria-live="polite">拖动滑杆比较同一区域</span></div>
    </div>
  </td>`;

const frame = previewRow.querySelector('.comparison-frame');
const before = previewRow.querySelector('.comparison-before');
const after = previewRow.querySelector('.comparison-after');
const range = previewRow.querySelector('.comparison-range');
const status = previewRow.querySelector('.comparison-status');
previewRow.querySelector('.comparison-credit').textContent = 'M4 模拟器 · 滤镜 ' + filterExposure + ' EV';
let active;

range.addEventListener('input', () => {
  frame.style.setProperty('--split', range.value + '%');
  range.setAttribute('aria-valuetext', 'ST ' + range.value + '%');
});

function closePreview() {
  if (!active) return;
  active.setAttribute('aria-expanded', 'false');
  active.removeAttribute('aria-controls');
  previewRow.remove();
  active = null;
}

for (const download of document.querySelectorAll('#all a[download][data-preview]')) {
  const key = download.getAttribute('href').split('/').at(-1).replace(/\.json$/, '');
  const row = download.closest('tr');
  const name = row.querySelector('th').firstChild.textContent.trim();
  const button = document.createElement('button');
  button.className = 'comparison-toggle';
  button.type = 'button';
  button.textContent = 'ST 对比';
  button.dataset.preview = key;
  button.setAttribute('aria-label', name + ' 与 ST 对比');
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
    before.src = st;
    after.hidden = true;
    range.disabled = true;
    after.alt = name + ' 的 M4 模拟器预览';
    after.src = download.dataset.preview;
    previewRow.querySelector('.comparison-name').textContent = name;
    status.textContent = '正在加载对比图';
    row.after(previewRow);
    try {
      await Promise.all([before.decode(), after.decode()]);
      if (active !== button) return;
      after.hidden = false;
      range.disabled = false;
      status.textContent = '拖动滑杆比较同一区域';
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
