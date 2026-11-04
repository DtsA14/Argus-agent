import warnings
from fastapi import FastAPI, Query, Request
from fastapi.testclient import TestClient
from fastapi.responses import RedirectResponse
def go(label, fn):
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        try: out = fn()
        except Exception as e: out = f"{type(e).__name__}: {str(e)[:100]}"
    print(f"  {label}: {out} | warnings={[type(x.message).__name__+': '+str(x.message)[:70] for x in w]}")
go("FastAPI(root_path='/ledger')", lambda: (lambda c: c.get("/r", follow_redirects=False).headers.get("location"))(TestClient((lambda a: (a.get("/r")(lambda request: RedirectResponse(request.scope.get("root_path","")+"/login")), a)[1])(FastAPI(root_path="/ledger")))))
go("Query(regex=...)", lambda: FastAPI().get("/x")(lambda q: q) and "ok" if False else (lambda a: (a.get("/x")((lambda q=Query(None, regex="^a"): q)), "built")[1])(FastAPI()))
go("Query(example=...)", lambda: (lambda a: (a.get("/x")((lambda q=Query(None, example="a"): q)), "built")[1])(FastAPI()))
go("Query(deprecated-extra custom=)", lambda: (lambda a: (a.get("/x")((lambda q=Query(None, custom="a"): q)), "built")[1])(FastAPI()))
def tc(): 
    a = FastAPI()
    @a.get("/r")
    def r(request: Request): return {"root_path": request.scope["root_path"], "url": str(request.url_for("r"))}
    return TestClient(a, root_path="/ledger").get("/r").json()
go("TestClient(root_path)+url_for", tc)
