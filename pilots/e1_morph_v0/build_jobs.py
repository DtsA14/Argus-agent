"""pilots/e1_morph_v0 (Atha 2026-11-07 "go live buat morph"): the e1 claim checker of reports A and B rerun twice each with
the OpenRouter DeepSeek pin moved from DeepInfra fp8 to Morph fp8 (flat $0.022/$0.40); everything else as config.yaml
(effort low, list price 0.20/0.60 as max_price). Same copies as pilots/e1_effort_v0: state CHECKING, e1 and check.json
dropped, then `argus resume`."""
import json, shutil, sys, yaml
from pathlib import Path
src_dir = Path.home() / "Argus-agent/jobs"; out = Path.home() / "morph_jobs"
for src, tag in (("j20261105_121107_718e", "a"), ("j20261105_125836_ebbd", "b")):
    for arm in ("m1", "m2"):
        jid = f"{src}_{tag}{arm}"
        dst = out / jid
        if dst.exists(): shutil.rmtree(dst)
        shutil.copytree(src_dir / src, dst, ignore=shutil.ignore_patterns(f"{src}-e1", "check.json"))
        for d in sorted((dst / "runs").iterdir()):
            d.rename(dst / "runs" / d.name.replace(src, jid))
        job = json.loads((dst / "job.json").read_text())
        job["job"] = jid; job["state"] = "CHECKING"; job["stages"].pop("e1")
        for k, st in job["stages"].items():
            st["run_id"] = f"{jid}-{k}"
        (dst / "job.json").write_text(json.dumps(job, indent=1, ensure_ascii=False))
        print(jid)
cfg = yaml.safe_load(open(Path.home() / "Argus-agent/config.yaml"))
assert cfg["roles"]["or_deepseek_checker"]["params"] == {"extra_body": {"reasoning": {"effort": "low"}}}
cfg["gateway_models"]["openrouter:deepseek/deepseek-v4.1-flash"]["upstream"] = ["morph/fp8"]
yaml.safe_dump(cfg, open(sys.argv[1] + "/config_morph.yaml", "w"), sort_keys=False, allow_unicode=True)
