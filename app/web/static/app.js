"use strict";

/* ========================================================================
 * 果蔬自助称重 — kiosk 前端
 * WS 事件驱动状态机：idle / recognizing / review / lowconf / selector / payment
 * ===================================================================== */

const DEMO = new URLSearchParams(location.search).has("demo");

const stage = document.getElementById("stage");
const els = {
  video: document.getElementById("video"),
  cameraHint: document.getElementById("cameraHint"),
  idleWeight: document.getElementById("idleWeight"),
  recogWeight: document.getElementById("recogWeight"),
  lowWeight: document.getElementById("lowWeight"),
  reviewName: document.getElementById("reviewName"),
  reviewConf: document.getElementById("reviewConf"),
  reviewWeight: document.getElementById("reviewWeight"),
  reviewUnit: document.getElementById("reviewUnit"),
  reviewTotal: document.getElementById("reviewTotal"),
  candidates: document.getElementById("candidates"),
  cats: document.getElementById("cats"),
  grid: document.getElementById("grid"),
  search: document.getElementById("search"),
  payName: document.getElementById("payName"),
  payTotal: document.getElementById("payTotal"),
  payWeight: document.getElementById("payWeight"),
  payUnit: document.getElementById("payUnit"),
  payOrder: document.getElementById("payOrder"),
  connToast: document.getElementById("connToast"),
  exitModal: document.getElementById("exitModal"),
};

let ws = null;
let returnState = "review";   // 选择器返回的目标状态
let products = [];            // 品类选择器数据
let activeCat = "全部";

/* ---------------- 状态机 / 进度条 ---------------- */
function setState(name) {
  stage.dataset.state = name;
  if (name === "review" || name === "lowconf") returnState = name;
  setProgress(name);
}

function setProgress(state) {
  const steps = stage.querySelectorAll(".progress .step");
  const bars = stage.querySelectorAll(".progress .bar");
  steps.forEach((s) => s.classList.remove("active", "done"));
  bars.forEach((b) => b.classList.remove("done"));
  const [place, recognize, confirm] = steps;
  const onConfirm = ["review", "lowconf", "selector"].includes(state);
  if (state === "idle") {
    place.classList.add("active");
  } else if (state === "recognizing") {
    place.classList.add("done"); bars[0].classList.add("done");
    recognize.classList.add("active");
  } else if (onConfirm) {
    place.classList.add("done"); recognize.classList.add("done");
    bars.forEach((b) => b.classList.add("done"));
    confirm.classList.add("active");
  } else if (state === "payment") {
    steps.forEach((s) => s.classList.add("done"));
    bars.forEach((b) => b.classList.add("done"));
  }
}

/* ---------------- 渲染 ---------------- */
function fmtConf(c) { return Math.round((c || 0) * 100) + "%"; }

function renderReview(d) {
  els.reviewName.textContent = d.name_cn || d.label || "—";
  els.reviewConf.textContent = "置信度 " + fmtConf(d.confidence);
  els.reviewWeight.textContent = (d.weight_kg ?? 0).toFixed(3);
  els.reviewUnit.textContent = d.price_per_kg != null ? d.price_per_kg.toFixed(2) : "—";
  els.reviewTotal.textContent = d.total_price != null ? d.total_price.toFixed(2) : "—";
}

function renderLowConf(d) {
  els.lowWeight.textContent = Math.round((d.weight_kg ?? 0) * 1000);
  els.candidates.innerHTML = "";
  (d.candidates || []).forEach((c) => {
    const btn = document.createElement("button");
    btn.className = "cand";
    btn.innerHTML =
      `<span>${c.zh_name || c.label}</span><span class="cand-conf">${fmtConf(c.confidence)}</span>`;
    btn.addEventListener("click", () => send({ type: "select", label: c.label }));
    els.candidates.appendChild(btn);
  });
}

function renderPayment(d, orderId) {
  els.payName.textContent = d.name_cn || d.label || "商品";
  els.payTotal.textContent = "¥" + (d.total_price != null ? d.total_price.toFixed(2) : "—");
  els.payWeight.textContent = (d.weight_kg ?? 0).toFixed(3);
  els.payUnit.textContent = d.price_per_kg != null ? d.price_per_kg.toFixed(2) : "—";
  els.payOrder.textContent = orderId ?? "—";
}

/* ---------------- 品类选择器 ---------------- */
async function openSelector() {
  setState("selector");
  if (products.length === 0) await loadProducts();
}

async function loadProducts() {
  if (DEMO) { products = DEMO_PRODUCTS.slice(); }
  else {
    try {
      const resp = await fetch("/api/ui/products");
      products = await resp.json();
    } catch (e) { products = []; }
  }
  buildCats();
  renderGrid();
}

function catOf(p) { return (p.label || "").split("_")[0] || "其他"; }

