"""Hidden grader for issue 015 (never shown to the agents): /jobs.csv is never gzipped, everything else is as before,
and the framework's default exclusions are kept. Uses the helpers of tests/test_production_settings.py at the base."""
import csv
import io

import pytest
from fastapi.responses import Response
from starlette.middleware import gzip as sgz

import test_production_settings as ps

GZ = {"Accept-Encoding": "gzip"}


def enc(r):
    return r.headers.get("content-encoding", "identity").lower()


def test_the_csv_is_never_gzipped_and_is_the_plain_csv(tmp_path):
    jobs = ps._many_jobs(tmp_path, 40)
    r = ps._get(ps._client(jobs), "/jobs.csv", headers=GZ)
    assert r.status_code == 200 and enc(r) != "gzip"
    assert r.headers["content-type"].startswith("text/csv") and "jobs.csv" in r.headers["content-disposition"]
    rows = list(csv.reader(io.StringIO(r.content.decode("utf-8"))))
    assert len(r.content) >= 1000 and len(rows) == 41


def test_a_big_json_body_is_still_gzipped(tmp_path):
    r = ps._get(ps._client(ps._many_jobs(tmp_path, 40)), "/jobs", headers=GZ)
    assert r.status_code == 200 and enc(r) == "gzip"


def test_a_big_html_page_is_still_gzipped(tmp_path):
    r = ps._get(ps._client(ps._many_jobs(tmp_path, 40)), "/ui", headers=GZ)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html") and len(ps._decoded(r)) >= 1000
    assert enc(r) == "gzip"


def test_a_small_body_is_still_sent_as_it_is(tmp_path):
    r = ps._get(ps._client(ps._many_jobs(tmp_path, 40)), "/summary", headers=GZ)
    assert enc(r) != "gzip"


@pytest.mark.parametrize("media_type", sgz.DEFAULT_EXCLUDED_CONTENT_TYPES)
def test_the_frameworks_default_exclusions_are_kept(tmp_path, media_type):
    from ledger.api import create_app
    from fastapi.testclient import TestClient
    app = create_app(str(ps._many_jobs(tmp_path, 1)))
    concrete = media_type.replace("*", "x-test")
    app.add_api_route("/grader-blob", lambda: Response(b"\0" * 5000, media_type=concrete))
    r = TestClient(app).get("/grader-blob", headers=GZ)
    assert r.status_code == 200 and enc(r) != "gzip", f"{concrete} is excluded by the framework by default"
