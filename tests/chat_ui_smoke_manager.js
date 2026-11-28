// P3: the real renderManager, proposalBox, sendTurn, pollManager and timeLeft of app.js, run in node on a tiny DOM and on the JSON the server sends.
const fs = require("fs"), vm = require("vm");
const src = fs.readFileSync(process.argv[2], "utf8");
function grab(name) {
  const i = src.indexOf("function " + name + "(");
  if (i < 0) throw new Error("no function " + name);
  let d = 0, j = src.indexOf("{", i);
  for (let k = j; k < src.length; k++) { if (src[k] === "{") d++; else if (src[k] === "}") { d--; if (d === 0) return src.slice(i, k + 1); } }
}
const helpers = `
function Node(tag) { this.tag = tag; this.children = []; this.className = ""; this.text = null; this.listeners = {}; this.attrs = {}; this.type = ""; this.disabled = false; }
Node.prototype.appendChild = function (c) { this.children.push(c); return c; };
Node.prototype.addEventListener = function (e, f) { this.listeners[e] = f; };
Node.prototype.setAttribute = function (k, v) { this.attrs[k] = v; };
function html(n) { if (n.tag === "#text") return n.text; return "<" + n.tag + (n.className ? "." + n.className : "") + (n.disabled ? "[disabled]" : "") + ">" + (n.text !== null ? n.text : "") + n.children.map(html).join("") + "</" + n.tag + ">"; }
function el(tag, cls, text) { var e = new Node(tag); if (cls) e.className = cls; if (text !== undefined && text !== null) e.text = String(text); return e; }
function clear(node) { node.children = []; }
function usd(n) { return typeof n === "number" ? "$" + n.toFixed(4) : "-"; }
function stateClass(s) { return /FAILED/.test(String(s)) ? "bad" : "warn"; }
function fact(c, k, v) { c.appendChild(el("p", "fact", k + ": " + v)); }
function who(kind, text) { return el("span", "who " + kind, text); }
function say(parent, kind, label, text, cls) { var p = el("p", cls || "say"); p.appendChild(who(kind, label)); p.appendChild({ tag: "#text", text: String(text), children: [] }); parent.appendChild(p); return p; }
function act(label, build, cls) { var b = el("button", cls, label); b.type = "button"; b.addEventListener("click", function () { prepare(build()); }); return b; }
var document = { createTextNode: function (t) { return { tag: "#text", text: String(t), children: [] }; } };
var stream = new Node("section"), notes = [], prepared = [], posted = [], modes = [], timers = [];
function grow() {}
var message = { value: "" }, repoSel = { value: "", hidden: false, options: [{ value: "ledger-cli" }, { value: "athena" }] };
var mode = "manager", fromProposal = null, pending = null;
function prepare(b) { prepared.push(JSON.stringify(b)); }
function showNote(t) { notes.push(t); }
function setMode(m) { modes.push(m); fromProposal = null; }
var shown = [];
function showResearch(id) { shown.push(id); }
var postAnswer = null;
function post(path, body) { posted.push(path + " " + JSON.stringify(body)); return postAnswer || Promise.resolve({ job: "x", started: true }); }
var gets = 0, threadsAnswer = { threads: [] }, topicsAnswer = { topics: [] }, managerAnswer = null, topicsInfo = null;
function get(path) { gets++; return Promise.resolve(path.indexOf("/api/topics") === 0 ? topicsAnswer : path.indexOf("/api/manager/") === 0 ? managerAnswer : threadsAnswer); }
function drawTopics() {}
var queued = [];
function setTimeout(f, ms) { timers.push(ms); queued.push(f); return queued.length; }
function clearTimeout() {}
var mgr = { job: null, data: null, seq: 0, epoch: 0, sending: false, stuck: false, timer: null, left: 0, before: 0, expect: 0, retry: null, topic: null, want: null, newTopic: false };
`;
const code = helpers + ["timeLeft", "proposalBox", "nextStepsBox", "continueCard", "newTopicCard", "renderManager", "sendTurn", "pollManager", "loadManager"].map(grab).join("\n");
const ctx = vm.createContext({ Math, String, Array, JSON, Object, Promise });
vm.runInContext(code, ctx);
const run = (s) => vm.runInContext(s, ctx);
const out = {};
const setTimeout2 = global.setTimeout;
const D = (over) => Object.assign({ job: "j20261126_023857_708b", state: "OPEN", max_usd: 0.2, spent_usd: 0.0004, expires_in_s: 43189, busy: false, conversation: [] }, over);
const P = { route: "prd", repo: "ledger-cli", text: "Tambah <b>ringkasan</b>", why: "alasan <i>x</i>" };
const CONV = [{ from: "human", n: 0, text: "ide <b>x</b>" }, { from: "manager", n: 1, source: "manager", say: "ok <script>", propose: P }, { from: "manager", n: 2, say: "tanya", propose: { route: "ask", repo: null, text: "", why: "" } },
  { from: "manager", n: 3, say: "tidak bisa", propose: { route: "none", repo: null, text: "", why: "" } }, { from: "manager", n: 4, say: "riset", propose: { route: "research", repo: null, text: "Bandingkan dua pustaka", why: "w" } },
  { from: "manager", n: 5, say: "gagal", error: "unusable", propose: null }];
