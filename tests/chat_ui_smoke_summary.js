// Runs the real summaryRows, summaryBlock, summaryDetails and cutText of app.js (SPEC_JOB_SUMMARY, F33) on a tiny DOM.
const fs = require("fs"), vm = require("vm");
const src = fs.readFileSync(process.argv[2], "utf8");
function grab(name) {
  const i = src.indexOf("function " + name + "(");
  if (i < 0) throw new Error("no function " + name);
  let d = 0, j = src.indexOf("{", i);
  for (let k = j; k < src.length; k++) { if (src[k] === "{") d++; else if (src[k] === "}") { d--; if (d === 0) return src.slice(i, k + 1); } }
}
const readerWords = src.slice(src.indexOf("var READER_WORDS"), src.indexOf("function summaryRows"));
const code = `
function Node(tag) { this.tag = tag; this.children = []; this.className = ""; this.text = null; }
Node.prototype.appendChild = function (c) { this.children.push(c); return c; };
function el(tag, cls, text) { var e = new Node(tag); if (cls) e.className = cls; if (text !== undefined && text !== null) e.text = String(text); return e; }
function html(n) { return "<" + n.tag + (n.className ? "." + n.className : "") + ">" + (n.text !== null ? n.text : "") + n.children.map(html).join("") + "</" + n.tag + ">"; }
function usd(n) { return typeof n === "number" ? "$" + n.toFixed(4) : "-"; }
` + readerWords + ["cutText", "summaryRows", "summaryBlock", "summaryDetails"].map(grab).join("\n");
const ctx = vm.createContext({ Number, String, Array, JSON });
vm.runInContext(code, ctx);
ctx.__j = null;
const rows = (job, f) => { ctx.__a = job; ctx.__b = f; return JSON.parse(vm.runInContext("JSON.stringify(summaryRows(__a, __b))", ctx)); };
const det = (job, f) => { ctx.__a = job; ctx.__b = f; return vm.runInContext("(function(){var d=summaryDetails(__a,__b);return d?html(d):null;})()", ctx); };
const block = (r) => { ctx.__r = r; return vm.runInContext("html(summaryBlock(__r))", ctx); };
const out = {};
const card = (over) => Object.assign({ purpose: { title: "Add a line" }, files: [{ path: "a.py" }, { path: "b.py" }], files_cut: 0, patch_read_kind: "ok", open: true,
  checks: [{ key: "c", ok: true, label: "paket review valid" }, { key: "h", ok: null, label: "contoh" }] }, over || {});
out.issue_wait = rows({ kind: "issue", state: "AWAITING_HUMAN", title: "T" }, { issue: { text: "Do the thing\n\nmore" }, examples: { summary: { after: 2, whatif: 1 } } });
out.issue_none = rows({ kind: "issue", state: "AWAITING_HUMAN", title: "T" }, { issue: { text: "x" }, examples: { summary: { after: 0, whatif: 0 }, no_examples: "cannot import" } });
out.issue_handed = rows({ kind: "issue", state: "HANDED_OFF", title: "T" }, { issue: { text: "x" }, examples: null, handoff: "j1" });
out.code_ready_open = rows({ kind: "code", state: "REVIEW_READY", title: "T" }, card());
out.code_ready_closed = rows({ kind: "code", state: "REVIEW_READY", title: "T" }, card({ open: false, checks: [{ key: "c", ok: true, label: "ok" }, { key: "h", ok: false, label: "ada contoh perilaku yang baru" }] }));
out.code_concerns = rows({ kind: "code", state: "REVIEW_READY", title: "T" }, card({ patch_read_kind: "concerns" }));
out.code_invalid = rows({ kind: "code", state: "REVIEW_READY", title: "T" }, card({ open: false, checks: [{ key: "c", ok: false, label: "paket review valid" }] }));
out.code_open_missing = rows({ kind: "code", state: "REVIEW_READY", title: "T" }, card({ open: undefined }));
out.code_two_false = rows({ kind: "code", state: "REVIEW_READY", title: "T" }, card({ open: false, checks: [{ key: "c", ok: true, label: "ok" }, { key: "f", ok: false, label: "first false" }, { key: "h", ok: false, label: "second false" }] }))[3][1];
out.code_applied = rows({ kind: "code", state: "APPLIED", title: "T" }, card({ open: false }));
out.code_running = rows({ kind: "code", state: "AGENT_RUNNING", title: "T" }, card());
out.code_approval = rows({ kind: "code", state: "AWAITING_APPROVAL", title: "T" }, card());
out.code_cut = rows({ kind: "code", state: "REVIEW_READY", title: "T" }, card({ files_cut: 3 }))[1][1];
out.research_checked = rows({ kind: "research", state: "REPORT_READY", title: "T" }, { question: "Q?", checked: true, counts: { SUPPORTED: 5, PARTIAL: 0, UNSUPPORTED: 1 }, spent_usd: 0.1 });
out.research_unchecked = rows({ kind: "research", state: "REPORT_READY", title: "T" }, { question: "Q?", checked: false, counts: { SUPPORTED: 0, PARTIAL: 0, UNSUPPORTED: 0 }, spent_usd: 0.1 });
out.prd = rows({ kind: "prd", state: "AWAITING_HUMAN", title: "T" }, { request: "R", issue_count: 2, turn: "w2", stale: false });
out.prd_stale = rows({ kind: "prd", state: "AWAITING_HUMAN", title: "T" }, { request: "R", issue_count: 2, turn: "w2", stale: true });
out.refused = rows({ kind: "code", state: "REVIEW_READY", title: "T" }, { refused: "not found" });
out.null_facts = rows({ kind: "code", state: "REVIEW_READY", title: "T" }, null);
out.manager = rows({ kind: "manager", state: "OPEN", title: "T" }, {});
out.long_request = rows({ kind: "prd", state: "AWAITING_HUMAN", title: "T" }, { request: "x".repeat(900), issue_count: 1 })[0][1].length;
out.odd = rows({ kind: "research", state: "REPORT_READY", title: "T" }, { question: 7, checked: true, counts: { SUPPORTED: "<b>", PARTIAL: null }, spent_usd: "x" });
out.block = block([["Hasil", "<img src=x onerror=1>"]]);
out.det_issue = det({ kind: "issue" }, { issue: { text: "full text" } });
out.det_code = det({ kind: "code" }, card({ files_cut: 2 }));
out.det_none = det({ kind: "code" }, { refused: "x" });
console.log(JSON.stringify(out, null, 1));
