/*
 * Drone Dispatch — logic suite.
 *
 * Pulls LEVELS / simulate / parseMap and the Python prelude straight out of
 * index.html, then hammers every level with the reference solution, the
 * starter, and a battery of adversarial programs.
 *
 *   node challenge/test/logic.test.js
 *
 * The invariant that matters most here: simulate() must ALWAYS return a
 * non-empty frames array, whatever the drone did. A crash path that returned
 * without frames is what left the Run button stuck on "Flying…".
 */
const fs = require("fs");
const path = require("path");
const os = require("os");
const { execFileSync } = require("child_process");

const HTML = path.join(__dirname, "..", "index.html");
const html = fs.readFileSync(HTML, "utf8");
const js = html.match(/<script>([\s\S]*)<\/script>/)[1];

function slice(startMark, endMark) {
  const a = js.indexOf(startMark);
  const b = js.indexOf(endMark, a);
  if (a < 0 || b < 0) throw new Error("marker not found in index.html: " + startMark);
  return js.slice(a, b);
}

const PRELUDE = js.match(/const PRELUDE = `([\s\S]*?)`;/)[1];
const logic =
  slice("const CHAPTERS = [", "/* ==================== Python side") +
  slice("const DIRS =", "/* ==================== rendering");
const { LEVELS, simulate, parseMap, FEATURE_LABEL, CHAPTERS, levelCases, grade } =
  new Function(logic + "\nreturn {LEVELS, simulate, parseMap, FEATURE_LABEL, CHAPTERS, levelCases, grade};")();

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "dispatch-"));
const runnerPath = path.join(tmp, "runner.py");
fs.writeFileSync(runnerPath, `${PRELUDE}
import sys, json
print(run_mission(json.loads(sys.argv[1]), sys.argv[2]))
`);

/* `c` is one flight case: {inject, battery}. A level's cases come from levelCases(). */
function runPython(src, c) {
  const payload = { inject: (c && c.inject) || {}, battery: (c && c.battery) == null ? 87 : c.battery };
  const out = execFileSync("python3",
    [runnerPath, JSON.stringify(src), JSON.stringify(payload)],
    { encoding: "utf8" });
  return JSON.parse(out);
}

let pass = 0, fail = 0;
const failures = [];
function check(name, cond, detail) {
  if (cond) { pass++; return true; }
  fail++; failures.push(name + (detail ? "  <- " + detail : ""));
  return false;
}

/* ------------------------------------------------------------------ *
 * The programs every level gets hit with. Most are things a camper
 * genuinely types. None of them may hang, throw, or strand the runner.
 * ------------------------------------------------------------------ */