run("mgr.job = null; mgr.data = null; mgr.expect = 0; renderManager();"); out.none = run("html(stream)");
run("mgr.expect = 5; renderManager();"); out.starting = run("html(stream)");
run("mgr.expect = 0; mgr.job = 'j20261126_023857_708b'; mgr.data = " + JSON.stringify(D({ conversation: CONV })) + "; renderManager();"); out.open = run("html(stream)");
run("mgr.data = " + JSON.stringify(D({ busy: true })) + "; renderManager();"); out.busy = run("html(stream)");
run("mgr.data = " + JSON.stringify(D({ state: "BLOCKED", max_usd: null })) + "; renderManager();"); out.blocked = run("html(stream)");
// the buttons of the proposal of turn 1 (prd) and of turn 4 (research)
run("mgr.data = " + JSON.stringify(D({ conversation: CONV })) + "; renderManager();");
const found = [];
(function walk(n) { if (n.tag === "button") found.push(n); n.children.forEach(walk); })(run("stream"));
out.buttons = found.map((b) => b.text + (b.disabled ? "[off]" : ""));
found.filter((b) => b.text === "Prepare").forEach((b) => b.listeners.click());
out.prepared = run("prepared");
found.filter((b) => b.text === "Edit first")[0].listeners.click();
out.edit = run("JSON.stringify([modes, message.value, repoSel.value, fromProposal])");
// the no-repo prd proposal has its Prepare off
run("mgr.data = " + JSON.stringify(D({ conversation: [{ from: "manager", n: 1, say: "x", propose: Object.assign({}, P, { repo: null }) }] })) + "; renderManager();");
const f2 = []; (function walk(n) { if (n.tag === "button") f2.push(n); n.children.forEach(walk); })(run("stream"));
out.norepo = f2.map((b) => b.text + (b.disabled ? "[off]" : ""));
// F44 (SPEC_FOREMAN_ISSUE_PREPARE): an issue proposal has Prepare (with its source) and Edit first (the form filled, the source kept)
const ISSUE = { route: "issue", repo: "ledger-cli", text: "Tambah opsi --month <b>x</b>", why: "alasan <i>y</i>" };
const issueView = (pr) => { run("mgr.data = " + JSON.stringify(D({ conversation: [{ from: "manager", n: 1, say: "x", propose: pr }] })) + "; renderManager();"); const bs = []; (function walk(n) { if (n.tag === "button") bs.push(n); n.children.forEach(walk); })(run("stream")); return bs; };
const prepBefore = run("prepared.length");
run("modes.length = 0; notes.length = 0; message.value = ''; repoSel.value = ''; fromProposal = null;");
let ib = issueView(ISSUE);
out.issueButtons = ib.map((b) => b.text + (b.disabled ? "[off]" : "")); out.issueHtml = run("html(stream)");
ib.filter((b) => b.text === "Prepare")[0].listeners.click();
out.issueBodies = run("prepared.slice(" + prepBefore + ")");
run("prepared.length = " + prepBefore + ";");
ib.filter((b) => b.text === "Edit first")[0].listeners.click();
out.issueEdit = run("JSON.stringify([modes, message.value, repoSel.value, fromProposal, notes, prepared.length - " + prepBefore + "])");
run("modes.length = 0; notes.length = 0; message.value = ''; repoSel.value = ''; fromProposal = null;");
ib = issueView(Object.assign({}, ISSUE, { repo: "bulking-app" })); ib.filter((b) => b.text === "Edit first")[0].listeners.click();
out.issueUnlisted = run("JSON.stringify([modes, message.value, repoSel.value, notes, fromProposal])");
run("modes.length = 0; notes.length = 0; message.value = ''; repoSel.value = ''; fromProposal = null;");
ib = issueView(Object.assign({}, ISSUE, { repo: null })); out.issueNoRepo = ib.map((b) => b.text + (b.disabled ? "[off]" : "")); out.issueNoRepoHtml = run("html(stream)");
out.issuePrepared = run("prepared.length") - prepBefore;
// P4: the next steps are the harness's sentences, as text, with a button that only moves the person
const NS = [{ job: "j20261126_052522_fcc7", kind: "research", state: "REPORT_READY", usd: 0.105, hint: "research", text: "The research is done. Read the report in the Research view. <b>x</b>" },
  { job: "j20261126_060000_aaaa", kind: "prd", state: "AWAITING_HUMAN", usd: 0, hint: "queue", text: "The PRD waits in the Queue tab." },
  { job: "j20261126_060100_aaaa", kind: "research", state: "RESEARCHING", usd: null, hint: "wait", text: "This research job is still going: RESEARCHING." }];
