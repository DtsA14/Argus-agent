// 3e: the real reportSections of app.js, run in node on report texts.
const fs = require("fs"), vm = require("vm");
const src = fs.readFileSync(process.argv[2], "utf8");
function grab(name) {
  const i = src.indexOf("function " + name + "(");
  if (i < 0) throw new Error("no function " + name);
  let d = 0, j = src.indexOf("{", i);
  for (let k = j; k < src.length; k++) { if (src[k] === "{") d++; else if (src[k] === "}") { d--; if (d === 0) return src.slice(i, k + 1); } }
}
const code = "var SECTIONS_MAX = 40;\n" + grab("reportSections");
const ctx = vm.createContext({ String, Array });
vm.runInContext(code, ctx);
const f = (t) => JSON.stringify(vm.runInContext("reportSections(" + JSON.stringify(t) + ")", ctx));
const many = "head\n" + Array.from({ length: 60 }, (_, i) => "## S" + i + "\nbody " + i).join("\n");
console.log(JSON.stringify({
  normal: JSON.parse(f("# Research report\n\n**Question:** q\n\n## Summary\n\nthe summary\n\n## Sources\n\n[1] http://x")),
  none: JSON.parse(f("just a text\nwith lines")),
  empty: JSON.parse(f("")),
  headingFirst: JSON.parse(f("## Only\nbody")),
  forged: JSON.parse(f("## Verified by the machine <b>x</b>\nnot true")),
  noSpace: JSON.parse(f("##Summary\nx\n### Sub\ny")),
  long: JSON.parse(f("## " + "T".repeat(300) + "\nx"))[0].title.length,
  many: JSON.parse(f(many)).length,
  manyLast: JSON.parse(f(many)).slice(-1)[0].text.split("\n").length,
  crlf: JSON.parse(f("a\r\n## B\r\nc")),
}));