function buildCats() {
  const keys = Array.from(new Set(products.map(catOf))).sort();
  const tabs = ["全部", ...keys];
  activeCat = "全部";
  els.cats.innerHTML = "";
  tabs.forEach((k) => {
    const div = document.createElement("div");
    div.className = "cat" + (k === activeCat ? " active" : "");
    div.textContent = k;
    div.addEventListener("click", () => {
      activeCat = k;
      els.cats.querySelectorAll(".cat").forEach((c) =>
        c.classList.toggle("active", c.textContent === k));
      renderGrid();
    });
    els.cats.appendChild(div);
  });
}

function renderGrid() {
  const q = (els.search.value || "").trim().toLowerCase();
  const list = products.filter((p) => {
    const catOk = activeCat === "全部" || catOf(p) === activeCat;
    const qOk = !q || (p.name_cn || "").toLowerCase().includes(q) ||
      (p.label || "").toLowerCase().includes(q);
    return catOk && qOk;
  });
  els.grid.innerHTML = "";
  if (list.length === 0) {
    els.grid.innerHTML = '<div class="grid-empty">没有匹配的商品</div>';
    return;
  }
  list.forEach((p) => {
    const cell = document.createElement("div");
    cell.className = "cell";
    cell.innerHTML =
      `<div class="cell-name">${p.name_cn || p.label}</div>` +
      `<div class="cell-price">¥${Number(p.price_per_kg).toFixed(2)}/kg</div>`;
    cell.addEventListener("click", () => send({ type: "select", label: p.label }));
    els.grid.appendChild(cell);
  });
}

/* ---------------- WebSocket ---------------- */
function dispatch(msg) {
  switch (msg.type) {
    case "weight": {
      const g = msg.weight_g ?? 0;
      els.idleWeight.textContent = g;
      els.recogWeight.textContent = g;
      break;
    }
    case "recognizing": setState("recognizing"); break;
    case "transaction_ready":
      if (msg.data && msg.data.low_confidence) { renderLowConf(msg.data); setState("lowconf"); }
      else { renderReview(msg.data); setState("review"); }
      break;
    case "confirmed": renderPayment(msg.data || {}, msg.transaction_id); setState("payment"); break;
    case "cleared": setState("idle"); break;
    case "error": showToast("识别异常：" + (msg.text || "")); break;
  }
}

function send(obj) {
  if (DEMO) { demoHandleSend(obj); return; }
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(obj));
}

function connect() {
  if (DEMO) return;
  const proto = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.onopen = () => els.connToast.hidden = true;
  ws.onmessage = (ev) => { try { dispatch(JSON.parse(ev.data)); } catch (e) {} };
  ws.onclose = () => { els.connToast.hidden = false; setTimeout(connect, 1500); };
  ws.onerror = () => { try { ws.close(); } catch (e) {} };
}

let toastTimer = null;
function showToast(text) {
  els.connToast.hidden = false;
  els.connToast.textContent = text;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    els.connToast.hidden = true;
    els.connToast.textContent = "连接已断开，重连中…";
  }, 3000);
}

/* ---------------- MJPEG 视频流（断流自恢复） ---------------- */
function bindVideo() {
  if (DEMO) {
    els.video.style.display = "none";
    els.cameraHint.textContent = "演示模式 · 实时画面占位";
    return;
  }
  els.video.onerror = () => {
    setTimeout(() => { els.video.src = "/stream/video?t=" + Date.now(); }, 1500);
  };
  els.video.src = "/stream/video";
}

/* ---------------- 二维码占位（伪 QR 图案） ---------------- */
function fillQR(groupId, seed) {
  const g = document.getElementById(groupId);
  if (!g) return;
  const n = 21, cell = 100 / n;
  let rng = seed;
  const rand = () => { rng = (rng * 1103515245 + 12345) & 0x7fffffff; return rng / 0x7fffffff; };
  let out = "";
  const finder = (ox, oy) => {
    for (let y = 0; y < 7; y++) for (let x = 0; x < 7; x++) {
      const edge = x === 0 || x === 6 || y === 0 || y === 6;
      const core = x >= 2 && x <= 4 && y >= 2 && y <= 4;
      if (edge || core)
        out += `<rect x="${(ox + x) * cell}" y="${(oy + y) * cell}" width="${cell}" height="${cell}"/>`;
    }
  };
  for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) {
    const inFinder = (x < 8 && y < 8) || (x > n - 9 && y < 8) || (x < 8 && y > n - 9);
    if (!inFinder && rand() > 0.5)
      out += `<rect x="${x * cell}" y="${y * cell}" width="${cell}" height="${cell}"/>`;
  }
  finder(0, 0); finder(n - 7, 0); finder(0, n - 7);
  g.innerHTML = out;
}

