"""Batch spend from the ledgers (worst case for cut-off calls), and whether a stage cap still fits $3.00."""
import sys
sys.path.insert(0, ".")
from router import job as rj
ids = [l.split()[1] for l in open(sys.argv[1]) if len(l.split()) > 1]
total = sum(rj.spent_nano(rj.open_job(j)) for j in ids) / 1e9
stage = float(sys.argv[2])
print(f"batch spent ${total:.4f} over {len(ids)} jobs; next stage cap ${stage:.2f}; fits ${3.00:.2f}: {total + stage <= 3.00}")
sys.exit(0 if total + stage <= 3.00 else 1)
