// ---- State ----
let currentItems = [];
let currentCategories = [];
let currentImageData = null;
let selectedMatchItem = null;
let sellImagePath = null;

// ---- Tab switching ----
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
    if (btn.dataset.tab === 'items') loadItems();
    if (btn.dataset.tab === 'report') loadReport();
  });
});

// ---- Toast ----
function showToast(msg, duration) {
  if (!duration) duration = 2500;
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(t._hide);
  t._hide = setTimeout(() => t.classList.remove('show'), duration);
}

// ---- API helper ----
async function api(url, opts) {
  if (!opts) opts = {};
  const res = await fetch(url, opts);
  const data = await res.json();
  if (!res.ok) { showToast(data.error || '请求失败'); throw new Error(data.error); }
  return data;
}

// ======================== CATEGORIES ========================
async function loadCategories() {
  currentCategories = await api('/api/categories');
  const sel = document.getElementById('formCategory');
  sel.innerHTML = currentCategories.map(c => `<option value="${c.id}">${c.name}</option>`).join('');
  const filter = document.getElementById('categoryFilter');
  if (!filter) return;
  filter.innerHTML = '<button class="cat-chip active" data-cat="">全部</button>' +
    currentCategories.map(c => `<button class="cat-chip" data-cat="${c.id}">${c.name}</button>`).join('');
  filter.querySelectorAll('.cat-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      filter.querySelectorAll('.cat-chip').forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      renderItems(chip.dataset.cat);
    });
  });
}

// ======================== ITEMS (CRUD) ========================
async function loadItems() {
  currentItems = await api('/api/items');
  renderItems();
}

document.getElementById('itemSearch').addEventListener('input', async (e) => {
  const q = e.target.value.trim();
  currentItems = q ? await api('/api/items?q=' + encodeURIComponent(q)) : await api('/api/items');
  renderItems();
});

function renderItems(categoryFilter) {
  const grid = document.getElementById('itemsGrid');
  let items = currentItems;
  if (categoryFilter) items = items.filter(i => i.category_id == categoryFilter);
  if (!items.length) {
    grid.innerHTML = '<div class="empty-state">暂无商品，点击右上角"添加"</div>';
    return;
  }
  grid.innerHTML = items.map(it => {
    const imgSrc = it.thumb_path ? '/uploads/' + it.thumb_path : '';
    const fallback = 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect fill="%23E8DDD0" width="100" height="100"/><text x="50" y="55" text-anchor="middle" fill="%238B7355" font-size="30">%F0%9F%92%8E</text></svg>';
    return '<div class="item-card">' +
      '<img src="' + (imgSrc || fallback) + '" alt="' + escHtml(it.name) + '" onerror="this.src=\'' + fallback + '\'">' +
      '<div class="item-actions">' +
        '<button onclick="editItem(' + it.id + ')" title="编辑">✏️</button>' +
        '<button onclick="deleteItem(' + it.id + ')" title="删除">🗑️</button>' +
      '</div>' +
      '<div class="item-body">' +
        '<div class="name">' + escHtml(it.name) + '</div>' +
        '<div class="price">¥' + it.price.toFixed(2) + '</div>' +
        '<div class="cat">' + escHtml(it.category_name || '') + '</div>' +
      '</div></div>';
  }).join('');
}

function escHtml(s) { var d=document.createElement('div'); d.textContent=s||''; return d.innerHTML; }

// ---- Add / Edit Item Form ----
document.getElementById('btnAddItem').addEventListener('click', function() { openItemForm(null); });
document.getElementById('btnSaveItem').addEventListener('click', saveItem);
document.getElementById('btnCancelItemForm').addEventListener('click', closeItemForm);
document.getElementById('closeItemFormBtn').addEventListener('click', closeItemForm);

document.getElementById('formImage').addEventListener('change', function() {
  var file = this.files[0];
  if (!file) return;
  var reader = new FileReader();
  reader.onload = function(e) {
    var preview = document.getElementById('formImagePreview');
    preview.src = e.target.result;
    preview.style.display = 'block';
    document.getElementById('formRemoveImage').style.display = 'inline-block';
  };
  reader.readAsDataURL(file);
});
document.getElementById('formRemoveImage').addEventListener('click', function() {
  document.getElementById('formImage').value = '';
  document.getElementById('formImagePreview').style.display = 'none';
  this.style.display = 'none';
});

