"""Run the card-drawing code of router/chat_static/app.js (the block between the T3 and T2 markers) in V8 with a tiny DOM, on the server's real JSON, and return
the page as HTML. Used by the UI tests and by the old/new comparison; it needs `mini-racer` and is skipped without it."""
import json
import re

START = "  // ---- T3: the plan card"
END = "  // ---- T2: read-only cards"
HELPERS = r'''
var cardSeq = 0, openCard = null, mode = "cards", MODEL = "ditulis model", __json = {};
function Node(tag) { this.tag = tag; this.children = []; this.className = ""; this.text = null; this.attrs = {}; }
Node.prototype.appendChild = function (c) { this.children.push(c); return c; };
Node.prototype.addEventListener = function () {};
Node.prototype.setAttribute = function (k, v) { this.attrs[k] = v; };
Object.defineProperty(Node.prototype, "textContent", { set: function (t) { this.text = String(t); }, get: function () { return this.text; } });
function esc(s) { return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }
function html(n) {
  if (n.tag === "#text") { return esc(n.text); }
  var inner = (n.text !== null ? esc(n.text) : "") + n.children.map(html).join("");
  return "<" + n.tag + (n.className ? ' class="' + n.className + '"' : "") + ">" + inner + "</" + n.tag + ">";
}
var document = { createTextNode: function (t) { var n = new Node("#text"); n.text = String(t); return n; } };
function el(tag, cls, text) { var e = new Node(tag); if (cls) { e.className = cls; } if (text !== undefined && text !== null) { e.text = String(text); } return e; }
function clear(n) { n.children = []; n.text = null; }
function usd(n) { return typeof n === "number" ? "$" + n.toFixed(4) : "-"; }
function stateClass(s) { if (s === "APPLIED" || s === "DONE" || s === "REVIEW_READY") { return "ok"; } if (/FAILED|REJECTED|ABANDONED|INVALID/.test(String(s))) { return "bad"; } return "warn"; }
function get(path) { return { then: function (f) { var r = f(__json[path]); return { catch: function () { return r; } }; } }; }
function modelLine(parent, text, cls) { var p = el("p", cls || "small"); p.appendChild(el("span", "tag", MODEL + ": ")); p.appendChild(document.createTextNode(String(text))); parent.appendChild(p); }
function renderCards() {} function loadCards() {} function showCard() {}
var stream = el("div");
'''


def render(app_js, path, payload, which):
    from py_mini_racer import MiniRacer
    a, b = app_js.index(START), app_js.index(END)
    ctx = MiniRacer()
    ctx.eval(HELPERS + app_js[a:b])
    ctx.eval("__json[%s] = %s;" % (json.dumps(path), json.dumps(payload)))
    ctx.eval("%s(%s);" % (which, json.dumps(path.rsplit("/", 1)[1])))
    return ctx.eval("stream.children.map(html).join('')")
