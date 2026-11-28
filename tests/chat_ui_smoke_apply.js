// Runs the real installActions and replyBox of app.js (SPEC_CHAT_APPLY_REPLY PR3) in node on a tiny DOM: which buttons exist, when they open, what they send.
const fs = require("fs"), vm = require("vm");
const src = fs.readFileSync(process.argv[2], "utf8");
function grab(name) {
  const i = src.indexOf("function " + name + "(");
  if (i < 0) throw new Error("no function " + name);
  let d = 0, j = src.indexOf("{", i);
  for (let k = j; k < src.length; k++) { if (src[k] === "{") d++; else if (src[k] === "}") { d--; if (d === 0) return src.slice(i, k + 1); } }
}
const helpers = `
function Node(tag) { this.tag = tag; this.children = []; this.className = ""; this.text = null; this.listeners = {}; this.disabled = false; this.type = ""; this.checked = false; this.value = ""; this.open = false; }
Node.prototype.appendChild = function (c) { this.children.push(c); return c; };
Node.prototype.addEventListener = function (e, f) { this.listeners[e] = f; };
Node.prototype.setAttribute = function () {};
function html(n) { if (n.tag === "#text") return n.text; return "<" + n.tag + (n.className ? "." + n.className : "") + (n.disabled ? "[off]" : "") + ">" + (n.text !== null ? n.text : "") + n.children.map(html).join("") + "</" + n.tag + ">"; }
function all(n, out) { out = out || []; out.push(n); n.children.forEach(function (c) { all(c, out); }); return out; }
var document = { createTextNode: function (t) { var n = new Node("#text"); n.text = String(t); return n; } };
function el(tag, cls, text) { var e = new Node(tag); if (cls) e.className = cls; if (text !== undefined && text !== null) e.text = String(text); return e; }
function clear(n) { n.children = []; }
var prepared = [], mode = "cards", cardSeq = 1;
function prepare(b) { prepared.push(b); }
var diffReply = null, diffThen = null;
function get() { return { then: function (f) { diffThen = f; return { catch: function () {} }; } }; }
function who() { return el("span"); }
function say(parent, w, label, text, cls) { parent.appendChild(el("p", cls, label + ": " + text)); }
`;
const code = helpers + grab("diffBlock") + "\n" + grab("replyBox") + "\n" + grab("installActions");
const ctx = vm.createContext({ Math, String, Array, JSON, encodeURIComponent });
vm.runInContext(code, ctx);
const run = (s) => vm.runInContext(s, ctx);
const SHA = "a1b2c3d4e5f6";
const out = {};
function buttons() { return JSON.parse(run("JSON.stringify(all(box).filter(function (n) { return n.tag === 'button'; }).map(function (b) { return [b.className, b.text, b.disabled]; }))")); }
// 1. the reply box
run("var d1 = { state: 'AWAITING_HUMAN' }; var box = replyBox('j1', d1);");
out.reply_buttons = buttons();
run("var ta = all(box).filter(function (n) { return n.tag === 'textarea'; })[0]; var rb = all(box).filter(function (n) { return n.tag === 'button'; })[0];");
out.reply_value_empty = run("ta.value");
run("rb.listeners.click()");
out.reply_click_while_empty = run("JSON.stringify(prepared)");
run("ta.value = 'use two decimals'; ta.listeners.input(); rb.listeners.click();");
out.reply_sent = run("JSON.stringify(prepared)");
out.reply_write_failed = run("html(replyBox('j1', { state: 'WRITE_FAILED' }))");
out.reply_other_states = ["APPROVED", "WRITING", "ACCEPTED"].map((s) => run("html(replyBox('j1', { state: '" + s + "' }))"));
// 2. the readers button
run("prepared = []; var box = installActions('j1', { patch_sha12: '" + SHA + "', apply: { action: 'patch_read_run', why: null, started: null } }, 1);");
out.reader_buttons = buttons();
run("all(box).filter(function (n) { return n.tag === 'button'; })[0].listeners.click()");
out.reader_sent = run("JSON.stringify(prepared)");
// 3. the install: closed until the whole patch is shown, the box is ticked and (for a concern) a reason of 10 characters is typed
function install(needs, diff) {
  run("prepared = []; diffThen = null; var d3 = { patch_sha12: '" + SHA + "', apply: { action: 'code_apply', why: null, started: null, needs_reason: " + needs + " } }; var box = installActions('j1', d3, 1);");
  const st = {};
  run("var tick = all(box).filter(function (n) { return n.tag === 'input' && n.type === 'checkbox'; })[0]; var why = all(box).filter(function (n) { return n.tag === 'input' && n.className === 'reason'; })[0]; var go = all(box).filter(function (n) { return n.tag === 'button'; })[0];");
  st.before_diff = { go_off: run("go.disabled"), tick_off: run("tick.disabled"), has_reason_field: run("!!why") };
  run("tick.checked = true; tick.listeners.change(); go.listeners.click();");
  st.ticked_but_no_diff_click = run("JSON.stringify(prepared)");
  run("diffThen(" + JSON.stringify(diff) + ");");
  st.after_diff = { go_off: run("go.disabled"), tick_off: run("tick.disabled"), html_has_diff: run("html(box).indexOf('+added') >= 0") };
  if (needs) {
    run("go.listeners.click();");
    st.no_reason_click = run("JSON.stringify(prepared)");
    run("why.value = '  because it is only a nit  '; why.listeners.input();");
    st.reason_typed_go_off = run("go.disabled");
    run("why.value = '123456789'; why.listeners.input();");
    st.reason_nine_go_off = run("go.disabled");
    run("why.value = '          x '; why.listeners.input();");
    st.reason_spaces_go_off = run("go.disabled");
    run("why.value = '  because it is only a nit  '; why.listeners.input();");
  }
  run("tick.checked = false; tick.listeners.change();");
  st.unticked_go_off = run("go.disabled");
  run("tick.checked = true; tick.listeners.change(); go.listeners.click();");
  st.sent = run("JSON.stringify(prepared)");
  return st;
}
out.install_fine = install(false, { text: "--- a\n+++ b\n+added", sha12: SHA, why: null });
out.install_concern = install(true, { text: "--- a\n+++ b\n+added", sha12: SHA, why: null });
// 4. a patch that cannot be shown whole, or a changed one: the button never opens
for (const [name, diff] of [["cut", { text: null, sha12: SHA, why: "the patch is too large to read here" }], ["changed", { text: "+added", sha12: "ffffffffffff", why: null }]]) {
  run("prepared = []; diffThen = null; var box = installActions('j1', { patch_sha12: '" + SHA + "', apply: { action: 'code_apply', why: null, started: null, needs_reason: false } }, 1);");
  run("var tick = all(box).filter(function (n) { return n.tag === 'input' && n.type === 'checkbox'; })[0]; var go = all(box).filter(function (n) { return n.tag === 'button'; })[0]; diffThen(" + JSON.stringify(diff) + "); tick.checked = true; tick.listeners.change(); go.listeners.click();");
  out["install_" + name] = { go_off: run("go.disabled"), tick_off: run("tick.disabled"), prepared: run("JSON.stringify(prepared)"), text: run("html(box)").match(/too large|changed since/)[0] };
}
// 5. no button: the server's reason, and the started-but-never-recorded warning
out.refused = run("html(installActions('j1', { patch_sha12: '" + SHA + "', apply: { action: null, why: 'the cap of this job is spent', started: null } }, 1))");
out.started_warning = run("html(installActions('j1', { patch_sha12: '" + SHA + "', apply: { action: null, why: null, started: '2026-11-28T01:02:03Z' } }, 1))");
console.log(JSON.stringify(out, null, 1));