function openItemForm(item) {
  document.getElementById('formItemId').value = item ? item.id : '';
  document.getElementById('itemFormTitle').textContent = item ? '编辑商品' : '添加商品';
  document.getElementById('formName').value = item ? item.name : '';
  document.getElementById('formPrice').value = item ? item.price : '';
  document.getElementById('formCategory').value = item ? item.category_id : (currentCategories[0] ? currentCategories[0].id : '');
  document.getElementById('formStock').value = item ? item.stock : 1;
  document.getElementById('formNote').value = item ? (item.note || '') : '';
  if (item && item.thumb_path) {
    var preview = document.getElementById('formImagePreview');
    preview.src = '/uploads/' + item.thumb_path;
    preview.style.display = 'block';
    document.getElementById('formRemoveImage').style.display = 'inline-block';
  } else {
    document.getElementById('formImagePreview').style.display = 'none';
    document.getElementById('formRemoveImage').style.display = 'none';
  }
  document.getElementById('formImage').value = '';
  document.getElementById('itemFormModal').style.display = 'flex';
}

function closeItemForm() {
  document.getElementById('itemFormModal').style.display = 'none';
}

async function saveItem() {
  var id = document.getElementById('formItemId').value;
  var fd = new FormData();
  fd.append('name', document.getElementById('formName').value.trim());
  fd.append('price', document.getElementById('formPrice').value);
  fd.append('category_id', document.getElementById('formCategory').value);
  fd.append('stock', document.getElementById('formStock').value);
  fd.append('note', document.getElementById('formNote').value.trim());
  var imgFile = document.getElementById('formImage').files[0];
  if (imgFile) fd.append('image', imgFile);
  try {
    if (id) {
      await api('/api/items/' + id, { method:'PUT', body:fd });
      showToast('商品已更新');
    } else {
      await api('/api/items', { method:'POST', body:fd });
      showToast('商品已添加');
    }
    closeItemForm();
    await loadItems();
  } catch(e) {}
}

async function editItem(id) {
  var item = currentItems.find(function(i) { return i.id === id; });
  if (item) openItemForm(item);
}

async function deleteItem(id) {
  if (!confirm('确定删除这个商品？')) return;
  await api('/api/items/' + id, { method:'DELETE' });
  showToast('已删除');
  await loadItems();
}

// ======================== SELL ========================
var mediaStream = null;

document.getElementById('btnCamera').addEventListener('click', async function() {
  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({ video:{ facingMode:'environment' } });
    var video = document.getElementById('video');
    video.style.display = 'block';
    video.srcObject = mediaStream;
    await video.play();
    document.getElementById('cameraPlaceholder').style.display = 'none';
    document.getElementById('capturedPreview').style.display = 'none';
    document.getElementById('btnCamera').textContent = '拍摄';
    document.getElementById('btnCamera').onclick = capturePhoto;
  } catch(e) {
    showToast('无法打开相机，请使用上传图片');
  }
});

function capturePhoto() {
  var video = document.getElementById('video');
  var canvas = document.getElementById('canvas');
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  var ctx = canvas.getContext('2d');
  ctx.drawImage(video, 0, 0);
  var dataUrl = canvas.toDataURL('image/jpeg', 0.85);
  var preview = document.getElementById('capturedPreview');
  preview.src = dataUrl;
  preview.style.display = 'block';
  video.style.display = 'none';
  currentImageData = dataUrl;
  if (mediaStream) {
    mediaStream.getTracks().forEach(function(t) { t.stop(); });
    mediaStream = null;
  }
  document.getElementById('btnCamera').textContent = '重拍';
  document.getElementById('btnCamera').onclick = restartCamera;
  document.getElementById('btnMatch').style.display = 'block';
}

function restartCamera() {
  document.getElementById('capturedPreview').style.display = 'none';
  document.getElementById('btnMatch').style.display = 'none';
  currentImageData = null;
  sellImagePath = null;
  document.getElementById('btnCamera').textContent = '拍照';
  document.getElementById('btnCamera').onclick = async function() {
    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({ video:{ facingMode:'environment' } });
      var video = document.getElementById('video');
      video.style.display = 'block';
      video.srcObject = mediaStream;
      await video.play();
      document.getElementById('cameraPlaceholder').style.display = 'none';
      document.getElementById('btnCamera').textContent = '拍摄';
      document.getElementById('btnCamera').onclick = capturePhoto;
    } catch(e) { showToast('无法打开相机'); }
  };
}

