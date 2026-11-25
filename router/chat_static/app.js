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
  var filter = "all";                                   // the panel's filter: all | waiting | research
  var groupOpen = Object.create(null);                                   // repo label -> the person's choice; absent: open when something waits, the job is open, or it is the first
  var lastChat = "status";                              // the mode the Chat tab returns to

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) { e.className = cls; }
    if (text !== undefined && text !== null) { e.textContent = String(text); }
    return e;
  }
  function clear(node) { while (node.firstChild) { node.removeChild(node.firstChild); } }
  function nJobs(n) { return n + (n === 1 ? " job" : " jobs"); }
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
    var a = el("a", "link", "Open in viewer");
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
    row.appendChild(el("span", null, spent !== undefined ? usd(spent) + " dari " + usd(t.max_usd) : usd(t.stages_usd) + " in finished stages, limit " + usd(t.max_usd)));
    c.appendChild(row);
    var link = viewerLink(t.viewer);
    if (link) { c.appendChild(link); }
    return c;
  }
  var NO_REPO = "No repo";
  function waitingIds() {
    var w = {};
    (typeof decisionRows === "undefined" ? [] : decisionRows).forEach(function (d) { w[d.id] = true; });
    return w;
  }
  function jobButton(t) {
    var li = el("li");
    var b = el("button", "job");
    b.type = "button";
    b.appendChild(el("span", "jt", t.title || t.id));
    var sub = el("span", "js");
    sub.appendChild(el("span", "kt", t.kind || "job"));
    sub.appendChild(el("span", "state " + stateClass(t.state), t.state));
    b.appendChild(sub);
    if (current === t.id) { b.setAttribute("aria-current", "true"); }
    b.addEventListener("click", function () { if (mode !== "status") { setMode("status"); } open(t.id); panel.classList.remove("open"); });
    li.appendChild(b);
    return li;
  }
  function renderList() {
    var q = query.value.trim().toLowerCase();
    var wait = waitingIds();
    var groups = Object.create(null), order = [];
    clear(list);
    threads.forEach(function (t) {
      var hay = [t.id, t.state, t.title, t.kind, t.repo].join(" ").toLowerCase();
      if (q && hay.indexOf(q) === -1) { return; }
      if (filter === "waiting" && !wait[t.id]) { return; }
      if (filter === "research" && t.kind !== "research") { return; }
      var g = t.repo || NO_REPO;
      if (!groups[g]) { groups[g] = []; order.push(g); }
      groups[g].push(t);
    });
    order.sort(function (x, y) { return (x === NO_REPO) - (y === NO_REPO); });      // the jobs without a repo last; the rest in the order the newest job put them
    order.forEach(function (g, i) {
      var items = groups[g];
      var n = items.filter(function (t) { return wait[t.id]; }).length;
      var isOpen = groupOpen[g] !== undefined ? groupOpen[g] : (n > 0 || i === 0 || items.some(function (t) { return t.id === current; }));
      var gl = el("li", "group");
      var h = el("button", "gh");
      h.type = "button";
      h.setAttribute("aria-expanded", isOpen ? "true" : "false");
      h.appendChild(el("span", "gn", g));
      if (n) { h.appendChild(el("span", "gw", n + " waiting")); } else { h.appendChild(el("span", "gc", nJobs(items.length))); }
      h.addEventListener("click", function () { groupOpen[g] = !isOpen; renderList(); });
      gl.appendChild(h);
      if (isOpen) {
        var inner = el("ul", "jobs");
        items.forEach(function (t) { inner.appendChild(jobButton(t)); });
        gl.appendChild(inner);
      }
      list.appendChild(gl);
    });
    if (!order.length) { list.appendChild(el("li", "muted", "No matching jobs.")); }
  }
  function renderOverview() {
    clear(stream);
    var q = query.value.trim().toLowerCase();
    var shown = threads.filter(function (t) { return !q || [t.id, t.state, t.title, t.kind].join(" ").toLowerCase().indexOf(q) !== -1; });
    if (!shown.length) { stream.appendChild(el("p", "muted", "No matching jobs.")); }
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
      var back = el("button", null, "All jobs");
      back.type = "button";
      back.addEventListener("click", function () { current = null; renderList(); renderOverview(); });
      stream.appendChild(back);
    }).catch(function () { clear(stream); stream.appendChild(el("p", "muted", "Cannot read this job.")); });
  }
  function load() {
    get("/api/threads").then(function (d) {
      threads = d.threads || [];
      skipped.textContent = d.skipped ? d.skipped + " jobs cannot be shown" : "";
      summary.textContent = nJobs(threads.length);
      renderList();
      if (current === null && mode === "status") { renderOverview(); }
      if (mode === "cost") { renderCost(); }
    }).catch(function () { summary.textContent = "failed to load"; });
    if (!(mode === "decide" && openDecision === null)) { loadDecisions(false); }       // in the Keputusan list the guarded poll below does it, once
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
  var LABELS = [["repo", "Repo"], ["job", "Job"], ["state", "State"], ["environment", "Environment"], ["commit", "Commit"],
    ["turn", "Turn"], ["turn_cap_usd", "Turn limit"], ["job_cap_usd", "Job limit"], ["reason", "Reason"],
    ["profile", "Profile"], ["model", "Model"], ["stage_models", "Model"], ["stage_caps", "Stage limits"], ["web", "Web"], ["data_sent", "Data sent"],
    ["free_models", "Free models"], ["runs_code", "Example code"], ["kind", "Kind"], ["job_title", "Title"], ["sha12", "Draft"], ["spent_usd", "Cost"], ["cap_usd", "Limit"], ["queue_usd", "Queue money"], ["queue", "Queue"], ["item", "Issue no."], ["drafter_cap_usd", "Drafter limit"], ["agent_cap_usd", "Agent limit"], ["attempt_usd", "One agent attempt"], ["money", "Money note"]];
  var USD_KEYS = { turn_cap_usd: 1, job_cap_usd: 1, spent_usd: 1, cap_usd: 1, queue_usd: 1, drafter_cap_usd: 1, agent_cap_usd: 1, attempt_usd: 1 };
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
    (card.flags || []).forEach(function (f) { say(c, "mesin", "tanda mesin", f, "say warn"); });      // the machine's marks come first, above every green line (T3 light)
    LABELS.forEach(function (kv) {
      var v = card[kv[0]];
      if (v === undefined || v === null || v === "") { return; }
      fact(c, kv[1], USD_KEYS[kv[0]] ? usd(v) : v);
    });
    if (card.issue_title) { fact(c, "Judul issue", card.issue_title); }
    if (card.folder_sha) { fact(c, "Sha folder", String(card.folder_sha).slice(0, 12)); }
    if (card.draft_sha) { fact(c, "Sha draf", String(card.draft_sha).slice(0, 12)); }
    if (card.writable) { fact(c, "Berkas yang boleh disentuh (tulisan model)", card.writable.join(", ")); }
    (card.validations || []).forEach(function (v) { fact(c, "Pemeriksaan " + v.id + " (tulisan model)", (v.must_pass || []).join(", ") || "tanpa nama tes"); });
    if (card.changed_tests_n) { say(c, "mesin", "tanda mesin", "Draf ini mengubah tes yang sudah ada: " + card.changed_tests.join(", ") + (card.changed_tests_n > card.changed_tests.length ? " dan " + (card.changed_tests_n - card.changed_tests.length) + " lagi" : ""), "say warn"); }
    if (card.summary_note) { say(c, "mesin", "tanda mesin", "Ringkasan rencana tidak tersedia untuk draf ini; isinya bisa dibaca di terminal (DRAFT_REVIEW.md).", "say warn"); }
    if (card.plan) {
      var more = el("details", "more");
      more.appendChild(el("summary", null, "Teks penulis (model), bukan bukti: rencana, risiko, catatan"));
      [["rencana", card.plan.steps], ["berkas rencana", card.plan.files], ["risiko", card.plan.risks], ["peringatan", card.warnings], ["tidak terbukti otomatis", card.unverifiable]].forEach(function (kv) {
        (kv[1] || []).forEach(function (s) { say(more, "model", kv[0] + " (tulisan model)", s, "say"); });
      });
      if (card.baseline_note) { say(more, "mesin", "tanda mesin", card.baseline_note, "say warn"); }
      c.appendChild(more);
    }
    if (card.refs === "unreadable") { say(c, "mesin", "tanda mesin", "Rujukan repo lain tidak terbaca di catatan job ini.", "say warn"); }
    else if (card.refs && card.refs.length) { say(c, "mesin", "repo rujukan (dibaca penulis, hanya baca)", card.refs.map(function (r) { return r.name + "@" + r.commit12; }).join(", "), "say"); }
    if (card.request) {
      say(c, card.request_by === "chat" ? "atha" : "tak", card.request_by === "chat" ? "permintaan pertama, dimulai lewat chat (tercatat via ui)" : "permintaan pertama, dari terminal (manusia atau sesi Claude, tidak tercatat)", card.request + (card.request_cut ? " … (dipotong)" : ""), "say");
      if (card.request_count > 1) { c.appendChild(el("p", "note", (card.request_count - 1) + " balasan dari terminal tidak ditampilkan di kartu ini.")); }
    }
    if (card.item_text) { say(c, "model", "isi issue (tulisan model, dari penulis PRD)", card.item_text, "say"); }
    if (card.summary) {
      var sum = el("details", "more");
      sum.appendChild(el("summary", null, "Ringkasan penulis (tulisan model, bukan bukti)"));
      say(sum, "model", "ringkasan penulis (tulisan model)", card.summary, "say");
      c.appendChild(sum);
    }
    (card.issues || []).forEach(function (i) { fact(c, "Issue " + i.n, i.title + (i.warning ? " (tanpa contoh perilaku baru)" : "")); });
    if (card.message) { c.appendChild(el("p", "msg human", card.message)); }
    if (card.issue_text) { c.appendChild(el("p", "msg", card.issue_text)); }
    c.appendChild(el("p", "note", "Eksposur biaya yang dihitung: " + usd(prep.exposure_usd) + ". Tidak ada yang berjalan sebelum Konfirmasi."));
    var row = el("div", "actions");
    var ok = el("button", "go", "Confirm");
    ok.type = "button";
    ok.disabled = true;                                 // armed after the server's minimum delay; never the default of a key press
    var no = el("button", null, "Cancel");
    no.type = "button";
    var armed = setTimeout(function () { ok.disabled = false; }, Math.ceil((prep.min_delay_s || 1) * 1000) + 300);
    var expire = setTimeout(function () { ok.disabled = true; c.appendChild(el("p", "note", "Card expired: prepare it again.")); }, ((prep.expires_s || 300) - 5) * 1000);
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
        c.appendChild(el("p", "note", card.action === "queue_go" ? "Queue money is released up to the limit on the card. Nothing runs yet; start the first issue from the queue card in the Queue tab." : card.draft_sha ? "The code agent is running (5 to 17 minutes). The result appears on the queue card; apply is still done from the terminal." : (card.queue && card.item) ? "The drafter is writing tests and the contract (a few minutes). The draft appears on the queue card; you still confirm it yourself." : card.action === "prd_new" ? "The PRD is being written (one turn). The result appears in the Queue tab. A refusal before the job is made (queue waiting, repo changed) shows only in the terminal. Running the queue is still done from the terminal." : card.action === "research_new" ? "The result is in the research list." : (card.action.indexOf("job_") === 0 ? "Decision recorded; the job state is in the Decisions tab." : "The result is in the issue list.")));
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
          c.appendChild(el("p", "note", "Status unknown, it may already be running. Check the " + (card.action === "prd_new" ? "Queue tab" : card.action === "research_new" ? "research list" : (card.action.indexOf("job_") === 0 ? "Decisions tab" : "issue list")) + " before trying again."));
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
        if (mode === "prd") { return; }
        if (mode === "cards" && openCard !== null) { if (openKind === "queue") { showCard("queue", openCard); } else { showPlan(openCard); } return; }
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
    if (!issues.length) { stream.appendChild(el("p", "muted", "No issues yet. Write one below.")); }
    issues.slice(0, 20).forEach(function (t) { stream.appendChild(issueCard(t)); });
  }
  function act(label, build, cls) {
    var b = el("button", cls, label);
    b.type = "button";
    b.addEventListener("click", function () { prepare(build()); });
    return b;
  }
  function formState() {
    var r = mode === "research", p = mode === "prd";
    repoSel.hidden = r || (!p && openIssue !== null);
    document.getElementById("prepare").textContent = r ? "Prepare research" : (p ? "Prepare PRD" : (openIssue !== null ? "Prepare reply" : "Prepare new issue"));
    message.placeholder = r ? "Write the research question (20 to 2000 characters)" : (p ? "Write the PRD request: what changes and why" : "Write a message");
  }
  function showIssue(id, keep) {                        // keep: the card on screen is this issue's own result or status
    if (!keep && id !== openIssue) { dropPending(); }
    get("/api/issues/" + encodeURIComponent(id)).then(function (d) {
      if (mode === "prd") { return; }                   // the user moved to the PRD form while this was read: draw nothing
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
      var back = el("button", null, "All issues");
      back.type = "button";
      back.addEventListener("click", function () { dropPending(); openIssue = null; formState(); renderIssues(); });
      stream.appendChild(back);
    }).catch(function () { clear(stream); stream.appendChild(el("p", "muted", "Cannot read this issue.")); });
  }
  function loadIssues() {
    get("/api/issues").then(function (d) {
      issues = d.issues || [];
      var keep = repoSel.value;
      clear(repoSel);
      (d.repos || []).forEach(function (r) { var o = el("option", null, r); o.value = r; repoSel.appendChild(o); });
      if (keep) { repoSel.value = keep; }
      if (mode === "issue" && openIssue === null) { renderIssues(); }
    }).catch(function () { summary.textContent = "failed to load issues"; });
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
    if (!researchJobs.length) { stream.appendChild(el("p", "muted", "No research yet. Write a question below.")); }
    researchJobs.slice(0, 20).forEach(function (t) { stream.appendChild(researchCard(t)); });
  }
  function loadResearch() {
    get("/api/research").then(function (d) {
      researchJobs = d.research || [];
      if (mode === "research" && openResearch === null) { renderResearchList(); }
    }).catch(function () { summary.textContent = "failed to load research"; });
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
      var back = el("button", null, "All research");
      back.type = "button";
      back.addEventListener("click", function () { researchSeq++; openResearch = null; renderResearchList(); loadResearch(); });
      stream.appendChild(back);
    }).catch(function () { clear(stream); stream.appendChild(el("p", "muted", "Cannot read this research.")); });
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
      why.placeholder = "Reason (required for Reject)";
      why.setAttribute("aria-label", "Alasan");
      c.appendChild(why);
      var hint = el("p", "note");
      hint.setAttribute("role", "status");
      c.appendChild(hint);
      var decide = function (label, action, needReason) {
        var b = el("button", null, label);
        b.type = "button";
        b.addEventListener("click", function () {
          if (needReason && why.value.trim() === "") { hint.textContent = "Fill in the reason in the field above the button first."; return; }
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
    if (!decisionRows.length) { stream.appendChild(el("p", "muted", "No jobs are waiting for a decision.")); }
    decisionRows.forEach(function (r) { stream.appendChild(decideCard(r)); });
  }
  function loadDecisions(rerender) {                    // rerender false: the poll in load() only refreshes the rows, the badge and the panel; the guarded poll and setMode draw the page
    get("/api/decisions").then(function (d) {
      decisionRows = d.decisions || [];
      updateBadge();
      renderList();
      if (rerender !== false && mode === "decide" && openDecision === null) { renderDecisions(); }
    }).catch(function () { if (rerender !== false) { summary.textContent = "failed to load decisions"; } });
  }
  function showDecision(id) {                           // the Decide link of the viewer: opens a card, chooses and prepares nothing
    openDecision = id;
    get("/api/decisions/" + encodeURIComponent(id)).then(function (d) {
      if (mode !== "decide" || openDecision !== id) { return; }
      if (d.kind === "issue") { setMode("issue"); showIssue(id); return; }
      clear(stream);
      stream.appendChild(decideCard(d));
      var back = el("button", null, "All decisions");
      back.type = "button";
      back.addEventListener("click", function () { openDecision = null; renderDecisions(); loadDecisions(); });
      stream.appendChild(back);
    }).catch(function () { clear(stream); stream.appendChild(el("p", "muted", "Cannot read this job.")); });
  }
  // ---- T3: the plan card and the install card (SPEC_KARTU_SETUJU), read only. Presentation only: every field is the server's, put on the page as text, in
  // sections that are questions; who speaks is a label (atha, model, mesin, pembaca). Nothing here chooses a colour from a number or a class of the test.
  var TIER_TITLE = { same: "Yang tidak boleh berubah", whatif: "Kalau ... maka", after: "Yang berubah" };
  var DOMAIN_LABEL = "";
  function who(kind, text) { return el("span", "who " + kind, text); }
  function say(parent, kind, label, text, cls) {        // a line with its speaker: the text is data
    var p = el("p", cls || "say");
    p.appendChild(who(kind, label));
    p.appendChild(document.createTextNode(String(text)));
    parent.appendChild(p);
    return p;
  }
  function who_(r) { return r && typeof r === "object" && r.kind && r.id ? r.kind + " " + r.id : ""; }   // a reader that is not {kind, id} is not named
  function sec(card, title) {
    var s = el("section", "sec");
    s.appendChild(el("h3", null, title));
    card.appendChild(s);
    return s;
  }
  function kv(parent, k, v, cls) {
    var r = el("div", "kv" + (cls ? " " + cls : ""));
    r.appendChild(el("span", "k", k));
    r.appendChild(el("span", "v", v));
    parent.appendChild(r);
  }
  function cardHead(card, title, d, extra) {
    var top = el("div", "kind");
    top.appendChild(el("b", null, title));
    top.appendChild(el("span", "state " + stateClass(d.state), String(d.state)));
    card.appendChild(top);
    var row = el("div", "row");
    row.appendChild(el("span", "mono", d.id));
    if (d.repo) { row.appendChild(el("span", null, d.repo)); }
    (extra || []).forEach(function (x) { row.appendChild(el("span", x.cls || null, x.text)); });
    card.appendChild(row);
  }
  function planExample(e) {
    var d = el("div", "ex2");
    var head = el("p", "small");
    head.appendChild(el("span", "tier", TIER_TITLE[e.tier] || e.tier));
    head.appendChild(document.createTextNode(" " + e.id));
    d.appendChild(head);
    if (e.says) { say(d, "model", MODEL, e.says); }
    if (!e.showable) { d.appendChild(el("p", "note", e.why || "contoh ini tidak bisa ditampilkan sebagai angka")); }
    if (e.call) { kv(d, "fungsi", e.call); }
    (e.assumptions || []).forEach(function (a) { kv(d, "Andaikan", a.name + " = " + a.shown); });
    (e.inputs || []).forEach(function (i) { kv(d, "masukan " + i.name, i.shown); });
    if (e.output && e.output.raises) { kv(d, "keluaran", e.output.shown); }
    else if (e.output) { e.output.forEach(function (o) { kv(d, "keluaran" + (o.label ? " " + o.label : ""), o.shown); }); }
    if (e.proof) { say(d, "mesin", "mesin", e.proof.wording, "say proof"); }
    return d;
  }
  function planReading(card, r) {                       // the domain reader's note: a model's statement, with the server's label
    var box = el("div", "reader");
    if (!DOMAIN_LABEL) { box.appendChild(el("p", "note", "pembacaan tidak ditampilkan: label 'bukan bukti, bukan manusia' tidak ada")); card.appendChild(box); return; }
    if (r.fresh) {
      var by = who_(r.reader) ? " (" + who_(r.reader) + (who_(r.reader2) ? " dan " + who_(r.reader2) : "") + ")" : "";
      say(box, "pembaca", "pembaca angka", "Dibaca Claude, " + r.at + ": " + (r.verdict === "ok" ? "sesuai permintaan" : "ada yang meragukan") + " (" + (r.sources || []).join("; ") + ")" + by, r.verdict === "ok" ? "say" : "say warn");
      modelLine(box, r.note);
      box.appendChild(el("p", "small", DOMAIN_LABEL));
    } else {
      box.appendChild(el("p", "note", r.why));
    }
    card.appendChild(box);
  }
  function countLine(it) {                              // only the counts the server sends (calls, same, whatif, after); nothing from the examples is tallied
    var c = it.counts;
    return c ? c.calls + " contoh (tetap " + c.same + ", kalau " + c.whatif + ", berubah " + c.after + ")" : null;
  }
  function planItem(it, dim) {
    var c = el("div", "issue" + (dim ? " stale" : ""));
    c.appendChild(el("h4", null, "Issue " + it.n));
    if (it.title) { say(c, "model", MODEL, it.title, "say"); }
    if (it.warning) { c.appendChild(el("p", "note", it.warning)); }
    if (it.no_examples) { modelLine(c, "tanpa contoh: " + it.no_examples); }
    if (it.why) { c.appendChild(el("p", "small", it.why)); }
    if (it.examples && it.examples.withheld) { c.appendChild(el("p", "note", "contoh ditahan harness")); return c; }
    var line = countLine(it);
    if (line) { c.appendChild(el("p", "sum", line)); }
    ["same", "whatif", "after"].forEach(function (tier) {
      (it.examples || []).filter(function (e) { return e.tier === tier; }).forEach(function (e) { c.appendChild(planExample(e)); });
    });
    if (it.domain_read) { planReading(c, it.domain_read); }
    return c;
  }
  function cardButtons(extra) {
    var wrap = el("div", "nav");
    (extra || []).forEach(function (x) {
      var b = el("button", null, x.text);
      b.type = "button";
      b.addEventListener("click", x.fn);
      wrap.appendChild(b);
    });
    var back = el("button", null, "All cards");
    back.type = "button";
    back.addEventListener("click", function () { cardSeq++; openCard = null; renderCards(); loadCards(); });
    wrap.appendChild(back);
    return wrap;
  }
  function planActions(id, t4) {                        // SPEC_CHAT_T4A: the server says which button the builders would let through; the second button is a placeholder for now (Atha)
    var box = el("div", "nav");
    if (!t4) { return box; }
    if (t4.action === "prd_approve") {
      var b = el("button", "go", "Setujui rencana");
      b.type = "button";
      b.addEventListener("click", function () { prepare({ action: "prd_approve", job: id }); });
      box.appendChild(b);
      box.appendChild(el("p", "small", "Tidak ada uang yang keluar: ini membuat antrean yang masih menunggu persetujuan uang."));
    } else if (t4.action === "queue_go") {                // SPEC_CHAT_T4A: the money. The page sends the job id, the acknowledgement the server names and the typed reason, nothing else
      var needs = t4.needs || [], ackItems = t4.ack_items || [], tick = null, why = null;
      var p = el("button", "go", "Jalankan antrean (uang keluar)");
      p.type = "button";
      if (needs.indexOf("ack") >= 0) {
        var lab = el("label", "small");
        tick = el("input");
        tick.type = "checkbox";
        lab.appendChild(tick);
        lab.appendChild(document.createTextNode(" Saya terima: issue " + ackItems.join(", ") + " tidak punya contoh perilaku baru, jadi mesin tidak bisa memeriksa angkanya."));
        box.appendChild(lab);
      }
      if (needs.indexOf("reason") >= 0) {
        why = el("input", "reason");
        why.type = "text";
        why.maxLength = 500;
        why.autocomplete = "off";
        why.placeholder = "Alasan menerima biaya ini (10 sampai 500 karakter)";
        why.setAttribute("aria-label", "Alasan");
        box.appendChild(why);
      }
      var ready = function () { p.disabled = (tick !== null && !tick.checked) || (why !== null && why.value.trim().length < 10); };
      if (tick) { tick.addEventListener("change", ready); }
      if (why) { why.addEventListener("input", ready); }
      ready();
      p.addEventListener("click", function () {
        if (p.disabled) { return; }
        var body = { action: "queue_go", job: id };
        if (tick) { body.ack = ackItems.join(","); }
        if (why) { body.reason = why.value.trim(); }
        prepare(body);
      });
      box.appendChild(p);
      box.appendChild(el("p", "small", "Menyetujui uang untuk seluruh antrean, sampai batas yang tertera di kartu berikutnya. Belum ada yang berjalan; issue pertama dimulai dari kartu antrean."));
    } else if (t4.why) {
      box.appendChild(el("p", "note", t4.why));
    }
    return box;
  }
  function showPlan(id) {
    var seq = ++cardSeq;
    openCard = id;
    openKind = "plan";
    get("/api/approve/prd/" + encodeURIComponent(id)).then(function (d) {
      if (seq !== cardSeq || mode !== "cards") { return; }
      clear(stream);
      DOMAIN_LABEL = d.domain_read_label || "";
      var dim = !!(d.stale || d.superseded);
      var card = el("article", "card plan" + (dim ? " stale" : ""));
      cardHead(card, "Kartu rencana", d, (d.turn ? [{ text: "giliran " + d.turn }] : []));
      if (d.stale) { card.appendChild(el("p", "note", "Hasil di commit lama: repo bergeser sejak folder ini ditulis.")); }
      if (d.superseded) { card.appendChild(el("p", "note", "Folder ini sudah digantikan giliran berikutnya.")); }
      if (d.why) { card.appendChild(el("p", "note", d.why)); }
      var s1 = sec(card, "1. Apa yang diminta?");
      if (d.request) {
        say(s1, d.request_by === "chat" ? "atha" : "tak", d.request_by === "chat" ? "permintaan, dimulai lewat chat (tercatat via ui):" : "permintaan (pembuat tidak tercatat):", d.request, "say");
        if (d.request_truncated) { s1.appendChild(el("p", "note", "permintaan dipotong")); }
      } else { s1.appendChild(el("p", "note", "permintaan tidak tercatat")); }
      var s2 = sec(card, "2. Apa yang akan dikerjakan?");
      if (d.summary) { say(s2, "model", MODEL, d.summary, "say"); } else if (d.summary_why) { s2.appendChild(el("p", "note", d.summary_why)); }
      s2.appendChild(el("p", "small", d.issue_count + " issue"));
      var s3 = sec(card, "3. Hasilnya nanti, dalam angka");
      if (d.defects) { s3.appendChild(el("p", "note", d.defects + " contoh tidak bisa ditampilkan sebagai angka (kartu cacat)")); }
      (d.items || []).forEach(function (it) { s3.appendChild(planItem(it, dim)); });
      var s4 = sec(card, "4. Berapa batas biayanya?");
      if (d.cost) {
        var ref = d.cost.reference && d.cost.reference.median !== null && d.cost.reference.median !== undefined ? "; acuan: median " + usd(d.cost.reference.median) + " dari " + d.cost.reference.n + " " + d.cost.reference.of : "; acuan: belum cukup data";
        if (!d.cost.ratio_text) { s4.appendChild(el("p", "say", "Rasio batas: belum cukup data job sebelumnya.")); }
        if (d.cost.ratio_text) { say(s4, "mesin", "mesin", "Batas yang diminta " + d.cost.ratio_text + " (1 = biasa; batas itu pagar, bukan perkiraan biaya).", "say big"); }
        s4.appendChild(el("p", "small", "biaya job " + usd(d.cost.spent) + "; batas antrean untuk " + d.issue_count + " issue " + usd(d.cost.proposed) + (d.cost.proposed_each !== null && d.cost.proposed_each !== undefined ? " (" + usd(d.cost.proposed_each) + " per issue)" : "") + ref + " (acuan: satu job)"));
      }
      var s5 = sec(card, "5. Apa yang belum diperiksa siapa pun?");
      s5.appendChild(el("p", "say", d.fixed_line));
      stream.appendChild(card);
      stream.appendChild(planActions(id, d.t4));
      stream.appendChild(cardButtons([{ text: "Kartu teknis", fn: function () { showCard("prd", id); } }]));
    }).catch(function () {
      if (seq !== cardSeq || mode !== "cards") { return; }
      clear(stream);
      stream.appendChild(el("p", "muted", "Kartu rencana tidak dapat dibaca."));
      stream.appendChild(cardButtons());
    });
  }
  function installReader(box, title, r, label) {
    box.appendChild(el("h4", null, title));
    if (!r) { box.appendChild(el("p", "note", "belum ada catatan")); return; }
    var line = function (x, n) {
      var by = who_(x.reader) ? " (" + who_(x.reader) + ")" : "";
      var nit = x.verdict === "concerns" && x.severity === "nit";
      var who = (x.reader && x.reader.kind === "argus") ? "Model" : "Claude";
      say(box, "pembaca", "pembaca patch " + n, who + ", " + x.at + ": " + (x.verdict === "ok" ? "ok" : nit ? "catatan kecil (nit)" : "ada yang meragukan") + by, x.verdict === "ok" || nit ? "say" : "say warn");
      modelLine(box, x.note);
    };
    line(r, 1);
    if (r.second) { line(r.second, 2); }
    box.appendChild(el("p", "small", label));
  }
  function showInstall(id) {
    var seq = ++cardSeq;
    openCard = id;
    get("/api/approve/code/" + encodeURIComponent(id)).then(function (d) {
      if (seq !== cardSeq || mode !== "cards") { return; }
      clear(stream);
      DOMAIN_LABEL = d.domain_read_label || "";
      var card = el("article", "card install");
      cardHead(card, "Kartu pasang", d, d.patch_sha12 ? [{ text: "patch " + d.patch_sha12, cls: "mono" }] : []);
      card.appendChild(el("p", d.open ? "say" : "note", d.open ? "Tidak ada syarat yang tertutup (yang tidak berlaku atau tidak tercatat disebut di daftar). Ini bukan jaminan aman." : "Pasang tertutup: ada syarat yang belum terpenuhi."));
      var s1 = sec(card, "1. Apa tujuannya?");
      say(s1, /model/.test(String(d.purpose.by)) ? "model" : "tak", d.purpose.by, d.purpose.title, "say");
      if (d.purpose.text) { modelLine(s1, d.purpose.text); }
      var s2 = sec(card, "2. Hasil perubahan, dalam angka");
      if (d.item) { s2.appendChild(planItem(d.item, false)); }
      var s3 = sec(card, "3. File mana yang disentuh?");
      var files = d.files || [];
      var flagged = files.filter(function (f) { return f.marks.length; }).length;
      s3.appendChild(el("p", "sum", files.length + " file, " + flagged + " bertanda mesin"));
      files.forEach(function (f) {
        var p = el("p", f.marks.length ? "file flagged" : "file");
        p.appendChild(el("span", "mono", f.path));
        if (f.marks.length) { p.appendChild(who("mesin", "mesin")); p.appendChild(document.createTextNode(" " + f.marks.join("; "))); }
        s3.appendChild(p);
      });
      if (!files.length) { s3.appendChild(el("p", "note", "daftar file tidak terbaca")); }
      if (d.files_cut) { s3.appendChild(el("p", "note", d.files_cut + " file lagi tidak ditampilkan")); }
      if (d.scope_note) { s3.appendChild(el("p", "note", d.scope_note)); }
      var s4 = sec(card, "4. Syarat pemasangan");
      var checks = d.checks || [];
      var n = { ya: 0, tidak: 0, na: 0 };
      checks.forEach(function (c) { if (c.ok === true) { n.ya++; } else if (c.ok === false) { n.tidak++; } else { n.na++; } });
      s4.appendChild(el("p", "sum", checks.length + " syarat: " + n.ya + " ya, " + n.tidak + " TIDAK, " + n.na + " tidak berlaku"));
      checks.forEach(function (c) {
        s4.appendChild(el("p", c.ok === false ? "cond bad" : "cond", "(" + c.key + ") " + (c.ok === true ? "ya" : c.ok === false ? "TIDAK" : "tidak berlaku") + ": " + c.label + (c.why ? " - " + c.why : "")));
      });
      var s5 = sec(card, "5. Siapa yang membaca patch?");
      installReader(s5, "Pembaca patch", d.patch_read, d.patch_read_label);
      s5.appendChild(el("p", "small", d.patch_reader_tested ? "pembaca patch sudah diuji" : "pembaca patch belum diuji"));
      s5.appendChild(el("p", "small", d.domain_reader_tested ? "pembaca angka sudah diuji" : "pembaca angka belum diuji"));
      if (d.approval) { s5.appendChild(el("p", "small", "persetujuan draf: " + d.approval.at + " oleh " + d.approval.by + " (" + d.approval.note + ")")); }
      var s6 = sec(card, "6. Berapa biayanya?");
      if (d.cost) {
        s6.appendChild(el("p", "say", "biaya job " + usd(d.cost.spent) + "; batas job " + usd(d.cost.cap) + (d.cost.reference && d.cost.reference.cap_median !== null && d.cost.reference.cap_median !== undefined ? "; batas job biasa (median) " + usd(d.cost.reference.cap_median) : "")));
      }
      var s7 = sec(card, "7. Apa yang belum diperiksa siapa pun?");
      s7.appendChild(el("p", "say", d.fixed_line));
      stream.appendChild(card);
      stream.appendChild(cardButtons());
    }).catch(function () {
      if (seq !== cardSeq || mode !== "cards") { return; }
      clear(stream);
      stream.appendChild(el("p", "muted", "Kartu pasang tidak dapat dibaca."));
      stream.appendChild(cardButtons());
    });
  }
  // ---- T2: read-only cards (docs/reviews/SPEC_CHAT_CARDS.md). Every string is put on the page as text; model text carries its tag, and the
  // status line is built from the machine's fields only (id, tier, status, where). No button, no storage, no request but GET. ----------------
  var cardRows = [];
  var cardSeq = 0;
  var openKind = null;                                  // "queue" when the card on screen is a queue's, else the plan or a PRD card
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
    if (!cardRows.length) { stream.appendChild(el("p", "muted", "No PRD or queue yet.")); }
    cardRows.forEach(function (r) { stream.appendChild(cardRow(r)); });
  }
  function loadCards() {
    var seq = ++cardSeq;
    get("/api/cards").then(function (d) {
      if (seq !== cardSeq) { return; }
      cardRows = d.rows || [];
      if (mode === "cards") { renderCards(); }
    }).catch(function () { summary.textContent = "failed to load cards"; });
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
  function stepActions(id, t4b) {                      // SPEC_CHAT_T4B: the server says which button the builders would let through (queues approved from the chat only)
    var box = el("div", "nav");
    if (!t4b) { return box; }
    if (t4b.action === "queue_step" || t4b.action === "draft_approve") {
      var b = el("button", "go", t4b.action === "queue_step" ? "Mulai issue " + t4b.item : "Setujui draf issue " + t4b.item);
      b.type = "button";
      b.addEventListener("click", function () { prepare({ action: t4b.action, queue: id }); });
      box.appendChild(b);
      box.appendChild(el("p", "small", t4b.action === "queue_step" ? "The drafter writes tests and the contract. Nothing is applied yet; you still confirm the draft yourself." : "The next card shows the draft; its tests and contract are model text. Apply is still done from the terminal."));
    } else if (t4b.why) {
      box.appendChild(el("p", "note", t4b.why));
    }
    return box;
  }
  function showCard(kind, id) {
    var seq = ++cardSeq;
    openCard = id;
    openKind = kind;
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
          if (it.job && it.job_state === "REVIEW_READY") {
            var inst = el("button", null, "Kartu pasang (angka)");
            inst.type = "button";
            inst.addEventListener("click", function () { showInstall(it.job); });
            q.appendChild(inst);
          }
          if (it.examples) { q.appendChild(exampleBlock(it.examples)); }
          stream.appendChild(q);
        } else { stream.appendChild(itemCard(it, d.stale || d.superseded)); }
      });
      if (kind === "queue") { stream.appendChild(stepActions(id, d.t4b)); }
      var back = el("button", null, "All cards");
      back.type = "button";
      back.addEventListener("click", function () { cardSeq++; openCard = null; renderCards(); loadCards(); });
      stream.appendChild(back);
    }).catch(function () {
      if (seq !== cardSeq || mode !== "cards") { return; }                      // an older answer, or the user moved to another page
      clear(stream);
      stream.appendChild(el("p", "muted", "Cannot read this card."));
      var back = el("button", null, "All cards");
      back.type = "button";
      back.addEventListener("click", function () { cardSeq++; openCard = null; renderCards(); loadCards(); });
      stream.appendChild(back);
    });
  }
  function updateBadge() {                              // the number of jobs that wait for a decision, from the same list the Keputusan tab shows
    var b = document.getElementById("decide-badge"), n = decisionRows.length;
    b.hidden = n === 0;
    b.textContent = n > 9 ? "9+" : String(n);
    b.setAttribute("aria-label", n + " jobs awaiting a decision");
  }
  var KIND_LABEL = { code: "Code", prd: "PRD", research: "Research", issue: "Issue" };
  function renderCost() {                               // what the job list already carries: the cost of finished stages. Not the daily cap, not what is booked (a later change).
    clear(stream);
    var total = 0, by = Object.create(null), unknown = 0;
    threads.forEach(function (t) {
      if (t.stages_unknown) { unknown++; }
      var u = typeof t.stages_usd === "number" ? t.stages_usd : 0;
      total += u;
      var k = KIND_LABEL[t.kind] || "Other";
      by[k] = (by[k] || 0) + u;
    });
    var c = el("article", "card");
    c.appendChild(el("h2", null, "Recorded stage cost"));
    fact(c, "Total (" + nJobs(threads.length) + " in the list)", usd(total));
    Object.keys(by).sort().forEach(function (k) { fact(c, k, usd(by[k])); });
    if (unknown) { c.appendChild(el("p", "note", nJobs(unknown) + (unknown === 1 ? " has" : " have") + " a stage with no cost figure: not counted, not zero.")); }
    c.appendChild(el("p", "note", "Only stage figures recorded in the job list (the newest only). The daily cap and the money already booked are not shown on this screen yet."));
    stream.appendChild(c);
    var rows = threads.filter(function (t) { return typeof t.stages_usd === "number" && t.stages_usd > 0; })
      .sort(function (x, y) { return y.stages_usd - x.stages_usd; }).slice(0, 15);
    if (rows.length) {
      var d = el("article", "card");
      d.appendChild(el("h2", null, "Per job"));
      rows.forEach(function (t) {
        var kv = el("div", "kv cost");
        kv.appendChild(el("span", "k", (t.repo ? t.repo + ": " : "") + (t.title || t.id)));
        kv.appendChild(el("span", "v", usd(t.stages_usd)));
        d.appendChild(kv);
      });
      stream.appendChild(d);
    }
  }
  function setMode(m) {
    mode = m;
    cardSeq++;
    dropPending();
    var inChat = m === "status" || m === "issue" || m === "prd" || m === "research";
    if (inChat) { lastChat = m; }
    Array.prototype.forEach.call(document.querySelectorAll("#chips button"), function (b) {
      b.setAttribute("aria-pressed", b.getAttribute("data-mode") === m ? "true" : "false");
    });
    Array.prototype.forEach.call(document.querySelectorAll("#tabs button"), function (b) {
      var t = b.getAttribute("data-tab");
      b.setAttribute("aria-pressed", (inChat ? t === "chat" : t === m) ? "true" : "false");
    });
    document.getElementById("chips").hidden = !inChat;
    document.getElementById("dock").hidden = !inChat;
    issueForm.hidden = m === "status" || m === "decide" || m === "cards" || m === "cost";
    query.hidden = m !== "status";
    researchSeq++;
    openCard = null;
    openResearch = null;
    openDecision = null;
    formState();
    if (m === "issue") { openIssue = null; formState(); loadIssues(); renderIssues(); }
    else if (m === "prd") { openIssue = null; formState(); loadIssues(); clear(stream); stream.appendChild(el("p", "muted", "Write a request for the PRD writer below. One turn; the result appears in the Queue tab.")); }
    else if (m === "research") { loadResearch(); renderResearchList(); }
    else if (m === "decide") { loadDecisions(); renderDecisions(); }
    else if (m === "cards") { loadCards(); renderCards(); }
    else if (m === "cost") { renderCost(); }
    else { renderOverview(); }
  }
  Array.prototype.forEach.call(document.querySelectorAll("#chips button"), function (b) {
    if (b.disabled) { return; }
    b.addEventListener("click", function () { setMode(b.getAttribute("data-mode")); });
  });
  Array.prototype.forEach.call(document.querySelectorAll("#tabs button"), function (b) {
    b.addEventListener("click", function () { var t = b.getAttribute("data-tab"); setMode(t === "chat" ? lastChat : t); });
  });
  Array.prototype.forEach.call(document.querySelectorAll("#filters button"), function (b) {
    b.addEventListener("click", function () {
      filter = b.getAttribute("data-filter");
      Array.prototype.forEach.call(document.querySelectorAll("#filters button"), function (x) { x.setAttribute("aria-pressed", x === b ? "true" : "false"); });
      renderList();
    });
  });
  issueForm.addEventListener("submit", function (e) {
    e.preventDefault();
    if (mode === "decide") { return; }
    if (mode === "research") { prepare({ action: "research_new", message: message.value }); }
    else if (mode === "prd") { prepare({ action: "prd_new", repo: repoSel.value, message: message.value }); }
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
