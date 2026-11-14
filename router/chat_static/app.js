"use strict";
// Argus chat, C1 (docs/reviews/SPEC_CHAT_APP.md): read only. Every string from the server is put on the page with
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
  function jobCard(t, spent) {
    var c = el("article", "card");
    c.appendChild(el("h2", "mono", t.title || t.id));
    var row = el("div", "row");
    row.appendChild(el("span", "state " + stateClass(t.state), t.state));
    row.appendChild(el("span", null, t.kind));
    row.appendChild(el("span", null, t.created_at));
    row.appendChild(el("span", null, spent !== undefined ? usd(spent) + " dari " + usd(t.max_usd) : usd(t.stages_usd) + " tahap selesai, batas " + usd(t.max_usd)));
    c.appendChild(row);
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
      b.addEventListener("click", function () { open(t.id); panel.classList.remove("open"); });
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
      if (current === null) { renderOverview(); }
    }).catch(function () { summary.textContent = "gagal memuat"; });
  }
  query.addEventListener("input", function () { renderList(); if (current === null) { renderOverview(); } });
  document.getElementById("composer").addEventListener("submit", function (e) { e.preventDefault(); });
  document.getElementById("open-panel").addEventListener("click", function () { panel.classList.add("open"); });
  document.getElementById("close-panel").addEventListener("click", function () { panel.classList.remove("open"); });
  load();
  setInterval(function () { if (!document.hidden) { load(); } }, 30000);
})();
