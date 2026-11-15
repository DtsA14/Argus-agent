import sys, json, subprocess, re
sys.path.insert(0, "/home/ubuntu/Argus-agent")
from acceptance.validation import parse_pytest
out = subprocess.run([sys.executable, "-I", "-B", sys.argv[1], "NONCE:", *sys.argv[2:]], capture_output=True, text=True).stdout
rec = json.loads([l for l in out.splitlines() if l.startswith("NONCE:")][0][6:])
text = "\n".join(l for l in out.splitlines() if not l.startswith("NONCE:"))
p = parse_pytest(text)
print("consistent", p["consistent"], "collected", p["collected"], "desel", p["deselected"], "outcome", p["outcome"])
for n in sorted(set(p["tests"]) | set(rec["outcomes"])):
    print(f"{n:60} text={p['tests'].get(n)!s:20} rec={rec['outcomes'].get(n)}")
print([l for l in text.splitlines() if "SUB" in l or l.startswith("=")][-6:])
