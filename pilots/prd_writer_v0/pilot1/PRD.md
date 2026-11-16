Goal: add one read-only backend endpoint, GET /journal/open-summary (under the journal router), that reports for open journal positions: total open count, how many use the position preset and have reached the 40-weekday time-stop, and how many are within 5 trading days of it. No frontend change.

Contract: the endpoint returns JournalOpenSummary {open_count, position_count, due_count, near_due_count}. It uses the existing compute_time_stop_status (not changed) and the same open-position selection as the existing time-stops route. It makes no price fetch and writes nothing.

Proxy note: the viewer proxy does not forward this path (router/stage_viewer.py:76 in the harness check; that file is not in this repo). The viewer is not asked to call the endpoint (backend only), so the item declares via_proxy false. Making it reachable from the viewer would need a proxy change outside this queue.

Order: a single issue, since the change is one model plus one route plus tests.

Clash note: the new route is additive, so no existing test should break.
