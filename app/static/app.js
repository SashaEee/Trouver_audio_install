const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
let DID = null, MODEL = null, EVENTS = [], ACTIVE = null, STORED = null, FILTER = "all", CATS = {};
let NOW = null;
const au = $("#au");

async function api(path, opts = {}) {
  const r = await fetch(path, { credentials: "same-origin", headers: { "Content-Type": "application/json" }, ...opts });
  let body = null; try { body = await r.json(); } catch (e) {}
  if (!r.ok) throw new Error((body && body.error) || ("HTTP " + r.status));
  return body;
}
function toast(msg) { const t = $("#toast"); t.textContent = msg; t.classList.add("show"); clearTimeout(t._t); t._t = setTimeout(() => t.classList.remove("show"), 2600); }
function fmt(s) { s = Math.max(0, Math.round(s || 0)); return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0"); }

/* ---- segmented selectors on login ---- */
function seg(id) {
  const root = $("#" + id);
  root.addEventListener("click", e => { const b = e.target.closest("button"); if (!b) return; $$("button", root).forEach(x => x.classList.remove("on")); b.classList.add("on"); });
  return () => $(".on", root).dataset.v;
}
const getBrand = seg("brand"), getRegion = seg("region");

/* ---- waveform (deterministic) ---- */
const _bars = {};
function bars(seed) {
  if (_bars[seed]) return _bars[seed];
  let s = 0; for (const c of String(seed)) s = (s * 31 + c.charCodeAt(0)) >>> 0;
  const rng = () => { s |= 0; s = (s + 0x6D2B79F5) | 0; let t = Math.imul(s ^ (s >>> 15), 1 | s); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  const n = 34, a = []; for (let i = 0; i < n; i++) a.push(0.18 + 0.82 * Math.pow(rng(), 0.6));
  return (_bars[seed] = a);
}
function wave(el, seed, played = 0) {
  const W = el.clientWidth || 100, H = el.clientHeight || 28, a = bars(seed), n = a.length, step = W / n;
  let svg = `<svg width="${W}" height="${H}" style="display:block" aria-hidden="true">`;
  for (let i = 0; i < n; i++) {
    const h = Math.round(a[i] * H), y = Math.round((H - h) / 2), x = Math.round(i * step), bw = Math.max(1.5, step - 1.6);
    const on = (i / n) < played;
    svg += `<rect x="${x}" y="${y}" width="${bw.toFixed(1)}" height="${h}" rx="1" fill="${on ? "#D85A30" : "#C8C6BC"}"/>`;
  }
  if (played > 0) svg += `<rect x="${Math.round(played * W)}" y="0" width="1.5" height="${H}" fill="#8E3417"/>`;
  el.innerHTML = svg + "</svg>";
}

/* ---- login ---- */
$("#login-form").addEventListener("submit", async e => {
  e.preventDefault();
  const btn = $("#login-btn"), err = $("#login-err");
  err.textContent = ""; btn.disabled = true; btn.textContent = "Входим…";
  try {
    const d = await api("/api/login", { method: "POST", body: JSON.stringify({ brand: getBrand(), region: getRegion(), email: $("#email").value, password: $("#password").value }) });
    enter(d.devices);
  } catch (ex) { err.textContent = ex.message; }
  finally { btn.disabled = false; btn.textContent = "Войти"; }
});

$("#logout").addEventListener("click", async () => { await api("/api/logout", { method: "POST" }); location.reload(); });

/* ---- enter editor ---- */
async function enter(devices) {
  if (!devices || !devices.length) { $("#login-err").textContent = "В аккаунте нет устройств"; return; }
  const dev = devices[0]; DID = dev.did; MODEL = dev.model;
  $("#login").classList.add("hidden"); $("#editor").classList.remove("hidden");
  $("#dev-chip").innerHTML = `<span class="dot ${dev.online ? "" : "off"}"></span>${dev.name} · ${dev.online ? "в сети" : "офлайн"}`;
  await Promise.all([loadState(), loadLibrary(), loadEvents()]);
}

async function loadState() {
  try {
    const s = await api(`/api/state?did=${encodeURIComponent(DID)}`);
    $("#vol").value = s.volume ?? 80; $("#vol-out").textContent = s.volume ?? 80;
    ACTIVE = s.active;
    try { STORED = JSON.parse(s.status).id; } catch (e) { STORED = null; }  // last custom pack on the robot
  } catch (e) {}
}

/* ---- volume ---- */
let volT; $("#vol").addEventListener("input", e => {
  $("#vol-out").textContent = e.target.value; clearTimeout(volT);
  volT = setTimeout(() => api("/api/volume", { method: "POST", body: JSON.stringify({ did: DID, level: +e.target.value }) }).then(() => toast("Громкость " + e.target.value)).catch(ex => toast(ex.message)), 450);
});

/* ---- library ---- */
async function loadLibrary() {
  const { packs } = await api("/api/library");
  $("#lib").innerHTML = packs.map(p => {
    const isActive = ACTIVE === p.id;
    // factory packs and the pack already in the robot's slot switch instantly; others must download
    const onRobot = p.kind === "official" || p.id === STORED || isActive;
    let actions;
    if (isActive) actions = `<button class="btn-ghost" disabled><i class="ti ti-check" aria-hidden="true"></i> Активна</button>`;
    else if (onRobot) actions = `<button class="btn-ghost" data-act="activate">Включить</button>`;
    else actions = `<button class="btn-ghost" data-act="install">Установить</button>`;
    const listen = `<button class="btn-ghost listen" data-act="audition" title="Прослушать примеры"><i class="ti ti-headphones" aria-hidden="true"></i> Послушать</button>`;
    return `
    <div class="pack ${isActive ? "active" : ""}" data-id="${p.id}">
      <div style="display:flex;align-items:center;justify-content:space-between;gap:8px">
        <span class="pn">${p.name}</span>
        <span class="tag ${p.kind === "official" ? "official" : p.kind === "custom" ? "custom" : ""}">${p.tag}</span>
      </div>
      <span class="pm">${p.coverage} фраз${isActive ? " · активна" : ""}</span>
      <div class="pa">${listen}${actions}</div>
    </div>`;
  }).join("");
}

$("#lib").addEventListener("click", async e => {
  const btn = e.target.closest("button"); if (!btn) return;
  const card = e.target.closest(".pack"), id = card.dataset.id, act = btn.dataset.act;
  if (act === "audition") { auditionPack(id, card.querySelector(".pn").textContent); return; }
  if (act === "activate") {
    btn.textContent = "…"; try { await api("/api/activate", { method: "POST", body: JSON.stringify({ did: DID, id }) }); toast("Включён: " + id); await loadState(); await loadLibrary(); await loadEvents(); } catch (ex) { toast(ex.message); btn.textContent = "Включить"; }
    return;
  }
  // install with honest progress
  const mark = card.querySelector(".pm"), label = btn.textContent;
  btn.disabled = true;
  try {
    await api("/api/install", { method: "POST", body: JSON.stringify({ did: DID, id }) });
    const done = await pollInstall(id, m => mark.textContent = m);
    if (done) { toast("Установлено и включено"); await loadState(); await loadLibrary(); await loadEvents(); }
    else { mark.textContent = "не долетело"; toast("Доставка не прошла, попробуйте ещё"); }
  } catch (ex) { toast(ex.message); }
  finally { btn.disabled = false; btn.textContent = label; }
});

// poll robot install status; calls onMark with a human string, retries on a dropped transfer
async function pollInstall(id, onMark) {
  let tries = 0;
  while (tries++ < 24) {
    await new Promise(r => setTimeout(r, 2500));
    let s; try { s = await api(`/api/state?did=${encodeURIComponent(DID)}`); } catch (e) { continue; }
    let st = {}; try { st = JSON.parse(s.status); } catch (e) {}
    if (st.id === id || st.state) onMark(`доставка ${st.progress || 0}%`);
    if (st.state === "success") return true;
    if (st.state === "fail") { onMark("обрыв — повторяю…"); try { await api("/api/install", { method: "POST", body: JSON.stringify({ did: DID, id }) }); } catch (e) {} }
  }
  return false;
}

// build the user's pack (RU base + their lines), host it, install + activate
async function buildInstall() {
  const btn = $("#build-btn"), lbl = $("#build-lbl"), orig = lbl.textContent;
  btn.disabled = true; lbl.textContent = "Собираю…";
  try {
    await api("/api/build_install", { method: "POST", body: JSON.stringify({ did: DID }) });
    lbl.textContent = "Доставка…";
    const done = await pollInstall("MY", m => lbl.textContent = m);
    if (done) {
      try { await api("/api/activate", { method: "POST", body: JSON.stringify({ did: DID, id: "MY" }) }); } catch (e) {}
      toast("Моя озвучка установлена и включена");
    } else { toast("Доставка не прошла — попробуйте ещё раз"); }
  } catch (ex) { toast(ex.message); }
  finally { btn.disabled = false; lbl.textContent = orig; await loadState(); await loadLibrary(); await loadEvents(); }
}
$("#build-btn").addEventListener("click", buildInstall);

function updateBuildBtn() {
  const n = EVENTS.filter(e => e.source === "custom").length;
  const btn = $("#build-btn");
  if (n > 0) { btn.style.display = ""; $("#build-lbl").textContent = `Собрать и установить · ${n}`; }
  else btn.style.display = "none";
}

/* ---- events ---- */
async function loadEvents() {
  const d = await api(`/api/events?did=${encodeURIComponent(DID)}`);
  EVENTS = d.events; CATS = d.categories; ACTIVE = d.active;
  const total = EVENTS.length, voiced = EVENTS.filter(e => e.source !== "stock").length;
  $("#cov-num").textContent = voiced; $("#cov-sub").textContent = `из ${total} озвучено`;
  const pack = EVENTS.filter(e => e.source === "pack").length, cust = EVENTS.filter(e => e.source === "custom").length, stock = total - pack - cust;
  $("#bar").innerHTML = `<i class="b-pack" style="width:${pack / total * 100}%"></i><i class="b-custom" style="width:${cust / total * 100}%"></i><i class="b-stock" style="width:${stock / total * 100}%"></i>`;
  const order = ["all", ...Object.keys(CATS), "stock"];
  const names = { all: "Все", ...CATS, stock: "Не озвучено" };
  $("#filters").innerHTML = order.map(k => `<button class="chip ${FILTER === k ? "on" : ""}" data-f="${k}">${names[k]}</button>`).join("");
  renderList();
  updateBuildBtn();
}

function renderList() {
  const list = $("#list");
  let items = EVENTS;
  if (FILTER === "stock") items = EVENTS.filter(e => e.source === "stock");
  else if (FILTER !== "all") items = EVENTS.filter(e => e.category === FILTER);
  const groups = {};
  items.forEach(e => (groups[e.category] = groups[e.category] || []).push(e));
  let html = "";
  for (const cat of Object.keys(CATS)) {
    if (!groups[cat]) continue;
    html += `<div class="group-h">${CATS[cat]}</div>`;
    for (const e of groups[cat]) {
      const srcLabel = { pack: ACTIVE === "MX" ? "Максим" : "Пакет", custom: "Твоя", stock: "Штатная" }[e.source];
      let phr = esc(e.phrase);
      if (e.source === "custom" && e.custom) {
        const kindIco = e.custom.kind === "tts" ? "текст" : "запись";
        phr = `<span class="cust-kind">${kindIco}</span> ${esc(e.custom.label || "ваша версия")}`;
      }
      html += `<div class="row ${e.source}" data-id="${e.id}">
        <div class="meaning"><div class="ttl">${e.title}</div><div class="phr">${phr}</div></div>
        <div class="wf" data-seed="${e.id}"></div>
        <div class="dur">·</div>
        <div class="src ${e.source}">${srcLabel}</div>
        <div class="acts"><button class="pbtn play" aria-label="Воспроизвести"><i class="ti ti-player-play" aria-hidden="true"></i></button><button class="pbtn rep" aria-label="Заменить"><i class="ti ti-${e.source === "stock" ? "plus" : "dots"}" aria-hidden="true"></i></button></div>
      </div>`;
    }
  }
  list.innerHTML = html || `<p style="color:var(--muted);padding:20px 4px">Здесь пусто.</p>`;
  $$(".wf", list).forEach(el => wave(el, el.dataset.seed, 0));
}
function esc(s) { return (s || "").replace(/[<>&]/g, c => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;" }[c])); }

$("#filters").addEventListener("click", e => { const b = e.target.closest("button"); if (!b) return; FILTER = b.dataset.f; renderList(); $$(".chip").forEach(c => c.classList.toggle("on", c.dataset.f === FILTER)); });

/* ---- playback ---- */
$("#list").addEventListener("click", e => {
  const row = e.target.closest(".row"); if (!row) return;
  if (e.target.closest(".play")) play(row.dataset.id);
  else if (e.target.closest(".rep")) openSheet(row.dataset.id);
});
function srcOf(id) { const e = EVENTS.find(x => x.id === id); return e ? e.source : "stock"; }
let MONTAGE = null, PLSEED = null;
function play(id) {
  const e = EVENTS.find(x => x.id === id); if (!e) return;
  if (NOW === id && !au.paused) { au.pause(); return; }
  MONTAGE = null; $("#player").classList.remove("montage");
  NOW = id; PLSEED = id;
  au.src = `/api/audio/${e.source}/${id}`;
  au.play().catch(() => toast("Нет превью для этой фразы"));
  $("#player").style.display = "flex";
  $("#pl-ttl").textContent = `${e.title} · «${e.phrase.slice(0, 48)}»`;
  setPlayIcons();
}

/* audition a whole pack: play its signature lines back-to-back, no install */
async function auditionPack(pid, name) {
  let d; try { d = await api(`/api/preview/${pid}`); } catch (ex) { toast(ex.message); return; }
  if (!d.items || !d.items.length) { toast("Нет примеров для этого пакета"); return; }
  MONTAGE = { pid, name, items: d.items, i: 0 };
  NOW = null;
  $("#player").classList.add("montage"); $("#player").style.display = "flex";
  playMontage();
}
function playMontage() {
  if (!MONTAGE) return;
  const it = MONTAGE.items[MONTAGE.i];
  PLSEED = "m" + MONTAGE.pid + it.eid;
  au.src = `/api/packaudio/${MONTAGE.pid}/${it.eid}`;
  au.play().catch(() => nextMontage());
  $("#pl-ttl").textContent = `${MONTAGE.name} · ${it.title} · ${MONTAGE.i + 1}/${MONTAGE.items.length}`;
  setPlayIcons();
}
function nextMontage() {
  if (!MONTAGE) return;
  MONTAGE.i++;
  if (MONTAGE.i < MONTAGE.items.length) playMontage();
  else { MONTAGE = null; $("#player").classList.remove("montage"); setPlayIcons(); }
}

au.addEventListener("timeupdate", () => {
  const p = au.duration ? au.currentTime / au.duration : 0;
  if (NOW) { const row = $(`.row[data-id="${NOW}"]`); if (row) { wave(row.querySelector(".wf"), NOW, p); row.querySelector(".dur").textContent = fmt(au.duration); } }
  wave($("#pl-wf"), PLSEED, p);
  $("#pl-time").textContent = `${fmt(au.currentTime)} / ${fmt(au.duration)}`;
});
au.addEventListener("ended", () => {
  if (MONTAGE) { nextMontage(); return; }
  setPlayIcons(); const row = $(`.row[data-id="${NOW}"]`); if (row) wave(row.querySelector(".wf"), NOW, 0);
});
au.addEventListener("pause", setPlayIcons); au.addEventListener("play", setPlayIcons);
function setPlayIcons() {
  $$(".row").forEach(r => { const b = r.querySelector(".play"); const on = r.dataset.id === NOW && !au.paused; r.classList.toggle("playing", on); b.classList.toggle("act", on); b.innerHTML = `<i class="ti ti-player-${on ? "pause" : "play"}" aria-hidden="true"></i>`; });
  $("#pp").innerHTML = `<i class="ti ti-player-${au.paused ? "play" : "pause"}" aria-hidden="true"></i>`;
}
$("#pp").addEventListener("click", () => { if (au.paused) au.play(); else au.pause(); });
$("#pl-replace").addEventListener("click", () => { if (NOW) openSheet(NOW); });

/* ====================== editor sheet (custom audio) ====================== */
let SHEET_EID = null, pvSeed = null;
const pv = $("#pv");

function openSheet(id) {
  const e = EVENTS.find(x => x.id === id); if (!e) return;
  SHEET_EID = id;
  $("#sheet-ttl").textContent = e.title;
  setSheetCur(e);
  $("#tts-text").value = (e.source === "custom" && e.custom && e.custom.kind === "tts") ? (e.custom.label || "") : "";
  resetSheetTabs();
  $("#sheet-remove").classList.toggle("hidden", e.source !== "custom");
  if (e.source === "custom") setPreviewSrc(`/api/audio/custom/${id}?v=${Date.now()}`, "c" + id, "ваша версия");
  else setPreviewSrc(null);
  $("#sheet-bg").classList.add("show");
  const s = $("#sheet"); s.classList.add("show"); s.setAttribute("aria-hidden", "false");
}
function setSheetCur(e) {
  $("#sheet-cur").textContent = e.source === "custom"
    ? `сейчас: ваша версия${e.custom && e.custom.label ? ` — «${e.custom.label}»` : ""}`
    : `штатная фраза: «${(e.phrase || "").slice(0, 64)}»`;
}
function closeSheet() {
  stopPv(); recDiscard();
  $("#sheet-bg").classList.remove("show");
  const s = $("#sheet"); s.classList.remove("show"); s.setAttribute("aria-hidden", "true");
  SHEET_EID = null;
}
$("#sheet-x").addEventListener("click", closeSheet);
$("#sheet-done").addEventListener("click", closeSheet);
$("#sheet-bg").addEventListener("click", closeSheet);
document.addEventListener("keydown", e => { if (e.key === "Escape" && SHEET_EID) closeSheet(); });

/* tabs */
$("#sheet-tabs").addEventListener("click", e => {
  const b = e.target.closest(".tab"); if (!b) return;
  const t = b.dataset.t;
  $$(".tab", $("#sheet-tabs")).forEach(x => x.classList.toggle("on", x === b));
  ["text", "rec", "file"].forEach(p => $("#pane-" + p).classList.toggle("hidden", p !== t));
});
function resetSheetTabs() {
  $$(".tab", $("#sheet-tabs")).forEach((x, i) => x.classList.toggle("on", i === 0));
  ["text", "rec", "file"].forEach((p, i) => $("#pane-" + p).classList.toggle("hidden", i !== 0));
  recDiscard(); pendingFile = null;
  $("#file-go").disabled = true; $("#file-hint").textContent = "Из видео вырежем звук автоматически";
  $("#rec-use").disabled = true; $("#rec-state").textContent = "Нажмите, чтобы записать";
}

/* after any edit saved server-side: refresh list + show saved preview, keep sheet open */
async function afterEdit(msg) {
  const id = SHEET_EID;
  toast(msg || "Готово");
  await loadEvents();
  const e = EVENTS.find(x => x.id === id); if (e) setSheetCur(e);
  $("#sheet-remove").classList.remove("hidden");
  setPreviewSrc(`/api/audio/custom/${id}?v=${Date.now()}`, "c" + id, "ваша версия");
}
async function uploadForm(fd, okMsg) {
  const r = await fetch("/api/upload", { method: "POST", credentials: "same-origin", body: fd });
  let b = null; try { b = await r.json(); } catch (e) {}
  if (!r.ok) throw new Error((b && b.error) || ("HTTP " + r.status));
  await afterEdit(okMsg);
}

/* text → voice */
$("#tts-go").addEventListener("click", async () => {
  const text = $("#tts-text").value.trim(); if (!text) { toast("Введите текст"); return; }
  const btn = $("#tts-go"); btn.disabled = true; btn.textContent = "…";
  try { await api("/api/tts", { method: "POST", body: JSON.stringify({ did: DID, eid: SHEET_EID, text }) }); await afterEdit("Озвучено"); }
  catch (ex) { toast(ex.message); }
  finally { btn.disabled = false; btn.textContent = "Озвучить"; }
});

/* record from mic */
let mediaRec = null, recChunks = [], recBlob = null, recTimer = null, recT0 = 0;
$("#rec-btn").addEventListener("click", async () => {
  if (mediaRec && mediaRec.state === "recording") { mediaRec.stop(); return; }
  if (!navigator.mediaDevices || !window.MediaRecorder) { toast("Запись не поддерживается этим браузером"); return; }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    recChunks = []; recBlob = null; mediaRec = new MediaRecorder(stream);
    mediaRec.ondataavailable = ev => { if (ev.data && ev.data.size) recChunks.push(ev.data); };
    mediaRec.onstop = () => {
      stream.getTracks().forEach(t => t.stop());
      clearInterval(recTimer);
      const btn = $("#rec-btn"); btn.classList.remove("live"); btn.innerHTML = '<i class="ti ti-microphone" aria-hidden="true"></i>';
      if (!recChunks.length) { $("#rec-state").textContent = "Пусто — попробуйте ещё"; return; }
      recBlob = new Blob(recChunks, { type: mediaRec.mimeType || "audio/webm" });
      $("#rec-state").textContent = "Запись готова — прослушайте";
      $("#rec-use").disabled = false;
      setPreviewSrc(URL.createObjectURL(recBlob), "r" + SHEET_EID, "новая запись");
    };
    mediaRec.start(); recT0 = Date.now();
    const btn = $("#rec-btn"); btn.classList.add("live"); btn.innerHTML = '<i class="ti ti-player-stop-filled" aria-hidden="true"></i>';
    $("#rec-use").disabled = true;
    recTimer = setInterval(() => {
      const s = (Date.now() - recT0) / 1000;
      $("#rec-state").innerHTML = `Идёт запись · <span class="mono">${s.toFixed(1)} с</span>`;
      if (s >= 15) mediaRec.stop();
    }, 100);
  } catch (ex) { toast("Нет доступа к микрофону"); }
});
function recDiscard() {
  try { if (mediaRec && mediaRec.state === "recording") mediaRec.stop(); } catch (e) {}
  clearInterval(recTimer); recBlob = null; recChunks = [];
  const btn = $("#rec-btn"); if (btn) { btn.classList.remove("live"); btn.innerHTML = '<i class="ti ti-microphone" aria-hidden="true"></i>'; }
}
$("#rec-use").addEventListener("click", async () => {
  if (!recBlob) return;
  const btn = $("#rec-use"); btn.disabled = true; btn.textContent = "…";
  try {
    const fd = new FormData(); fd.append("did", DID); fd.append("eid", SHEET_EID); fd.append("audio", recBlob, "recording.webm");
    await uploadForm(fd, "Запись сохранена");
  } catch (ex) { toast(ex.message); }
  finally { btn.disabled = false; btn.textContent = "Использовать"; }
});

/* upload file (audio or video) */
let pendingFile = null;
$("#drop").addEventListener("click", () => $("#file").click());
$("#file").addEventListener("change", e => {
  const f = e.target.files[0]; e.target.value = "";
  if (!f) return;
  pendingFile = f;
  $("#file-hint").textContent = f.name.length > 38 ? f.name.slice(0, 36) + "…" : f.name;
  $("#file-go").disabled = false;
  setPreviewSrc(URL.createObjectURL(f), "f" + SHEET_EID, "выбранный файл");
});
$("#file-go").addEventListener("click", async () => {
  if (!pendingFile) return;
  const btn = $("#file-go"); btn.disabled = true; btn.textContent = "…";
  try {
    const fd = new FormData(); fd.append("did", DID); fd.append("eid", SHEET_EID); fd.append("audio", pendingFile, pendingFile.name);
    await uploadForm(fd, "Файл загружен");
    pendingFile = null;
  } catch (ex) { toast(ex.message); }
  finally { btn.textContent = "Загрузить"; }
});

/* remove custom → back to stock */
$("#sheet-remove").addEventListener("click", async () => {
  const id = SHEET_EID;
  try {
    await api("/api/remove", { method: "POST", body: JSON.stringify({ did: DID, eid: id }) });
    toast("Возвращена штатная");
    await loadEvents();
    const e = EVENTS.find(x => x.id === id); if (e) setSheetCur(e);
    $("#sheet-remove").classList.add("hidden"); setPreviewSrc(null);
  } catch (ex) { toast(ex.message); }
});

/* sheet preview player */
function setPreviewSrc(src, seed, tag) {
  const box = $("#sheet-prev");
  stopPv();
  if (!src) { box.style.display = "none"; return; }
  box.style.display = "flex"; pvSeed = seed; $("#prev-tag").textContent = tag || "";
  pv.src = src; wave($("#prev-wf"), seed, 0);
  $("#prev-pp").innerHTML = '<i class="ti ti-player-play" aria-hidden="true"></i>';
}
function stopPv() { try { pv.pause(); pv.currentTime = 0; } catch (e) {} }
$("#prev-pp").addEventListener("click", () => { if (pv.paused) pv.play(); else pv.pause(); });
pv.addEventListener("timeupdate", () => { const p = pv.duration ? pv.currentTime / pv.duration : 0; wave($("#prev-wf"), pvSeed, p); });
pv.addEventListener("play", () => $("#prev-pp").innerHTML = '<i class="ti ti-player-pause" aria-hidden="true"></i>');
pv.addEventListener("pause", () => $("#prev-pp").innerHTML = '<i class="ti ti-player-play" aria-hidden="true"></i>');
pv.addEventListener("ended", () => { $("#prev-pp").innerHTML = '<i class="ti ti-player-play" aria-hidden="true"></i>'; wave($("#prev-wf"), pvSeed, 0); });

/* ---- resume session on reload ---- */
(async () => {
  try { const s = await api("/api/session"); enter(s.devices); } catch (e) {}
})();
window.addEventListener("resize", () => { $$(".wf").forEach(el => wave(el, el.dataset.seed, el.dataset.id === NOW ? (au.duration ? au.currentTime / au.duration : 0) : 0)); });

/* ====================== pack builder (bulk arrange) ====================== */
let CLIPS = [], ASSIGN = {}, SEL = null, BFILTER = "all", DRAG_CID = null;
const bpv = $("#pv");  // reuse the sheet preview element; builder is its own screen

$("#open-builder").addEventListener("click", openBuilder);
$("#b-back").addEventListener("click", closeBuilder);

async function openBuilder() {
  if (!EVENTS.length) await loadEvents();
  $("#editor").classList.add("hidden"); $("#builder").classList.remove("hidden");
  // seed assignments from existing custom edits so the screen reflects reality
  ASSIGN = {}; SEL = null;
  try { const d = await api("/api/clips"); CLIPS = d.clips || []; } catch (e) { CLIPS = []; }
  renderTray(); renderSlots(); updateBcov();
  window.scrollTo(0, 0);
}
function closeBuilder() {
  try { bpv.pause(); } catch (e) {}
  $("#builder").classList.add("hidden"); $("#editor").classList.remove("hidden");
  loadState(); loadLibrary(); loadEvents();
}

/* ---- upload clips ---- */
$("#b-upload").addEventListener("click", () => $("#b-files").click());
$("#b-files").addEventListener("change", async e => {
  const files = [...e.target.files]; e.target.value = "";
  if (!files.length) return;
  const fd = new FormData(); files.forEach(f => fd.append("files", f, f.name));
  $("#b-upload").disabled = true;
  try {
    const r = await fetch("/api/clips/upload", { method: "POST", credentials: "same-origin", body: fd });
    const b = await r.json(); if (!r.ok) throw new Error(b.error || "ошибка загрузки");
    CLIPS = CLIPS.concat(b.clips); renderTray();
    toast(`Загружено клипов: ${b.clips.length}`);
  } catch (ex) { toast(ex.message); }
  finally { $("#b-upload").disabled = false; }
});

$("#b-clear").addEventListener("click", async () => {
  if (!CLIPS.length) return;
  try { await api("/api/clips/clear", { method: "POST" }); } catch (e) {}
  CLIPS = []; ASSIGN = {}; SEL = null; renderTray(); renderSlots(); updateBcov();
});

/* ---- tray ---- */
function usedCount(cid) { return Object.values(ASSIGN).filter(x => x === cid).length; }
function renderTray() {
  const t = $("#b-tray"); $("#b-clips-n").textContent = CLIPS.length;
  if (!CLIPS.length) { t.innerHTML = `<div class="b-tray-empty">Пока пусто.<br>Нажмите «Загрузить клипы» — можно выбрать сразу много файлов.</div>`; return; }
  t.innerHTML = CLIPS.map(c => {
    const u = usedCount(c.id);
    return `<div class="clip ${SEL === c.id ? "sel" : ""}" draggable="true" data-cid="${c.id}">
      <button class="cpp" data-act="cplay" aria-label="Прослушать"><i class="ti ti-player-play" aria-hidden="true"></i></button>
      <div style="min-width:0"><div class="cn">${esc(c.name)}</div><div class="cmeta">${c.dur ? fmt(c.dur) : "клип"}</div></div>
      ${u ? `<span class="used">${u} ${u === 1 ? "слот" : "слота"}</span>` : `<i class="ti ti-grip-vertical" style="color:var(--faint)" aria-hidden="true"></i>`}
    </div>`;
  }).join("");
}
function clipName(cid) { const c = CLIPS.find(x => x.id === cid); return c ? c.name : "клип"; }

/* ---- slots ---- */
function renderSlots() {
  const list = $("#b-slot-list"), groups = {};
  EVENTS.forEach(e => (groups[e.category] = groups[e.category] || []).push(e));
  let html = "";
  for (const cat of Object.keys(CATS)) {
    const items = (groups[cat] || []).filter(e => {
      if (BFILTER === "empty") return !ASSIGN[e.id];
      if (BFILTER === "filled") return !!ASSIGN[e.id];
      return true;
    });
    if (!items.length) continue;
    html += `<div class="group-h">${CATS[cat]}</div>`;
    for (const e of items) {
      const cid = ASSIGN[e.id];
      const target = cid
        ? `<div class="s-chip"><button class="cpp act" data-act="splay" aria-label="Прослушать"><i class="ti ti-player-play" aria-hidden="true"></i></button><span class="cn">${esc(clipName(cid))}</span><button class="x" data-act="unassign" aria-label="Убрать">×</button></div>`
        : `<div class="s-empty"><i class="ti ti-plus" aria-hidden="true"></i> ${SEL ? "поставить сюда" : "перетащите клип"}</div>`;
      html += `<div class="slot ${SEL ? "armed" : ""}" data-eid="${e.id}">
        <div class="s-mean"><div class="s-ttl">${e.title}</div><div class="s-phr">${esc(e.phrase)}</div></div>
        <div class="s-target" data-cid="${cid || ""}">${target}</div>
      </div>`;
    }
  }
  list.innerHTML = html || `<p style="color:var(--muted);padding:18px 4px">Здесь пусто.</p>`;
}

/* ---- filters ---- */
$("#b-filter").addEventListener("click", e => {
  const b = e.target.closest("button"); if (!b) return;
  BFILTER = b.dataset.f; $$("#b-filter button").forEach(x => x.classList.toggle("on", x === b));
  renderSlots();
});

/* ---- assignment ---- */
function assign(eid, cid) { if (!cid) return; ASSIGN[eid] = cid; renderTray(); renderSlots(); updateBcov(); }
function unassign(eid) { delete ASSIGN[eid]; renderTray(); renderSlots(); updateBcov(); }
function selectClip(cid) { SEL = (SEL === cid) ? null : cid; renderTray(); renderSlots(); }
function updateBcov() {
  const n = Object.keys(ASSIGN).length, total = EVENTS.length;
  $("#b-cov").textContent = `${n} из ${total} фраз`;
  const btn = $("#b-build"); btn.disabled = n === 0;
  $("#b-build-lbl").textContent = n ? `Собрать и установить · ${n}` : "Собрать и установить";
  $("#b-hint").style.display = SEL ? "block" : (n ? "none" : "block");
  $("#b-hint").textContent = SEL ? "Теперь нажмите на фразу справа — клип встанет в неё." : "Выберите клип слева, затем нажмите на фразу — или перетащите.";
}

/* tray clicks: play or select */
$("#b-tray").addEventListener("click", e => {
  const card = e.target.closest(".clip"); if (!card) return;
  const cid = card.dataset.cid;
  if (e.target.closest('[data-act="cplay"]')) { bplay(cid); return; }
  selectClip(cid);
});
/* slot clicks: assign (if armed), play, unassign */
$("#b-slot-list").addEventListener("click", e => {
  const slot = e.target.closest(".slot"); if (!slot) return;
  const eid = slot.dataset.eid;
  if (e.target.closest('[data-act="unassign"]')) { unassign(eid); return; }
  if (e.target.closest('[data-act="splay"]')) { bplay(ASSIGN[eid]); return; }
  if (SEL) assign(eid, SEL);
});

/* drag & drop */
$("#b-tray").addEventListener("dragstart", e => { const c = e.target.closest(".clip"); if (!c) return; DRAG_CID = c.dataset.cid; c.classList.add("dragging"); });
$("#b-tray").addEventListener("dragend", e => { const c = e.target.closest(".clip"); if (c) c.classList.remove("dragging"); DRAG_CID = null; });
$("#b-slot-list").addEventListener("dragover", e => { const s = e.target.closest(".slot"); if (s && DRAG_CID) { e.preventDefault(); s.classList.add("dragover"); } });
$("#b-slot-list").addEventListener("dragleave", e => { const s = e.target.closest(".slot"); if (s) s.classList.remove("dragover"); });
$("#b-slot-list").addEventListener("drop", e => { const s = e.target.closest(".slot"); if (s && DRAG_CID) { e.preventDefault(); assign(s.dataset.eid, DRAG_CID); s.classList.remove("dragover"); } });

/* ---- by-order template ---- */
$("#b-order").addEventListener("click", () => {
  if (!CLIPS.length) { toast("Сначала загрузите клипы"); return; }
  const slots = [];
  for (const cat of Object.keys(CATS)) EVENTS.filter(e => e.category === cat).forEach(e => slots.push(e.id));
  let i = 0;
  for (const eid of slots) { if (i >= CLIPS.length) break; ASSIGN[eid] = CLIPS[i].id; i++; }
  renderTray(); renderSlots(); updateBcov();
  toast(`Разложено по порядку: ${i} фраз`);
});

/* ---- builder preview playback ---- */
let BNOW = null;
function bplay(cid) {
  if (!cid) return;
  if (BNOW === cid && !bpv.paused) { bpv.pause(); return; }
  BNOW = cid; bpv.src = `/api/clips/audio/${cid}`;
  bpv.play().catch(() => toast("Не удалось воспроизвести"));
  setBicons();
}
bpv.addEventListener("play", setBicons); bpv.addEventListener("pause", setBicons); bpv.addEventListener("ended", setBicons);
function setBicons() {
  $$("#builder .cpp").forEach(b => {
    const card = b.closest(".clip"), slot = b.closest(".slot");
    const cid = card ? card.dataset.cid : (slot ? ASSIGN[slot.dataset.eid] : null);
    const on = cid && cid === BNOW && !bpv.paused;
    b.innerHTML = `<i class="ti ti-player-${on ? "pause" : "play"}" aria-hidden="true"></i>`;
  });
}

/* ---- build & install from the arrangement ---- */
$("#b-build").addEventListener("click", async () => {
  const n = Object.keys(ASSIGN).length; if (!n) return;
  const btn = $("#b-build"), lbl = $("#b-build-lbl"), orig = lbl.textContent;
  btn.disabled = true; lbl.textContent = "Собираю…";
  try {
    await api("/api/clips/build", { method: "POST", body: JSON.stringify({ did: DID, assign: ASSIGN }) });
    lbl.textContent = "Доставка…";
    const done = await pollInstall("MY", m => lbl.textContent = m);
    if (done) {
      try { await api("/api/activate", { method: "POST", body: JSON.stringify({ did: DID, id: "MY" }) }); } catch (e) {}
      toast("Ваша озвучка установлена и включена");
      closeBuilder();
    } else { toast("Доставка не прошла — попробуйте ещё раз"); }
  } catch (ex) { toast(ex.message); }
  finally { btn.disabled = false; lbl.textContent = orig; }
});
