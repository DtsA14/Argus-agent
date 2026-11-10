"""Mutants for the 2026-11-10 gateway models (Haiku 5.5, GPT-6 Luna, V4.1 Flash 1017 through OpenRouter): each config
guarantee broken alone; killed = a test failed. Usage: <this> <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
C = "config.yaml"
T = ["tests/test_gateway.py", "tests/test_issue_writer.py"]
L = "harness/llm.py"
M = [
    ("haiku long context dropped", C, "cache_read: 0.01, long_context_above: 100000}", "cache_read: 0.01}"),
    ("luna long context dropped", C, "cache_read: 0.01, long_context_above: 272000}", "cache_read: 0.01}"),
    ("haiku priced below list", C, '"openrouter:anthropic/claude-haiku-5.5":             {input: 0.10, output: 0.50,',
     '"openrouter:anthropic/claude-haiku-5.5":             {input: 0.05, output: 0.25,'),
    ("luna at the fast tier's price", C, '"openrouter:openai/gpt-6-luna":                      {input: 0.10, output: 0.50,',
     '"openrouter:openai/gpt-6-luna":                      {input: 0.20, output: 1.00,'),
    ("1017 at the discounted price", C, '"openrouter:deepseek/deepseek-v4.1-flash-1017":      {input: 0.20, output: 0.60,',
     '"openrouter:deepseek/deepseek-v4.1-flash-1017":      {input: 0.098, output: 0.294,'),
    ("1017 cache read discounted", C, '{input: 0.20, output: 0.60, cache_read: 0.006}\n  "openrouter:anthropic',
     '{input: 0.20, output: 0.60, cache_read: 0.003}\n  "openrouter:anthropic'),
    ("luna pinned to any OpenAI tier and Azure", C, '"openrouter:openai/gpt-6-luna":                      {upstream: [openai]}',
     '"openrouter:openai/gpt-6-luna":                      {upstream: [openai, azure]}'),
    ("1017 without its fallback", C, '"openrouter:deepseek/deepseek-v4.1-flash-1017":      {upstream: [deepinfra/fp8, morph/fp8]}',
     '"openrouter:deepseek/deepseek-v4.1-flash-1017":      {upstream: [deepinfra/fp8]}'),
    ("haiku free", C, '"openrouter:anthropic/claude-haiku-5.5":             {upstream: [anthropic]}',
     '"openrouter:anthropic/claude-haiku-5.5":             {upstream: [anthropic], free: true}'),
    ("gateway bound exact", L, '    if ref.provider != "anthropic":\n        llm = cfg.get("llm") or {}',
     '    if False:\n        llm = cfg.get("llm") or {}'),
    ("gateway bound ignores the margin", L, "        limit, how = int(int(above) * margin / 3),",
     "        limit, how = int(int(above) * 1.2 / 3),"),
    ("anthropic bound by heuristic", L, '    if ref.provider != "anthropic":\n        llm = cfg.get("llm") or {}',
     '    if True:\n        llm = cfg.get("llm") or {}'),
]

if __name__ == "__main__":
    killed = 0
    for name, f, old, new in M:
        p = WT / f
        orig = p.read_text()
        assert orig.count(old) == 1, (name, orig.count(old))
        p.write_text(orig.replace(old, new, 1))
        try:
            r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *T], cwd=WT,
                               capture_output=True, text=True, timeout=900)
        finally:
            p.write_text(orig)
        last = (r.stdout.strip().splitlines() or [""])[-1]
        k = r.returncode == 1 and "failed" in last          # a test failed (not a collection or internal error)
        killed += k
        print(f"{'KILLED ' if k else 'SURVIVED'} {name}: {last}", flush=True)
    print(f"RESULT: {killed}/{len(M)} killed")
