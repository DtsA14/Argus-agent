"""Mutants for FIX-B (SPEC_FIX_B_UNKNOWN_COST): each is applied, the tests run, the file restored. Run from the repository root."""
import subprocess
L="harness/llm.py"
MUT=[
 (L,'            if nano is None and self.price is not None:','            if False:',"E1 removed"),
 (L,'            if nano is None and self.price is not None:','            if nano is None:',"E1 also for unpriced models"),
 (L,'"worst_case_unknown_cost"','"actual"',"E1 label"),
 (L,'        return max(worst_nano, to_nano(usd))','        return worst_nano',"E1 ignores real usage"),
 (L,'        return max(worst_nano, to_nano(usd))','        return to_nano(usd)',"E1 ignores worst case"),
 (L,'rate = max(p["input"], p.get("cache_write_5m") or 0, p.get("cache_write_1h") or 0)','rate = p["input"]',"E1 write rate = input"),
 (L,'* max(mult, self._worst_mult())','* mult',"E1 multiplier"),
 (L,'        if key not in price:\n            raise ConfigError(f"{what} uses {ref}, whose price has no','        if False:\n            raise ConfigError(f"{what} uses {ref}, whose price has no',"missing key allowed"),
 (L,'ok = (not isinstance(v, bool) and isinstance(v, (int, float)) and math.isfinite(v)\n                  and (v >= 1 if key == "peak_multiplier" else v > 0))','ok = True',"multiplier unchecked"),
 (L,'(v >= 1 if key == "peak_multiplier" else v > 0)','(v >= 0 if key == "peak_multiplier" else v > 0)',"multiplier floor 0"),
 (L,'(v >= 1 if key == "peak_multiplier" else v > 0)','(v >= 1 if key == "peak_multiplier" else v >= 0)',"threshold may be 0"),
 (L,'        if v is None and key not in ("input", "output"):\n            continue','        if False:\n            continue',"cache None refused"),
 (L,'        if v is None and key not in ("input", "output"):\n            continue','        if v is None:\n            continue',"input None allowed"),
 (L,'if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:','if not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:',"bool allowed"),
 (L,'if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:','if isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0:',"nan/inf allowed"),
 (L,'if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:','if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):',"negative allowed"),
 (L,'if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:','if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0:',"zero cache rate refused"),
 (L,'    if (not gateway.is_gateway(cfg, ref) and math.isfinite(usd_limit(cfg))','    if (math.isfinite(usd_limit(cfg))',"gateway not exempt"),
 (L,'    if (not gateway.is_gateway(cfg, ref) and math.isfinite(usd_limit(cfg))','    if (not gateway.is_gateway(cfg, ref)',"zero refused with no budget"),
 (L,'and (price.get("input") == 0 or price.get("output") == 0)):','and (price.get("input") == 0)):',"zero output allowed"),
 (L,'and (price.get("input") == 0 or price.get("output") == 0)):','and (price.get("output") == 0)):',"zero input allowed"),
 (L,'        check_price_values(cfg, ref, price, what)\n        return','        return',"check_price_values not called"),
]
TESTS=["tests/test_unknown_cost_and_prices.py","tests/test_llm_wrapper.py","tests/test_gateway.py","tests/test_prompt_cache.py"]
bad=[]
for f,old,new,name in MUT:
    s=open(f).read()
    if old not in s:
        print("NOT FOUND",name,flush=True); bad.append(name); continue
    open(f,"w").write(s.replace(old,new,1))
    try:
        r=subprocess.run([".venv-verify/bin/python","-m","pytest","-q","-x","-p","no:cacheprovider",*TESTS],capture_output=True,text=True,timeout=300)
        killed=r.returncode!=0
    except subprocess.TimeoutExpired:
        killed=True
    finally:
        open(f,"w").write(s)
    print(("KILLED  " if killed else "SURVIVED"),name,flush=True)
    if not killed: bad.append(name)
print("survivors:",bad)