/* ---------------- 按钮（事件委托） ---------------- */
stage.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-action]");
  if (!btn) return;
  const action = btn.dataset.action;
  if (action === "confirm") send({ type: "confirm" });
  else if (action === "clear") send({ type: "clear" });
  else if (action === "open-selector") openSelector();
  else if (action === "close-selector") setState(returnState);
  else if (action === "finish") send({ type: "clear" });
  else if (action === "open-exit") els.exitModal.hidden = false;
  else if (action === "exit-cancel") els.exitModal.hidden = true;
  else if (action === "exit-confirm") doExit();
});

/* 退出：确认后通知后端结束 kiosk（演示模式禁用） */
function doExit() {
  if (DEMO) { els.exitModal.hidden = true; showToast("演示模式：退出已禁用"); return; }
  const title = els.exitModal.querySelector(".modal-title");
  if (title) title.textContent = "正在退出…";
  fetch("/api/exit", { method: "POST" }).catch(() => {});
}
els.search.addEventListener("input", renderGrid);

/* ---------------- 启动 ---------------- */
function init() {
  fillQR("qrPatternA", 1234567);
  fillQR("qrPatternB", 7654321);
  bindVideo();
  setState("idle");
  if (DEMO) startDemo(); else connect();
}

/* ======================================================================
 * 演示模式（?demo=1）：无需后端/硬件，依次走查全部 6 状态
 * ==================================================================== */
const DEMO_PRODUCTS = [
  { label: "apple_fuji", name_cn: "红富士苹果", price_per_kg: 12.8 },
  { label: "apple_granny", name_cn: "青苹果", price_per_kg: 11.0 },
  { label: "banana_yellow", name_cn: "黄香蕉", price_per_kg: 8.5 },
  { label: "orange", name_cn: "橙子", price_per_kg: 10.0 },
  { label: "cabbage_broccoli", name_cn: "西兰花", price_per_kg: 9.9 },
  { label: "beet_round", name_cn: "红甜菜根", price_per_kg: 7.2 },
  { label: "avocado_hass", name_cn: "哈斯牛油果", price_per_kg: 25.0 },
  { label: "apricot_jerdel", name_cn: "野杏", price_per_kg: 15.5 },
];
const DEMO_TXN = {
  label: "apple_fuji", name_cn: "红富士苹果", confidence: 0.96,
  weight_kg: 0.326, price_per_kg: 12.8, total_price: 4.17,
  low_confidence: false, candidates: [],
};
const DEMO_LOW = {
  label: "unknown", name_cn: null, confidence: 0.41,
  weight_kg: 0.258, price_per_kg: null, total_price: null, low_confidence: true,
  candidates: [
    { label: "apple_fuji", zh_name: "红富士苹果", confidence: 0.41 },
    { label: "apple_granny", zh_name: "青苹果", confidence: 0.33 },
    { label: "beet_round", zh_name: "红甜菜根", confidence: 0.18 },
  ],
};
const DEMO_STEPS = [
  () => dispatch({ type: "cleared" }) || dispatch({ type: "weight", weight_g: 0, stable: false }),
  () => dispatch({ type: "weight", weight_g: 326, stable: false }),
  () => dispatch({ type: "recognizing" }),
  () => dispatch({ type: "transaction_ready", data: DEMO_TXN }),
  () => dispatch({ type: "transaction_ready", data: DEMO_LOW }),
  () => openSelector(),
  () => dispatch({ type: "confirmed", transaction_id: 1042, data: DEMO_TXN }),
];
let demoIdx = 0;
function startDemo() {
  showToast("演示模式：点击/空格切换状态，自动轮播中");
  setTimeout(() => (els.connToast.hidden = true), 100); // 不长期遮挡
  els.connToast.hidden = false;
  els.connToast.textContent = "演示模式 · 点击或空格切换";
  demoIdx = 0; DEMO_STEPS[0]();
  const advance = () => { demoIdx = (demoIdx + 1) % DEMO_STEPS.length; DEMO_STEPS[demoIdx](); };
  document.addEventListener("click", (e) => { if (!e.target.closest("[data-action], .cand, .cell, .cat")) advance(); });
  document.addEventListener("keydown", (e) => { if (e.code === "Space") { e.preventDefault(); advance(); } });
  setInterval(advance, 3000);
}
function demoHandleSend(obj) {
  if (obj.type === "select") {
    const p = DEMO_PRODUCTS.find((x) => x.label === obj.label) || DEMO_PRODUCTS[0];
    const d = { ...DEMO_LOW, label: p.label, name_cn: p.name_cn,
      price_per_kg: p.price_per_kg, total_price: +(p.price_per_kg * DEMO_LOW.weight_kg).toFixed(2),
      low_confidence: false };
    dispatch({ type: "transaction_ready", data: d });
  } else if (obj.type === "confirm") {
    dispatch({ type: "confirmed", transaction_id: 1042, data: DEMO_TXN });
  } else if (obj.type === "clear") {
    dispatch({ type: "cleared" });
  }
}

init();