const ADVERSARIAL = [
  ["off the map",          "drone.takeoff()\ndrone.forward(9999)\n"],
  ["deliver on home",      "drone.takeoff()\ndrone.deliver()\n"],
  ["deliver on ground",    "drone.deliver()\n"],
  ["move before takeoff",  "drone.forward(10)\n"],
  ["land before takeoff",  "drone.land()\n"],
  ["negative distance",    "drone.takeoff()\ndrone.forward(-40)\ndrone.land()\n"],
  ["zero distance",        "drone.takeoff()\ndrone.forward(0)\ndrone.land()\n"],
  ["double takeoff",       "drone.takeoff()\ndrone.takeoff()\ndrone.land()\ndrone.land()\n"],
  ["spin in place",        "drone.takeoff()\nfor i in range(40):\n    drone.cw(90)\ndrone.land()\n"],
  ["odd turn angle",       "drone.takeoff()\ndrone.cw(45)\ndrone.forward(20)\ndrone.land()\n"],
  ["reverse turn",         "drone.takeoff()\ndrone.ccw(180)\ndrone.forward(30)\ndrone.land()\n"],
  ["every direction",      "drone.takeoff()\ndrone.forward(20)\ndrone.back(20)\ndrone.left(20)\ndrone.right(20)\ndrone.land()\n"],
  ["vertical + wait",      "drone.takeoff()\ndrone.up(50)\ndrone.wait(1)\ndrone.down(50)\ndrone.land()\n"],
  ["float distance",       "drone.takeoff()\ndrone.forward(25.7)\ndrone.land()\n"],
  ["no drone commands",    "x = 1\nprint(x)\n"],
  ["empty program",        ""],
  ["only a comment",       "# nothing here\n"],
  ["syntax error",         "drone.takeoff(\n"],
  ["indentation error",    "drone.takeoff()\n  drone.land()\n"],
  ["name error",           "drone.takeoff()\ndrone.forward(nope)\n"],
  ["zero division",        "drone.takeoff()\nx = 1 / 0\n"],
  ["string distance",      "drone.takeoff()\ndrone.forward('far')\n"],
  ["bool distance",        "drone.takeoff()\ndrone.forward(True)\n"],
  ["index error",          "stops = [1]\ndrone.takeoff()\ndrone.forward(stops[9])\n"],
  ["key error",            "drone.takeoff()\nd = {}\ndrone.forward(d['nope'])\n"],
  ["command flood",        "drone.takeoff()\nfor i in range(2000):\n    drone.cw(90)\n"],
  ["print then fly",       "print('hello')\ndrone.takeoff()\ndrone.land()\n"],
  ["unicode print",        "print('flying \\u2708')\ndrone.takeoff()\ndrone.land()\n"],
  // the easytello surface
  ["flip on the ground",   "drone.flip('f')\n"],
  ["flip every direction", "drone.takeoff()\nfor d in ['l','r','f','b']:\n    drone.flip(d)\ndrone.land()\n"],
  ["flip uppercase",       "drone.takeoff()\ndrone.flip('F')\ndrone.land()\n"],
  ["flip bad direction",   "drone.takeoff()\ndrone.flip('x')\n"],
  ["flip a number",        "drone.takeoff()\ndrone.flip(3)\n"],
  ["flip nothing",         "drone.takeoff()\ndrone.flip('')\n"],
  ["speed low",            "drone.speed(10)\ndrone.takeoff()\ndrone.forward(20)\ndrone.land()\n"],
  ["speed high",           "drone.speed(100)\ndrone.takeoff()\ndrone.forward(20)\ndrone.land()\n"],
  ["speed out of range",   "drone.speed(500)\ndrone.takeoff()\n"],
  ["speed a string",       "drone.speed('fast')\n"],
  ["emergency mid-air",    "drone.takeoff()\ndrone.forward(20)\ndrone.emergency()\n"],
  ["emergency first",      "drone.emergency()\n"],
  ["telemetry only",       "print(drone.get_battery(), drone.get_speed(), drone.get_time())\n"],
  ["battery drives a branch", "b = drone.get_battery()\ndrone.takeoff()\nif b > 0:\n    drone.forward(10)\ndrone.land()\n"],
  ["video stream",         "drone.streamon()\ndrone.takeoff()\ndrone.land()\ndrone.streamoff()\n"],
];

/* deterministic pseudo-random fuzz, so a failure is reproducible */
function makeFuzz(seed, n) {
  let s = seed;
  const rnd = () => (s = (s * 1103515245 + 12345) % 2147483648) / 2147483648;
  const verbs = ["forward", "back", "left", "right", "cw", "ccw", "deliver", "land",
                 "takeoff", "up", "down", "flip", "speed", "emergency"];
  const lines = [];
  for (let i = 0; i < n; i++) {
    const v = verbs[Math.floor(rnd() * verbs.length)];
    if (v === "deliver" || v === "land" || v === "takeoff" || v === "emergency") lines.push(`drone.${v}()`);
    else if (v === "cw" || v === "ccw") lines.push(`drone.${v}(${[90, 180, 270][Math.floor(rnd() * 3)]})`);
    else if (v === "flip") lines.push(`drone.flip('${"lrfb"[Math.floor(rnd() * 4)]}')`);
    else if (v === "speed") lines.push(`drone.speed(${10 + Math.floor(rnd() * 90)})`);
    else lines.push(`drone.${v}(${Math.floor(rnd() * 30) * 10 - 60})`);
  }
  // a fuzz program may legitimately raise; wrap so the flight still gets simulated
  return "try:\n    " + lines.join("\n    ") + "\nexcept Exception as e:\n    print('caught', e)\n";
}

