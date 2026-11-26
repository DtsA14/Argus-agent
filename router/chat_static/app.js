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
  var KIND_LABEL = { code: "Code", prd: "PRD", research: "Research", issue: "Issue" };
  var waitingRows = [];                                 // what waits for the person (/api/waiting); the Decisions tab and the badge count it with the open jobs
  var waitingMeta = { capped: false, unknown: false, stale: false };
  var decideSeq = 0;
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
  function jobCard(t, spent, compact) {
    var c = el("article", "card" + (compact ? " compact" : ""));
    c.appendChild(el("h2", t.title ? null : "mono", t.title || t.id));
    var row = el("div", "row");
    row.appendChild(el("span", "state " + stateClass(t.state), t.state));
    row.appendChild(el("span", null, (KIND_LABEL[t.kind] || t.kind) + (t.repo ? " · " + t.repo : "")));
    if (!compact) { row.appendChild(el("span", null, t.created_at)); }
    row.appendChild(el("span", null, spent !== undefined ? usd(spent) + " of " + usd(t.max_usd) : usd(t.stages_usd) + " in finished stages, limit " + usd(t.max_usd)));
    c.appendChild(row);
    if (!compact) {
      var link = viewerLink(t.viewer);
      if (link) { c.appendChild(link); }
    }
    return c;
  }
  var NO_REPO = "No repo";
  function waitingIds() {
    var w = {};
    (typeof decisionRows === "undefined" ? [] : decisionRows).forEach(function (d) { w[d.id] = true; });
    waitingRows.forEach(function (r) { if (r.job) { w[r.job] = true; } if (r.card === "plan") { w[r.id] = true; } });
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
    b.addEventListener("click", function () { if (mode !== "status") { setMode("status"); } open(t.id); closePanel(); });
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
      var c = jobCard(t, undefined, true);
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
      updateSummary();
      renderList();
      if (current === null && mode === "status") { renderOverview(); }
      if (mode === "cost") { renderCost(); loadCap(); }
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
    ["free_models", "Free models"], ["runs_code", "Example code"], ["kind", "Kind"], ["job_title", "Title"], ["sha12", "Draft"], ["spent_usd", "Cost"], ["cap_usd", "Limit"], ["queue_usd", "Queue money"], ["queue", "Queue"], ["item", "Issue no."], ["drafter_cap_usd", "Drafter limit"], ["agent_cap_usd", "Agent limit"], ["attempt_usd", "One agent attempt"], ["money", "Money note"], ["ttl_hours", "Session lasts (hours)"], ["max_turns", "Turns at most"], ["turn_note", "One turn"], ["confirms", "This confirmation covers"], ["source_note", "Where the text comes from"]];
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
    (card.flags || []).forEach(function (f) { say(c, "mesin", "machine flag", f, "say warn"); });      // the machine's marks come first, above every green line (T3 light)
    LABELS.forEach(function (kv) {
      var v = card[kv[0]];
      if (v === undefined || v === null || v === "") { return; }
      fact(c, kv[1], USD_KEYS[kv[0]] ? usd(v) : v);
    });
    if (card.source) { fact(c, "Started from", "the foreman's proposal" + (card.source.edited ? ", edited by you" : ", as written")); }
    if (card.issue_title) { fact(c, "Issue title", card.issue_title); }
    if (card.folder_sha) { fact(c, "Folder sha", String(card.folder_sha).slice(0, 12)); }
    if (card.draft_sha) { fact(c, "Draft sha", String(card.draft_sha).slice(0, 12)); }
    if (card.writable) { fact(c, "Files it may touch (written by a model)", card.writable.join(", ")); }
    (card.validations || []).forEach(function (v) { fact(c, "Check " + v.id + " (written by a model)", (v.must_pass || []).join(", ") || "no test name"); });
    if (card.changed_tests_n) { say(c, "mesin", "machine flag", "This draft changes existing tests: " + card.changed_tests.join(", ") + (card.changed_tests_n > card.changed_tests.length ? " and " + (card.changed_tests_n - card.changed_tests.length) + " more" : ""), "say warn"); }
    if (card.summary_note) { say(c, "mesin", "machine flag", "The plan summary is not available for this draft; its content can be read in the terminal (DRAFT_REVIEW.md).", "say warn"); }
    if (card.plan) {
      var more = el("details", "more");
      more.appendChild(el("summary", null, "Text by the writer (a model), not proof: plan, risks, notes"));
      [["plan", card.plan.steps], ["planned files", card.plan.files], ["risks", card.plan.risks], ["warnings", card.warnings], ["not proven automatically", card.unverifiable]].forEach(function (kv) {
        (kv[1] || []).forEach(function (s) { say(more, "model", kv[0] + " (written by a model)", s, "say"); });
      });
      if (card.baseline_note) { say(more, "mesin", "machine flag", card.baseline_note, "say warn"); }
      c.appendChild(more);
    }
    if (card.refs === "unreadable") { say(c, "mesin", "machine flag", "The reference repos cannot be read from this job's record.", "say warn"); }
    else if (card.refs && card.refs.length) { say(c, "mesin", "reference repos (read by the writer, read only)", card.refs.map(function (r) { return r.name + "@" + r.commit12; }).join(", "), "say"); }
    if (card.request) {
      say(c, card.request_by === "chat" ? "atha" : "tak", card.request_by === "chat" ? "first request, started from the chat (recorded via the UI)" : "first request, from the terminal (a person or a Claude session, not recorded)", card.request + (card.request_cut ? " … (cut)" : ""), "say");
      if (card.request_count > 1) { c.appendChild(el("p", "note", (card.request_count - 1) + " replies from the terminal are not shown on this card.")); }
    }
    if (card.item_text) { say(c, "model", "issue text (written by a model, from the PRD writer)", card.item_text, "say"); }
    if (card.summary) {
      var sum = el("details", "more");
      sum.appendChild(el("summary", null, "Writer's summary (written by a model, not proof)"));
      say(sum, "model", "writer's summary (written by a model)", card.summary, "say");
      c.appendChild(sum);
    }
    (card.issues || []).forEach(function (i) { fact(c, "Issue " + i.n, i.title + (i.warning ? " (no example of new behaviour)" : "")); });
    if (card.message) { c.appendChild(el("p", "msg human", card.message)); }
    if (card.issue_text) { c.appendChild(el("p", "msg", card.issue_text)); }
    c.appendChild(el("p", "note", "Cost exposure counted: " + usd(prep.exposure_usd) + ". Nothing runs before Confirm."));
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
        c.appendChild(el("h2", null, "Started"));
        if (r.job) { fact(c, "Job", r.job); }
        c.appendChild(el("p", "note", card.action === "manager_new" ? "The session is being made; it appears in the Foreman view in a few seconds. Its turns are not confirmed again." : card.action === "queue_go" ? "Queue money is released up to the limit on the card. Nothing runs yet; start the first issue from the queue card in the Queue tab." : card.draft_sha ? "The code agent is running (5 to 17 minutes). The result appears on the queue card; apply is still done from the terminal." : (card.queue && card.item) ? "The drafter is writing tests and the contract (a few minutes). The draft appears on the queue card; you still confirm it yourself." : card.action === "prd_new" ? "The PRD is being written (one turn). The result appears in the Queue tab. A refusal before the job is made (queue waiting, repo changed) shows only in the terminal. Running the queue is still done from the terminal." : card.action === "research_new" ? "The result is in the research list." : (card.action.indexOf("job_") === 0 ? "Decision recorded; the job state is in the Decisions tab." : "The result is in the issue list.")));
        var close = el("button", null, "Close");
        close.type = "button";
        close.addEventListener("click", function () { removeCard(c); });
        c.appendChild(close);
        done(r);
      }).catch(function (e) {
        c.sent = false;
        settle();
        if (e.answered) {
          c.appendChild(el("p", "note", "Refused: " + e.message));
          no.disabled = false;
        } else {                                        // no answer: the server may have run it; do not prepare the same thing again blind
          c.appendChild(el("p", "note", "Status unknown, it may already be running. Check the " + (card.action === "prd_new" ? "Queue tab" : card.action === "manager_new" ? "Foreman view" : card.action === "research_new" ? "research list" : (card.action.indexOf("job_") === 0 ? "Decisions tab" : "issue list")) + " before trying again."));
          no.disabled = false;
          if (card.action === "research_new") { loadResearch(); }
          else if (card.action === "manager_new") { mgr.expect = 12; if (mode === "manager") { loadManager(); } }
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
    if (fromProposal && (body.action === "research_new" || body.action === "prd_new") && body.source_job === undefined) { body.source_job = fromProposal.job; body.source_turn = String(fromProposal.turn); }
    var ctx = { mode: mode, open: openIssue };
    post("/api/prepare", body).then(function (prep) {
      busy = false;
      if (pending && pending.sent) { return; }          // a confirm went out meanwhile: this card is not shown, its token lapses
      if (mode !== ctx.mode || openIssue !== ctx.open) { return; }     // the user moved on while it was prepared: the token just lapses
      dropPending();
      var c = renderCard(prep, function (r) {
        message.value = "";
        fromProposal = null;                            // the source belongs to the one form it filled: a later form is the person's own
        if (mode === "manager") { if (body.action === "manager_new") { mgr.expect = 12; loadManager(); } return; }       // a job from a proposal: the Started card says where it went
        if (mode === "research") { loadResearch(); if (r.job) { showResearch(r.job); } return; }
        if (mode === "prd") { return; }
        if (mode === "cards" && openCard !== null) { if (openKind === "queue") { showCard("queue", openCard); } else if (openKind === "draft") { showDraft(openCard); } else { showPlan(openCard); } return; }
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
      showNote("Could not prepare: " + e.message);
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
    var f = mode === "manager";
    message.maxLength = f ? 2000 : 6000;                // the server refuses a foreman message over 2000 characters
    repoSel.hidden = r || (!p && openIssue !== null) || f;
    var what = f ? "Send to the foreman" : r ? "Prepare research" : (p ? "Prepare PRD" : (openIssue !== null ? "Prepare reply" : "Prepare new issue"));
    document.getElementById("prepare").setAttribute("aria-label", what);
    document.getElementById("type-label").textContent = f ? "Foreman" : r ? "Research" : (p ? "PRD" : (openIssue !== null ? "Reply to this issue" : "New issue"));
    message.placeholder = f ? "Talk with the foreman (2000 characters at most)" : r ? "Write the research question (20 to 2000 characters)" : (p ? "Write the PRD request: what changes and why" : "Write a message");
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
      row.appendChild(el("span", null, "turn " + d.turn));
      c.appendChild(row);
      if (d.busy) { c.appendChild(el("p", "note", "The writer is still working.")); }
      (d.conversation || []).forEach(function (m) {
        c.appendChild(el("p", "msg " + (m.from === "human" ? "human" : ""), (m.from === "human" ? "You: " : "Writer: ") + m.text));
        (m.questions || []).forEach(function (q) { c.appendChild(el("p", "msg", "? " + q)); });
      });
      if (d.issue) { c.appendChild(el("h2", null, "Issue")); c.appendChild(el("p", "msg", d.issue.text)); }
      if (d.examples) { c.appendChild(el("h2", null, "Examples")); c.appendChild(exampleBlock(d.examples)); }
      if (d.last_run) { c.appendChild(el("p", "muted", d.last_run.line)); }
      var link = viewerLink(d.handoff ? VIEWER + d.handoff : null);
      if (link) { c.appendChild(link); }
      var acts = el("div", "actions");
      if (!d.busy) {
        acts.appendChild(act("Reply", function () { return { action: "issue_reply", job: d.id, message: message.value }; }));
        if (d.issue) { acts.appendChild(act("Prepare Start", function () { return { action: "issue_start", job: d.id }; }, "go")); }
        acts.appendChild(act("Abandon", function () { return { action: "issue_abandon", job: d.id, reason: message.value }; }));
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
    if (t.busy) { row.appendChild(el("span", null, "running")); }
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
      if (d.busy) { row.appendChild(el("span", null, "running")); }
      if (typeof d.spent_usd === "number" || d.spent_usd === null) { row.appendChild(el("span", null, usd(d.spent_usd) + " of " + usd(d.cap_usd))); }
      c.appendChild(row);
      if (d.state === "starting") { c.appendChild(el("p", "note", "The research is starting.")); }
      if (d.state === "refused") { c.appendChild(el("p", "note", "Refused before it started: " + d.line)); }
      if (d.stalled) { c.appendChild(el("p", "note", "No process from this chat is running it: it is running from the terminal or has stalled. Check argus status " + d.id + ".")); }
      if (d.question) { c.appendChild(el("p", "msg human", "Question: " + d.question)); }
      if (d.report) {
        var n = d.counts || {};
        var tally = " " + (n.SUPPORTED || 0) + " supported, " + (n.PARTIAL || 0) + " partial, " + (n.UNSUPPORTED || 0) + " unsupported.";
        c.appendChild(el("p", "note", d.checked ? "Checked by e1 (it only marks claims):" + tally : "Not checked by e1."));
        c.appendChild(el("p", "note", d.banner));
        if (d.report.withheld) { c.appendChild(el("p", "note", d.report.withheld)); }
        else {
          if (d.report.cut) { c.appendChild(el("p", "note", "Cut: sources at the end may be missing.")); }
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
    if (typeof r.spent_usd === "number") { row.appendChild(el("span", null, usd(r.spent_usd) + " of " + usd(r.cap_usd))); }
    c.appendChild(row);
    c.appendChild(el("p", "muted mono", r.id));
    c.appendChild(el("p", "note", r.sha12 ? "Draft " + r.sha12 + ". Read the draft in the viewer before deciding." : "No draft yet."));
    if (r.draft_problem) { c.appendChild(el("p", "note", "The draft cannot be read: " + r.draft_problem)); }
    if (r.busy) { c.appendChild(el("p", "note", "This chat is still running something on this job.")); }
    var link = viewerLink(VIEWER + r.id);
    if (link) { c.appendChild(link); }
    var acts = el("div", "actions");
    if (!r.busy && r.allowed && r.allowed.length) {
      var why = el("input", "reason");                  // the reason is in the card, above its buttons, never in a shared box
      why.type = "text";
      why.maxLength = 300;
      why.autocomplete = "off";
      why.placeholder = "Reason (required for Reject)";
      why.setAttribute("aria-label", "Reason");
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
  // SPEC_CHAT_UI3B: what waits for the person. The label is fixed here; a tap opens the card that already holds the button (the Queue tab), nothing is prepared from this list.
  function waitLabel(r) {
    if (r.action === "prd_approve") { return "Plan ready for your decision"; }
    if (r.action === "queue_go") { return "Queue waits for your go (money)"; }
    var n = typeof r.item === "number" ? "issue " + r.item : "the next issue";
    if (r.action === "queue_step") { return "Start " + n + " (drafter)"; }
    return "Draft of " + n + " is ready for you";
  }
  function waitingCard(r) {
    var c = el("article", "card compact waiting");
    c.appendChild(el("h2", null, waitLabel(r)));
    var row = el("div", "row");
    if (r.repo) { row.appendChild(el("span", null, r.repo)); }
    if (r.title && r.title !== r.repo) { row.appendChild(el("span", null, r.title)); }     // a queue's title is its repository's name: not twice
    c.appendChild(row);
    c.addEventListener("click", function () {
      setMode("cards");
      if (r.card === "plan") { showPlan(r.id); } else { showCard("queue", r.id); }
    });
    return c;
  }
  function waitingJobs() {                              // the code jobs behind the draft rows: they are also open jobs, and count once
    var w = {};
    waitingRows.forEach(function (r) { if (r.job) { w[r.job] = true; } });
    return w;
  }
  function openJobs() {
    var w = waitingJobs();
    return decisionRows.filter(function (d) { return !w[d.id]; });
  }
  function needCount() { return waitingRows.length + openJobs().length; }
  function renderDecisions() {
    clear(stream);
    var rows = openJobs();
    if (waitingRows.length) {
      stream.appendChild(el("h2", "sec-title", "Waiting for you"));
      waitingRows.forEach(function (r) { stream.appendChild(waitingCard(r)); });
    }
    if (waitingMeta.unknown) { stream.appendChild(el("p", "note", "The daily cap could not be computed: the queue's go and the steps of queues whose go was more than 24 hours ago are not listed.")); }
    if (waitingMeta.capped) { stream.appendChild(el("p", "note", "Not everything was checked: this list may be incomplete.")); }
    if (waitingMeta.stale) { stream.appendChild(el("p", "note", "Could not refresh this list: the rows shown may be out of date.")); }
    if (rows.length) {
      stream.appendChild(el("h2", "sec-title", "Open jobs"));
      rows.forEach(function (r) { stream.appendChild(decideCard(r)); });
    }
    if (!waitingRows.length && !rows.length) { stream.appendChild(el("p", "muted", "Nothing is waiting for you.")); }
  }
  function loadDecisions(rerender) {                    // rerender false: the poll in load() only refreshes the rows, the badge and the panel; the guarded poll and setMode draw the page
    var seq = ++decideSeq;
    var w = get("/api/waiting").catch(function () { return null; });
    get("/api/decisions").then(function (d) {
      return w.then(function (wd) { return [d, wd]; });
    }).then(function (both) {
      if (seq !== decideSeq) { return; }                // an older answer
      decisionRows = both[0].decisions || [];
      if (both[1]) {
        waitingRows = both[1].waiting || [];
        waitingMeta = { capped: !!both[1].capped, unknown: !!both[1].cap_unknown, stale: false };
      } else {
        waitingMeta = { capped: waitingMeta.capped, unknown: waitingMeta.unknown, stale: true };   // the list could not be read: the rows stay as they were and the page says they may be out of date
      }
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
  var TIER_TITLE = { same: "What must not change", whatif: "If ... then", after: "What changes" };
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
    if (!e.showable) { d.appendChild(el("p", "note", e.why || "this example cannot be shown as numbers")); }
    if (e.call) { kv(d, "function", e.call); }
    (e.assumptions || []).forEach(function (a) { kv(d, "Assume", a.name + " = " + a.shown); });
    (e.inputs || []).forEach(function (i) { kv(d, "input " + i.name, i.shown); });
    if (e.output && e.output.raises) { kv(d, "output", e.output.shown); }
    else if (e.output) { e.output.forEach(function (o) { kv(d, "output" + (o.label ? " " + o.label : ""), o.shown); }); }
    if (e.proof) { say(d, "mesin", "machine", e.proof.wording, "say proof"); }
    return d;
  }
  function planReading(card, r) {                       // the domain reader's note: a model's statement, with the server's label
    var box = el("div", "reader");
    if (!DOMAIN_LABEL) { box.appendChild(el("p", "note", "reading not shown: the label 'not proof, not a human' is missing")); card.appendChild(box); return; }
    if (r.fresh) {
      var by = who_(r.reader) ? " (" + who_(r.reader) + (who_(r.reader2) ? " and " + who_(r.reader2) : "") + ")" : "";
      say(box, "pembaca", "number reader", "Read by Claude, " + r.at + ": " + (r.verdict === "ok" ? "matches the request" : "something is doubtful") + " (" + (r.sources || []).join("; ") + ")" + by, r.verdict === "ok" ? "say" : "say warn");
      modelLine(box, r.note);
      box.appendChild(el("p", "small", DOMAIN_LABEL));
    } else {
      box.appendChild(el("p", "note", r.why));
    }
    card.appendChild(box);
  }
  function countLine(it) {                              // only the counts the server sends (calls, same, whatif, after); nothing from the examples is tallied
    var c = it.counts;
    return c ? c.calls + " examples (unchanged " + c.same + ", if-then " + c.whatif + ", changed " + c.after + ")" : null;
  }
  function planItem(it, dim) {
    var c = el("div", "issue" + (dim ? " stale" : ""));
    c.appendChild(el("h4", null, "Issue " + it.n));
    if (it.title) { say(c, "model", MODEL, it.title, "say"); }
    if (it.warning) { c.appendChild(el("p", "note", it.warning)); }
    if (it.no_examples) { modelLine(c, "no examples: " + it.no_examples); }
    if (it.why) { c.appendChild(el("p", "small", it.why)); }
    if (it.examples && it.examples.withheld) { c.appendChild(el("p", "note", "examples withheld by the harness")); return c; }
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
      var b = el("button", "go", "Accept plan");
      b.type = "button";
      b.addEventListener("click", function () { prepare({ action: "prd_approve", job: id }); });
      box.appendChild(b);
      box.appendChild(el("p", "small", "No money is spent: this creates a queue that still waits for the money go."));
    } else if (t4.action === "queue_go") {                // SPEC_CHAT_T4A: the money. The page sends the job id, the acknowledgement the server names and the typed reason, nothing else
      var needs = t4.needs || [], ackItems = t4.ack_items || [], tick = null, why = null;
      var p = el("button", "go", "Run queue (money is spent)");
      p.type = "button";
      if (needs.indexOf("ack") >= 0) {
        var lab = el("label", "small");
        tick = el("input");
        tick.type = "checkbox";
        lab.appendChild(tick);
        lab.appendChild(document.createTextNode(" I accept: issue " + ackItems.join(", ") + " has no example of new behaviour, so the machine cannot check its numbers."));
        box.appendChild(lab);
      }
      if (needs.indexOf("reason") >= 0) {
        why = el("input", "reason");
        why.type = "text";
        why.maxLength = 500;
        why.autocomplete = "off";
        why.placeholder = "Reason for accepting this cost (10 to 500 characters)";
        why.setAttribute("aria-label", "Reason");
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
      box.appendChild(el("p", "small", "Releases money for the whole queue, up to the limit shown on the next card. Nothing runs yet; the first issue is started from the queue card."));
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
      cardHead(card, "Plan card", d, (d.turn ? [{ text: "turn " + d.turn }] : []));
      if (d.stale) { card.appendChild(el("p", "note", "Result is on an old commit: the repo has moved on since this folder was written.")); }
      if (d.superseded) { card.appendChild(el("p", "note", "This folder has been replaced by a later turn.")); }
      if (d.why) { card.appendChild(el("p", "note", d.why)); }
      var s1 = sec(card, "1. What was asked?");
      if (d.request) {
        say(s1, d.request_by === "chat" ? "atha" : "tak", d.request_by === "chat" ? "request, started from the chat (recorded via the UI):" : "request (author not recorded):", d.request, "say");
        if (d.request_truncated) { s1.appendChild(el("p", "note", "request cut")); }
      } else { s1.appendChild(el("p", "note", "request not recorded")); }
      var s2 = sec(card, "2. What will be done?");
      if (d.summary) { say(s2, "model", MODEL, d.summary, "say"); } else if (d.summary_why) { s2.appendChild(el("p", "note", d.summary_why)); }
      s2.appendChild(el("p", "small", d.issue_count + " issue"));
      var s3 = sec(card, "3. The result, in numbers");
      if (d.defects) { s3.appendChild(el("p", "note", d.defects + " examples cannot be shown as numbers (defective card)")); }
      (d.items || []).forEach(function (it) { s3.appendChild(planItem(it, dim)); });
      var s4 = sec(card, "4. What is the cost limit?");
      if (d.cost) {
        var ref = d.cost.reference && d.cost.reference.median !== null && d.cost.reference.median !== undefined ? "; reference: median " + usd(d.cost.reference.median) + " of " + d.cost.reference.n + " " + d.cost.reference.of : "; reference: not enough data";
        if (!d.cost.ratio_text) { s4.appendChild(el("p", "say", "Limit ratio: not enough data from earlier jobs.")); }
        if (d.cost.ratio_text) { say(s4, "mesin", "machine", "Requested limit " + d.cost.ratio_text + " (1 = usual; the limit is a fence, not an estimate of cost).", "say big"); }
        s4.appendChild(el("p", "small", "job cost " + usd(d.cost.spent) + "; queue limit for " + d.issue_count + " issues " + usd(d.cost.proposed) + (d.cost.proposed_each !== null && d.cost.proposed_each !== undefined ? " (" + usd(d.cost.proposed_each) + " per issue)" : "") + ref + " (reference: one job)"));
      }
      var s5 = sec(card, "5. What has nobody checked?");
      s5.appendChild(el("p", "say", d.fixed_line));
      stream.appendChild(card);
      stream.appendChild(planActions(id, d.t4));
      stream.appendChild(cardButtons([{ text: "Technical card", fn: function () { showCard("prd", id); } }]));
    }).catch(function () {
      if (seq !== cardSeq || mode !== "cards") { return; }
      clear(stream);
      stream.appendChild(el("p", "muted", "The plan card cannot be read."));
      stream.appendChild(cardButtons());
    });
  }
  function installReader(box, title, r, label) {
    box.appendChild(el("h4", null, title));
    if (!r) { box.appendChild(el("p", "note", "no note yet")); return; }
    var line = function (x, n) {
      var by = who_(x.reader) ? " (" + who_(x.reader) + ")" : "";
      var nit = x.verdict === "concerns" && x.severity === "nit";
      var who = (x.reader && x.reader.kind === "argus") ? "Model" : "Claude";
      say(box, "pembaca", "patch reader " + n, who + ", " + x.at + ": " + (x.verdict === "ok" ? "ok" : nit ? "minor note (nit)" : "something is doubtful") + by, x.verdict === "ok" || nit ? "say" : "say warn");
      modelLine(box, x.note);
    };
    line(r, 1);
    if (r.second) { line(r.second, 2); }
    box.appendChild(el("p", "small", label));
  }
  // SPEC_CHAT_UI3D: the detail of a job's last draft. Read only: GET only, text nodes only. The diff lines carry their own + and - so colour is never the only mark;
  // the writer's words are labelled model text; what the machine checked (the old text's hash) is labelled machine.
  function diffBlock(text) {
    var box = el("div", "diff");
    String(text).split("\n").forEach(function (ln, i) {
      var head = i < 2 && (ln.indexOf("--- ") === 0 || ln.indexOf("+++ ") === 0);       // only the two header lines: a changed line that starts with ++ is still a changed line
      var k = head ? "hdr" : (ln.charAt(0) === "+" ? "add" : (ln.charAt(0) === "-" ? "del" : (ln.charAt(0) === "@" ? "hunk" : "ctx")));
      box.appendChild(el("div", "dl " + k, ln === "" ? " " : ln));
    });
    return box;
  }
  function showDraft(job) {
    var seq = ++cardSeq;
    openCard = job;
    openKind = "draft";
    get("/api/draft/" + encodeURIComponent(job)).then(function (d) {
      if (seq !== cardSeq || mode !== "cards") { return; }
      clear(stream);
      var c = el("article", "card");
      c.appendChild(el("h2", null, "Draft details"));
      fact(c, "Job", d.job);
      fact(c, "Draft sha", d.draft_sha12);
      fact(c, "State", d.state);
      var s2 = sec(c, "Existing tests this draft changes");
      if (d.tests_ok === false) { s2.appendChild(el("p", "note", "The list of changed tests cannot be read.")); }
      else if (!d.tests_n) { s2.appendChild(el("p", "muted", "None: the draft only adds new tests.")); }
      (d.tests || []).forEach(function (t) {
        var box = el("div", "ex2");
        box.appendChild(el("p", "mono", t.path || "(path not shown)"));
        if (t.diff !== null && t.diff !== undefined) {
          if (t.before === "matches") { say(box, "mesin", "old text matches the recorded hash", "", "small"); }
          else if (t.before === "differs") { say(box, "mesin", "warning", "the old text does NOT match the recorded hash: this diff may not be against the version the drafter saw", "say warn"); }
          else { say(box, "mesin", "no recorded hash to check the old text against", "", "small"); }
          if (t.diff === "") { box.appendChild(el("p", "muted", "No difference between the old text and the new text.")); }
          else { box.appendChild(diffBlock(t.diff)); }
          if (t.diff_cut) { box.appendChild(el("p", "note", "The diff is cut here: it is longer than the page shows.")); }
        }
        if (t.note) { box.appendChild(el("p", "note", t.note)); }
        (t.removed || []).forEach(function (n) { say(box, "model", "removed (written by a model)", n.node + ": " + n.reason, "say"); });
        (t.modified || []).forEach(function (n) { say(box, "model", "modified (written by a model)", n.node + ": " + n.reason, "say"); });
        s2.appendChild(box);
      });
      if (d.tests_n > (d.tests || []).length) { s2.appendChild(el("p", "note", "Only the first " + d.tests.length + " of " + d.tests_n + " files are shown.")); }
      if (d.summary_note) { s2.appendChild(el("p", "note", "The writer's plan is not available for this draft.")); }
      var s1 = el("details", "more");                      // the list can be long: folded, after the diff the person came for
      s1.appendChild(el("summary", null, "May write " + (d.writable || []).length + " files, must pass " + (d.must_pass || []).length + " tests"));
      (d.writable || []).forEach(function (w) { say(s1, "mesin", "may write", w, "say"); });
      (d.must_pass || []).forEach(function (w) { say(s1, "mesin", "must pass", w, "say"); });
      c.appendChild(s1);
      var s3 = sec(c, "The writer's text (written by a model, not proof)");
      var pl = d.plan || {};
      [["step", pl.steps], ["file", pl.files], ["risk", pl.risks], ["warning", d.warnings], ["not proven by the machine", d.unverifiable]].forEach(function (kv) {
        (kv[1] || []).forEach(function (x) { say(s3, "model", kv[0] + " (written by a model)", x, "say"); });
      });
      stream.appendChild(c);
      stream.appendChild(cardButtons());
    }).catch(function () {
      if (seq !== cardSeq || mode !== "cards") { return; }
      clear(stream);
      stream.appendChild(el("p", "muted", "The draft details cannot be read."));
      stream.appendChild(cardButtons());
    });
  }
  function showInstall(id) {
    var seq = ++cardSeq;
    openCard = id;
    get("/api/approve/code/" + encodeURIComponent(id)).then(function (d) {
      if (seq !== cardSeq || mode !== "cards") { return; }
      clear(stream);
      DOMAIN_LABEL = d.domain_read_label || "";
      var card = el("article", "card install");
      cardHead(card, "Install card", d, d.patch_sha12 ? [{ text: "patch " + d.patch_sha12, cls: "mono" }] : []);
      card.appendChild(el("p", d.open ? "say" : "note", d.open ? "No condition is closed (conditions that are not applicable or are not recorded are named in the list). This is not a guarantee of safety." : "Install is closed: a condition is not met."));
      var s1 = sec(card, "1. What is the purpose?");
      say(s1, /model/.test(String(d.purpose.by)) ? "model" : "tak", d.purpose.by, d.purpose.title, "say");
      if (d.purpose.text) { modelLine(s1, d.purpose.text); }
      var s2 = sec(card, "2. Result of the change, in numbers");
      if (d.item) { s2.appendChild(planItem(d.item, false)); }
      var s3 = sec(card, "3. Which files does it touch?");
      var files = d.files || [];
      var flagged = files.filter(function (f) { return f.marks.length; }).length;
      s3.appendChild(el("p", "sum", files.length + " files, " + flagged + " flagged by the machine"));
      files.forEach(function (f) {
        var p = el("p", f.marks.length ? "file flagged" : "file");
        p.appendChild(el("span", "mono", f.path));
        if (f.marks.length) { p.appendChild(who("mesin", "machine")); p.appendChild(document.createTextNode(" " + f.marks.join("; "))); }
        s3.appendChild(p);
      });
      if (!files.length) { s3.appendChild(el("p", "note", "the file list cannot be read")); }
      if (d.files_cut) { s3.appendChild(el("p", "note", d.files_cut + " more files not shown")); }
      if (d.scope_note) { s3.appendChild(el("p", "note", d.scope_note)); }
      var s4 = sec(card, "4. Install conditions");
      var checks = d.checks || [];
      var n = { ya: 0, tidak: 0, na: 0 };
      checks.forEach(function (c) { if (c.ok === true) { n.ya++; } else if (c.ok === false) { n.tidak++; } else { n.na++; } });
      s4.appendChild(el("p", "sum", checks.length + " conditions: " + n.ya + " yes, " + n.tidak + " NO, " + n.na + " not applicable"));
      checks.forEach(function (c) {
        s4.appendChild(el("p", c.ok === false ? "cond bad" : "cond", "(" + c.key + ") " + (c.ok === true ? "yes" : c.ok === false ? "NO" : "not applicable") + ": " + c.label + (c.why ? " - " + c.why : "")));
      });
      var s5 = sec(card, "5. Who reads the patch?");
      installReader(s5, "Patch reader", d.patch_read, d.patch_read_label);
      s5.appendChild(el("p", "small", d.patch_reader_tested ? "patch reader has been tested" : "patch reader has not been tested"));
      s5.appendChild(el("p", "small", d.domain_reader_tested ? "number reader has been tested" : "number reader has not been tested"));
      if (d.approval) { s5.appendChild(el("p", "small", "draft decision: " + d.approval.at + " by " + d.approval.by + " (" + d.approval.note + ")")); }
      var s6 = sec(card, "6. What does it cost?");
      if (d.cost) {
        s6.appendChild(el("p", "say", "job cost " + usd(d.cost.spent) + "; job limit " + usd(d.cost.cap) + (d.cost.reference && d.cost.reference.cap_median !== null && d.cost.reference.cap_median !== undefined ? "; usual job limit (median) " + usd(d.cost.reference.cap_median) : "")));
      }
      var s7 = sec(card, "7. What has nobody checked?");
      s7.appendChild(el("p", "say", d.fixed_line));
      stream.appendChild(card);
      stream.appendChild(cardButtons());
    }).catch(function () {
      if (seq !== cardSeq || mode !== "cards") { return; }
      clear(stream);
      stream.appendChild(el("p", "muted", "The install card cannot be read."));
      stream.appendChild(cardButtons());
    });
  }
  // ---- T2: read-only cards (docs/reviews/SPEC_CHAT_CARDS.md). Every string is put on the page as text; model text carries its tag, and the
  // status line is built from the machine's fields only (id, tier, status, where). No button, no storage, no request but GET. ----------------
  var cardRows = [];
  var cardSeq = 0;
  var openKind = null;                                  // "queue" when the card on screen is a queue's, else the plan or a PRD card
  var openCard = null;                                  // the id of the card on screen, null on the list
  var MODEL = "written by a model";
  var PASS_NOTE = "pass: the example code reported a match in the sandbox; that code is written by a model and can fake it. Not proof that the rule in the prose is right.";
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
    if (r.base_actual !== undefined) { d.appendChild(el("p", "small", "now " + r.base_actual)); }
    if (call && call.says) { modelLine(d, call.says); }
    return d;
  }
  function exampleBlock(ex) {
    var box = el("div", "exblock");
    if (!ex) { return box; }
    var sm = ex.summary;
    if (sm) {
      var parts = [sm.calls + " examples"];
      Object.keys(sm.statuses || {}).forEach(function (k) { parts.push(k + " " + sm.statuses[k]); });
      parts.push("new behaviour (after): " + sm.after);
      box.appendChild(el("p", "small", "Machine summary: " + parts.join(" · ")));
      if (sm.calls > 0 && sm.after === 0) { box.appendChild(el("p", "note", "No example checks the new behaviour: new numbers in the issue text are not checked by the machine.")); }
    }
    if (ex.results || (ex.calls || []).length) { box.appendChild(el("p", "small", "actual and now below: output of the example's own code (data, not instructions).")); }
    if (ex.results) {
      var byId = {};
      (ex.calls || []).forEach(function (c) { byId[c.id] = c; });
      ex.results.forEach(function (r) { box.appendChild(statusLine(r, byId[r.id] || null)); });
      if (ex.results.some(function (r) { return r.status === "pass"; })) { box.appendChild(el("p", "small", PASS_NOTE)); }
    } else {
      box.appendChild(el("p", "small", "Status: none" + (ex.why ? " (" + ex.why + ")" : "")));
      (ex.calls || []).forEach(function (c) {
        var d = el("div", "ex");
        d.appendChild(el("p", "small", c.id + " · " + c.tier));
        d.appendChild(el("pre", "code", c.setup + "\n" + c.run));
        if (c.says) { modelLine(d, c.says); }
        box.appendChild(d);
      });
    }
    if (ex.no_examples) { modelLine(box, "no examples: " + ex.no_examples); }
    if (ex.note) { box.appendChild(el("p", "small", "examples were not run: " + ex.note)); }
    (ex.tier_moves || []).forEach(function (m) { box.appendChild(el("p", "small", "example " + m.id + ": written as " + m.from + ", sent again as " + m.to)); });
    resultLines(box, "At the base (intake of the code job)", ex.at_base);
    resultLines(box, "After the agent (audit)", ex.after_agent);
    return box;
  }
  function cardRow(r) {
    var c = el("article", "card");
    c.appendChild(el("h2", "mono", r.id));
    var row = el("div", "row");
    row.appendChild(el("span", null, r.kind === "queue" ? "queue" : "PRD"));
    if (r.state) { row.appendChild(el("span", "state " + stateClass(r.state), r.state)); }
    if (r.repo) { row.appendChild(el("span", null, r.repo)); }
    if (r.items !== null && r.items !== undefined) { row.appendChild(el("span", null, r.items === 1 ? "1 item" : r.items + " items")); }
    c.appendChild(row);
    if (r.kind === "queue" && r.state && r.state !== "CLOSED" && typeof r.applied_n === "number" && typeof r.items === "number" && r.items > 0) {      // only items whose card shows a commit count; nothing running or failed is called done
      var bar = el("progress", "pbar");
      bar.max = r.items;
      bar.value = r.applied_n;
      bar.setAttribute("aria-label", r.applied_n + " of " + r.items + " applied");
      c.appendChild(bar);
      c.appendChild(el("p", "small", r.applied_n + " of " + r.items + " applied"));
    }
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
    (it.touches || []).forEach(function (t) { modelLine(c, "touches " + t); });
    (it.creates || []).forEach(function (t) { modelLine(c, "creates " + t); });
    (it.clashes || []).forEach(function (k) { modelLine(c, "clashes with " + k.file + ":" + k.line + " " + k.why); });
    if (it.examples) { c.appendChild(el("h2", null, "Examples")); c.appendChild(exampleBlock(it.examples)); }
    return c;
  }
  function stepActions(id, t4b) {                      // SPEC_CHAT_T4B: the server says which button the builders would let through (queues approved from the chat only)
    var box = el("div", "nav");
    if (!t4b) { return box; }
    if (t4b.action === "queue_step" || t4b.action === "draft_approve") {
      var b = el("button", "go", t4b.action === "queue_step" ? "Start issue " + t4b.item : "Accept draft of issue " + t4b.item);
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
      if (d.turn) { row.appendChild(el("span", null, "turn " + d.turn)); }
      if (d.folder_sha12) { row.appendChild(el("span", "mono", d.folder_sha12)); }
      head.appendChild(row);
      if (d.stale) { head.appendChild(el("p", "note", "Result is on an old commit: the repo has moved on since this folder was written.")); }
      if (d.superseded) { head.appendChild(el("p", "note", "This folder has been replaced by a later turn.")); }
      if (d.why) { head.appendChild(el("p", "note", d.why)); }
      if (d.next) { head.appendChild(el("p", "msg", d.next)); }
      if (d.closed) { head.appendChild(el("p", "small", "closing note: " + d.closed)); }
      if (d.prd_md) { head.appendChild(el("span", "tag", MODEL + ": PRD")); head.appendChild(el("p", "msg", d.prd_md)); }
      (d.questions || []).forEach(function (q) { modelLine(head, "? " + q); });
      (d.warnings || []).forEach(function (w) { head.appendChild(el("p", "note", w)); });
      if (d.money) { head.appendChild(el("p", "small", "job cost " + usd(d.money.spent) + " of " + usd(d.money.job_cap) + (d.money.queue_usd !== null && d.money.queue_usd !== undefined ? "; queue proposed " + usd(d.money.queue_usd) : ""))); }
      (d.queues || []).forEach(function (q) { head.appendChild(el("p", "small", "queue " + q)); });
      if (kind === "prd") {
        var plan = el("button", null, "Plan card (numbers)");
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
          r2.appendChild(el("span", null, it.job ? it.job : "no job yet"));
          if (it.job_state) { r2.appendChild(el("span", "state " + stateClass(it.job_state), it.job_state)); }
          if (it.applied) { r2.appendChild(el("span", "mono", "applied " + it.applied)); }
          if (!it.text_matches) { r2.appendChild(el("span", "note", "the issue file changed")); }
          q.appendChild(r2);
          if (it.job && (it.job_state === "AWAITING_APPROVAL" || it.job_state === "REVIEW_READY" || it.job_state === "APPLIED")) {
            var det = el("button", null, "Draft details");
            det.type = "button";
            det.addEventListener("click", function () { showDraft(it.job); });
            q.appendChild(det);
          }
          if (it.job && it.job_state === "REVIEW_READY") {
            var inst = el("button", null, "Install card (numbers)");
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
  function updateSummary() {                            // the line under the title: how many jobs, and how many items wait for the person (the same number as the badge)
    summary.textContent = nJobs(threads.length) + (needCount() ? " · " + needCount() + " waiting" : "");
    var spent = 0;
    threads.forEach(function (t) { spent += typeof t.stages_usd === "number" ? t.stages_usd : 0; });
    document.getElementById("panel-cost").textContent = "Recorded stage cost: " + usd(spent);
  }
  function setChrome() {                              // the box sits above the tab bar in the Chat tab only; the "+" menu closes with every move
    var inChat = mode === "status" || mode === "issue" || mode === "prd" || mode === "research" || mode === "manager";
    document.getElementById("dock").hidden = !inChat;
    closeMenu();
  }
  function closeMenu() {
    document.getElementById("plus-menu").hidden = true;
    document.getElementById("plus").setAttribute("aria-expanded", "false");
    document.getElementById("more-menu").hidden = true;
    document.getElementById("more").setAttribute("aria-expanded", "false");
  }
  function openNew() {                                // the panel's New request: the Chat tab, writing a new issue
    closePanel();
    setMode("issue");
  }
  function closePanel() { panel.classList.remove("open"); document.getElementById("scrim").hidden = true; }
  function updateBadge() {                              // the number of jobs that wait for a decision, from the same list the Keputusan tab shows
    var b = document.getElementById("decide-badge"), n = needCount();
    b.hidden = n === 0;
    b.textContent = n > 9 ? "9+" : String(n);
    updateSummary();
    b.setAttribute("aria-label", n + (n === 1 ? " item" : " items") + " waiting for you");
  }
  var capInfo = null;                                    // {cap_usd, booked_usd, unknown} from /api/cap; null until read; {failed: true} when it could not be read
  var DAY_MS = 24 * 3600 * 1000;
  function usd2(n) { return "$" + n.toFixed(2); }
  var capSeq = 0;
  function loadCap() {
    var seq = ++capSeq;
    get("/api/cap").then(function (d) { if (seq === capSeq) { capInfo = d; if (mode === "cost") { renderCost(); } } })
      .catch(function () { if (seq === capSeq) { capInfo = { failed: true }; if (mode === "cost") { renderCost(); } } });
  }
  var JOB_TIME = /^j(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})_[0-9a-f]{4}$/;
  function recentJob(t) {                               // the time written in the job's id (UTC), not a field of the file: a forged or local-time date cannot move a job into or out of the window
    var m = JOB_TIME.exec(String(t.id));
    if (!m) { return false; }
    var ms = Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +m[6]), age = Date.now() - ms;
    return age >= 0 && age <= DAY_MS;
  }
  function renderCost() {                               // two different numbers: what the cap counts (booked, from the server) and what the jobs recorded (from the job list). Never merged, unknown never shown as zero.
    clear(stream);
    var booked = el("article", "card");
    booked.appendChild(el("h2", null, "Booked against the daily cap"));
    if (capInfo === null) {
      booked.appendChild(el("p", "muted", "Loading…"));
    } else if (capInfo.failed || capInfo.unknown || typeof capInfo.booked_usd !== "number" || typeof capInfo.cap_usd !== "number") {
      booked.appendChild(el("p", "note", "The daily cap could not be computed right now."));
    } else {
      fact(booked, "Booked (last 24 hours)", usd2(capInfo.booked_usd) + " of " + usd2(capInfo.cap_usd));
      if (capInfo.cap_usd > 0) {
        var bar = el("progress", "pbar");
        bar.max = capInfo.cap_usd;
        bar.value = Math.min(capInfo.booked_usd, capInfo.cap_usd);
        bar.setAttribute("aria-label", usd2(capInfo.booked_usd) + " of " + usd2(capInfo.cap_usd) + " booked");
        booked.appendChild(bar);
      }
      fact(booked, "Left", usd2(Math.max(0, capInfo.cap_usd - capInfo.booked_usd)));
    }
    booked.appendChild(el("p", "note", "The cap counts the full limit of every job, start, reply and queue started from this chat in the last 24 hours, not what they spent. A request whose own limit is more than Left is refused."));
    stream.appendChild(booked);
    var day = threads.filter(recentJob), dayTotal = 0, dayBy = Object.create(null), dayUnknown = 0;
    day.forEach(function (t) {
      if (t.stages_unknown) { dayUnknown++; }
      var u = typeof t.stages_usd === "number" ? t.stages_usd : 0;
      dayTotal += u;
      var k = KIND_LABEL[t.kind] || "Other";
      dayBy[k] = (dayBy[k] || 0) + u;
    });
    var spent = el("article", "card");
    spent.appendChild(el("h2", null, "Recorded in the last 24 hours"));
    fact(spent, "Total (" + nJobs(day.length) + " created)", usd(dayTotal));
    Object.keys(dayBy).sort().forEach(function (k) { fact(spent, k, usd(dayBy[k])); });
    if (dayUnknown) { spent.appendChild(el("p", "note", nJobs(dayUnknown) + (dayUnknown === 1 ? " has" : " have") + " a stage with no cost figure: not counted, not zero.")); }
    spent.appendChild(el("p", "note", "Stage costs written in the job files of jobs created in the last 24 hours. Money still being spent by a running stage is not in it yet."));
    if (threads.length >= 100) { spent.appendChild(el("p", "note", "The list holds only the newest 100 jobs: this total may be incomplete.")); }       // LIST_MAX of the server
    stream.appendChild(spent);
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
    c.appendChild(el("p", "note", "Only stage figures recorded in the job list (the newest only)."));
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
    fromProposal = null;
    mgrStop();
    dropPending();
    var inChat = m === "status" || m === "issue" || m === "prd" || m === "research" || m === "manager";
    if (inChat) { lastChat = m; }
    Array.prototype.forEach.call(document.querySelectorAll("#tabs button"), function (b) {
      var t = b.getAttribute("data-tab");
      b.setAttribute("aria-pressed", (inChat ? t === "chat" : t === m) ? "true" : "false");
    });
    issueForm.hidden = !inChat;
    setChrome();
    researchSeq++;
    openCard = null;
    openResearch = null;
    openDecision = null;
    formState();
    if (m === "issue") { openIssue = null; formState(); loadIssues(); renderIssues(); }
    else if (m === "prd") { openIssue = null; formState(); loadIssues(); clear(stream); stream.appendChild(el("p", "muted", "Write a request for the PRD writer below. One turn; the result appears in the Queue tab.")); }
    else if (m === "research") { loadResearch(); renderResearchList(); }
    else if (m === "manager") { openIssue = null; formState(); loadManager(); }
    else if (m === "decide") { loadDecisions(); renderDecisions(); }
    else if (m === "cards") { loadCards(); renderCards(); }
    else if (m === "cost") { capInfo = null; renderCost(); loadCap(); }
    else { renderOverview(); }
  }
  Array.prototype.forEach.call(document.querySelectorAll("#plus-menu button"), function (b) {
    b.addEventListener("click", function () { setMode(b.getAttribute("data-mode")); });
  });
  document.getElementById("more").addEventListener("click", function () {
    var menu = document.getElementById("more-menu"), now = menu.hidden;
    closeMenu();
    menu.hidden = !now;
    this.setAttribute("aria-expanded", now ? "true" : "false");
  });
  document.getElementById("refresh").addEventListener("click", function () { closeMenu(); load(); });
  document.getElementById("plus").addEventListener("click", function () {
    var menu = document.getElementById("plus-menu"), now = menu.hidden;
    menu.hidden = !now;
    this.setAttribute("aria-expanded", now ? "true" : "false");
  });
  Array.prototype.forEach.call(document.querySelectorAll("#tabs button"), function (b) {
    b.addEventListener("click", function () { var t = b.getAttribute("data-tab"); setMode(t === "chat" ? (mode === lastChat && lastChat !== "status" ? "status" : lastChat) : t); });
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
    if (mode === "manager") { sendTurn(); return; }
    if (mode === "decide") { return; }
    if (mode === "research") { prepare({ action: "research_new", message: message.value }); }
    else if (mode === "prd") { prepare({ action: "prd_new", repo: repoSel.value, message: message.value }); }
    else if (openIssue !== null) { prepare({ action: "issue_reply", job: openIssue, message: message.value }); }
    else { prepare({ action: "issue_new", repo: repoSel.value, message: message.value }); }
  });
  query.addEventListener("input", function () { renderList(); if (current === null) { renderOverview(); } });
  document.getElementById("composer").addEventListener("submit", function (e) { e.preventDefault(); });
  document.getElementById("open-panel").addEventListener("click", function () { panel.classList.add("open"); document.getElementById("scrim").hidden = false; });
  document.getElementById("close-panel").addEventListener("click", closePanel);
  document.getElementById("scrim").addEventListener("click", closePanel);
  document.getElementById("new-request-panel").addEventListener("click", openNew);
  // ---- P3: the foreman (SPEC_CHAT_MANAGER_P1, P2b). A session is one confirmation; its turns are POST /api/manager/turn with the session and the message, nothing else.
  // The foreman's words and its proposals are text from a model: put on the page as text, labelled, never as a card. A proposal is not a start: its button only
  // PREPARES (the same card, the same Confirm as a typed form), and says where the text came from.
  var mgr = { job: null, data: null, seq: 0, epoch: 0, sending: false, stuck: false, timer: null, left: 0, before: 0, expect: 0, retry: null };
  var fromProposal = null;                              // {job, turn}: the form was filled from a proposal; every move of the mode clears it
  function mgrStop() {
    mgr.seq++;
    mgr.epoch++;
    mgr.stuck = false;
    if (mgr.timer) { clearTimeout(mgr.timer); mgr.timer = null; }
    if (mgr.retry) { clearTimeout(mgr.retry); mgr.retry = null; }
    mgr.left = 0;
  }
  function timeLeft(s) {
    if (typeof s !== "number") { return "unknown"; }
    var m = Math.floor(s / 60);
    return Math.floor(m / 60) + " h " + (m % 60) + " min";
  }
  function loadManager() {
    var my = ++mgr.seq;
    get("/api/threads").then(function (d) {
      if (mode !== "manager" || my !== mgr.seq) { return; }
      var open = (d.threads || []).filter(function (t) { return t.kind === "manager" && t.state === "OPEN"; })[0];
      if (!open) {
        mgr.job = null;
        mgr.data = null;
        renderManager();
        if (mgr.expect > 0) { mgr.expect--; if (mgr.retry) { clearTimeout(mgr.retry); } mgr.retry = setTimeout(loadManager, 2000); }
        return;
      }
      mgr.expect = 0;
      if (mgr.job !== open.id) { mgr.stuck = false; }
      mgr.job = open.id;
      return get("/api/manager/" + encodeURIComponent(open.id)).then(function (m) {
        if (mode !== "manager" || my !== mgr.seq) { return; }
        mgr.data = m;
        renderManager();
      });
    }).catch(function () { if (mode === "manager" && my === mgr.seq) { clear(stream); stream.appendChild(el("p", "muted", "Cannot read the foreman session.")); } });
  }
  function proposalBox(e) {
    var p = e.propose;
    var b = el("div", "proposal");
    if (p.route === "ask") { b.appendChild(el("p", "note", "The foreman is waiting for your answer.")); return b; }
    if (p.route !== "research" && p.route !== "prd") { b.appendChild(el("p", "note", "The foreman sees no route for this in Argus.")); return b; }
    b.appendChild(el("h3", null, "The foreman proposes: " + (p.route === "prd" ? "a PRD" : "research")));
    if (p.route === "prd") { fact(b, "Repo", p.repo || "none named: use Edit first"); }
    b.appendChild(el("p", "msg", p.text));
    say(b, "model", "reason (written by the model)", p.why, "say");
    b.appendChild(el("p", "note", "Nothing is started. Prepare shows a card; you read it and confirm it yourself."));
    var row = el("div", "actions");
    var ready = p.route === "research" || !!p.repo;
    var go = el("button", "go", "Prepare");
    go.type = "button";
    go.disabled = !ready;
    go.addEventListener("click", function () {
      var body = p.route === "prd" ? { action: "prd_new", repo: p.repo, message: p.text } : { action: "research_new", message: p.text };
      body.source_job = mgr.job;
      body.source_turn = String(e.n);
      prepare(body);
    });
    var edit = el("button", null, "Edit first");
    edit.type = "button";
    edit.addEventListener("click", function () {
      var job = mgr.job;
      setMode(p.route);                                // clears fromProposal; the form is then filled, and its submit carries the source
      message.value = p.text;
      if (p.route === "prd" && p.repo) { repoSel.value = p.repo; }
      fromProposal = { job: job, turn: e.n };
    });
    row.appendChild(go);
    row.appendChild(edit);
    b.appendChild(row);
    return b;
  }
  function renderManager() {
    clear(stream);
    var d = mgr.data;
    var c = el("article", "card");
    c.appendChild(el("h2", null, "Foreman"));
    if (!mgr.job || !d) {
      c.appendChild(el("p", "note", mgr.expect > 0 ? "The session is starting." : "Think an idea through with the foreman, a model. It can propose research or a PRD, but it starts nothing: you prepare, read and confirm. One confirmation covers the whole session, up to its limit."));
      if (mgr.expect <= 0) { c.appendChild(act("Prepare a session", function () { return { action: "manager_new" }; }, "go")); }
      stream.appendChild(c);
      return;
    }
    var row = el("div", "row");
    row.appendChild(el("span", "state " + stateClass(d.state), d.state));
    row.appendChild(el("span", null, "left " + (typeof d.max_usd === "number" && typeof d.spent_usd === "number" ? usd(Math.max(0, d.max_usd - d.spent_usd)) + " of " + usd(d.max_usd) : "unknown")));
    row.appendChild(el("span", null, "time left " + timeLeft(d.expires_in_s)));
    c.appendChild(row);
    if (d.busy) { c.appendChild(el("p", "note", "The foreman is answering.")); }
    var turns = (d.conversation || []).filter(function (e) { return e.from === "human"; }).length;
    var over = mgr.stuck || d.expires_in_s === 0 || (typeof d.turn_cap_usd === "number" && typeof d.max_usd === "number" && typeof d.spent_usd === "number" && d.max_usd - d.spent_usd < d.turn_cap_usd) || (typeof d.max_turns === "number" && turns >= d.max_turns);
    if (!(d.conversation || []).length) { c.appendChild(el("p", "muted", "Say something below.")); }
    (d.conversation || []).forEach(function (e) {
      if (e.from === "human") { c.appendChild(el("p", "msg human", "You: " + e.text)); return; }
      say(c, "model", "foreman (a model, not Argus)", e.say, "say foreman");
      if (e.error) { c.appendChild(el("p", "note", "This turn failed: " + e.error)); }
      if (e.propose) { c.appendChild(proposalBox(e)); }
    });
    if (over && !d.busy) {                              // the server leaves an expired or used-up session OPEN and refuses its turns: the way on is a new session (a new confirmation)
      c.appendChild(el("p", "note", "This session cannot take another turn (time, budget or turns used up, or refused). Start a new one: the old one stays as it is."));
      c.appendChild(act("Prepare a new session", function () { return { action: "manager_new" }; }, "go"));
    }
    stream.appendChild(c);
  }
  function pollManager() {                              // after a turn is sent: read the session every 2 s until the answer is in, or 2 minutes
    var n = mgr.data && mgr.data.conversation ? mgr.data.conversation.length : 0;
    mgr.left--;
    if (mgr.left <= 0 || (mgr.data && !mgr.data.busy && n >= mgr.before + 2)) { mgr.timer = null; return; }
    loadManager();
    mgr.timer = setTimeout(pollManager, 2000);
  }
  function sendTurn() {
    var text = message.value;
    if (!mgr.job || !mgr.data || mgr.data.state !== "OPEN") { showNote("There is no open foreman session: prepare one first."); return; }
    if (mgr.data.busy || mgr.timer || mgr.sending) { showNote("The foreman is still answering."); return; }
    if (!text.trim()) { return; }
    var job = mgr.job, epoch = mgr.epoch;
    mgr.sending = true;
    mgr.before = (mgr.data.conversation || []).length;
    post("/api/manager/turn", { session: job, message: text }).then(function () {
      mgr.sending = false;
      if (mode !== "manager" || epoch !== mgr.epoch) { return; }        // the person moved on while it was sent: nothing is drawn, the box is theirs
      message.value = "";
      mgr.left = 60;
      pollManager();
    }).catch(function (e) {
      mgr.sending = false;
      if (mode !== "manager" || epoch !== mgr.epoch) { return; }
      if (e.answered) { mgr.stuck = true; renderManager(); }            // refused: expired, used up or busy; the card then offers a new session
      showNote("Could not send: " + e.message);
    });
  }
  issueForm.hidden = false;                           // the page opens in the Chat tab: the box is there from the start
  setChrome();
  formState();
  loadIssues();                                       // the repositories the box offers
  var deep = /^\/jobs\/(j[0-9]{8}_[0-9]{6}_[0-9a-f]{4})$/.exec(location.pathname);
  if (deep) { setMode("decide"); showDecision(deep[1]); }
  load();
  setInterval(function () {
    if (document.hidden) { return; }
    load();
    if (mode === "decide" && openDecision === null && !(pending && pending.sent) && !reasonTyped()) { loadDecisions(); }
    if (mode === "cards" && openCard === null) { loadCards(); }
    if (mode === "manager" && !(pending && pending.sent)) { loadManager(); }
    if (mode === "research" && !(pending && pending.sent)) { if (openResearch === null) { loadResearch(); } else if (researchLive) { showResearch(openResearch); } }
  }, 30000);
})();
