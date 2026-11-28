// UI-3a: the real renderList, jobButton, renderCost and updateBadge of app.js, run in node on a tiny DOM and on the JSON the server sends.
const fs = require("fs"), vm = require("vm");
const src = fs.readFileSync(process.argv[2], "utf8");
function grab(name) {
  const i = src.indexOf("function " + name + "(");
  if (i < 0) throw new Error("no function " + name);
  let d = 0, j = src.indexOf("{", i);
  for (let k = j; k < src.length; k++) { if (src[k] === "{") d++; else if (src[k] === "}") { d--; if (d === 0) return src.slice(i, k + 1); } }
}
const helpers = `
function Node(tag) { this.tag = tag; this.children = []; this.className = ""; this.text = null; this.listeners = {}; this.attrs = {}; this.type = ""; this.hidden = false; }
Node.prototype.appendChild = function (c) { this.children.push(c); return c; };
Node.prototype.addEventListener = function (e, f) { this.listeners[e] = f; };
Node.prototype.setAttribute = function (k, v) { this.attrs[k] = v; };
function html(n) { if (n.tag === "#text") return n.text; var a = n.attrs["aria-expanded"] ? "[" + n.attrs["aria-expanded"] + "]" : ""; return "<" + n.tag + (n.className ? "." + n.className : "") + a + ">" + (n.text !== null ? n.text : "") + n.children.map(html).join("") + "</" + n.tag + ">"; }
function el(tag, cls, text) { var e = new Node(tag); if (cls) e.className = cls; if (text !== undefined && text !== null) e.text = String(text); return e; }
function clear(node) { node.children = []; }
function nJobs(n) { return n + (n === 1 ? " job" : " jobs"); }
function usd(n) { return typeof n === "number" ? "$" + n.toFixed(4) : "-"; }
function stateClass(s) { return /FAILED/.test(String(s)) ? "bad" : "warn"; }
function fact(c, k, v) { c.appendChild(el("p", "fact", k + ": " + v)); }
var nodes = {}; var document = { getElementById: function (id) { return nodes[id] || (nodes[id] = new Node("span")); } };
var badge = document.getElementById("decide-badge"); var summary = document.getElementById("summary");
var list = new Node("ul"), stream = new Node("section"), panel = { classList: { remove: function () {} } };
var capInfo = null, budgetInfo = null, DAY_MS = 24 * 3600 * 1000;
function usd2(n) { return "$" + Number(n).toFixed(2); }
var KIND_LABEL = { code: "Code", prd: "PRD", research: "Research", issue: "Issue" };
function showCard() {}
function decideCard(r) { var c = el("article", "card"); c.appendChild(el("h2", null, r.title || r.id)); return c; }
var waitingRows = [], waitingMeta = { capped: false, unknown: false };
var query = { value: "" }, mode = "status", current = null, threads = [], decisionRows = [], filter = "all", groupOpen = Object.create(null);
function setMode() {} function open() {}
`;
const code = helpers + "var NO_REPO = \"No repo\";\n" + src.match(/  var JOB_TIME = .*;\n/)[0] + ["budgetWindow", "budgetCard", "budgetChipText", "waitingIds", "jobButton", "renderList", "waitLabel", "waitingCard", "waitingJobs", "openJobs", "needCount", "renderDecisions", "cardRow", "updateSummary", "updateBadge", "usd2", "recentJob", "renderCost"].map(grab).join("\n");
const NOW = Date.parse("2026-11-25T12:00:00Z");
const ctx = vm.createContext({ Math, String, Array, JSON, Object, Date: { now: () => NOW, parse: Date.parse, UTC: Date.UTC } });
vm.runInContext(code, ctx);
const run = (s) => vm.runInContext(s, ctx);
const T = [
  { id: "j20261125_080000_aaa1", repo: "ledger-cli", kind: "code", state: "AWAITING_APPROVAL", title: "Antrean <b>x</b>", stages_usd: 0.03 },
  { id: "j20261124_080000_aaa2", repo: "ledger-cli", kind: "prd", state: "DONE", title: "PRD kategori", stages_usd: 0.07 },
  { id: "j20261125_090000_aaa3", repo: "athena", kind: "code", state: "APPLIED", title: "buffer", stages_usd: 0 },
  { id: "j20261125_100000_aaa4", repo: null, kind: "research", state: "DONE", title: "Dexie atau idb", stages_usd: 0.14 },
  { id: "not-a-job-id", repo: "constructor", kind: "code", state: "DONE", title: "a prototype name", stages_usd: 0, stages_unknown: 2 },
];
const out = {};
run("threads = " + JSON.stringify(T) + "; decisionRows = [{ id: 'j20261125_080000_aaa1' }];");
run("renderList();"); out.all = run("html(list)");
run("filter = 'waiting'; renderList();"); out.waiting = run("html(list)");
run("filter = 'research'; renderList();"); out.research = run("html(list)");
run("filter = 'all'; groupOpen = Object.create(null); groupOpen['athena'] = true; groupOpen['ledger-cli'] = false; renderList();"); out.toggled = run("html(list)");
run("groupOpen = Object.create(null); query.value = 'zzz'; renderList();"); out.none = run("html(list)");
run("query.value = ''; updateBadge();"); out.badge1 = run("badge.hidden + '|' + badge.textContent");
run("decisionRows = []; updateBadge();"); out.badge0 = run("badge.hidden + '|' + badge.textContent");
run("decisionRows = new Array(12).fill({ id: 'x' }); updateBadge();"); out.badge12 = run("badge.hidden + '|' + badge.textContent");
out.summary = run("summary.textContent"); out.panelcost = run("document.getElementById('panel-cost').textContent");
run("decisionRows = [{ id: 'jd', title: 'old job', state: 'REVIEW_READY' }, { id: 'jc', title: 'draft job', state: 'AWAITING_APPROVAL' }]; waitingRows = [{ action: 'prd_approve', card: 'plan', id: 'jp', job: null, repo: 'ledger-cli', title: 'a <b>plan</b>', item: null }, { action: 'draft_approve', card: 'queue', id: 'qa', job: 'jc', repo: 'athena', title: null, item: 2 }, { action: 'queue_step', card: 'queue', id: 'qb', job: null, repo: null, title: null, item: 3 }, { action: 'queue_go', card: 'plan', id: 'jq', job: null, repo: null, title: null, item: null }]; updateBadge();");
out.need = run("badge.hidden + '|' + badge.textContent + '|' + summary.textContent + '|' + badge.attrs['aria-label']");
run("renderDecisions();"); out.decisions = run("html(stream)");
run("waitingMeta = { capped: true, unknown: true }; renderDecisions();"); out.decisionsNotes = run("html(stream)");
run("waitingRows = []; decisionRows = []; waitingMeta = { capped: false, unknown: false }; renderDecisions();"); out.nothing = run("html(stream)");
run("waitingRows = [{ action: 'draft_approve', card: 'queue', id: 'qa', job: 'jc', repo: null, title: null, item: 2 }]; decisionRows = [{ id: 'jc', title: 'draft job', state: 'X' }]; filter = 'waiting'; threads = [{ id: 'jc', repo: 'athena', kind: 'code', state: 'AWAITING_APPROVAL', title: 'draft job' }, { id: 'jx', repo: 'athena', kind: 'code', state: 'DONE', title: 'other' }]; renderList();"); out.panelwaiting = run("html(list)");
run("threads = " + JSON.stringify(T) + "; filter = 'all';");
out.bars = run("[{ kind: 'queue', state: 'DONE', items: 5, applied_n: 5, id: 'q1' }, { kind: 'queue', state: 'CLOSED', items: 2, applied_n: 0, id: 'q2' }, { kind: 'queue', state: null, items: 21, applied_n: null, id: 'q3' }, { kind: 'queue', state: 'WAITING', items: 3, applied_n: 1, id: 'q4' }, { kind: 'prd', state: 'AWAITING_HUMAN', items: 2, applied_n: undefined, id: 'p1' }, { kind: 'queue', state: 'STOPPED', items: 0, applied_n: 0, id: 'q5' }].map(function (r) { var c = cardRow(r); return c.children.filter(function (x) { return x.tag === 'progress'; }).map(function (x) { return x.max + '/' + x.value; }).join(',') + '|' + html(c).indexOf('of'); })");
run("waitingRows = [{ action: 'queue_step', card: 'queue', id: 'qb', job: null, repo: 'athena', title: 'athena', item: null }, { action: 'draft_approve', card: 'queue', id: 'qc', job: null, repo: null, title: null, item: null }]; decisionRows = []; waitingMeta = { capped: false, unknown: false, stale: true }; renderDecisions();"); out.nulls = run("html(stream)");
run("capInfo = null; renderCost();"); out.costNull = run("html(stream)");
run("capInfo = { cap_usd: 7, booked_usd: 1.08, unknown: false }; renderCost();"); out.costOk = run("html(stream)");
out.bar = run("stream.children[0].children.filter(function (x) { return x.tag === 'progress'; }).map(function (x) { return x.max + '/' + x.value; }).join(',')");
run("capInfo = { cap_usd: 7, booked_usd: 8.5, unknown: false }; renderCost();"); out.costOver = run("html(stream)");
out.barOver = run("stream.children[0].children.filter(function (x) { return x.tag === 'progress'; }).map(function (x) { return x.max + '/' + x.value; }).join(',')");
run("capInfo = { cap_usd: 7, booked_usd: null, unknown: true }; renderCost();"); out.costUnknown = run("html(stream)");
run("capInfo = { failed: true }; renderCost();"); out.costFailed = run("html(stream)");
run("capInfo = { cap_usd: 0, booked_usd: 0, unknown: false }; renderCost();"); out.costZero = run("html(stream)");
run("capInfo = { cap_usd: '7', booked_usd: '1', unknown: false }; renderCost();"); out.costStrings = run("html(stream)");
run("capInfo = { cap_usd: 7, booked_usd: 6.996, unknown: false }; renderCost();"); out.costRound = run("html(stream)");
// SPEC_BUDGET_V2 part 1: the daily and monthly meters, text only, unknown never zero
const W = (o) => Object.assign({ date: "2026-11-28", spent_usd: 0.354, limit_usd: 1, warn: false, unknown: null }, o);
run("budgetInfo = null; renderCost();"); out.budgetNull = run("html(stream)");
run("budgetInfo = { off: true }; renderCost();"); out.budgetOff = run("html(stream)");
run("budgetInfo = " + JSON.stringify({ day: W({}), month: W({ spent_usd: 7.55, limit_usd: 30 }), note: "jobs directory only", unknown: null }) + "; renderCost();"); out.budgetOk = run("html(stream)");
run("budgetInfo = " + JSON.stringify({ day: W({ spent_usd: 0.9, warn: true }), month: W({ spent_usd: 7.55, limit_usd: 30 }), note: "n" }) + "; renderCost();"); out.budgetWarn = run("html(stream)");
run("budgetInfo = " + JSON.stringify({ day: W({ spent_usd: null, unknown: { reason: "unpriced call", job: "j<b>1</b>" } }), month: W({ spent_usd: null, unknown: { reason: "unreadable", job: "j20261101_000000_aaaa" } }), note: "n" }) + "; renderCost();"); out.budgetUnknown = run("html(stream)");
out.chip = ["null", "{ off: true }", JSON.stringify({ day: W({}) }), JSON.stringify({ day: W({ spent_usd: null, unknown: { reason: "x", job: "y" } }) }), JSON.stringify({ day: W({ spent_usd: "0.3" }) })].map((b) => run("budgetChipText(" + b + ")"));
out.recent = run("['j20261125_080000_aaa1', 'j20261124_110000_aaa1', 'j20261124_120000_aaa1', 'j20261124_120001_aaa1', 'j20271125_080000_aaa1', 'j20261125_120001_aaa1', 'x', 'j20261125_080000_AAAA'].map(function (id) { return recentJob({ id: id }) ? 1 : 0; }).join('')");
run("var keep = threads; threads = []; for (var i = 0; i < 100; i++) { threads.push({ id: 'j20261125_080000_aaa1', kind: 'code', stages_usd: 0.01 }); } capInfo = null; renderCost();"); out.cost100 = run("html(stream)");
run("threads = keep; capInfo = null; renderCost();"); out.cost = run("html(stream)");
console.log(JSON.stringify(out, null, 1));
