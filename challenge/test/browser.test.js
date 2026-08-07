/*
 * Drone Dispatch — browser suite.
 *
 * Drives headless Chrome over CDP against a real URL: boots Pyodide, plays
 * every level, and hits each one with programs that crash, raise, hang or do
 * nothing. The load-bearing assertion is the one the logic suite cannot make:
 * after ANY run the page is usable again — Run enabled, status back to
 * "Python ready", no uncaught exception.
 *
 *   node challenge/test/browser.test.js http://localhost:8123/challenge/
 *
 * Needs Chrome already listening on :9222, e.g.
 *   "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
 *     --headless=new --remote-debugging-port=9222 --user-data-dir=/tmp/dd about:blank
 */
const URL_BASE = process.argv[2];
if (!URL_BASE) { console.error("usage: node browser.test.js <url>"); process.exit(2); }

const STUCK_PROGRAMS = [
  ["crash into scenery",  "drone.takeoff()\ndrone.forward(9999)\n"],
  ["deliver on home",     "drone.takeoff()\ndrone.deliver()\n"],
  ["move before takeoff", "drone.forward(30)\n"],
  ["python raises",       "drone.takeoff()\nx = 1 / 0\n"],
  ["syntax error",        "drone.takeoff(\n"],
  ["no commands",         "x = 1\n"],
  ["bad flip",            "drone.takeoff()\ndrone.flip('sideways')\n"],
  ["flip on the ground",  "drone.flip('f')\n"],
  ["command flood",       "drone.takeoff()\nfor i in range(2000):\n    drone.cw(90)\n"],
];