/* the invariant: a simulation result must always be animatable and checkable */
function assertUsable(label, L, map, res, c) {
  if (!res.ok) return;                      // python raised; the UI reports it and stops
  if (!res.log.length) return;              // nothing to animate; the UI says so
  let sim;
  try { sim = simulate(res.log, map); }
  catch (e) { check(label + ": simulate throws", false, e.message); return; }

  check(label + ": returns frames", Array.isArray(sim.frames) && sim.frames.length > 0,
        "frames=" + JSON.stringify(sim.frames));
  if (!Array.isArray(sim.frames)) return;
  const badFrame = sim.frames.find(f =>
    !Number.isInteger(f.x) || !Number.isInteger(f.y) ||
    f.x < 0 || f.y < 0 || f.x >= map.w || f.y >= map.h ||
    !Number.isInteger(f.heading) || f.heading < 0 || f.heading > 3);
  check(label + ": frames stay on the map", !badFrame, JSON.stringify(badFrame));

  // anything the renderer reads off a frame has to be in range
  const badRender = sim.frames.find(f =>
    !(typeof f.speed === "number" && f.speed >= 10 && f.speed <= 100) ||
    !(typeof (f.roll || 0) === "number" && (f.roll || 0) >= 0 && (f.roll || 0) <= 1));
  check(label + ": frames are renderable", !badRender, JSON.stringify(badRender));
  check(label + ": flips are recorded as a list", Array.isArray(sim.flips));

  // the goal function must survive any state the simulator can produce
  try {
    const v = L.goal(sim, c);
    check(label + ": goal returns a verdict",
          v && typeof v.pass === "boolean" && (v.pass || typeof v.msg === "string"),
          JSON.stringify(v));
    // a crashed flight must never be graded as a win
    if (sim.crashed) check(label + ": crash never passes", !v.pass, sim.crashed);
  } catch (e) {
    check(label + ": goal throws", false, e.message);
  }
}

/* ------------------------------ run ------------------------------ */

console.log(`Drone Dispatch — logic suite (${LEVELS.length} levels)\n`);

check("chapters cover every level",
      LEVELS.every(l => CHAPTERS[l.chapter]), "a level points at a missing chapter");
check("every chapter is used",
      CHAPTERS.every((c, i) => LEVELS.some(l => l.chapter === i)), "a chapter has no levels");
check("levels are in chapter order",
      LEVELS.every((l, i) => i === 0 || l.chapter >= LEVELS[i - 1].chapter));

/* ---- the drone exposes the easytello surface campers will meet later ---- */
const EASYTELLO = ["takeoff", "land", "forward", "back", "left", "right", "up", "down",
                   "cw", "ccw", "flip", "speed", "emergency",
                   "get_battery", "get_speed", "get_time", "streamon", "streamoff"];
{
  const probe = runPython(
    "import json\nprint(json.dumps([m for m in " + JSON.stringify(EASYTELLO) +
    " if not callable(getattr(drone, m, None))]))\n", null);
  const missing = probe.stdout.trim();
  check("drone exposes every easytello method", missing === "[]", missing + " " + (probe.error || ""));
  const flips = runPython(
    "drone.takeoff()\nfor d in ['l','r','f','b']:\n    drone.flip(d)\n", null);
  check("flip accepts all four directions", flips.ok, flips.error);
  check("flip is logged with its direction",
        flips.ok && flips.log.filter(c => c[0] === "flip").length === 4 &&
        flips.log.filter(c => c[0] === "flip").every(c => "lrfb".includes(c[1])),
        JSON.stringify(flips.log));
  const bad = runPython("drone.takeoff()\ndrone.flip('sideways')\n", null);
  check("flip rejects a bad direction", !bad.ok && /ValueError/.test(bad.error || ""), bad.error);
  const battery = runPython("print(drone.get_battery())\n", { battery: 42 });
  check("get_battery reports the level's reading", battery.stdout.trim() === "42", battery.stdout);
  const defBattery = runPython("print(drone.get_battery())\n", null);
  check("get_battery has a default", /^\d+$/.test(defBattery.stdout.trim()), defBattery.stdout);
}

/* ---- the advanced-track feature detectors: each fires on its construct only ---- */
{
  const FEATURE_PROBES = [
    ["elif",   "if x:\n    pass\nelif y:\n    pass\n", "if x:\n    pass\nelse:\n    pass\n"],
    ["elif",   "def f():\n    if x:\n        pass\n    elif y:\n        pass\n", "if x:\n    pass\nelse:\n    if y:\n        pass\n"],
    ["try",    "try:\n    pass\nexcept ValueError:\n    pass\n", "try:\n    pass\nfinally:\n    pass\n"],
    ["boolop", "z = x and y\n",                           "z = x == y\n"],
    ["return", "def f():\n    return 1\n",               "def f():\n    return\n"],
    ["nested", "for a in b:\n    while c:\n        pass\n", "for a in b:\n    pass\nfor c in d:\n    pass\n"],
    ["try",    "try:\n    pass\nexcept ValueError:\n    pass\n", "pass\n"],
    ["class",  "class P:\n    pass\n",                   "def P():\n    pass\n"],
    ["sort",   "y = sorted(x)\n",                         "y = list(x)\n"],
    ["sort",   "x.sort()\n",                              "x.reverse()\n"],
    ["comp",   "y = [a for a in b]\n",                    "y = sum(a for a in b)\n"],
    ["while",  "while x:\n    pass\n",                   "for x in y:\n    pass\n"],
  ];
  FEATURE_PROBES.forEach(([f, yes, no]) => {
    const hit = runPython(yes, null), miss = runPython(no, null);
    check(`feature ${f} detected`, hit.features[f] === true, yes);
    check(`feature ${f} not falsely detected`, miss.features[f] === false, no);
  });
}