run("modes.length = 0; shown.length = 0; mgr.job = 'j20261126_023857_708b'; mgr.data = " + JSON.stringify(D({ next_steps: NS })) + "; renderManager();");
out.next = run("html(stream)");
const nb = []; (function walk(n) { if (n.tag === "button") nb.push(n); n.children.forEach(walk); })(run("stream"));
out.nextButtons = nb.map((b) => b.text);
nb.filter((b) => b.text === "Open the report")[0].listeners.click(); nb.filter((b) => b.text === "Open the Queue tab")[0].listeners.click();
out.nextClicks = run("JSON.stringify([modes, shown, prepared.length, posted.length])");
run("mgr.data = " + JSON.stringify(D({ next_steps: [] })) + "; renderManager();"); out.nextNone = run("html(stream)").includes("Next steps");
// F47-C2: the offer to continue the topic is the server's own answer (can_take_turn), not the page's derivation; a refused turn is only a note
const over = (o) => { run("mgr.stuck = false; mgr.job = 'j20261126_023857_708b'; mgr.data = " + JSON.stringify(D(o)) + "; renderManager();"); return run("html(stream)").includes("Continue this topic?"); };
out.over = { healthy: over({ can_take_turn: true }), ended: over({ can_take_turn: false }), unknown: over({ can_take_turn: null }), missing: over({}), busy: over({ can_take_turn: false, busy: true }),
  expiredButTrue: over({ expires_in_s: 0, can_take_turn: true }), poorButTrue: over({ spent_usd: 0.199, can_take_turn: true }) };
