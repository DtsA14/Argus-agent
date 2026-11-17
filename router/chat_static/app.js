"use strict";
// Argus chat, C1 read only and C2b issue mode (docs/reviews/SPEC_CHAT_APP.md). The only writes are POST /api/prepare (spends nothing)
// and POST /api/confirm with the token the server gave and nothing else; the server rebuilds the card and holds the argv. Every string from the server is put on the page with
// textContent; there is no HTML sink, no eval, no storage, no worker and no message listener (the build scan tests it).
(function () {
  var stream = document.getElementById("stream");
  var list = document.getElementById("threads");
  var summary = document.getElementById("summary");
  var skipped = document.getElementById("skipped");
  var panel = document.getElementById("panel");
  var query = document.getElementById("query");
  var threads = [];
  var current = null;

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) { e.className = cls; }
    if (text !== undefined && text !== null) { e.textContent = String(text); }
    return e;
  }
  function clear(node) { while (node.firstChild) { node.removeChild(node.firstChild); } }
  function usd(n) { return typeof n === "number" ? "$" + n.toFixed(4) : "-"; }
  function stateClass(s) {
    if (s === "APPLIED" || s === "DONE" || s === "REVIEW_READY") { return "ok"; }
    if (/FAILED|REJECTED|ABANDONED|INVALID/.test(String(s))) { return "bad"; }
    return "warn";
  }
  function get(path) {
    return fetch(path, { credentials: "omit", cache: "no-store", headers: { "Accept": "application/json" } })
      .then(function (r) { if (!r.ok) { throw new Error("HTTP " + r.status); } return r.json(); });
  }
  var VIEWER = "http://localhost:8710/jobs/";
  // The one link the page makes (SPEC_CHAT_APP 11.2, 11.7): the server's viewer URL, accepted only as the viewer's job page
  // for an id of plain characters; never built from text of a job, an issue or a report.
  function viewerLink(url) {
    if (typeof url !== "string" || url.indexOf(VIEWER) !== 0 || !/^[a-z0-9_]+$/.test(url.slice(VIEWER.length))) { return null; }
    var a = el("a", "link", "Buka di viewer");
    a.rel = "noopener noreferrer";
    a.href = url;
    a.addEventListener("click", function (e) { e.stopPropagation(); });
    return a;
  }
  function jobCard(t, spent) {
    var c = el("article", "card");
    c.appendChild(el("h2", "mono", t.title || t.id));
    var row = el("div", "row");
    row.appendChild(el("span", "state " + stateClass(t.state), t.state));
    row.appendChild(el("span", null, t.kind));
    row.appendChild(el("span", null, t.created_at));
    row.appendChild(el("span", null, spent !== undefined ? usd(spent) + " dari " + usd(t.max_usd) : usd(t.stages_usd) + " tahap selesai, batas " + usd(t.max_usd)));
    c.appendChild(row);
    var link = viewerLink(t.viewer);
    if (link) { c.appendChild(link); }
    return c;
  }
  function renderList() {
    var q = query.value.trim().toLowerCase();
    clear(list);
    threads.forEach(function (t) {
      var hay = [t.id, t.state, t.title, t.kind].join(" ").toLowerCase();
      if (q && hay.indexOf(q) === -1) { return; }
      var li = el("li");
      var b = el("button", null, (t.title || t.id) + " · " + t.state);
      b.type = "button";
      if (current === t.id) { b.setAttribute("aria-current", "true"); }
      b.addEventListener("click", function () { if (mode !== "status") { setMode("status"); } open(t.id); panel.classList.remove("open"); });
      li.appendChild(b);
      list.appendChild(li);
    });
  }
  function renderOverview() {
    clear(stream);
    var q = query.value.trim().toLowerCase();
    var shown = threads.filter(function (t) { return !q || [t.id, t.state, t.title, t.kind].join(" ").toLowerCase().indexOf(q) !== -1; });
    if (!shown.length) { stream.appendChild(el("p", "muted", "Tidak ada job yang cocok.")); }
    shown.slice(0, 20).forEach(function (t) {
      var c = jobCard(t);
      c.addEventListener("click", function () { open(t.id); });
      stream.appendChild(c);
    });
  }
  function open(id) {
    current = id;
    renderList();
    get("/api/threads/" + encodeURIComponent(id)).then(function (d) {
      clear(stream);
      var c = jobCard(d.job, d.spent_usd);
      c.appendChild(el("p", "muted mono", d.job.id));
      var rows = Object.keys(d.job.stages || {}).sort();
      if (rows.length) {
        var tb = el("table");
        rows.forEach(function (k) {
          var s = d.job.stages[k];
          var tr = el("tr");
          [k, s.kind, s.status, s.usd === null || s.usd === undefined ? "-" : usd(s.usd)].forEach(function (v) { tr.appendChild(el("td", null, v)); });
          tb.appendChild(tr);
        });
        c.appendChild(tb);
      }
      stream.appendChild(c);
      var back = el("button", null, "Semua job");
      back.type = "button";
      back.addEventListener("click", function () { current = null; renderList(); renderOverview(); });
      stream.appendChild(back);
    }).catch(function () { clear(stream); stream.appendChild(el("p", "muted", "Job tidak dapat dibaca.")); });
  }
  function load() {
    get("/api/threads").then(function (d) {
      threads = d.threads || [];
      skipped.textContent = d.skipped ? d.skipped + " job tidak dapat ditampilkan" : "";
      summary.textContent = threads.length + " job";
      renderList();
      if (current === null && mode === "status") { renderOverview(); }
    }).catch(function () { summary.textContent = "gagal memuat"; });
  }

  // ---- C2b: issue mode. The card is the server's, shown field by field as text; Confirm sends only the token. -------------
  var mode = "status";
  var issueForm = document.getElementById("issue-form");
  var repoSel = document.getElementById("repo");
  var message = document.getElementById("message");
  var issues = [];
  var openIssue = null;
  var busy = false;
  var slot = document.getElementById("slot");
  var pending = null;                                   // the one card that may be live; a new one settles and removes the old
  function post(path, body) {
    return fetch(path, { method: "POST", credentials: "omit", cache: "no-store",
      headers: { "Content-Type": "application/json", "Accept": "application/json" }, body: JSON.stringify(body) })
      .then(function (r) {
        return r.json().catch(function () { return {}; }).then(function (j) {
          if (!r.ok) { var err = new Error(j && j.refused ? String(j.refused) : "HTTP " + r.status); err.answered = true; throw err; }
          return j;
        });
      });
  }
  var LABELS = [["repo", "Repo"], ["job", "Job"], ["state", "State"], ["environment", "Lingkungan"], ["commit", "Commit"],
    ["turn", "Giliran"], ["turn_cap_usd", "Batas giliran"], ["job_cap_usd", "Batas job"], ["reason", "Alasan"],
    ["profile", "Profil"], ["stage_models", "Model"], ["stage_caps", "Batas tahap"], ["web", "Web"], ["data_sent", "Data keluar"],
    ["free_models", "Model gratis"], ["runs_code", "Kode contoh"], ["kind", "Jenis"], ["job_title", "Judul"], ["sha12", "Draf"], ["spent_usd", "Biaya"], ["cap_usd", "Batas"]];
  var USD_KEYS = { turn_cap_usd: 1, job_cap_usd: 1, spent_usd: 1, cap_usd: 1 };
  function fact(parent, label, value) {
    var p = el("p", "fact");
    p.appendChild(el("b", null, label + ": "));
    p.appendChild(document.createTextNode(String(value)));
    parent.appendChild(p);
  }
  function renderCard(prep, done) {
    var card = prep.card;
    var c = el("article", "card");
    c.appendChild(el("h2", null, card.title));
    LABELS.forEach(function (kv) {
      var v = card[kv[0]];
      if (v === undefined || v === null || v === "") { return; }
      fact(c, kv[1], USD_KEYS[kv[0]] ? usd(v) : v);
    });
    if (card.issue_title) { fact(c, "Judul issue", card.issue_title); }
    if (card.message) { c.appendChild(el("p", "msg human", card.message)); }
    if (card.issue_text) { c.appendChild(el("p", "msg", card.issue_text)); }
    c.appendChild(el("p", "note", "Eksposur biaya yang dihitung: " + usd(prep.exposure_usd) + ". Tidak ada yang berjalan sebelum Konfirmasi."));
    var row = el("div", "actions");
    var ok = el("button", "go", "Konfirmasi");
    ok.type = "button";
    ok.disabled = true;                                 // armed after the server's minimum delay; never the default of a key press
    var no = el("button", null, "Batal");
    no.type = "button";
    var armed = setTimeout(function () { ok.disabled = false; }, Math.ceil((prep.min_delay_s || 1) * 1000) + 300);
    var expire = setTimeout(function () { ok.disabled = true; c.appendChild(el("p", "note", "Kartu kedaluwarsa: siapkan lagi.")); }, ((prep.expires_s || 300) - 5) * 1000);
    function settle() { clearTimeout(armed); clearTimeout(expire); ok.disabled = true; no.disabled = true; }
    no.addEventListener("click", function () { removeCard(c); });
    c.settle = settle;
    ok.addEventListener("click", function () {
      if (ok.disabled) { return; }
      ok.disabled = true;
      c.sent = true;
      no.disabled = true;                               // once sent, the server may run it: no Batal that only looks like one
      post("/api/confirm", { token: prep.token }).then(function (r) {
        c.sent = false;
        settle();
        clear(c);
        c.appendChild(el("h2", null, "Dijalankan"));
        if (r.job) { fact(c, "Job", r.job); }
        c.appendChild(el("p", "note", card.action === "research_new" ? "Hasilnya ada di daftar riset." : (card.action.indexOf("job_") === 0 ? "Keputusan tercatat; keadaan job ada di daftar keputusan." : "Hasilnya ada di daftar issue.")));
        var close = el("button", null, "Tutup");
        close.type = "button";
        close.addEventListener("click", function () { removeCard(c); });
        c.appendChild(close);
        done(r);
      }).catch(function (e) {
        c.sent = false;
        settle();
        if (e.answered) {
          c.appendChild(el("p", "note", "Ditolak: " + e.message));
          no.disabled = false;
        } else {                                        // no answer: the server may have run it; do not prepare the same thing again blind
          c.appendChild(el("p", "note", "Status tidak diketahui, mungkin sudah berjalan. Cek daftar " + (card.action === "research_new" ? "riset" : (card.action.indexOf("job_") === 0 ? "keputusan" : "issue")) + " sebelum mencoba lagi."));
          no.disabled = false;
          if (card.action === "research_new") { loadResearch(); }
          else if (card.action.indexOf("job_") === 0) { loadDecisions(); }
          else {
            loadIssues();
            if (mode === "issue" && openIssue !== null) { showIssue(openIssue, true); }
          }
        }
      });
    });
    row.appendChild(ok);
    row.appendChild(no);
    c.appendChild(row);
    return c;
  }
  function removeCard(c) {                              // a button acts on its own card, never on whichever card is current
    c.settle();
    if (c.parentNode) { c.parentNode.removeChild(c); }
    if (pending === c) { pending = null; }
  }
  function dropPending() {
    if (pending && pending.sent) { return; }               // a confirm is on its way: the card stays until the server answers
    if (pending) { pending.settle(); if (pending.parentNode) { pending.parentNode.removeChild(pending); } pending = null; }
  }
  function showNote(text) {
    dropPending();
    var c = el("article", "card");
    c.appendChild(el("p", "note", text));
    c.settle = function () {};
    pending = c;
    slot.appendChild(c);
  }
  function prepare(body) {
    if (busy || (pending && pending.sent)) { return; }
    busy = true;
    var ctx = { mode: mode, open: openIssue };
    post("/api/prepare", body).then(function (prep) {
      busy = false;
      if (pending && pending.sent) { return; }          // a confirm went out meanwhile: this card is not shown, its token lapses
      if (mode !== ctx.mode || openIssue !== ctx.open) { return; }     // the user moved on while it was prepared: the token just lapses
      dropPending();
      var c = renderCard(prep, function (r) {
        message.value = "";
        if (mode === "research") { loadResearch(); if (r.job) { showResearch(r.job); } return; }
        if (mode === "decide") { if (openDecision !== null) { showDecision(openDecision); } else { loadDecisions(); } return; }
        loadIssues();
        if (r.job && mode === "issue") { showIssue(r.job, true); }
      });
      pending = c;
      slot.appendChild(c);
      c.scrollIntoView({ block: "nearest" });
    }).catch(function (e) {
      busy = false;
      if (pending && pending.sent) { return; }
      showNote("Tidak bisa disiapkan: " + e.message);
    });
  }
  function issueCard(t) {
    var c = el("article", "card");
    c.appendChild(el("h2", null, t.title || t.id));
    var row = el("div", "row");
    row.appendChild(el("span", "state " + stateClass(t.state), t.state));
    row.appendChild(el("span", null, t.repo));
    c.appendChild(row);
    c.addEventListener("click", function () { showIssue(t.id); });
    return c;
  }
  function renderIssues() {
    clear(stream);
    if (!issues.length) { stream.appendChild(el("p", "muted", "Belum ada issue. Tulis satu di bawah.")); }
    issues.slice(0, 20).forEach(function (t) { stream.appendChild(issueCard(t)); });
  }
  function act(label, build, cls) {
    var b = el("button", cls, label);
    b.type = "button";
    b.addEventListener("click", function () { prepare(build()); });
    return b;
  }
  function formState() {
    var r = mode === "research";
    repoSel.hidden = r || openIssue !== null;
    document.getElementById("prepare").textContent = r ? "Siapkan riset" : (openIssue !== null ? "Siapkan balasan" : "Siapkan issue baru");
    message.placeholder = r ? "Tulis pertanyaan riset (20 sampai 2000 karakter)" : "Tulis pesan";
  }
  function showIssue(id, keep) {                        // keep: the card on screen is this issue's own result or status
    if (!keep && id !== openIssue) { dropPending(); }
    get("/api/issues/" + encodeURIComponent(id)).then(function (d) {
      openIssue = id;
      formState();
      clear(stream);
      var c = el("article", "card");
      c.appendChild(el("h2", "mono", d.id));
      var row = el("div", "row");
      row.appendChild(el("span", "state " + stateClass(d.state), d.state));
      row.appendChild(el("span", null, d.repo));
      row.appendChild(el("span", null, "giliran " + d.turn));
      c.appendChild(row);
      if (d.busy) { c.appendChild(el("p", "note", "Penulis masih bekerja.")); }
      (d.conversation || []).forEach(function (m) {
        c.appendChild(el("p", "msg " + (m.from === "human" ? "human" : ""), (m.from === "human" ? "Anda: " : "Penulis: ") + m.text));
        (m.questions || []).forEach(function (q) { c.appendChild(el("p", "msg", "? " + q)); });
      });
      if (d.issue) { c.appendChild(el("h2", null, "Issue")); c.appendChild(el("p", "msg", d.issue.text)); }
      if (d.examples) { c.appendChild(el("h2", null, "Contoh")); c.appendChild(exampleBlock(d.examples)); }
      if (d.last_run) { c.appendChild(el("p", "muted", d.last_run.line)); }
      var link = viewerLink(d.handoff ? VIEWER + d.handoff : null);
      if (link) { c.appendChild(link); }
      var acts = el("div", "actions");
      if (!d.busy) {
        acts.appendChild(act("Balas", function () { return { action: "issue_reply", job: d.id, message: message.value }; }));
        if (d.issue) { acts.appendChild(act("Siapkan Start", function () { return { action: "issue_start", job: d.id }; }, "go")); }
        acts.appendChild(act("Buang", function () { return { action: "issue_abandon", job: d.id, reason: message.value }; }));
      }
      c.appendChild(acts);
      stream.appendChild(c);
      var back = el("button", null, "Semua issue");
      back.type = "button";
      back.addEventListener("click", function () { dropPending(); openIssue = null; formState(); renderIssues(); });
      stream.appendChild(back);
    }).catch(function () { clear(stream); stream.appendChild(el("p", "muted", "Issue tidak dapat dibaca.")); });
  }
  function loadIssues() {
    get("/api/issues").then(function (d) {
      issues = d.issues || [];
      var keep = repoSel.value;
      clear(repoSel);
      (d.repos || []).forEach(function (r) { var o = el("option", null, r); o.value = r; repoSel.appendChild(o); });
      if (keep) { repoSel.value = keep; }
      if (mode === "issue" && openIssue === null) { renderIssues(); }
    }).catch(function () { summary.textContent = "gagal memuat issue"; });
  }
  // ---- C3: research mode. A report is text from the web and a model: it goes on the page as text under the server's banner. ----------
  var researchJobs = [];
  var openResearch = null;
  var researchSeq = 0;                                  // a draw belongs to the last request: an older answer draws nothing
  var researchLive = false;                             // the open job can still change, so the poll redraws it
  function researchCard(t) {
    var c = el("article", "card");
    c.appendChild(el("h2", null, t.title || t.id));
    var row = el("div", "row");
    row.appendChild(el("span", "state " + stateClass(t.state), t.state));
    if (t.busy) { row.appendChild(el("span", null, "berjalan")); }
    c.appendChild(row);
    c.addEventListener("click", function () { showResearch(t.id); });
    return c;
  }
  function renderResearchList() {
    clear(stream);
    if (!researchJobs.length) { stream.appendChild(el("p", "muted", "Belum ada riset. Tulis pertanyaan di bawah.")); }
    researchJobs.slice(0, 20).forEach(function (t) { stream.appendChild(researchCard(t)); });
  }
  function loadResearch() {
    get("/api/research").then(function (d) {
      researchJobs = d.research || [];
      if (mode === "research" && openResearch === null) { renderResearchList(); }
    }).catch(function () { summary.textContent = "gagal memuat riset"; });
  }
  function showResearch(id) {
    var my = ++researchSeq;
    openResearch = id;
    get("/api/research/" + encodeURIComponent(id)).then(function (d) {
      if (mode !== "research" || my !== researchSeq) { return; }
      researchLive = !!(d.busy || d.state === "starting" || d.stalled);
      clear(stream);
      var c = el("article", "card");
      c.appendChild(el("h2", "mono", d.id));
      var row = el("div", "row");
      row.appendChild(el("span", "state " + stateClass(d.state), d.state));
      if (d.busy) { row.appendChild(el("span", null, "berjalan")); }
      if (typeof d.spent_usd === "number" || d.spent_usd === null) { row.appendChild(el("span", null, usd(d.spent_usd) + " dari " + usd(d.cap_usd))); }
      c.appendChild(row);
      if (d.state === "starting") { c.appendChild(el("p", "note", "Riset sedang dimulai.")); }
      if (d.state === "refused") { c.appendChild(el("p", "note", "Ditolak sebelum dimulai: " + d.line)); }
      if (d.stalled) { c.appendChild(el("p", "note", "Tidak ada proses dari chat ini yang menjalankannya: berjalan dari terminal atau terhenti. Cek argus status " + d.id + ".")); }
      if (d.question) { c.appendChild(el("p", "msg human", "Pertanyaan: " + d.question)); }
      if (d.report) {
        var n = d.counts || {};
        var tally = " " + (n.SUPPORTED || 0) + " didukung, " + (n.PARTIAL || 0) + " sebagian, " + (n.UNSUPPORTED || 0) + " tidak didukung.";
        c.appendChild(el("p", "note", d.checked ? "Sudah dicek oleh e1 (hanya menandai klaim):" + tally : "Belum dicek oleh e1."));
        c.appendChild(el("p", "note", d.banner));
        if (d.report.withheld) { c.appendChild(el("p", "note", d.report.withheld)); }
        else {
          if (d.report.cut) { c.appendChild(el("p", "note", "Dipotong: sumber di akhir bisa hilang.")); }
          c.appendChild(el("pre", "report", d.report.text));
        }
      }
      var link = viewerLink(d.state === "starting" || d.state === "refused" ? null : VIEWER + d.id);
      if (link) { c.appendChild(link); }
      stream.appendChild(c);
      var back = el("button", null, "Semua riset");
      back.type = "button";
      back.addEventListener("click", function () { researchSeq++; openResearch = null; renderResearchList(); loadResearch(); });
      stream.appendChild(back);
    }).catch(function () { clear(stream); stream.appendChild(el("p", "muted", "Riset tidak dapat dibaca.")); });
  }
  // ---- C4: decisions. Reject and abandon of a job through the same prepare and confirm; no draft is accepted here. ------------------------
  var decisionRows = [];
  var openDecision = null;                              // a job opened from the Decide link: its card replaces the list
  function decideCard(r) {
    var c = el("article", "card");
    c.appendChild(el("h2", null, r.title || r.id));
    var row = el("div", "row");
    row.appendChild(el("span", "state " + stateClass(r.state), r.state));
    if (r.kind) { row.appendChild(el("span", null, r.kind)); }
    if (typeof r.spent_usd === "number") { row.appendChild(el("span", null, usd(r.spent_usd) + " dari " + usd(r.cap_usd))); }
    c.appendChild(row);
    c.appendChild(el("p", "muted mono", r.id));
    c.appendChild(el("p", "note", r.sha12 ? "Draf " + r.sha12 + ". Baca draf di viewer sebelum memutuskan." : "Belum ada draf."));
    if (r.draft_problem) { c.appendChild(el("p", "note", "Draf tidak dapat dibaca: " + r.draft_problem)); }
    if (r.busy) { c.appendChild(el("p", "note", "Chat ini masih menjalankan sesuatu pada job ini.")); }
    var link = viewerLink(VIEWER + r.id);
    if (link) { c.appendChild(link); }
    var acts = el("div", "actions");
    if (!r.busy && r.allowed && r.allowed.length) {
      var why = el("input", "reason");                  // the reason is in the card, above its buttons, never in a shared box
      why.type = "text";
      why.maxLength = 300;
      why.autocomplete = "off";
      why.placeholder = "Alasan (wajib untuk Reject)";
      why.setAttribute("aria-label", "Alasan");
      c.appendChild(why);
      var hint = el("p", "note");
      hint.setAttribute("role", "status");
      c.appendChild(hint);
      var decide = function (label, action, needReason) {
        var b = el("button", null, label);
        b.type = "button";
        b.addEventListener("click", function () {
          if (needReason && why.value.trim() === "") { hint.textContent = "Isi alasan dulu di kolom di atas tombol."; return; }
          hint.textContent = "";
          prepare({ action: action, job: r.id, sha: r.sha12 || "", reason: why.value });
        });
        acts.appendChild(b);
      };
      if (r.allowed.indexOf("reject") !== -1) { decide("Reject", "job_reject", true); }
      if (r.allowed.indexOf("abandon") !== -1) { decide("Abandon", "job_abandon", false); }
    }
    c.appendChild(acts);
    return c;
  }
  function reasonTyped() {                              // the poll must not wipe a reason that is being typed
    return Array.prototype.some.call(document.querySelectorAll("#stream input.reason"), function (i) {
      return i.value.trim() !== "" || i === document.activeElement;
    });
  }
  function renderDecisions() {
    clear(stream);
    if (!decisionRows.length) { stream.appendChild(el("p", "muted", "Tidak ada job yang menunggu keputusan.")); }
    decisionRows.forEach(function (r) { stream.appendChild(decideCard(r)); });
  }
  function loadDecisions() {
    get("/api/decisions").then(function (d) {
      decisionRows = d.decisions || [];
      if (mode === "decide" && openDecision === null) { renderDecisions(); }
    }).catch(function () { summary.textContent = "gagal memuat keputusan"; });
  }
  function showDecision(id) {                           // the Decide link of the viewer: opens a card, chooses and prepares nothing
    openDecision = id;
    get("/api/decisions/" + encodeURIComponent(id)).then(function (d) {
      if (mode !== "decide" || openDecision !== id) { return; }
      if (d.kind === "issue") { setMode("issue"); showIssue(id); return; }
      clear(stream);
      stream.appendChild(decideCard(d));
      var back = el("button", null, "Semua keputusan");
      back.type = "button";
      back.addEventListener("click", function () { openDecision = null; renderDecisions(); loadDecisions(); });
      stream.appendChild(back);
    }).catch(function () { clear(stream); stream.appendChild(el("p", "muted", "Job tidak dapat dibaca.")); });
  }
  // ---- T3: the plan card (SPEC_KARTU_SETUJU), read only
  var TIER_TITLE = { same: "Yang tidak boleh berubah", whatif: "Kalau ... maka", after: "Yang berubah" };
  function planExample(e) {
    var d = el("div", "ex");
    d.appendChild(el("p", "small", e.id));
    if (e.says) { modelLine(d, e.says); }
    if (!e.showable) { d.appendChild(el("p", "note", e.why || "contoh ini tidak bisa ditampilkan sebagai angka")); }
    if (e.call) { d.appendChild(el("p", "small", "fungsi: " + e.call)); }
    (e.assumptions || []).forEach(function (a) { d.appendChild(el("pre", "code", "Andaikan: " + a.name + " = " + a.shown)); });
    (e.inputs || []).forEach(function (i) { d.appendChild(el("pre", "code", "masukan " + i.name + " = " + i.shown)); });
    if (e.output && e.output.raises) { d.appendChild(el("pre", "code", "keluaran: " + e.output.shown)); }
    else if (e.output) { e.output.forEach(function (o) { d.appendChild(el("pre", "code", "keluaran" + (o.label ? " " + o.label : "") + " = " + o.shown)); }); }
    if (e.proof) { d.appendChild(el("pre", "code", "Mesin: " + e.proof.wording)); }
    return d;
  }
  function planItem(it, dim) {
    var c = el("article", "card" + (dim ? " stale" : ""));
    c.appendChild(el("h2", null, "Issue " + it.n));
    if (it.title) { modelLine(c, it.title, "msg"); }
    if (it.warning) { c.appendChild(el("p", "note", it.warning)); }
    if (it.no_examples) { modelLine(c, "tanpa contoh: " + it.no_examples); }
    if (it.why) { c.appendChild(el("p", "small", it.why)); }
    if (it.examples && it.examples.withheld) { c.appendChild(el("p", "note", "contoh ditahan harness")); return c; }
    ["same", "whatif", "after"].forEach(function (tier) {
      var group = (it.examples || []).filter(function (e) { return e.tier === tier; });
      if (!group.length) { return; }
      c.appendChild(el("h2", null, TIER_TITLE[tier]));
      group.forEach(function (e) { c.appendChild(planExample(e)); });
    });
    return c;
  }
  function showPlan(id) {
    var seq = ++cardSeq;
    openCard = id;
    get("/api/approve/prd/" + encodeURIComponent(id)).then(function (d) {
      if (seq !== cardSeq || mode !== "cards") { return; }
      clear(stream);
      var dim = !!(d.stale || d.superseded);
      var head = el("article", "card" + (dim ? " stale" : ""));
      head.appendChild(el("h2", null, "Kartu rencana"));
      var row = el("div", "row");
      row.appendChild(el("span", "mono", d.id));
      row.appendChild(el("span", "state " + stateClass(d.state), String(d.state)));
      if (d.repo) { row.appendChild(el("span", null, d.repo)); }
      if (d.turn) { row.appendChild(el("span", null, "giliran " + d.turn)); }
      head.appendChild(row);
      if (d.stale) { head.appendChild(el("p", "note", "Hasil di commit lama: repo bergeser sejak folder ini ditulis.")); }
      if (d.superseded) { head.appendChild(el("p", "note", "Folder ini sudah digantikan giliran berikutnya.")); }
      if (d.why) { head.appendChild(el("p", "note", d.why)); }
      if (d.request) {
        head.appendChild(el("span", "tag", d.request_by === "chat" ? "permintaan, ditulis lewat chat:" : "permintaan (pembuat tidak tercatat):"));
        head.appendChild(el("p", "msg", d.request));
        if (d.request_truncated) { head.appendChild(el("p", "note", "permintaan dipotong")); }
      }
      if (d.summary) { modelLine(head, d.summary, "msg"); } else if (d.summary_why) { head.appendChild(el("p", "note", d.summary_why)); }
      head.appendChild(el("p", "small", d.issue_count + " issue"));
      if (d.cost) {
        var ref = d.cost.reference ? "; acuan: median " + usd(d.cost.reference.median) + " dari " + d.cost.reference.n + " " + d.cost.reference.of : "; acuan: belum cukup data";
        head.appendChild(el("p", "small", "biaya job " + usd(d.cost.spent) + "; batas antrean untuk " + d.issue_count + " issue " + usd(d.cost.proposed) + (d.cost.proposed_each !== null && d.cost.proposed_each !== undefined ? " (" + usd(d.cost.proposed_each) + " per issue)" : "") + ref + " (acuan: satu job)"));
      }
      if (d.defects) { head.appendChild(el("p", "note", d.defects + " contoh tidak bisa ditampilkan sebagai angka (kartu cacat)")); }
      head.appendChild(el("p", "small", d.fixed_line));
      stream.appendChild(head);
      (d.items || []).forEach(function (it) { stream.appendChild(planItem(it, dim)); });
      var tech = el("button", null, "Kartu teknis");
      tech.type = "button";
      tech.addEventListener("click", function () { showCard("prd", id); });
      stream.appendChild(tech);
      var back = el("button", null, "Semua kartu");
      back.type = "button";
      back.addEventListener("click", function () { cardSeq++; openCard = null; renderCards(); loadCards(); });
      stream.appendChild(back);
    }).catch(function () {
      if (seq !== cardSeq || mode !== "cards") { return; }
      clear(stream);
      stream.appendChild(el("p", "muted", "Kartu rencana tidak dapat dibaca."));
      var back = el("button", null, "Semua kartu");
      back.type = "button";
      back.addEventListener("click", function () { cardSeq++; openCard = null; renderCards(); loadCards(); });
      stream.appendChild(back);
    });
  }
  // ---- T2: read-only cards (docs/reviews/SPEC_CHAT_CARDS.md). Every string is put on the page as text; model text carries its tag, and the
  // status line is built from the machine's fields only (id, tier, status, where). No button, no storage, no request but GET. ----------------
  var cardRows = [];
  var cardSeq = 0;
  var openCard = null;                                  // the id of the card on screen, null on the list
  var MODEL = "ditulis model";
  var PASS_NOTE = "pass: kode contoh melaporkan cocok di sandbox; kode itu ditulis model dan bisa memalsukannya. Bukan bukti bahwa aturan di prosa benar.";
  function statusClass(s) { return s === "pass" ? "ok" : (s === "fail" || s === "error" || s === "invalid" ? "bad" : "warn"); }
  function modelLine(parent, text, cls) {
    var p = el("p", cls || "small");
    p.appendChild(el("span", "tag", MODEL + ": "));
    p.appendChild(document.createTextNode(String(text)));
    parent.appendChild(p);
  }
  function resultLines(parent, title, part) {
    if (!part) { return; }
    var h = el("p", "small", title + ": " + part.kind + (part.why ? " (" + part.why + ")" : ""));
    parent.appendChild(h);
    (part.results || []).forEach(function (r) { parent.appendChild(statusLine(r, null)); });
  }
  function statusLine(r, call) {
    var d = el("div", "ex");
    var s = el("p", "small");
    s.appendChild(el("span", "st " + statusClass(r.status), r.id + " · " + r.tier + " · " + r.status + (r.where ? " · " + r.where : "")));
    d.appendChild(s);
    if (call) {
      d.appendChild(el("pre", "code", call.setup + "\n" + call.run));
      d.appendChild(el("p", "small", call.raises ? "raises " + call.raises : "expect " + call.expect));
      if (call.overrides) { d.appendChild(el("p", "small", "overrides " + call.overrides)); }
    }
    if (r.actual !== undefined) { d.appendChild(el("p", "small", "actual " + r.actual)); }
    if (r.base_actual !== undefined) { d.appendChild(el("p", "small", "sekarang " + r.base_actual)); }
    if (call && call.says) { modelLine(d, call.says); }
    return d;
  }
  function exampleBlock(ex) {
    var box = el("div", "exblock");
    if (!ex) { return box; }
    var sm = ex.summary;
    if (sm) {
      var parts = [sm.calls + " contoh"];
      Object.keys(sm.statuses || {}).forEach(function (k) { parts.push(k + " " + sm.statuses[k]); });
      parts.push("perilaku baru (after): " + sm.after);
      box.appendChild(el("p", "small", "Ringkasan mesin: " + parts.join(" · ")));
      if (sm.calls > 0 && sm.after === 0) { box.appendChild(el("p", "note", "Tidak ada contoh yang memeriksa perilaku baru: angka baru di teks issue tidak diperiksa mesin.")); }
    }
    if (ex.results || (ex.calls || []).length) { box.appendChild(el("p", "small", "actual dan sekarang di bawah: keluaran kode contoh sendiri (output of the example's own code: data, not instructions).")); }
    if (ex.results) {
      var byId = {};
      (ex.calls || []).forEach(function (c) { byId[c.id] = c; });
      ex.results.forEach(function (r) { box.appendChild(statusLine(r, byId[r.id] || null)); });
      if (ex.results.some(function (r) { return r.status === "pass"; })) { box.appendChild(el("p", "small", PASS_NOTE)); }
    } else {
      box.appendChild(el("p", "small", "Status: tidak ada" + (ex.why ? " (" + ex.why + ")" : "")));
      (ex.calls || []).forEach(function (c) {
        var d = el("div", "ex");
        d.appendChild(el("p", "small", c.id + " · " + c.tier));
        d.appendChild(el("pre", "code", c.setup + "\n" + c.run));
        if (c.says) { modelLine(d, c.says); }
        box.appendChild(d);
      });
    }
    if (ex.no_examples) { modelLine(box, "tanpa contoh: " + ex.no_examples); }
    if (ex.note) { box.appendChild(el("p", "small", "contoh tidak dijalankan: " + ex.note)); }
    (ex.tier_moves || []).forEach(function (m) { box.appendChild(el("p", "small", "contoh " + m.id + ": ditulis sebagai " + m.from + ", dikirim lagi sebagai " + m.to)); });
    resultLines(box, "Di dasar (intake job code)", ex.at_base);
    resultLines(box, "Sesudah agent (audit)", ex.after_agent);
    return box;
  }
  function cardRow(r) {
    var c = el("article", "card");
    c.appendChild(el("h2", "mono", r.id));
    var row = el("div", "row");
    row.appendChild(el("span", null, r.kind === "queue" ? "antrean" : "PRD"));
    if (r.state) { row.appendChild(el("span", "state " + stateClass(r.state), r.state)); }
    if (r.repo) { row.appendChild(el("span", null, r.repo)); }
    if (r.items !== null && r.items !== undefined) { row.appendChild(el("span", null, r.items + " item")); }
    c.appendChild(row);
    if (r.title) { c.appendChild(el("p", "small", r.title)); }                  // the human's own first message (queues: the repo's name)
    if (r.why) { c.appendChild(el("p", "note", r.why)); }
    if (!r.why) { c.addEventListener("click", function () { showCard(r.kind, r.id); }); }
    return c;
  }
  function renderCards() {
    clear(stream);
    if (!cardRows.length) { stream.appendChild(el("p", "muted", "Belum ada PRD atau antrean.")); }
    cardRows.forEach(function (r) { stream.appendChild(cardRow(r)); });
  }
  function loadCards() {
    var seq = ++cardSeq;
    get("/api/cards").then(function (d) {
      if (seq !== cardSeq) { return; }
      cardRows = d.rows || [];
      if (mode === "cards") { renderCards(); }
    }).catch(function () { summary.textContent = "gagal memuat kartu"; });
  }
  function itemCard(it, dim) {
    var c = el("article", "card" + (dim ? " stale" : ""));
    c.appendChild(el("h2", null, "Issue " + it.n));
    if (it.title && !it.text) { modelLine(c, it.title, "msg"); }          // the text starts with the title: it is not shown twice
    if (it.text) { var body = el("p", "msg", it.text); c.appendChild(el("span", "tag", MODEL + ":")); c.appendChild(body); }
    (it.touches || []).forEach(function (t) { modelLine(c, "menyentuh " + t); });
    (it.creates || []).forEach(function (t) { modelLine(c, "membuat " + t); });
    (it.clashes || []).forEach(function (k) { modelLine(c, "bentrok " + k.file + ":" + k.line + " " + k.why); });
    if (it.examples) { c.appendChild(el("h2", null, "Contoh")); c.appendChild(exampleBlock(it.examples)); }
    return c;
  }
  function showCard(kind, id) {
    var seq = ++cardSeq;
    openCard = id;
    get("/api/cards/" + kind + "/" + encodeURIComponent(id)).then(function (d) {
      if (seq !== cardSeq || mode !== "cards") { return; }
      clear(stream);
      var head = el("article", "card" + (d.stale || d.superseded ? " stale" : ""));
      head.appendChild(el("h2", "mono", d.id));
      var row = el("div", "row");
      row.appendChild(el("span", "state " + stateClass(d.state), String(d.state)));
      if (d.repo) { row.appendChild(el("span", null, d.repo)); }
      if (d.turn) { row.appendChild(el("span", null, "giliran " + d.turn)); }
      if (d.folder_sha12) { row.appendChild(el("span", "mono", d.folder_sha12)); }
      head.appendChild(row);
      if (d.stale) { head.appendChild(el("p", "note", "Hasil di commit lama: repo bergeser sejak folder ini ditulis.")); }
      if (d.superseded) { head.appendChild(el("p", "note", "Folder ini sudah digantikan giliran berikutnya.")); }
      if (d.why) { head.appendChild(el("p", "note", d.why)); }
      if (d.next) { head.appendChild(el("p", "msg", d.next)); }
      if (d.closed) { head.appendChild(el("p", "small", "catatan penutup: " + d.closed)); }
      if (d.prd_md) { head.appendChild(el("span", "tag", MODEL + ": PRD")); head.appendChild(el("p", "msg", d.prd_md)); }
      (d.questions || []).forEach(function (q) { modelLine(head, "? " + q); });
      (d.warnings || []).forEach(function (w) { head.appendChild(el("p", "note", w)); });
      if (d.money) { head.appendChild(el("p", "small", "biaya job " + usd(d.money.spent) + " dari " + usd(d.money.job_cap) + (d.money.queue_usd !== null && d.money.queue_usd !== undefined ? "; antrean diusulkan " + usd(d.money.queue_usd) : ""))); }
      (d.queues || []).forEach(function (q) { head.appendChild(el("p", "small", "antrean " + q)); });
      if (kind === "prd") {
        var plan = el("button", null, "Kartu rencana (angka)");
        plan.type = "button";
        plan.addEventListener("click", function () { showPlan(id); });
        head.appendChild(plan);
      }
      stream.appendChild(head);
      (d.items || []).forEach(function (it) {
        if (kind === "queue") {
          var q = el("article", "card");
          q.appendChild(el("h2", null, "Item " + it.n));
          if (it.title) { modelLine(q, it.title, "msg"); }
          var r2 = el("div", "row");
          r2.appendChild(el("span", null, it.job ? it.job : "belum ada job"));
          if (it.job_state) { r2.appendChild(el("span", "state " + stateClass(it.job_state), it.job_state)); }
          if (it.applied) { r2.appendChild(el("span", "mono", "applied " + it.applied)); }
          if (!it.text_matches) { r2.appendChild(el("span", "note", "berkas issue berubah")); }
          q.appendChild(r2);
          if (it.examples) { q.appendChild(exampleBlock(it.examples)); }
          stream.appendChild(q);
        } else { stream.appendChild(itemCard(it, d.stale || d.superseded)); }
      });
      var back = el("button", null, "Semua kartu");
      back.type = "button";
      back.addEventListener("click", function () { cardSeq++; openCard = null; renderCards(); loadCards(); });
      stream.appendChild(back);
    }).catch(function () {
      if (seq !== cardSeq || mode !== "cards") { return; }                      // an older answer, or the user moved to another page
      clear(stream);
      stream.appendChild(el("p", "muted", "Kartu tidak dapat dibaca."));
      var back = el("button", null, "Semua kartu");
      back.type = "button";
      back.addEventListener("click", function () { cardSeq++; openCard = null; renderCards(); loadCards(); });
      stream.appendChild(back);
    });
  }
  function setMode(m) {
    mode = m;
    cardSeq++;
    dropPending();
    Array.prototype.forEach.call(document.querySelectorAll("#chips button"), function (b) {
      b.setAttribute("aria-pressed", b.getAttribute("data-mode") === m ? "true" : "false");
    });
    issueForm.hidden = m === "status" || m === "decide" || m === "cards";
    query.hidden = m !== "status";
    researchSeq++;
    openCard = null;
    openResearch = null;
    openDecision = null;
    formState();
    if (m === "issue") { openIssue = null; formState(); loadIssues(); renderIssues(); }
    else if (m === "research") { loadResearch(); renderResearchList(); }
    else if (m === "decide") { loadDecisions(); renderDecisions(); }
    else if (m === "cards") { loadCards(); renderCards(); }
    else { renderOverview(); }
  }
  Array.prototype.forEach.call(document.querySelectorAll("#chips button"), function (b) {
    if (b.disabled) { return; }
    b.addEventListener("click", function () { setMode(b.getAttribute("data-mode")); });
  });
  issueForm.addEventListener("submit", function (e) {
    e.preventDefault();
    if (mode === "decide") { return; }
    if (mode === "research") { prepare({ action: "research_new", message: message.value }); }
    else if (openIssue !== null) { prepare({ action: "issue_reply", job: openIssue, message: message.value }); }
    else { prepare({ action: "issue_new", repo: repoSel.value, message: message.value }); }
  });
  query.addEventListener("input", function () { renderList(); if (current === null) { renderOverview(); } });
  document.getElementById("composer").addEventListener("submit", function (e) { e.preventDefault(); });
  document.getElementById("open-panel").addEventListener("click", function () { panel.classList.add("open"); });
  document.getElementById("close-panel").addEventListener("click", function () { panel.classList.remove("open"); });
  var deep = /^\/jobs\/(j[0-9]{8}_[0-9]{6}_[0-9a-f]{4})$/.exec(location.pathname);
  if (deep) { setMode("decide"); showDecision(deep[1]); }
  load();
  setInterval(function () {
    if (document.hidden) { return; }
    load();
    if (mode === "decide" && openDecision === null && !(pending && pending.sent) && !reasonTyped()) { loadDecisions(); }
    if (mode === "cards" && openCard === null) { loadCards(); }
    if (mode === "research" && !(pending && pending.sent)) { if (openResearch === null) { loadResearch(); } else if (researchLive) { showResearch(openResearch); } }
  }, 30000);
})();
