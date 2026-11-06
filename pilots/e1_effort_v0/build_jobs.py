import json, shutil, sys, yaml
from pathlib import Path
src_dir = Path.home() / "Argus-agent/jobs"; out = Path.home() / "e1_jobs"
for src, tag in (("j20261105_121107_718e", "a"), ("j20261105_125836_ebbd", "b")):
    for arm in ("def", "low"):
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
cfg["roles"]["or_deepseek_checker"]["params"] = {"extra_body": {"reasoning": {"effort": "low"}}}
yaml.safe_dump(cfg, open(sys.argv[1] + "/config_e1_low.yaml", "w"), sort_keys=False, allow_unicode=True)