run("mgr.stuck = true;"); out.over.stuck = run("mgr.data = " + JSON.stringify(D({ can_take_turn: true })) + "; renderManager(); html(stream)").includes("Continue this topic?");
out.stuckNote = run("html(stream)").includes("The last turn was refused"); out.unknownNote = over({ can_take_turn: null }) === false && run("html(stream)").includes("cannot tell whether this session");
run("mgr.stuck = false;");
// the topic: its title, its sessions, the carried head's fold and the two cards' exact bodies
const TOPIC = { id: "jT1", title: "Ekspor <b>CSV</b>", legacy: false, sessions: [{ id: "jT1", state: "BLOCKED" }, { id: "jT2", state: "OPEN" }], newest: "jT2" };
run("mgr.stuck = false; mgr.job = 'jT2'; mgr.data = " + JSON.stringify(D({ topic: TOPIC, can_take_turn: false, conversation: [{ from: "summary", n: 0, text: "kepala", carried: true, covers: [0, 1] }, { from: "human", n: 1, text: "halo" }] })) + "; renderManager();");
out.topicHtml = run("html(stream)");
const bs0 = []; (function walk(n) { if (n.tag === "button") bs0.push(n); n.children.forEach(walk); })(run("stream"));
const prepBefore2 = run("prepared.length");
bs0.filter((b) => b.text === "Continue topic")[0].listeners.click();
out.continueBody = run("prepared.slice(" + prepBefore2 + ")"); run("prepared.length = " + prepBefore2 + ";");
run("mgr.job = null; mgr.data = null; mgr.expect = 0; renderManager();");
const walkAll = (root, tag) => { const a = []; (function w(n) { if (n.tag === tag) a.push(n); n.children.forEach(w); })(root); return a; };
const nt = walkAll(run("stream"), "input")[0], ntb = walkAll(run("stream"), "button").filter((b) => b.text === "Prepare")[0];
out.newTopicInput = [nt.maxLength, nt.attrs && nt.attrs["aria-label"]];
nt.value = "  Judul topik  "; ntb.listeners.click(); nt.value = "   "; ntb.listeners.click();
out.newTopicBodies = run("prepared.slice(" + prepBefore2 + ")"); run("prepared.length = " + prepBefore2 + ";");
// F47-A: a summary entry is a closed fold of text with its label, never a foreman entry and never a proposal
run("mgr.stuck = false; mgr.job = 'j20261126_023857_708b'; mgr.data = " + JSON.stringify(D({ conversation: [{ from: "human", n: 0, text: "halo" }, { from: "summary", n: 1, text: "Fakta: repo <b>ledger-cli</b>", covers: [0, 1] }, { from: "manager", n: 2, say: "oke", propose: null }] })) + "; renderManager();");
out.summaryHtml = run("html(stream)");
// sendTurn
run("posted.length = 0; notes.length = 0; mgr.job = null; mgr.data = null; message.value = 'halo'; sendTurn();"); out.sendNoSession = run("JSON.stringify([posted, notes])");
run("posted.length = 0; notes.length = 0; mgr.job = 'j20261126_023857_708b'; mgr.data = " + JSON.stringify(D({ busy: true })) + "; sendTurn();"); out.sendBusy = run("JSON.stringify([posted, notes])");
run("posted.length = 0; notes.length = 0; mgr.data = " + JSON.stringify(D({ state: "BLOCKED" })) + "; sendTurn();"); out.sendEnded = run("JSON.stringify([posted, notes])");
run("posted.length = 0; notes.length = 0; mgr.data = " + JSON.stringify(D()) + "; message.value = '   '; sendTurn();"); out.sendEmpty = run("JSON.stringify([posted, notes])");
run("posted.length = 0; notes.length = 0; message.value = 'halo mandor'; mgr.sending = false; mgr.timer = null; sendTurn();");
setTimeout(() => {
  out.sendOk = run("JSON.stringify([posted, notes, message.value, mgr.left, mgr.timer !== null])");
  out.timeLeft = run("[timeLeft(43189), timeLeft(60), timeLeft(null), timeLeft('x')].join('|')");
  run("posted.length = 0; notes.length = 0; mgr.job = 'j20261126_023857_708b'; mgr.data = " + JSON.stringify(D()) + "; message.value = 'halo lagi'; mgr.timer = null; mgr.sending = false; mgr.stuck = false; postAnswer = Promise.reject(Object.assign(new Error('the session is busy'), { answered: true })); sendTurn();");
  setTimeout(() => {
    out.sendRefused = run("JSON.stringify([posted, notes, message.value, mgr.stuck])");
    // leaving the mode while a turn is in flight: nothing is drawn, the box is the person's, no polling starts
    run("mgr.job = 'j20261126_023857_708b'; mgr.data = " + JSON.stringify(D()) + "; mgr.sending = false; mgr.timer = null; mgr.stuck = false; mode = 'manager'; message.value = 'tulis'; postAnswer = null; timers.length = 0; sendTurn(); mode = 'research'; mgr.epoch++; message.value = 'form lain';");
    setTimeout(() => {
      out.leave = run("JSON.stringify([message.value, mgr.timer, timers.length, mgr.sending])");
      // the poll stops at its bound, and when the answer is in; the session search is bounded
      run("mode = 'manager'; mgr.job = 'j'; mgr.data = " + JSON.stringify(D({ conversation: [{ from: "human", n: 0 }, { from: "manager", n: 1 }] })) + "; mgr.before = 0; mgr.left = 5; gets = 0; pollManager();"); out.pollDone = run("[gets, mgr.timer].join('|')");
      run("mgr.data = " + JSON.stringify(D({ conversation: [{ from: "human", n: 0 }] })) + "; mgr.before = 0; mgr.left = 3; gets = 0; queued.length = 0; pollManager();");
      for (let i = 0; i < 10 && run("queued.length"); i++) { run("queued.shift()")(); }
      out.pollBound = run("[gets, mgr.timer].join('|')");
      // after a compaction a turn adds THREE entries (summary, human, foreman): the poll waits for the foreman's own entry, not for a count
      run("mgr.data = " + JSON.stringify(D({ conversation: [{ from: "human", n: 0 }, { from: "manager", n: 1 }, { from: "summary", n: 2 }, { from: "human", n: 3 }] })) + "; mgr.before = 2; mgr.left = 5; gets = 0; queued.length = 0; mgr.timer = null; pollManager();");
      out.pollSummaryWaits = run("[gets, mgr.timer !== null].join('|')");
      run("mgr.data = " + JSON.stringify(D({ conversation: [{ from: "human", n: 0 }, { from: "manager", n: 1 }, { from: "summary", n: 2 }, { from: "human", n: 3 }, { from: "manager", n: 4 }] })) + "; mgr.before = 2; mgr.left = 5; gets = 0; queued.length = 0; mgr.timer = null; pollManager();");
      out.pollSummaryDone = run("[gets, mgr.timer].join('|')");
run("mode = 'manager'; mgr.job = 'j20261126_023857_708b'; notes.length = 0; posted.length = 0; mgr.sending = false; mgr.timer = null; mgr.epoch++; mgr.data = " + JSON.stringify(D()) + "; message.value = 'satu'; sendTurn(); sendTurn(); mgr.epoch++;"); out.double = run("JSON.stringify([posted.length, notes[notes.length - 1]])");
      run("mgr.left = 0; mgr.expect = 12; mgr.retry = null; mgr.seq = 0; gets = 0; queued.length = 0; loadManager();");
      let rounds = 0;
      (function step() { setTimeout2(() => { if (run("queued.length") && rounds < 40) { rounds++; run("queued.shift()")(); step(); } else { out.search = run("[gets, mgr.expect].join('|')"); scenarios(); } }, 5); })();
    }, 20);
  }, 20);
}, 20);

