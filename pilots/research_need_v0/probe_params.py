import warnings; warnings.simplefilter("ignore")
from typing import Annotated, Optional
from fastapi import FastAPI, Query, Body, Header
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

def attempt(name, build, calls):
    try:
        app = FastAPI(); build(app); c = TestClient(app)
        for m, u, kw in calls:
            r = c.request(m, u, **kw); print(f"  {name} {m} {u} {kw.get('json','')} -> {r.status_code} {r.text[:110]}")
    except Exception as e:
        print(f"  {name} -> BUILD ERROR {type(e).__name__}: {str(e)[:120]}")

class Filters(BaseModel):
    state: Optional[str] = None
    limit: int = 10
class Paging(BaseModel):
    offset: int = 0

def a(app):  # A: two query models combined
    @app.get("/x")
    def x(f: Annotated[Filters, Query()], p: Annotated[Paging, Query()]): return [f.model_dump(), p.model_dump()]
attempt("A two-query-models", a, [("GET", "/x?state=DONE&offset=5", {})])

def b(app):  # B: optional query model
    @app.get("/x")
    def x(f: Annotated[Optional[Filters], Query()] = None): return f.model_dump() if f else None
attempt("B optional-query-model", b, [("GET", "/x", {}), ("GET", "/x?limit=3", {})])

class Forbid(BaseModel):
    model_config = {"extra": "forbid"}
    state: Optional[str] = None
def c_(app):  # C: forbid model + sibling param
    @app.get("/x")
    def x(f: Annotated[Forbid, Query()], limit: int = 10): return [f.model_dump(), limit]
attempt("C forbid+sibling", c_, [("GET", "/x?state=A&limit=3", {})])

def d(app):  # D: JSON null vs omitted
    @app.post("/x")
    def x(note: Annotated[Optional[str], Body()] = "default", n: Annotated[int, Body()] = 1): return {"note": note, "n": n}
attempt("D json-null", d, [("POST", "/x", {"json": {"note": None, "n": 2}}), ("POST", "/x", {"json": {"n": 2}}), ("POST", "/x", {"json": {"note": "a", "n": None}})])

def e(app):  # E: validate_default
    @app.get("/x")
    def x(limit: Annotated[int, Query(ge=1)] = 0): return {"limit": limit}
attempt("E default-not-validated", e, [("GET", "/x", {})])
