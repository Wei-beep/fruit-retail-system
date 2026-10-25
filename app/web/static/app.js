"use strict";

/* ========================================================================
 * 果蔬自助称重 — kiosk 前端
 * WS 事件驱动状态机：idle / recognizing / review / lowconf / selector / payment
 * ===================================================================== */

const DEMO = new URLSearchParams(location.search).has("demo");

/* ========================================================================
 * i18n — 中/EN 文案表 + 热切换
 * 静态文本走 HTML 的 data-i18n / data-i18n-ph / data-i18n-alt / data-i18n-aria；
 * 动态渲染（待确认/低置信/支付/选择器）由各 render 函数读 t()，切换时重渲染。
 * 商品名中文取后端 name_cn/zh_name；英文由稳定 label 转为可读名称。
 * ===================================================================== */
const I18N = {
  zh: {
    title: "果蔬自助称重",
    step_place: "放置", step_recognize: "识别", step_confirm: "确认",
    exit_aria: "退出",
    video_alt: "实时画面",
    camera_hint: "请将商品放在框内",
    camera_hint_demo: "演示模式 · 实时画面占位",
    idle_lead: "请将商品放到秤上",
    idle_sub: "放好后将自动识别",
    idle_weighing_sub: "请保持稳定，正在读数…",
    recognizing_lead: "正在识别…",
    conf_prefix: "置信度 ", conf_init: "置信度 —",
    count_prefix: "数量 ", count_init: "数量 —",
    label_weight: "重量", label_unit: "单价", label_total: "总价",
    btn_confirm: "确认", btn_cancel: "取消",
    link_redo: "识别不对？手动选择 ›",
    low_warn: "⚠ 识别可能不准，请确认品类",
    mixed_warn: "检测到多种商品，请拿走别的，只保留一种",
    mixed_detected: "检测到：",
    low_maybe: "可能是：",
    low_browse_all: "查看全部品类",
    selector_title: "选择商品品类",
    search_ph: "搜索名称…",
    btn_back: "返回",
    grid_empty: "没有匹配的商品",
    cat_all: "全部", cat_other: "其他",
    pay_scan: "扫码支付",
    pay_sub: "请使用微信或支付宝扫码完成支付",
    pay_qr_alt: "支付二维码",
    receipt_title: "订单确认",
    order_no: "单号",
    btn_finish: "完成",
    item_fallback: "商品",
    exit_title: "确定要退出吗？",
    exit_sub: "退出后将结束当前自助称重程序",
    exiting: "正在退出…",
    btn_no: "否", btn_yes_exit: "是，退出",
    conn_lost: "连接已断开，重连中…",
    error_prefix: "识别异常：",
    demo_hint: "演示模式 · 点击或空格切换",
    demo_start: "演示模式：点击/空格切换状态，自动轮播中",
    demo_exit_disabled: "演示模式：退出已禁用",
  },
  en: {
    title: "Self-Checkout Scale",
    step_place: "Place", step_recognize: "Identify", step_confirm: "Confirm",
    exit_aria: "Exit",
    video_alt: "Live view",
    camera_hint: "Place the item inside the box",
    camera_hint_demo: "Demo mode · live view placeholder",
    idle_lead: "Place item on the scale",
    idle_sub: "It will be recognized automatically",
    idle_weighing_sub: "Hold steady, reading…",
    recognizing_lead: "Recognizing…",
    conf_prefix: "Confidence ", conf_init: "Confidence —",
    count_prefix: "Count ", count_init: "Count —",
    label_weight: "Weight", label_unit: "Unit price", label_total: "Total",
    btn_confirm: "Confirm", btn_cancel: "Cancel",
    link_redo: "Wrong? Choose manually ›",
    low_warn: "⚠ Recognition may be off — please confirm the item",
    mixed_warn: "Multiple item types detected. Remove the others and keep one type only.",
    mixed_detected: "Detected:",
    low_maybe: "Could be:",
    low_browse_all: "Browse all items",
    selector_title: "Select an item",
    search_ph: "Search name…",
    btn_back: "Back",
    grid_empty: "No matching items",
    cat_all: "All", cat_other: "Other",
    pay_scan: "Scan to pay",
    pay_sub: "Scan with WeChat or Alipay to complete payment",
    pay_qr_alt: "Payment QR code",
    receipt_title: "Order summary",
    order_no: "Order",
    btn_finish: "Done",
    item_fallback: "Item",
    exit_title: "Exit the app?",
    exit_sub: "This will close the self-checkout program",
    exiting: "Exiting…",
    btn_no: "No", btn_yes_exit: "Yes, exit",
    conn_lost: "Disconnected — reconnecting…",
    error_prefix: "Recognition error: ",
    demo_hint: "Demo mode · tap or space to switch",
    demo_start: "Demo: tap/space to switch states, auto-cycling",
    demo_exit_disabled: "Demo mode: exit disabled",
  },
};
let lang = "zh";
function t(key) {
  const table = I18N[lang] || I18N.zh;
  return key in table ? table[key] : (I18N.zh[key] ?? key);
}

