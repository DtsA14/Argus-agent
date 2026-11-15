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
    ["turn", "Giliran"], ["turn_cap_usd", "Batas giliran"], ["job_cap_usd", "Batas job"], ["reason", "Alasan"]];
  var USD_KEYS = { turn_cap_usd: 1, job_cap_usd: 1 };
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
    no.addEventListener("click", function () { dropPending(); });
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
        c.appendChild(el("p", "note", "Hasilnya ada di daftar issue."));
        var close = el("button", null, "Tutup");
        close.type = "button";
        close.addEventListener("click", function () { dropPending(); });
        c.appendChild(close);
        done(r);
      }).catch(function (e) {
        c.sent = false;
        settle();
        if (e.answered) {
          c.appendChild(el("p", "note", "Ditolak: " + e.message));
          no.disabled = false;
        } else {                                        // no answer: the server may have run it; do not prepare the same thing again blind
          c.appendChild(el("p", "note", "Status tidak diketahui, mungkin sudah berjalan. Cek daftar issue sebelum mencoba lagi."));
          no.disabled = false;
          loadIssues();
        }
      });
    });
    row.appendChild(ok);
    row.appendChild(no);
    c.appendChild(row);
    return c;
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
      if (mode !== ctx.mode || openIssue !== ctx.open) { return; }     // the user moved on while it was prepared: the token just lapses
      dropPending();
      var c = renderCard(prep, function (r) { message.value = ""; loadIssues(); if (r.job) { showIssue(r.job); } });
      pending = c;
      slot.appendChild(c);
      c.scrollIntoView({ block: "nearest" });
    }).catch(function (e) {
      busy = false;
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
    repoSel.hidden = openIssue !== null;
    document.getElementById("prepare").textContent = openIssue !== null ? "Siapkan balasan" : "Siapkan issue baru";
  }
  function showIssue(id) {
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
      back.addEventListener("click", function () { openIssue = null; formState(); renderIssues(); });
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
  function setMode(m) {
    mode = m;
    dropPending();
    Array.prototype.forEach.call(document.querySelectorAll("#chips button"), function (b) {
      b.setAttribute("aria-pressed", b.getAttribute("data-mode") === m ? "true" : "false");
    });
    issueForm.hidden = m !== "issue";
    query.hidden = m === "issue";
    if (m === "issue") { openIssue = null; formState(); loadIssues(); renderIssues(); } else { renderOverview(); }
  }
  Array.prototype.forEach.call(document.querySelectorAll("#chips button"), function (b) {
    if (b.disabled) { return; }
    b.addEventListener("click", function () { setMode(b.getAttribute("data-mode")); });
  });
  issueForm.addEventListener("submit", function (e) {
    e.preventDefault();
    if (openIssue !== null) { prepare({ action: "issue_reply", job: openIssue, message: message.value }); }
    else { prepare({ action: "issue_new", repo: repoSel.value, message: message.value }); }
  });
  query.addEventListener("input", function () { renderList(); if (current === null) { renderOverview(); } });
  document.getElementById("composer").addEventListener("submit", function (e) { e.preventDefault(); });
  document.getElementById("open-panel").addEventListener("click", function () { panel.classList.add("open"); });
  document.getElementById("close-panel").addEventListener("click", function () { panel.classList.remove("open"); });
  load();
  setInterval(function () { if (!document.hidden) { load(); } }, 30000);
})();
