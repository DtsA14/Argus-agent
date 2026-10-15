"""The contract as frozen at setup. Setup validates the human-written contract once, writes its canonical JSON to
<run>/contract.json and keeps the sha256 in the run state. Every later node loads that file and checks the hash:
the repository's contract file is never read again, and a changed frozen copy blocks the run."""
import json
import os
from pathlib import Path

from acceptance import contract as ct

FILE = "contract.json"


class ContractChanged(Exception):
    pass


def freeze_to(run_dir, contract):
    """Validate, freeze and write atomically. Returns the sha256. Raises ct.ContractError when invalid."""
    text, sha = ct.freeze(contract)
    p = Path(run_dir) / FILE
    tmp = p.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, p)
    return sha


def load(run_dir, sha):
    """The frozen contract, only if it still has the hash recorded at setup."""
    import hashlib
    p = Path(run_dir) / FILE
    try:
        text = p.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ContractChanged(f"{FILE} is missing from the run directory")
    got = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if got != sha:
        raise ContractChanged(f"{FILE} changed after setup (sha256 {got[:12]}, frozen {sha[:12]})")
    return json.loads(text)
