const fs = require("fs"), vm = require("vm");
const src = fs.readFileSync(process.argv[2], "utf8");
function grab(name) { const i = src.indexOf("function " + name + "("); let d = 0, j = src.indexOf("{", i); for (let k = j; k < src.length; k++) { if (src[k] === "{") d++; else if (src[k] === "}") { d--; if (d === 0) return src.slice(i, k + 1); } } }
const helpers = `
function Node(tag) { this.tag = tag; this.children = []; this.className = ""; this.text = null; this.listeners = {}; this.disabled = false; this.type = ""; this.checked = false; this.value = ""; }
Node.prototype.appendChild = function (c) { this.children.push(c); return c; };
Node.prototype.addEventListener = function (e, f) { this.listeners[e] = f; };
Node.prototype.setAttribute = function () {};
function find(n, f) { if (f(n)) return n; for (var i = 0; i < n.children.length; i++) { var r = find(n.children[i], f); if (r) return r; } return null; }
var document = { createTextNode: function (t) { var n = new Node("#text"); n.text = String(t); return n; } };
function el(tag, cls, text) { var e = new Node(tag); if (cls) e.className = cls; if (text !== undefined && text !== null) e.text = String(text); return e; }
var prepared = []; function prepare(b) { prepared.push(JSON.stringify(b)); }
` + grab("planActions");
const ctx = vm.createContext({ String, JSON });
vm.runInContext(helpers, ctx);
const run = (s) => vm.runInContext(s, ctx);
const log = [];
// both inputs needed
run(`var box = planActions("j20261117_100000_aaaa", { action: "queue_go", why: null, needs: ["ack", "reason"], ack_items: [1, 3] });
var btn = find(box, function (n) { return n.tag === "button"; }), tick = find(box, function (n) { return n.type === "checkbox"; }), why = find(box, function (n) { return n.className === "reason"; });`);
log.push(["start disabled", run("btn.disabled")]);
run("tick.checked = true; tick.listeners.change();"); log.push(["ack only: disabled", run("btn.disabled")]);
run('why.value = "kurang"; why.listeners.input();'); log.push(["short reason: disabled", run("btn.disabled")]);
run('why.value = "  alasan yang cukup panjang  "; why.listeners.input();'); log.push(["ack+reason: enabled", !run("btn.disabled")]);
run("btn.listeners.click();"); log.push(["prepared", run("prepared.join('|')")]);
run("tick.checked = false; tick.listeners.change(); prepared = []; btn.listeners.click();"); log.push(["unticked: disabled and nothing sent", run("btn.disabled && prepared.length === 0")]);
// nothing needed
run(`prepared = []; var box2 = planActions("j20261117_100000_aaaa", { action: "queue_go", why: null, needs: [], ack_items: [] });
var b2 = find(box2, function (n) { return n.tag === "button"; }); b2.listeners.click();`);
log.push(["no needs: enabled, sends job only", run("!b2.disabled && prepared.join('|')")]);
// ack only
run(`prepared = []; var box3 = planActions("j20261117_100000_aaaa", { action: "queue_go", why: null, needs: ["ack"], ack_items: [2] });
var b3 = find(box3, function (n) { return n.tag === "button"; }), t3 = find(box3, function (n) { return n.type === "checkbox"; }); t3.checked = true; t3.listeners.change(); b3.listeners.click();`);
log.push(["ack only", run("prepared.join('|')")]);
console.log(log.map((x) => x.join(": ")).join("\n"));