LEVELS.forEach((L, i) => {
  const tag = `L${i + 1} (ch${L.chapter + 1} ${L.title})`;
  const map = parseMap(L.map);

  /* ---- the map itself ---- */
  check(`${tag} map is rectangular`, new Set(L.map.map(r => r.length)).size === 1);
  check(`${tag} has exactly one home pad`,
        L.map.join("").split("").filter(c => c === "H").length === 1);
  check(`${tag} uses only known tiles`,
        /^[.#TWH*A-G]+$/.test(L.map.join("")), L.map.join("").replace(/[.#TWH*A-G]/g, ""));
  check(`${tag} has a brief`, typeof L.brief === "string" && L.brief.length > 20);
  check(`${tag} has a hint`, typeof L.hint === "string" && L.hint.length > 20);
  check(`${tag} requires only known features`,
        (L.requires || []).every(f => FEATURE_LABEL[f]), JSON.stringify(L.requires));

  /* a level needs something to aim at: a lettered pad or a waypoint */
  const padsOnMap = Object.keys(map.pads).filter(p => p !== "H");
  check(`${tag} has an objective on the map`,
        padsOnMap.length > 0 || map.waypoints.length > 0);

  const cases = levelCases(L);
  check(`${tag} has at least one case`, cases.length > 0);
  if (L.cases) check(`${tag} every case is labelled`, L.cases.every(c => typeof c.label === "string" && c.label));

  /* fly `src` once per case; the level only counts as won if every case wins */
  const flyAll = src => cases.map(c => {
    const res = runPython(src, c);
    if (!res.ok) return { c, res, sim: null, v: { pass: false } };
    const sim = simulate(res.log, map);
    return { c, res, sim, v: grade(L, res, sim, c) };
  });
  const wins = runs => runs.every(r => r.v.pass);

  /* ---- starter code ---- */
  const starts = flyAll(L.starter);
  starts.forEach(({ c, res: st }, n) => {
    const ct = cases.length > 1 ? `${tag} case ${n + 1}` : tag;
    check(`${ct} starter parses`, !(st.error || "").startsWith("SyntaxError"), st.error);
    if (L.starterRaises) {
      // these starters crash on purpose: the crash IS the lesson
      check(`${ct} starter raises ${L.starterRaises}`,
            !st.ok && (st.error || "").startsWith(L.starterRaises), st.error || "it ran clean");
    } else {
      check(`${ct} starter does not raise`, st.ok, st.error);
    }
    assertUsable(`${ct} starter`, L, map, st, c);
  });
  check(`${tag} starter does not already pass`, !wins(starts), "the starter code solves the level as given");

  /* ---- reference solution ---- */
  const sols = flyAll(L.solution);
  sols.forEach(({ c, res: sol, sim, v }, n) => {
    const ct = cases.length > 1 ? `${tag} case ${n + 1}` : tag;
    if (!check(`${ct} solution runs clean`, sol.ok, sol.error)) return;
    check(`${ct} solution does not crash`, !sim.crashed, sim.crashed);
    const missing = (L.requires || []).filter(f => !sol.features[f]);
    check(`${ct} solution uses required features`, missing.length === 0, JSON.stringify(missing));
    check(`${ct} solution satisfies the goal`, v.pass, v.msg);
    check(`${ct} solution lands`, sol.log.some(r => r[0] === "land"));
    assertUsable(`${ct} solution`, L, map, sol, c);
  });

  /* ---- negative controls ---- */
  check(`${tag} takeoff+land alone is rejected`, !wins(flyAll("drone.takeoff()\ndrone.land()\n")));

  /* dropping each required construct must also be rejected */
  (L.requires || []).forEach(f => {
    const s0 = sols[0];
    if (!s0.sim) return;
    const v = grade(L, { features: { ...s0.res.features, [f]: false } }, s0.sim, s0.c);
    check(`${tag} rejects a solution without ${FEATURE_LABEL[f]}`, !v.pass, "grade() still passed");
  });

  /* ---- adversarial programs ---- */
  ADVERSARIAL.forEach(([name, src]) => {
    let runs;
    try { runs = flyAll(src); }
    catch (e) { check(`${tag} ${name}: python runner survives`, false, e.message); return; }
    runs.forEach(({ c, res }) => {
      check(`${tag} ${name}: reports ok or an error string`,
            res.ok === true || typeof res.error === "string", JSON.stringify(res).slice(0, 120));
      check(`${tag} ${name}: command flood is capped`,
            !res.log || res.log.length <= 600, res.log && res.log.length);
      assertUsable(`${tag} ${name}`, L, map, res, c);
    });
    // none of these may be graded as a win
    check(`${tag} ${name}: does not pass the level`, !wins(runs), "adversarial program cleared the level");
  });

  /* ---- fuzz ---- */
  for (let seed = 1; seed <= 12; seed++) {
    const c = cases[seed % cases.length];
    const res = runPython(makeFuzz(seed * (i + 7), 25), c);
    assertUsable(`${tag} fuzz#${seed}`, L, map, res, c);
  }
});

/* ------------------------------------------------------------------ *
 * Plausible wrong answers: the mistakes campers actually make on the
 * advanced levels. Each must be rejected, not just the random junk above.
 * ------------------------------------------------------------------ */
const WRONG = [
  ["Three Forecasts", "only handles clear and storm",
   'drone.takeoff()\nif weather == "clear":\n    drone.forward(120)\n    drone.deliver()\nelif weather == "storm":\n    pass\ndrone.land()\n'],
  ["Three Forecasts", "else-if instead of elif",
   'drone.takeoff()\nif weather == "clear":\n    drone.forward(120)\n    drone.deliver()\nelse:\n    if weather == "wind":\n        drone.forward(50)\n        drone.deliver()\ndrone.land()\n'],
  ["Go / No-Go", "or instead of and",
   'drone.takeoff()\nfor stop in STOPS:\n    drone.forward(stop["distance"])\n    if stop["wind"] < 20 or stop["open"]:\n        drone.deliver()\ndrone.land()\n'],
  ["Sort the Route", "sorts names alphabetically",
   'here = 0\ndrone.takeoff()\nfor name in sorted(STOPS):\n    d = STOPS[name]\n    drone.forward(d - here)\n    here = d\n    drone.deliver()\ndrone.land()\n'],
  ["Package Objects", "flips at every pad",
   'class Package:\n    def __init__(self, d, f):\n        self.d = d\n        self.f = f\n    def drop(self):\n        drone.forward(self.d)\n        drone.deliver()\n        drone.flip("f")\nload = [Package(30, False), Package(30, True), Package(40, False)]\ndrone.takeoff()\nfor p in load:\n    p.drop()\ndrone.land()\n'],
  ["One-Line Lists", "converts but does not filter",
   'hops = [t * 10 for t in TILES]\ndrone.takeoff()\nfor h in hops:\n    drone.forward(h)\n    drone.deliver()\ndrone.land()\n'],
  ["Garbled Manifest", "skips the garbled reading",
   'drone.takeoff()\ndrone.cw(90)\nfor t in READINGS:\n    try:\n        d = int(t)\n    except ValueError:\n        continue\n    drone.forward(d)\n    drone.deliver()\ndrone.land()\n'],
  ["Round Trip", "never flies home",
   'route = [30, 40, 30]\ndef total(h):\n    return sum(h)\ndrone.takeoff()\nfor h in route:\n    drone.forward(h)\n    drone.deliver()\ndrone.land()\n'],
  ["Night Shift", "discards the sorted() result",
   'def to_cm(t):\n    try:\n        return int(t)\n    except ValueError:\n        return None\nq = [to_cm(ORDERS[n]) for n in ORDERS if to_cm(ORDERS[n]) is not None]\nsorted(q)\nhere = 0\ndrone.takeoff()\nif weather == "storm":\n    drone.right(30)\nwhile q:\n    t = q.pop(0)\n    drone.forward(t - here)\n    drone.deliver()\n    here = t\ndrone.back(here)\ndrone.left(30)\ndrone.land()\n'],
];
WRONG.forEach(([title, why, src]) => {
  const L = LEVELS.find(l => l.title === title);
  if (!check(`wrong answer targets a real level: ${title}`, !!L)) return;
  const map = parseMap(L.map);
  const won = levelCases(L).every(c => {
    const res = runPython(src, c);
    return res.ok && grade(L, res, simulate(res.log, map), c).pass;
  });
  check(`${title} rejects: ${why}`, !won, "a wrong answer cleared the level");
});

console.log(`checks passed: ${pass}`);
console.log(`checks failed: ${fail}`);
if (fail) {
  console.log("\nfailures:");
  failures.forEach(f => console.log("  " + f));
}
process.exit(fail ? 1 : 0);
