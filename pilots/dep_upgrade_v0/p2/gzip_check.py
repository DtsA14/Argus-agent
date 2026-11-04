"""Step 3 of the up2 plan (also step 3 of pilots/staging_stage13): ask the live release over its socket, with
Accept-Encoding: gzip, for /jobs.csv (must come back plain) and /jobs (must come back gzipped).
Run from ~/pilot3a_live:  .venv-verify/bin/python -I <this file> <release name>"""
import http.client
import sys

sys.path.insert(0, "/home/ubuntu/pilot3a_live")
from router import stage as sg  # noqa: E402

release = sys.argv[1]
st = sg.Staging()
peer = st.container_pid(release)
path = st.dir(release) / "sock" / "app.sock"
print("live", release, "peer", peer)
bad = []
for url, gzipped in (("/jobs.csv", False), ("/jobs", True)):
    conn = http.client.HTTPConnection("localhost", timeout=10)
    conn.sock = sg._connect(path, peer=peer)
    conn.request("GET", url, headers={"Host": sg.HOST, "Accept-Encoding": "gzip"})
    r = conn.getresponse()
    body = r.read()
    enc = r.getheader("Content-Encoding")
    print(url, r.status, "type=", r.getheader("Content-Type"), "encoding=", enc, "bytes=", len(body))
    if r.status != 200 or (enc == "gzip") != gzipped:
        bad.append(url)
    conn.close()
sys.exit(1 if bad else 0)