document.getElementById('btnUpload').addEventListener('click', function() {
  document.getElementById('fileInput').click();
});
document.getElementById('fileInput').addEventListener('change', function() {
  var file = this.files[0];
  if (!file) return;
  var reader = new FileReader();
  reader.onload = function(e) {
    var preview = document.getElementById('capturedPreview');
    preview.src = e.target.result;
    preview.style.display = 'block';
    document.getElementById('cameraPlaceholder').style.display = 'none';
    document.getElementById('video').style.display = 'none';
    currentImageData = e.target.result;
    document.getElementById('btnCamera').textContent = '重拍';
    document.getElementById('btnCamera').onclick = restartCamera;
    document.getElementById('btnMatch').style.display = 'block';
  };
  reader.readAsDataURL(file);
});

document.getElementById('btnMatch').addEventListener('click', async function() {
  if (!currentImageData) return;
  document.getElementById('sellResults').innerHTML = '<div class="results-placeholder"><p>识别中…</p></div>';
  var blob = dataURLToBlob(currentImageData);
  var fd = new FormData();
  fd.append('image', blob, 'sell.jpg');
  try {
    var data = await api('/api/match', { method:'POST', body:fd });
    sellImagePath = data.image;
    renderMatchResults(data.matches);
  } catch(e) {
    document.getElementById('sellResults').innerHTML = '<div class="results-placeholder"><p>识别失败，请重试</p></div>';
  }
});

function dataURLToBlob(dataUrl) {
  var parts = dataUrl.split(',');
  var mime = parts[0].match(/:(.*?);/)[1];
  var bytes = atob(parts[1]);
  var buf = new ArrayBuffer(bytes.length);
  var view = new Uint8Array(buf);
  for (var i=0; i<bytes.length; i++) view[i] = bytes.charCodeAt(i);
  return new Blob([buf], { type:mime });
}

function renderMatchResults(matches) {
  if (!matches.length) {
    document.getElementById('sellResults').innerHTML = '<div class="results-placeholder"><p>未找到匹配商品，请先添加该商品到目录</p></div>';
    return;
  }
  var html = '<div style="margin-bottom:10px;font-weight:500;font-size:14px;">匹配结果（点击选择）</div>';
  matches.forEach(function(item, idx) {
    var imgSrc = item.thumb_path ? '/uploads/' + item.thumb_path : '';
    var fallback = 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect fill="%23E8DDD0" width="100" height="100"/><text x="50" y="55" text-anchor="middle" fill="%238B7355" font-size="30">%F0%9F%92%8E</text></svg>';
    var scorePct = Math.round((item.match_score || 0) * 100);
    html += '<div class="match-card' + (idx===0?' selected':'') + '" data-item-id="' + item.id + '" onclick="selectMatch(this, ' + item.id + ')">' +
      '<img src="' + (imgSrc || fallback) + '" alt="">' +
      '<div class="match-info">' +
        '<div class="name">' + escHtml(item.name) + '</div>' +
        '<div class="price">¥' + item.price.toFixed(2) + '</div>' +
      '</div>' +
      '<div class="match-score">' + scorePct + '%</div></div>';
  });
  html += '<button class="btn btn-accent" style="width:100%;padding:12px;margin-top:6px;font-size:15px;" onclick="openSaleModal()">选择该商品并出售</button>';
  document.getElementById('sellResults').innerHTML = html;
  selectedMatchItem = matches[0] ? matches[0].id : null;
}

function selectMatch(el, itemId) {
  document.querySelectorAll('.match-card').forEach(function(c) { c.classList.remove('selected'); });
  el.classList.add('selected');
  selectedMatchItem = itemId;
}

function openSaleModal() {
  if (!selectedMatchItem) return showToast('请先选择匹配的商品');
  var item = currentItems.find(function(i) { return i.id === selectedMatchItem; });
  if (!item) return showToast('商品信息异常');
  var fallback = 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect fill="%23E8DDD0" width="100" height="100"/><text x="50" y="55" text-anchor="middle" fill="%238B7355" font-size="30">%F0%9F%92%8E</text></svg>';
  var imgSrc = item.thumb_path ? '/uploads/' + item.thumb_path : fallback;
  document.getElementById('saleModalBody').innerHTML =
    '<div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;padding:10px;background:var(--bg);border-radius:8px;">' +
    '<img src="' + imgSrc + '" style="width:48px;height:48px;border-radius:8px;object-fit:cover;">' +
    '<div><strong>' + escHtml(item.name) + '</strong><br><span style="color:var(--primary);font-weight:600;">¥' + item.price.toFixed(2) + '</span></div></div>' +
    '<label>数量</label><input type="number" id="saleQuantity" value="1" min="1" style="margin-bottom:8px">' +
    '<label>收款方式</label><select id="salePayment"><option value="现金">现金</option><option value="微信">微信</option><option value="支付宝">支付宝</option></select>' +
    '<label>备注（可选）</label><input type="text" id="saleNote" placeholder="如：优惠后价格">';
  document.getElementById('saleModal').style.display = 'flex';
}

