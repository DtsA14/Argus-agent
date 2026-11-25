// SPEC_CHAT_UI3D: the real diffBlock and showDraft of app.js in node on a tiny DOM, on the JSON the server sends.
const fs = require("fs"), vm = require("vm");
const src = fs.readFileSync(process.argv[2], "utf8");
function grab(name) {
  const i = src.indexOf("function " + name + "(");
  if (i < 0) throw new Error("no function " + name);
  let d = 0, j = src.indexOf("{", i);
  for (let k = j; k < src.length; k++) { if (src[k] === "{") d++; else if (src[k] === "}") { d--; if (d === 0) return src.slice(i, k + 1); } }
}
const helpers = `
function Node(tag) { this.tag = tag; this.children = []; this.className = ""; this.text = null; this.listeners = {}; this.type = ""; }
Node.prototype.appendChild = function (c) { this.children.push(c); return c; };
Node.prototype.addEventListener = function (e, f) { this.listeners[e] = f; };
Node.prototype.setAttribute = function () {};
function html(n) { if (n.tag === "#text") return n.text; return "<" + n.tag + (n.className ? "." + n.className.replace(/ /g, ".") : "") + ">" + (n.text !== null ? n.text : "") + n.children.map(html).join("") + "</" + n.tag + ">"; }
var document = { createTextNode: function (t) { var n = new Node("#text"); n.text = String(t); return n; } };
function el(tag, cls, text) { var e = new Node(tag); if (cls) e.className = cls; if (text !== undefined && text !== null) e.text = String(text); return e; }
function clear(node) { node.children = []; }
var stream = new Node("section"), cardSeq = 0, mode = "cards", openCard = null, openKind = null, reply = null, failed = false, requested = [];
function get(path) { requested.push(path); return { then: function (f) { if (!failed) { f(reply); } return { catch: function (g) { if (failed) { g(new Error("x")); } } }; } }; }
function cardButtons() { var n = new Node("div"); n.className = "nav"; return n; }
`;
const code = helpers + ["fact", "who", "say", "sec", "diffBlock", "showDraft"].map(grab).join("\n");
const ctx = vm.createContext({ String, Array, JSON, Object });
vm.runInContext(code, ctx);
const run = (s) => vm.runInContext(s, ctx);
const out = {};
out.blockLines = run(`html(diffBlock("--- a/t.py\\n+++ b/t.py\\n@@ -1,2 +1,3 @@\\n same\\n-old\\n+new\\n+++i;\\n--x\\n\\n+<b>tag</b>")).split("<div.dl.").slice(1).map(function (x) { return x.split(">")[0]; }).join(",")`);
out.blockText = run(`html(diffBlock("+<b>tag</b>"))`);
const full = {
  job: "j20261117_110000_aaa1", draft_sha: "a".repeat(64), draft_sha12: "a".repeat(12), state: "AWAITING_APPROVAL", writable: ["src/a.py", "tests/test_a.py"], must_pass: ["tests/test_a.py::test_x"], tests_n: 7,
  tests: [{ path: "tests/test_a.py", diff: "--- a/tests/test_a.py\n+++ b/tests/test_a.py\n+def test_z():", before_verified: true, note: null, removed: [{ node: "test_old", reason: "no <i>longer</i> true" }], modified: [{ node: "test_y", reason: "moved" }] },
          { path: null, diff: null, note: "the path is not shown", before_verified: false, removed: [], modified: [] },
          { path: "tests/test_b.py", diff: null, note: "unavailable", before_verified: false, removed: [], modified: [] },
          { path: "tests/test_c.py", diff: "--- a/c\n+++ b/c\n-x", before_verified: false, note: null, removed: [], modified: [] }],
  plan: { steps: ["add test_z"], files: ["tests/test_a.py"], risks: ["it may break"] }, warnings: ["w1"], unverifiable: ["the page stays"], summary_note: "summary unavailable" };
run("reply = " + JSON.stringify(full) + "; showDraft('j20261117_110000_aaa1');");
out.page = run("html(stream)");
out.state = run("[cardSeq, openCard, openKind, requested.join('|')].join(';')");
run("reply = { job: 'j', draft_sha12: 'b'.repeat(12), draft_sha: 'b'.repeat(64), state: 'X', writable: [], must_pass: [], tests: [], tests_n: 0 }; showDraft('j');");
out.none = run("html(stream)");
run("failed = true; showDraft('j');"); out.failed = run("html(stream)");
run("failed = false; mode = 'chat'; clear(stream); reply = " + JSON.stringify(full) + "; showDraft('j');"); out.leftTab = run("html(stream)");
console.log(JSON.stringify(out, null, 1));
