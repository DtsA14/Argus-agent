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
var KIND_LABEL = { code: "Code", prd: "PRD", research: "Research", issue: "Issue" };
var query = { value: "" }, mode = "status", current = null, threads = [], decisionRows = [], filter = "all", groupOpen = Object.create(null);
function setMode() {} function open() {}
`;
const code = helpers + "var NO_REPO = \"No repo\";\n" + ["waitingIds", "jobButton", "renderList", "updateSummary", "updateBadge", "renderCost"].map(grab).join("\n");
const ctx = vm.createContext({ Math, String, Array, JSON, Object });
vm.runInContext(code, ctx);
const run = (s) => vm.runInContext(s, ctx);
const T = [
  { id: "j1", repo: "ledger-cli", kind: "code", state: "AWAITING_APPROVAL", title: "Antrean <b>x</b>", stages_usd: 0.03 },
  { id: "j2", repo: "ledger-cli", kind: "prd", state: "DONE", title: "PRD kategori", stages_usd: 0.07 },
  { id: "j3", repo: "athena", kind: "code", state: "APPLIED", title: "buffer", stages_usd: 0 },
  { id: "j4", repo: null, kind: "research", state: "DONE", title: "Dexie atau idb", stages_usd: 0.14 },
  { id: "j5", repo: "constructor", kind: "code", state: "DONE", title: "a prototype name", stages_usd: 0, stages_unknown: 2 },
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
run("renderCost();"); out.cost = run("html(stream)");
console.log(JSON.stringify(out, null, 1));