function scenarios() {                                  // which topic and session loadManager shows (the server's list, the person's choice, a session just confirmed)
  const topics = [{ id: "jT1", title: "Lama", sessions: 1, latest: { id: "jT1", state: "BLOCKED", can_take_turn: false } }, { id: "jT2", title: "Baru", sessions: 2, latest: { id: "jT3", state: "OPEN", can_take_turn: true } },
                  { id: "jT4", title: "Terbaru tapi habis", sessions: 1, latest: { id: "jT4", state: "BLOCKED", can_take_turn: false } }];
  const pick = (setup) => new Promise((resolve) => { run("mode = 'manager'; mgr.job = null; mgr.data = null; mgr.topic = null; mgr.want = null; mgr.newTopic = false; mgr.expect = 0; mgr.seq = 0; mgr.stuck = false; " + setup + "; loadManager();"); setTimeout2(() => resolve(run("JSON.stringify([mgr.topic, mgr.job, mgr.want, mgr.newTopic, mgr.expect])")), 15); });
  run("topicsAnswer = " + JSON.stringify({ topics }) + "; managerAnswer = " + JSON.stringify(D({ can_take_turn: true })));
  (async () => {
    out.pickDefault = await pick("");                                                   // no choice: the newest topic that can take a turn, not the newest
    out.pickChosen = await pick("mgr.topic = 'jT1'");                                  // the person chose one
    out.pickGone = await pick("mgr.topic = 'jNOPE'");                                  // a chosen topic that is no longer listed: the default again
    out.pickWant = await pick("mgr.want = 'jT3'; mgr.expect = 5");                      // a session just confirmed: the topic whose newest session it is
    out.pickWantLate = await pick("mgr.want = 'jLATER'; mgr.expect = 5");              // not listed yet: nothing is picked, it is waited for
    out.pickNew = await pick("mgr.newTopic = true");                                    // New topic: nothing is picked, the card shows
    out.newCard = run("html(stream)").includes("New topic");
    run("topicsAnswer = { topics: [] };");
    out.pickEmpty = await pick("");
    console.log(JSON.stringify(out));
  })();
}