async function main() {
  const list = await (await fetch("http://localhost:9222/json/list")).json();
  const page = list.find(t => t.type === "page");
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  let id = 0;
  const pending = new Map();
  let errors = [];

  await new Promise(r => ws.addEventListener("open", r));
  ws.addEventListener("message", ev => {
    const m = JSON.parse(ev.data);
    if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
    if (m.method === "Runtime.exceptionThrown")
      errors.push(m.params.exceptionDetails.exception?.description || m.params.exceptionDetails.text);
    if (m.method === "Runtime.consoleAPICalled" && m.params.type === "error")
      errors.push("console.error: " + m.params.args.map(a => a.value).join(" "));
  });
  const send = (method, params = {}) => new Promise(res => {
    const myId = ++id;
    pending.set(myId, res);
    ws.send(JSON.stringify({ id: myId, method, params }));
  });
  // always wrap in an IIFE: repeated top-level `const` in Runtime.evaluate
  // throws "already declared" and quietly produces a false negative
  const ev = async expr => {
    const r = await send("Runtime.evaluate",
      { expression: `(function(){${expr}})()`, awaitPromise: true, returnByValue: true });
    return r.result?.result?.value;
  };
  const sleep = ms => new Promise(r => setTimeout(r, ms));

  let pass = 0, fail = 0;
  const failures = [];
  const check = (name, cond, detail) => {
    if (cond) { pass++; return true; }
    fail++; failures.push(name + (detail ? "  <- " + detail : ""));
    return false;
  };

  await send("Runtime.enable");
  await send("Page.enable");
  await send("Page.navigate", { url: URL_BASE });
  await sleep(2500);
  await ev("localStorage.removeItem('drone-dispatch-v1'); location.reload(); return 1;");
  await sleep(3000);

  for (let i = 0; i < 120; i++) {
    if (await ev("return document.getElementById('status').textContent === 'Python ready';")) break;
    await sleep(1000);
  }
  check("pyodide booted",
        await ev("return document.getElementById('status').textContent === 'Python ready';"),
        await ev("return document.getElementById('status').textContent;"));

  const levelCount = await ev("return LEVELS.length;");
  check("levels and pips agree",
        levelCount === await ev("return document.querySelectorAll('.pip').length;"));
  check("a fresh visit opens on Learn", await ev("return !document.getElementById('learnPane').hidden;"));
  check("learn content rendered", await ev("return document.getElementById('learnBody').innerText.length > 300;"));

  /* waits for a run to settle and reports what the page looks like afterwards */
  async function runAndSettle(maxSeconds = 40) {
    await ev("document.getElementById('runBtn').click(); return 1;");
    for (let t = 0; t < maxSeconds * 2; t++) {
      await sleep(500);
      const s = await ev(`return {busy: document.getElementById('runBtn').disabled,
                                  status: document.getElementById('status').textContent,
                                  out: document.getElementById('console').innerText};`);
      if (!s.busy && s.out && s.status === "Python ready") return { settled: true, ...s };
    }
    return Object.assign({ settled: false }, await ev(
      `return {busy: document.getElementById('runBtn').disabled,
               status: document.getElementById('status').textContent,
               out: document.getElementById('console').innerText};`));
  }

  for (let i = 0; i < levelCount; i++) {
    const title = await ev(`return LEVELS[${i}].title;`);
    const tag = `L${i + 1} (${title})`;

    /* ---- the starter must render and must NOT already win ---- */
    await ev(`localStorage.removeItem('drone-dispatch-v1'); go(${i}); setMode('code'); return 1;`);
    check(`${tag} shows its brief`, (await ev("return document.getElementById('brief').innerText;")).length > 15);
    check(`${tag} canvas has pixels`, await ev(`
      const c = document.getElementById('map');
      const d = c.getContext('2d').getImageData(0,0,c.width,c.height).data;
      let n = 0; for (let j = 0; j < d.length; j += 4) if (d[j] || d[j+1] || d[j+2]) n++;
      return n > 500;`));

    /* ---- adversarial programs: the page must always come back ---- */
    for (const [name, src] of STUCK_PROGRAMS) {
      errors = [];
      await ev(`editor.setValue(${JSON.stringify(src)}, -1); return 1;`);
      const r = await runAndSettle();
      check(`${tag} ${name}: page recovers`, r.settled,
            JSON.stringify({ busy: r.busy, status: r.status, out: (r.out || "").slice(0, 120) }));
      check(`${tag} ${name}: says something useful`, (r.out || "").trim().length > 0);
      check(`${tag} ${name}: no page exception`, errors.length === 0, errors.join(" | "));
      check(`${tag} ${name}: level not marked done`, !(await ev(`return !!store.done[${i}];`)),
            "an adversarial program cleared the level");
    }

    /* ---- the reference solution must clear it ---- */
    errors = [];
    await ev(`editor.setValue(LEVELS[${i}].solution, -1); return 1;`);
    const r = await runAndSettle(60);
    check(`${tag} solution settles`, r.settled, JSON.stringify(r).slice(0, 200));
    check(`${tag} solution is graded complete`, await ev(`return !!store.done[${i}];`), (r.out || "").slice(0, 200));
    check(`${tag} celebration modal opens`, await ev("return document.getElementById('scrim').classList.contains('show');"));
    check(`${tag} solution raises no page exception`, errors.length === 0, errors.join(" | "));
    await ev("closeModal(); return 1;");

    /* ---- replay must not strand the page either ---- */
    errors = [];
    await ev("document.getElementById('replayBtn').click(); return 1;");
    await sleep(1500);
    check(`${tag} replay is safe`, errors.length === 0, errors.join(" | "));

    /* ---- pip reflects completion, hint and map info open ---- */
    check(`${tag} pip marked done`,
          await ev(`return document.querySelectorAll('.pip')[${i}].classList.contains('done');`));
    await ev("document.getElementById('helpBtn').click(); return 1;");
    check(`${tag} hint modal opens`, await ev("return document.getElementById('scrim').classList.contains('show');"));
    await ev("closeModal(); document.getElementById('mapInfoBtn').click(); return 1;");
    check(`${tag} map info opens`, await ev("return document.getElementById('scrim').classList.contains('show');"));
    await ev("closeModal(); return 1;");
  }

  /* ---- the watchdog, once: five seconds is five seconds ---- */
  errors = [];
  await ev("go(0); setMode('code'); editor.setValue('drone.takeoff()\\nwhile True:\\n    x = 1\\n', -1); return 1;");
  const t0 = Date.now();
  const loop = await runAndSettle(40);
  const secs = (Date.now() - t0) / 1000;
  check("runaway loop is stopped", /too long/.test(loop.out || ""), (loop.out || "").slice(0, 160));
  check("watchdog fires inside 12s", secs < 12, secs.toFixed(1) + "s");
  check("page survives the runaway loop", loop.settled && errors.length === 0, errors.join(" | "));

  /* ---- navigation and layout ---- */
  await ev("go(0); return 1;");
  check("prev disabled on the first level", await ev("return document.getElementById('prevBtn').disabled;"));
  await ev(`go(${levelCount - 1}); return 1;`);
  check("next disabled on the last level", await ev("return document.getElementById('nextBtn').disabled;"));
  await ev("go(0); setMode('learn'); return 1;");
  check("learn hides the editor", await ev("return document.getElementById('codePane').hidden;"));
  await ev("setMode('code'); return 1;");
  check("code hides the lesson", await ev("return document.getElementById('learnPane').hidden;"));

  const before = await ev("return document.querySelector('.left').clientWidth;");
  const g = await ev("const r = document.getElementById('gutter').getBoundingClientRect(); return {x: r.x + 3, y: r.y + r.height / 2};");
  await send("Input.dispatchMouseEvent", { type: "mousePressed", x: g.x, y: g.y, button: "left", clickCount: 1, pointerType: "mouse" });
  await send("Input.dispatchMouseEvent", { type: "mouseMoved", x: g.x - 150, y: g.y, button: "left", pointerType: "mouse" });
  await send("Input.dispatchMouseEvent", { type: "mouseReleased", x: g.x - 150, y: g.y, button: "left", pointerType: "mouse" });
  await sleep(300);
  check("splitter resizes the panes",
        Math.abs((await ev("return document.querySelector('.left').clientWidth;")) - before) > 80);

  /* ---- progress survives a reload ---- *
   * Retry the read: evaluating against a context that is still being torn
   * down returns undefined, which looks exactly like lost progress. */
  await ev("location.reload(); return 1;");
  let stored;
  for (let t = 0; t < 30; t++) {
    await sleep(500);
    stored = await ev("return Object.keys(JSON.parse(localStorage.getItem('drone-dispatch-v1')||'{}').done||{}).length;");
    if (typeof stored === "number" && stored >= levelCount) break;
  }
  check("progress persists across a reload", stored >= levelCount, "done count = " + stored);

  console.log(`checks passed: ${pass}`);
  console.log(`checks failed: ${fail}`);
  if (fail) { console.log("\nfailures:"); failures.forEach(f => console.log("  " + f)); }
  ws.close();
  process.exit(fail ? 1 : 0);
}
main().catch(e => { console.error(e); process.exit(1); });