/* 套用所有静态文案：文本 / 输入占位 / 图片 alt / aria-label */
function applyStaticI18n() {
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    el.textContent = t(el.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-ph]").forEach((el) => {
    el.placeholder = t(el.dataset.i18nPh);
  });
  document.querySelectorAll("[data-i18n-alt]").forEach((el) => {
    el.alt = t(el.dataset.i18nAlt);
  });
  document.querySelectorAll("[data-i18n-aria]").forEach((el) => {
    el.setAttribute("aria-label", t(el.dataset.i18nAria));
  });
}
function applyDemoHint() { if (DEMO) els.cameraHint.textContent = t("camera_hint_demo"); }

/* 切换语言：更新开关高亮 + 全站重渲染（含动态面板） */
function setLang(next) {
  if (next !== "zh" && next !== "en") return;
  lang = next;
  document.querySelectorAll(".lang-opt").forEach((b) =>
    b.classList.toggle("active", b.dataset.lang === next));
  relocalize();
}
function relocalize() {
  applyStaticI18n();
  document.title = t("title");
  document.documentElement.lang = lang === "zh" ? "zh-CN" : "en";
  // 重渲染当前已有数据的动态面板（静态套用会把它们覆盖成初始占位）
  if (last.review) renderReview(last.review);
  if (last.low) renderLowConf(last.low);
  if (last.pay) renderPayment(last.pay, last.payOrder);
  if (products.length) { buildCats(); renderGrid(); }
  applyDemoHint();
}

