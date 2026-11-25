// Runs the real new/changed functions of app.js (stepActions, renderCard) in node on a tiny DOM, on the JSON the server sends.
const fs = require("fs"), vm = require("vm");
const src = fs.readFileSync(process.argv[2], "utf8");
function grab(name) {                                   // a function declaration, by brace matching
  const i = src.indexOf("function " + name + "(");
  if (i < 0) throw new Error("no function " + name);
  let d = 0, j = src.indexOf("{", i);
  for (let k = j; k < src.length; k++) { if (src[k] === "{") d++; else if (src[k] === "}") { d--; if (d === 0) return src.slice(i, k + 1); } }
}
function grabVar(re) { const m = src.match(re); if (!m) throw new Error("no var " + re); return m[0]; }
const helpers = `
function Node(tag) { this.tag = tag; this.children = []; this.className = ""; this.text = null; this.listeners = {}; this.disabled = false; this.type = ""; }
Node.prototype.appendChild = function (c) { this.children.push(c); return c; };
Node.prototype.addEventListener = function (e, f) { this.listeners[e] = f; };
Node.prototype.setAttribute = function () {};
function html(n) { if (n.tag === "#text") return n.text; return "<" + n.tag + (n.className ? "." + n.className : "") + ">" + (n.text !== null ? n.text : "") + n.children.map(html).join("") + "</" + n.tag + ">"; }
var document = { createTextNode: function (t) { var n = new Node("#text"); n.text = String(t); return n; } };
function el(tag, cls, text) { var e = new Node(tag); if (cls) e.className = cls; if (text !== undefined && text !== null) e.text = String(text); return e; }
function usd(n) { return typeof n === "number" ? "$" + n.toFixed(4) : "-"; }
var prepared = [];
function prepare(b) { prepared.push(b); }
`;
const code = helpers + grab("stepActions") + "\n" + grabVar(/var LABELS = [\s\S]*?\];\n/) + grabVar(/var USD_KEYS = .*;\n/) + grab("fact") + grab("who") + grab("say") + grab("renderCard") + `
function removeCard() {} function post() { return { then: function () { return { catch: function () {} }; } }; }
var slot = el("div"), pending = null, busy = false;
`;
const ctx = vm.createContext({ setTimeout: () => 0, clearTimeout: () => {}, Math, String, Array, JSON });
vm.runInContext(code, ctx);
const out = {};
const run = (s) => vm.runInContext(s, ctx);
// 1. the queue card's button
for (const t of [{ action: "queue_step", item: 2, why: null }, { action: "draft_approve", item: 1, why: null }, { action: null, item: null, why: "sedang jalan" }, { action: null, item: null, why: null }]) {
  run("prepared = []; var box = stepActions('q20261117T100400Z-abcd', " + JSON.stringify(t) + ");");
  const h = run("html(box)");
  let clicked = null;
  if (t.action) { run("box.children[0].listeners.click()"); clicked = run("JSON.stringify(prepared)"); }
  out[String(t.action)] = { html: h, prepared: clicked };
}
// 2. the confirm cards
const cards = [
  { action: "queue_step", title: "Start the issue (a drafter run)", queue: "q1", item: 1, job: null, repo: "athena", commit: "abc", item_text: "One", flags: ["x"], job_cap_usd: 1, queue_usd: 3, drafter_cap_usd: 0.75, money: "m" },
  { action: "draft_approve", title: "Approve the draft (the agent starts)", queue: "q1", item: 1, job: "j1", repo: "athena", item_text: "One", draft_sha: "a".repeat(64), writable: ["src/a.py", "tests/test_a.py"], validations: [{ id: "v1", must_pass: ["tests/test_a.py::test_x"] }], profile: "default", agent_cap_usd: 0.5, attempt_usd: 0.1, flags: ["profile: default"], money: "m" },
  { action: "draft_approve", title: "Approve the draft (the agent starts)", queue: "q1", item: 1, job: "j1", repo: "athena", item_text: "One", draft_sha: "b".repeat(64), writable: ["src/a.py"], validations: [],
    changed_tests: ["tests/test_old.py"], changed_tests_n: 3, plan: { files: ["src/a.py"], steps: ["<b>do</b> the thing"], risks: ["it may break b"] }, warnings: ["w1"], unverifiable: ["the page stays"], baseline_note: "no baseline recorded", flags: [], exposure_usd: 0 },
  { action: "draft_approve", title: "Approve the draft (the agent starts)", queue: "q1", item: 1, job: "j1", repo: "athena", item_text: "One", draft_sha: "c".repeat(64), writable: ["src/a.py"], validations: [],
    changed_tests: [], changed_tests_n: 0, summary_note: "summary unavailable", flags: [] },
];
let n = 0;
for (const c of cards) {
  run("var r = renderCard({ card: " + JSON.stringify(c) + ", exposure_usd: 0, min_delay_s: 1, expires_s: 300, token: 't' }, function () {}); var rh = html(r);");
  out["card:" + c.action + (n++ > 1 ? ":" + n : "")] = run("rh");
}
console.log(JSON.stringify(out, null, 1));
