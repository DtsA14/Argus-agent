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
var capInfo = null, DAY_MS = 24 * 3600 * 1000;
var KIND_LABEL = { code: "Code", prd: "PRD", research: "Research", issue: "Issue" };
function showCard() {}
function decideCard(r) { var c = el("article", "card"); c.appendChild(el("h2", null, r.title || r.id)); return c; }
var waitingRows = [], waitingMeta = { capped: false, unknown: false };
var query = { value: "" }, mode = "status", current = null, threads = [], decisionRows = [], filter = "all", groupOpen = Object.create(null);
function setMode() {} function open() {}
`;
const code = helpers + "var NO_REPO = \"No repo\";\n" + ["waitingIds", "jobButton", "renderList", "waitLabel", "waitingCard", "waitingJobs", "openJobs", "needCount", "renderDecisions", "cardRow", "updateSummary", "updateBadge", "usd2", "recentJob", "renderCost"].map(grab).join("\n");
const NOW = Date.parse("2026-11-25T12:00:00Z");
const ctx = vm.createContext({ Math, String, Array, JSON, Object, Date: { now: () => NOW, parse: Date.parse } });
vm.runInContext(code, ctx);
const run = (s) => vm.runInContext(s, ctx);
const T = [
  { id: "j1", repo: "ledger-cli", created_at: "2026-11-25T08:00:00Z", kind: "code", state: "AWAITING_APPROVAL", title: "Antrean <b>x</b>", stages_usd: 0.03 },
  { id: "j2", repo: "ledger-cli", created_at: "2026-11-24T08:00:00Z", kind: "prd", state: "DONE", title: "PRD kategori", stages_usd: 0.07 },
  { id: "j3", repo: "athena", created_at: "2026-11-25T09:00:00Z", kind: "code", state: "APPLIED", title: "buffer", stages_usd: 0 },
  { id: "j4", repo: null, created_at: "2026-11-25T10:00:00Z", kind: "research", state: "DONE", title: "Dexie atau idb", stages_usd: 0.14 },
  { id: "j5", repo: "constructor", created_at: "garbage", kind: "code", state: "DONE", title: "a prototype name", stages_usd: 0, stages_unknown: 2 },
];
const out = {};
run("threads = " + JSON.stringify(T) + "; decisionRows = [{ id: 'j1' }];");
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
run("capInfo = null; renderCost();"); out.cost = run("html(stream)");
console.log(JSON.stringify(out, null, 1));
