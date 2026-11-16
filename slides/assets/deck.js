/* agent-seminar deck engine — no dependencies.
 * Keys: → ↓ Space PgDn next · ← ↑ PgUp previous · Home/End · number+Enter jump
 *       O overview · N notes · P presenter window · F fullscreen · ? help · Esc close
 */
(function () {
  "use strict";
  const deck = document.querySelector(".deck");
  const slides = Array.from(document.querySelectorAll(".slide"));
  const total = slides.length;
  const params = new URLSearchParams(location.search);
  const isPresenter = params.has("presenter");
  let index = 0;
  let jumpBuffer = "";
  let jumpTimer = null;
  const channel = "BroadcastChannel" in window ? new BroadcastChannel("agent-seminar-deck") : null;

  // ---------------------------------------------------------------- setup
  const chapterNames = {
    intro: "들어가며", concept: "개념", config: "opencode.json", skill: "스킬", mcp: "MCP",
    plugin: "플러그인", combined: "종합", wrap: "마무리", appendix: "부록",
  };
  slides.forEach((s, i) => {
    s.dataset.index = String(i);
    const no = document.createElement("div");
    no.className = "pageno";
    no.textContent = `${i + 1} / ${total}`;
    s.appendChild(no);
    const ch = s.dataset.chapter;
    if (ch && !s.classList.contains("title") && !s.classList.contains("divider") && !s.querySelector(".chapter-tag")) {
      const tag = document.createElement("div");
      tag.className = "chapter-tag";
      tag.textContent = s.dataset.part || chapterNames[ch] || "";
      s.prepend(tag);
    }
  });

  const progress = el("div", "hud-progress");
  const notesPanel = el("div", "notes-panel");
  const jumpBox = el("div", "jump-box");
  const help = el("div", "help-panel");
  help.innerHTML = `<div>
    <div><kbd>→</kbd><kbd>Space</kbd>다음 &nbsp; <kbd>←</kbd>이전 &nbsp; <kbd>Home</kbd><kbd>End</kbd>처음 / 끝</div>
    <div><kbd>숫자</kbd><kbd>Enter</kbd>해당 쪽으로 이동</div>
    <div><kbd>O</kbd>전체 보기 &nbsp; <kbd>N</kbd>발표자 메모 &nbsp; <kbd>P</kbd>발표자 창 &nbsp; <kbd>F</kbd>전체 화면</div>
    <div><kbd>Ctrl</kbd><kbd>P</kbd>인쇄(PDF 저장: 배경 그래픽 켜기)</div>
    <div><kbd>Esc</kbd>닫기 &nbsp; <kbd>?</kbd>이 도움말</div></div>`;
  document.body.append(progress, notesPanel, jumpBox, help);

  function el(tag, cls) { const e = document.createElement(tag); e.className = cls; return e; }

  // ---------------------------------------------------------------- scaling
  function fit() {
    const s = Math.min(window.innerWidth / 1920, window.innerHeight / 1080);
    document.documentElement.style.setProperty("--scale", String(s));
    if (isPresenter) layoutPresenter();
  }
  window.addEventListener("resize", fit);

  // ---------------------------------------------------------------- navigation
  function stepsOf(s) { return Array.from(s.querySelectorAll(".step")); }

  // Shrink code blocks whose longest line is wider than the box (down to 70%), then wrap as a last resort.
  // Runs on a slide once it is laid out (display:flex), so measurements are real.
  function fitCode(root) {
    root.querySelectorAll("figure.code pre").forEach((pre) => {
      const code = pre.querySelector("code");
      if (!code || code.dataset.fit || pre.clientWidth === 0) return;
      let size = parseFloat(getComputedStyle(code).fontSize);
      const min = size * 0.7;
      while (pre.scrollWidth > pre.clientWidth + 1 && size > min) {
        size -= 0.5;
        code.style.fontSize = `${size}px`;
      }
      if (pre.scrollWidth > pre.clientWidth + 1) code.style.whiteSpace = "pre-wrap";
      code.dataset.fit = "1";
    });
  }

  function show(i, opts = {}) {
    index = Math.max(0, Math.min(total - 1, i));
    slides.forEach((s, k) => s.classList.toggle("active", k === index));
    const cur = slides[index];
    fitCode(cur);
    const steps = stepsOf(cur);
    steps.forEach((st) => st.classList.toggle("shown", !!opts.allSteps));
    progress.style.width = `${((index + 1) / total) * 100}%`;
    const notes = cur.querySelector("aside.notes");
    notesPanel.innerHTML = notes ? notes.innerHTML : "<p>(메모 없음)</p>";
    const hash = `#${index + 1}`;
    if (location.hash !== hash) history.replaceState(null, "", hash + "");
    document.title = `${index + 1}/${total} · ${cur.dataset.title || cur.querySelector("h1,h2")?.textContent || "agent-seminar"}`;
    if (!opts.fromChannel && channel) channel.postMessage({ index, allSteps: !!opts.allSteps });
    if (isPresenter) renderPresenter();
  }

  function next() {
    const hidden = stepsOf(slides[index]).filter((s) => !s.classList.contains("shown"));
    if (hidden.length) { hidden[0].classList.add("shown"); syncSteps(); return; }
    if (index < total - 1) show(index + 1);
  }
  function prev() {
    const shown = stepsOf(slides[index]).filter((s) => s.classList.contains("shown"));
    if (shown.length) { shown[shown.length - 1].classList.remove("shown"); syncSteps(); return; }
    if (index > 0) show(index - 1, { allSteps: true });
  }
  function syncSteps() {
    if (!channel) return;
    channel.postMessage({ index, steps: stepsOf(slides[index]).map((s) => s.classList.contains("shown")) });
  }

  if (channel) {
    channel.onmessage = (e) => {
      const d = e.data || {};
      if (typeof d.index !== "number") return;
      if (d.index !== index) show(d.index, { fromChannel: true, allSteps: d.allSteps });
      if (Array.isArray(d.steps)) stepsOf(slides[index]).forEach((s, k) => s.classList.toggle("shown", !!d.steps[k]));
      if (isPresenter) renderPresenter();
    };
  }

  // ---------------------------------------------------------------- overview / notes / fullscreen
  function toggleOverview(force) {
    const on = force ?? !document.body.classList.contains("overview");
    document.body.classList.toggle("overview", on);
    if (on) slides[index].scrollIntoView({ block: "center" });
  }
  deck.addEventListener("click", (e) => {
    if (!document.body.classList.contains("overview")) return;
    const s = e.target.closest(".slide");
    if (s) { toggleOverview(false); show(Number(s.dataset.index)); }
  });

  function openPresenter() {
    const url = new URL(location.href);
    url.searchParams.set("presenter", "1");
    url.hash = `#${index + 1}`;
    window.open(url.toString(), "agent-seminar-presenter", "width=1400,height=860");
  }

  // ---------------------------------------------------------------- presenter view
  let pv = null;
  let startedAt = null;
  function buildPresenter() {
    document.body.classList.add("presenter");
    pv = el("div", "presenter-view");
    pv.innerHTML = `<div class="pv-current"><div class="pv-frame"></div></div>
      <div class="pv-side"><div class="pv-next"><div class="pv-frame"></div></div>
      <div class="pv-meta"><span class="pv-count"></span><span class="pv-clock">00:00</span></div>
      <div class="pv-notes"></div></div>`;
    document.body.appendChild(pv);
    pv.querySelector(".pv-clock").addEventListener("click", () => { startedAt = Date.now(); });
    setInterval(() => {
      if (!startedAt) return;
      const sec = Math.floor((Date.now() - startedAt) / 1000);
      pv.querySelector(".pv-clock").textContent = `${String(Math.floor(sec / 60)).padStart(2, "0")}:${String(sec % 60).padStart(2, "0")}`;
    }, 1000);
  }
  function frameInto(box, slide) {
    const frame = box.querySelector(".pv-frame");
    frame.innerHTML = "";
    if (!slide) return;
    const clone = slide.cloneNode(true);
    clone.classList.add("active");
    frame.appendChild(clone);
    const s = Math.min(box.clientWidth / 1920, box.clientHeight / 1080);
    frame.style.transform = `scale(${s})`;
  }
  function layoutPresenter() {
    if (!pv) return;
    const cur = pv.querySelector(".pv-current");
    cur.style.height = `${(cur.clientWidth * 1080) / 1920}px`;
    const nx = pv.querySelector(".pv-next");
    nx.style.height = `${(nx.clientWidth * 1080) / 1920}px`;
    renderPresenter();
  }
  function renderPresenter() {
    if (!pv) return;
    frameInto(pv.querySelector(".pv-current"), slides[index]);
    frameInto(pv.querySelector(".pv-next"), slides[index + 1]);
    pv.querySelector(".pv-count").textContent = `${index + 1} / ${total}`;
    const notes = slides[index].querySelector("aside.notes");
    pv.querySelector(".pv-notes").innerHTML = notes ? notes.innerHTML : "<p>(메모 없음)</p>";
    if (!startedAt) startedAt = Date.now();
  }

  // ---------------------------------------------------------------- input
  document.addEventListener("keydown", (e) => {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    const k = e.key;
    if (/^[0-9]$/.test(k)) {
      jumpBuffer += k; jumpBox.textContent = `→ ${jumpBuffer}`; jumpBox.style.display = "block";
      clearTimeout(jumpTimer); jumpTimer = setTimeout(() => { jumpBuffer = ""; jumpBox.style.display = "none"; }, 2500);
      return;
    }
    if (k === "Enter" && jumpBuffer) {
      show(Number(jumpBuffer) - 1, { allSteps: true }); jumpBuffer = ""; jumpBox.style.display = "none"; e.preventDefault(); return;
    }
    switch (k) {
      case "ArrowRight": case "ArrowDown": case "PageDown": case " ": case "Enter": next(); break;
      case "ArrowLeft": case "ArrowUp": case "PageUp": case "Backspace": prev(); break;
      case "Home": show(0); break;
      case "End": show(total - 1, { allSteps: true }); break;
      case "o": case "O": toggleOverview(); break;
      case "n": case "N": document.body.classList.toggle("show-notes"); break;
      case "p": case "P": if (!isPresenter) openPresenter(); break;
      case "f": case "F":
        if (document.fullscreenElement) document.exitFullscreen(); else document.documentElement.requestFullscreen?.();
        break;
      case "?": document.body.classList.toggle("show-help"); break;
      case "Escape": toggleOverview(false); document.body.classList.remove("show-help"); break;
      default: return;
    }
    e.preventDefault();
  });

  let touchX = null;
  document.addEventListener("touchstart", (e) => { touchX = e.touches[0].clientX; }, { passive: true });
  document.addEventListener("touchend", (e) => {
    if (touchX === null) return;
    const dx = e.changedTouches[0].clientX - touchX;
    if (Math.abs(dx) > 50) (dx < 0 ? next : prev)();
    touchX = null;
  });
  window.addEventListener("hashchange", () => {
    const n = Number(location.hash.slice(1));
    if (n && n - 1 !== index) show(n - 1, { allSteps: true });
  });
  window.addEventListener("beforeprint", () => { slides.forEach((s) => stepsOf(s).forEach((st) => st.classList.add("shown"))); fitCode(document); });

  // ---------------------------------------------------------------- start
  if (isPresenter) buildPresenter();
  fit();
  const start = Number(location.hash.slice(1));
  show(start ? start - 1 : 0, { allSteps: !!start, fromChannel: true });
  if (isPresenter) setTimeout(layoutPresenter, 50);
})();
