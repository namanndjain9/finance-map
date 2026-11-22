// Injected into every recorded page (Playwright add_init_script). Draws the demo-only layer on top
// of the real app: a visible cursor with click ripples, a glowing spotlight, and the narrator mascot
// (the same stick figure as the app's run track) with a speech bubble. The app itself is untouched.
(() => {
  if (window.demo) return;
  const css = `
  #demo-layer { position: fixed; inset: 0; pointer-events: none; z-index: 2147483647;
    font-family: "Segoe UI", system-ui, sans-serif; }
  #demo-cursor { position: absolute; left: 0; top: 0; width: 34px; height: 34px;
    transform: translate(-6px, -4px); filter: drop-shadow(0 3px 5px rgba(0,0,0,.35)); opacity: 0;
    transition: opacity .3s; }
  #demo-cursor.on { opacity: 1; }
  .demo-ripple { position: absolute; width: 18px; height: 18px; margin: -9px 0 0 -9px; border-radius: 50%;
    border: 3px solid #2563eb; animation: demo-ripple .6s ease-out forwards; }
  @keyframes demo-ripple { to { transform: scale(3.4); opacity: 0; } }
  #demo-spot { position: absolute; border-radius: 14px; opacity: 0;
    box-shadow: 0 0 0 4px rgba(37,99,235,.85), 0 0 28px 8px rgba(37,99,235,.45);
    transition: left .55s cubic-bezier(.3,.7,.2,1), top .55s cubic-bezier(.3,.7,.2,1),
      width .55s cubic-bezier(.3,.7,.2,1), height .55s cubic-bezier(.3,.7,.2,1), opacity .4s; }
  #demo-spot.on { opacity: 1; animation: demo-glow 1.8s ease-in-out infinite; }
  @keyframes demo-glow { 50% { box-shadow: 0 0 0 4px rgba(37,99,235,.55), 0 0 40px 14px rgba(37,99,235,.25); } }

  #demo-guide { position: absolute; right: 34px; bottom: 26px; display: flex; align-items: flex-end; gap: 12px;
    transition: transform .6s cubic-bezier(.3,1.4,.5,1), opacity .4s; }
  #demo-guide.away { transform: translateY(170px); opacity: 0; }
  #demo-bubble { background: #fff; color: #0f172a; border-radius: 18px; padding: 14px 20px; font-size: 25px;
    font-weight: 650; box-shadow: 0 10px 30px rgba(15,23,42,.25); border: 2px solid #2563eb; position: relative;
    margin-bottom: 92px; max-width: 460px; transform-origin: 100% 100%; transition: transform .35s, opacity .35s; }
  #demo-bubble::after { content: ""; position: absolute; right: -14px; bottom: 18px; border: 10px solid transparent;
    border-left: 14px solid #2563eb; }
  #demo-bubble.hidden { transform: scale(.6); opacity: 0; }
  #demo-pad { width: 132px; height: 170px; border-radius: 26px; background: linear-gradient(160deg,#2563eb,#7c3aed);
    box-shadow: 0 12px 30px rgba(37,99,235,.45); display: grid; place-items: center; }
  #demo-fig { width: 90px; height: 132px; overflow: visible; }
  #demo-fig line, #demo-fig circle.head { stroke: #fff; stroke-width: 3.2; stroke-linecap: round; fill: none; }
  #demo-fig .eye { fill: #fff; }
  #demo-fig .mouth { fill: #fff; transform-box: fill-box; transform-origin: center; transform: scaleY(.25); }
  #demo-fig .arm, #demo-fig .leg { transform-box: view-box; }
  #demo-fig .arm { transform-origin: 15px 15px; }
  #demo-fig .leg { transform-origin: 15px 26px; }
  #demo-fig .arm-a { transform: rotate(28deg); } #demo-fig .arm-b { transform: rotate(-28deg); }
  #demo-fig .leg-a { transform: rotate(12deg); } #demo-fig .leg-b { transform: rotate(-12deg); }
  #demo-fig .body { animation: demo-breathe 3s ease-in-out infinite; transform-box: view-box; transform-origin: 15px 40px; }
  @keyframes demo-breathe { 50% { transform: translateY(-1px) scale(1.01); } }
  #demo-guide.talking .mouth { animation: demo-talk .22s ease-in-out infinite alternate; }
  @keyframes demo-talk { from { transform: scaleY(.2); } to { transform: scaleY(1.1); } }
  #demo-guide.talking .arm-b { animation: demo-gesture 1.1s ease-in-out infinite; }
  @keyframes demo-gesture { 0%,100% { transform: rotate(-28deg); } 50% { transform: rotate(-115deg); } }
  #demo-guide.talking .body { animation: demo-bob .55s ease-in-out infinite alternate; }
  @keyframes demo-bob { to { transform: translateY(-1.5px) rotate(-2deg); } }
  #demo-guide.wave .arm-b { animation: demo-wave .5s ease-in-out infinite alternate; }
  @keyframes demo-wave { from { transform: rotate(-150deg); } to { transform: rotate(-110deg); } }
  `;
  const figure = `
  <svg id="demo-fig" viewBox="0 0 30 44" aria-hidden="true"><g class="body">
    <circle class="head" cx="15" cy="7" r="5"/>
    <circle class="eye" cx="13.2" cy="6.2" r=".75"/><circle class="eye" cx="16.8" cy="6.2" r=".75"/>
    <ellipse class="mouth" cx="15" cy="9.3" rx="1.5" ry="1"/>
    <line x1="15" y1="12" x2="15" y2="26"/>
    <g class="arm arm-a"><line x1="15" y1="15" x2="15" y2="24"/></g>
    <g class="arm arm-b"><line x1="15" y1="15" x2="15" y2="24"/></g>
    <g class="leg leg-a"><line x1="15" y1="26" x2="15" y2="40"/></g>
    <g class="leg leg-b"><line x1="15" y1="26" x2="15" y2="40"/></g>
  </g></svg>`;
  const cursorSvg = `<svg id="demo-cursor" viewBox="0 0 24 24"><path d="M3 2l7 19 2.6-7.6L20 11z"
    fill="#fff" stroke="#0f172a" stroke-width="1.6" stroke-linejoin="round"/></svg>`;

  function mount() {
    if (document.getElementById("demo-layer")) return;
    const style = document.createElement("style");
    style.textContent = css;
    document.head.appendChild(style);
    const layer = document.createElement("div");
    layer.id = "demo-layer";
    layer.innerHTML = `<div id="demo-spot"></div>
      <div id="demo-guide" class="away"><div id="demo-bubble" class="hidden"></div><div id="demo-pad">${figure}</div></div>
      ${cursorSvg}`;
    document.body.appendChild(layer);
    const cursor = layer.querySelector("#demo-cursor");
    addEventListener("mousemove", (e) => {
      cursor.style.left = e.clientX + "px";
      cursor.style.top = e.clientY + "px";
    }, true);
    addEventListener("mousedown", (e) => {
      const r = document.createElement("div");
      r.className = "demo-ripple";
      r.style.left = e.clientX + "px";
      r.style.top = e.clientY + "px";
      layer.appendChild(r);
      setTimeout(() => r.remove(), 700);
    }, true);
  }

  let spotTarget = null;
  function placeSpot() {
    const spot = document.getElementById("demo-spot");
    if (!spot) return;
    const el = spotTarget && document.querySelector(spotTarget);
    if (!el) { spot.classList.remove("on"); return; }
    const r = el.getBoundingClientRect(), pad = 8;
    Object.assign(spot.style, { left: r.left - pad + "px", top: r.top - pad + "px",
      width: r.width + 2 * pad + "px", height: r.height + 2 * pad + "px" });
    spot.classList.add("on");
  }
  setInterval(placeSpot, 120); // follows scrolling and layout changes

  let talkTimer = 0;
  window.demo = {
    mount,
    showCursor() { mount(); document.getElementById("demo-cursor").classList.add("on"); },
    say(caption, ms) {
      mount();
      const guide = document.getElementById("demo-guide"), bubble = document.getElementById("demo-bubble");
      guide.classList.remove("away", "wave");
      bubble.classList.add("hidden");
      setTimeout(() => { bubble.textContent = caption; bubble.classList.remove("hidden"); }, 250);
      guide.classList.add("talking");
      clearTimeout(talkTimer);
      talkTimer = setTimeout(() => guide.classList.remove("talking"), ms);
    },
    mascot(show) { mount(); document.getElementById("demo-guide").classList.toggle("away", !show); },
    wave() { mount(); document.getElementById("demo-guide").classList.add("wave"); },
    spotlight(selector) { mount(); spotTarget = selector && selector !== "none" ? selector : null; placeSpot(); },
  };
  if (document.readyState === "loading") addEventListener("DOMContentLoaded", mount);
  else mount();
})();