const stage = document.getElementById("stage");
const els = {
  video: document.getElementById("video"),
  cameraHint: document.getElementById("cameraHint"),
  idleWeight: document.getElementById("idleWeight"),
  recogWeight: document.getElementById("recogWeight"),
  lowWeight: document.getElementById("lowWeight"),
  reviewName: document.getElementById("reviewName"),
  reviewCount: document.getElementById("reviewCount"),
  reviewConf: document.getElementById("reviewConf"),
  reviewWeight: document.getElementById("reviewWeight"),
  reviewUnit: document.getElementById("reviewUnit"),
  reviewTotal: document.getElementById("reviewTotal"),
  candidates: document.getElementById("candidates"),
  lowBrowseAll: document.getElementById("lowBrowseAll"),
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
// 分类用稳定 key（英文前缀派生），与显示名解耦，便于语言热切换时保持选中态
const CAT_ALL = "__all__";
const CAT_OTHER = "__other__";
let activeCat = CAT_ALL;
// 各动态面板最近一次数据，供语言切换后重渲染
let last = { review: null, low: null, pay: null, payOrder: null };

/* ---------------- 状态机 / 进度条 ---------------- */
function setState(name) {
  stage.dataset.state = name;
  // 回到空闲时复位触发标志，先显示「请放置」引导，待新一轮称重触发后再显示克重
  if (name === "idle") stage.dataset.triggered = "0";
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
const ZH_NAME_OVERRIDES = {
  onion_purple: "红地里蛇果",
  avocado_hass: "紫李子",
  pepper_sweet_red: "红地里蛇果",
  pomegranate: "圆油桃",
  tomato_pink: "红樱桃番茄",
};
const EN_NAME_OVERRIDES = {
  apple_fuji: "Fuji Apple",
  apple_golden: "Golden Apple",
  apple_granny: "Green Apple",
  apple_ligol: "Ligol Apple",
  apple_red_delicious: "Red Apple",
  apple_spartan: "Spartan Apple",
  apricot_armenian: "Armenian Apricot",
  apricot_jerdel: "Jerdel Apricot",
  avocado_hass: "Purple Plum",
  avocado_zutano: "Zutano Avocado",
  banana_mini: "Mini Banana",
  banana_yellow: "Banana",
  beet_round: "Beet",
  cabbage_broccoli: "Broccoli",
  cabbage_peking: "Napa Cabbage",
  cabbage_white: "Cabbage",
  cucumber_long: "Long Cucumber",
  cucumber_medium: "Cucumber",
  grape_black: "Black Grape",
  grape_green: "Green Grape",
  grape_pink: "Pink Grape",
  lemon_orange: "Orange Lemon",
  lemon_yellow: "Lemon",
  melon_torpeda: "Torpeda Melon",
  nectarine_flat: "Flat Nectarine",
  nectarine_round: "Nectarine",
  onion_purple: "Red Apple",
  onion_white: "White Onion",
  pear_conference: "Conference Pear",
  pear_williams_rouge: "Red Pear",
  pepper_chili: "Chili",
  pepper_sweet_elonged: "Sweet Pepper",
  pepper_sweet_green: "Green Pepper",
  pepper_sweet_red: "Red Apple",
  pepper_sweet_yellow: "Yellow Pepper",
  plum_pink: "Pink Plum",
  plum_purple: "Purple Plum",
  pomegranate: "Nectarine",
  potato_pink: "Pink Potato",
  potato_yellow: "Potato",
  pumpkin_elonged: "Pumpkin",
  raddish_elonged: "Radish",
  raddish_round: "Round Radish",
  salad_green: "Green Salad",
  tomato_bull_heart: "Beef Tomato",
  tomato_cherry_red: "Cherry Tomato",
  tomato_cherry_yellow: "Yellow Cherry Tomato",
  tomato_cherry_yellow_packaged: "Packed Cherry Tomato",
  tomato_pink: "Cherry Tomato",
  tomato_slivka: "Plum Tomato",
  tomato_yellow: "Yellow Tomato",
  watermelon_elonged: "Watermelon",
  zucchini_green: "Green Zucchini",
  zucchini_white: "White Zucchini",
};
function humanizeLabel(label) {
  if (!label) return "";
  return String(label)
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
function itemName(item, fallback = t("item_fallback")) {
  if (!item) return fallback;
  if (lang === "en") return EN_NAME_OVERRIDES[item.label] || item.name_en || humanizeLabel(item.label) || item.name_cn || item.zh_name || fallback;
  return ZH_NAME_OVERRIDES[item.label] || item.name_cn || item.zh_name || humanizeLabel(item.label) || fallback;
}

function renderReview(d) {
  els.reviewName.textContent = itemName(d, "—");
  els.reviewCount.textContent = t("count_prefix") + (d.count ?? 0);
  els.reviewConf.textContent = t("conf_prefix") + fmtConf(d.confidence);
  els.reviewWeight.textContent = (d.weight_kg ?? 0).toFixed(3);
  els.reviewUnit.textContent = d.price_per_kg != null ? d.price_per_kg.toFixed(2) : "—";
  els.reviewTotal.textContent = d.total_price != null ? d.total_price.toFixed(2) : "—";
}

function renderLowConf(d) {
  els.lowWeight.textContent = Math.round((d.weight_kg ?? 0) * 1000);
  els.candidates.innerHTML = "";
  const banner = document.querySelector(".warn-banner");
  const title = document.querySelector(".candidates-title");
  const mixed = !!d.mixed_detected;
  if (banner) banner.textContent = mixed ? t("mixed_warn") : t("low_warn");
  if (title) title.textContent = mixed ? t("mixed_detected") : t("low_maybe");
  if (els.lowBrowseAll) els.lowBrowseAll.style.display = mixed ? "none" : "";
  const list = mixed ? (d.detected_labels || []) : (d.candidates || []);
  list.forEach((c) => {
    if (mixed) {
      const item = document.createElement("div");
      item.className = "cand cand-static";
      item.innerHTML =
        `<span class="cand-name">${itemName(c)}</span><span class="cand-conf">×${c.count ?? 1}</span>`;
      els.candidates.appendChild(item);
      return;
    }
    const btn = document.createElement("button");
    btn.className = "cand";
    btn.innerHTML =
      `<span class="cand-name">${itemName(c)}</span><span class="cand-conf">${fmtConf(c.confidence)}</span>`;
    btn.addEventListener("click", () => send({ type: "select", label: c.label }));
    els.candidates.appendChild(btn);
  });
}

function renderPayment(d, orderId) {
  els.payName.textContent = itemName(d);
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

function catKeyOf(p) { return (p.label || "").split("_")[0] || CAT_OTHER; }
function catLabel(key) {
  if (key === CAT_ALL) return t("cat_all");
  if (key === CAT_OTHER) return t("cat_other");
  return key;  // 真实分类（英文前缀，语言无关）
}

function buildCats() {
  const keys = Array.from(new Set(products.map(catKeyOf))).sort();
  const tabs = [CAT_ALL, ...keys];
  if (!tabs.includes(activeCat)) activeCat = CAT_ALL;  // 语言切换重建时保持选中态
  els.cats.innerHTML = "";
  tabs.forEach((k) => {
    const div = document.createElement("div");
    div.className = "cat" + (k === activeCat ? " active" : "");
    div.dataset.cat = k;
    div.textContent = catLabel(k);
    div.addEventListener("click", () => {
      activeCat = k;
      els.cats.querySelectorAll(".cat").forEach((c) =>
        c.classList.toggle("active", c.dataset.cat === k));
      renderGrid();
    });
    els.cats.appendChild(div);
  });
}

function renderGrid() {
  const q = (els.search.value || "").trim().toLowerCase();
  const list = products.filter((p) => {
    const catOk = activeCat === CAT_ALL || catKeyOf(p) === activeCat;
    const display = itemName(p, "").toLowerCase();
    const qOk = !q || display.includes(q) || (p.name_cn || "").toLowerCase().includes(q) ||
      (p.label || "").toLowerCase().includes(q);
    return catOk && qOk;
  });
  els.grid.innerHTML = "";
  if (list.length === 0) {
    els.grid.innerHTML = `<div class="grid-empty">${t("grid_empty")}</div>`;
    return;
  }
  list.forEach((p) => {
    const cell = document.createElement("div");
    cell.className = "cell";
    cell.innerHTML =
      `<div class="cell-name">${itemName(p, p.label)}</div>` +
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
      const triggered = !!msg.triggered;
      // 触发后才在空闲面板显示实时克重；未触发则停留在「请放置」引导
      stage.dataset.triggered = triggered ? "1" : "0";
      if (triggered) els.idleWeight.textContent = g;
      els.recogWeight.textContent = g;
      break;
    }
    case "recognizing": setState("recognizing"); break;
    case "transaction_ready":
      if (msg.data && msg.data.low_confidence) {
        last.low = msg.data; last.review = null;
        renderLowConf(msg.data); setState("lowconf");
      } else {
        last.review = msg.data; last.low = null;
        renderReview(msg.data); setState("review");
      }
      break;
    case "confirmed":
      last.pay = msg.data || {}; last.payOrder = msg.transaction_id;
      renderPayment(last.pay, last.payOrder); setState("payment");
      break;
    case "cleared": last.review = last.low = last.pay = null; setState("idle"); break;
    case "error": showToast(t("error_prefix") + (msg.text || "")); break;
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
    els.connToast.textContent = t("conn_lost");
  }, 3000);
}

/* ---------------- MJPEG 视频流（断流自恢复） ---------------- */
function bindVideo() {
  if (DEMO) {
    els.video.style.display = "none";
    applyDemoHint();
    return;
  }
  els.video.onerror = () => {
    setTimeout(() => { els.video.src = "/stream/video?t=" + Date.now(); }, 1500);
  };
  els.video.src = "/stream/video";
}

/* ---------------- 按钮（事件委托） ---------------- */
stage.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-action]");
  if (!btn) return;
  const action = btn.dataset.action;
  if (action === "lang") setLang(btn.dataset.lang);
  else if (action === "confirm") send({ type: "confirm" });
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
  if (DEMO) { els.exitModal.hidden = true; showToast(t("demo_exit_disabled")); return; }
  const title = els.exitModal.querySelector(".modal-title");
  if (title) title.textContent = t("exiting");
  fetch("/api/exit", { method: "POST" }).catch(() => {});
}
els.search.addEventListener("input", renderGrid);

/* ---------------- 触摸拖动滚动（左侧分类 / 右侧网格） ----------------
 * 触摸 kiosk 下原生惯性滚动常失效（触摸被当鼠标），改用 pointer 事件 1:1 拖动滚动，
 * 同时区分"轻点选择"与"滑动滚动"：滑动后吞掉误触发的 click，避免顺手选中分类/商品。 */
function enableDragScroll(el) {
  if (!el) return;
  let active = false, startY = 0, startTop = 0, moved = false;
  el.addEventListener("pointerdown", (e) => {
    active = true; moved = false; startY = e.clientY; startTop = el.scrollTop;
  });
  el.addEventListener("pointermove", (e) => {
    if (!active) return;
    const dy = e.clientY - startY;
    if (!moved && Math.abs(dy) > 6) {
      moved = true;
      try { el.setPointerCapture(e.pointerId); } catch (_) {}
    }
    if (moved) { el.scrollTop = startTop - dy; e.preventDefault(); }
  });
  const stop = () => { active = false; };
  el.addEventListener("pointerup", stop);
  el.addEventListener("pointercancel", stop);
  el.addEventListener("pointerleave", stop);
  el.addEventListener("click", (e) => {
    if (moved) { e.preventDefault(); e.stopPropagation(); moved = false; }
  }, true);
}

/* ---------------- 启动 ---------------- */
function init() {
  document.getElementById("languageModal")?.remove();
  applyStaticI18n();              // 默认 zh，与 HTML 一致；统一从文案表取，便于将来改默认语言
  document.title = t("title");
  bindVideo();
  enableDragScroll(els.cats);
  enableDragScroll(els.grid);
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
  count: 3, weight_kg: 0.326, price_per_kg: 12.8, total_price: 4.17,
  low_confidence: false, candidates: [],
};
const DEMO_LOW = {
  label: "unknown", name_cn: null, confidence: 0.41,
  count: 1, weight_kg: 0.258, price_per_kg: null, total_price: null, low_confidence: true,
  candidates: [
    { label: "apple_fuji", zh_name: "红富士苹果", confidence: 0.41 },
    { label: "apple_granny", zh_name: "青苹果", confidence: 0.33 },
    { label: "beet_round", zh_name: "红甜菜根", confidence: 0.18 },
  ],
};
const DEMO_MIXED = {
  label: "apple_fuji", name_cn: "红富士苹果", confidence: 0.88,
  count: 2, weight_kg: 0.412, price_per_kg: null, total_price: null,
  low_confidence: true, mixed_detected: true,
  detected_labels: [
    { label: "apple_fuji", zh_name: "红富士苹果", confidence: 0.88, count: 2 },
    { label: "banana_yellow", zh_name: "黄香蕉", confidence: 0.76, count: 1 },
  ],
  candidates: [],
};
const DEMO_STEPS = [
  () => dispatch({ type: "cleared" }) || dispatch({ type: "weight", weight_g: 8, stable: false, triggered: false }),
  () => dispatch({ type: "weight", weight_g: 326, stable: false, triggered: true }),
  () => dispatch({ type: "recognizing" }),
  () => dispatch({ type: "transaction_ready", data: DEMO_TXN }),
  () => dispatch({ type: "transaction_ready", data: DEMO_MIXED }),
  () => dispatch({ type: "transaction_ready", data: DEMO_LOW }),
  () => openSelector(),
  () => dispatch({ type: "confirmed", transaction_id: 1042, data: DEMO_TXN }),
];
let demoIdx = 0;
function startDemo() {
  showToast(t("demo_start"));
  setTimeout(() => (els.connToast.hidden = true), 100); // 不长期遮挡
  els.connToast.hidden = false;
  els.connToast.textContent = t("demo_hint");
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