function closeSaleModal() {
  document.getElementById('saleModal').style.display = 'none';
}

document.getElementById('closeSaleModalBtn').addEventListener('click', closeSaleModal);
document.getElementById('btnCancelSale').addEventListener('click', closeSaleModal);
document.getElementById('saleModal').addEventListener('click', function(e) {
  if (e.target === e.currentTarget) closeSaleModal();
});

document.getElementById('btnConfirmSale').addEventListener('click', async function() {
  if (!selectedMatchItem) return;
  var item = currentItems.find(function(i) { return i.id === selectedMatchItem; });
  if (!item) return;
  var quantity = parseInt(document.getElementById('saleQuantity').value) || 1;
  var payment = document.getElementById('salePayment').value;
  var note = document.getElementById('saleNote').value.trim();
  try {
    await api('/api/sales', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({ item_id:item.id, item_name:item.name, price:item.price, quantity:quantity, payment_method:payment, note:note })
    });
    showToast('已卖出 ' + quantity + ' 件 ' + item.name + '，共 ¥' + (item.price * quantity).toFixed(2));
    closeSaleModal();
    restartCamera();
    document.getElementById('sellResults').innerHTML = '<div class="results-placeholder"><p>拍照或上传饰品图片，系统自动匹配</p></div>';
  } catch(e) {}
});

// ======================== REPORT ========================
async function loadReport() {
  var today = new Date().toISOString().slice(0,10);
  document.getElementById('reportStart').value = today;
  document.getElementById('reportEnd').value = today;
  await queryReport(today, today);
}

document.getElementById('btnQueryReport').addEventListener('click', async function() {
  var start = document.getElementById('reportStart').value;
  var end = document.getElementById('reportEnd').value;
  if (!start || !end) return showToast('请选择日期范围');
  await queryReport(start, end);
});

async function queryReport(start, end) {
  var data = await api('/api/sales/range?start=' + start + '&end=' + end);
  var uniqueItems = new Set(data.sales.map(function(s) { return s.item_id; }));
  document.getElementById('summaryCards').innerHTML =
    '<div class="summary-card"><div class="label">总销售额</div><div class="value">¥' + data.total.toFixed(2) + '</div></div>' +
    '<div class="summary-card"><div class="label">销售单数</div><div class="value">' + data.sales.length + '</div></div>' +
    '<div class="summary-card"><div class="label">卖出品种</div><div class="value">' + uniqueItems.size + '</div></div>';
  if (!data.sales.length) {
    document.getElementById('reportList').innerHTML = '<div class="empty-state">该时间段暂无销售记录</div>';
    return;
  }
  var fallback = 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect fill="%23E8DDD0" width="100" height="100"/><text x="50" y="55" text-anchor="middle" fill="%238B7355" font-size="30">%F0%9F%92%8E</text></svg>';
  document.getElementById('reportList').innerHTML = data.sales.map(function(s) {
    var imgSrc = s.thumb_path ? '/uploads/' + s.thumb_path : fallback;
    var itemLabel = escHtml(s.item_name) + (s.quantity > 1 ? ' ×' + s.quantity : '');
    var timeStr = s.sale_time ? s.sale_time.slice(11,16) : '';
    var extra = timeStr + ' ' + (s.payment_method || '') + (s.note ? ' · ' + escHtml(s.note) : '');
    return '<div class="sale-row">' +
      '<img src="' + imgSrc + '" alt="">' +
      '<div class="sale-info"><div class="name">' + itemLabel + '</div><div class="time">' + extra + '</div></div>' +
      '<div class="sale-price">¥' + (s.price * s.quantity).toFixed(2) + '</div></div>';
  }).join('');
}

// ---- Init ----
loadCategories();
loadItems();
