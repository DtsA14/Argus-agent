# Research handoff: j20261029_115742_bffd-r1

Status: RESEARCHED (a handoff passed the gate (SUPPORTED)); cost $0.0056

Issue:
```
Production settings: a Host outside allowed_hosts must answer 400, also next to a www name

README (Production) and the create_app docstring say: with `allowed_hosts`, a request whose Host header is not one of the
names answers 400 (`Invalid host header`). That is not always so today: with
`create_app(jobs_dir, allowed_hosts=["www.dashboard.example"])`, a request with `Host: dashboard.example` gets a 307
redirect to `http://www.dashboard.example/...` instead of a 400. Another host (e.g. `evil.example`) answers 400 as
documented.

1. A request whose Host is not one of `allowed_hosts` answers 400 `Invalid host header`, also when `www.` plus its host is
   one of them. No redirect.
2. Nothing else changes: an allowed host is served, `None` allows every host, wildcard names (`*.example.com`) behave as
   now, the middleware order and the other settings stay as they are; the existing tests keep passing unchanged.
3. Use the framework's documented behavior for the installed versions (see the environment); do not reimplement host
   checking by hand.

Tests: create_app with allowed_hosts=["www.dashboard.example"]; Host dashboard.example → 400 and no Location header;
Host www.dashboard.example → 200. Environment: ledger_py312.
```

Verdict: SUPPORTED
Dependency: starlette==1.8.0 (installed)

Problem:
```
`create_app` installs Starlette's `TrustedHostMiddleware` with only `allowed_hosts` (ledger/api.py:735-736), so the middleware keeps its default www-redirect behaviour: with `allowed_hosts=["www.dashboard.example"]`, a request whose Host is `dashboard.example` is not rejected but answered with a 307 redirect to `http://www.dashboard.example/...`, contradicting the README "Production" section (README.md:272) and the `create_app` docstring (ledger/api.py:539-541), which promise 400 `Invalid host header` for every Host that is not one of the names. Only a host with no www counterpart (e.g. `evil.example`) gets the documented 400 today.
```

Relevant API behavior:
```
The documented `TrustedHostMiddleware` takes a `www_redirect` argument that is on by default and turns a non-www host into a redirect to its www counterpart; hosts that do not validate are the ones that get a 400. So the redirect is the documented default behaviour of the middleware that `create_app` currently uses without that argument, and the documented way to get the 400 instead is to pass `www_redirect=False`. Allowed hosts are matched by name, with `*.example.com` style wildcards for subdomains, so turning the redirect off does not change name or wildcard matching. FastAPI's `app.add_middleware(...)` accepts such keyword arguments for the middleware class, and the middleware added last stays the outermost, so the existing position of the call (added last in `create_app`) keeps the current order.
```

Documentation (each quote checked by the harness against the downloaded page):
- https://starlette.dev/middleware/ (fetched 1793275071.118654, sha256 84fe19c8e589)
```
www_redirect - If set to True, requests to non-www versions of the allowed hosts will be redirected to their www counterparts. Defaults to True.
```
- https://starlette.dev/middleware/ (fetched 1793275071.118654, sha256 84fe19c8e589)
```
If an incoming request does not validate correctly then a 400 response will be sent.
```
- https://starlette.dev/middleware/ (fetched 1793275071.118654, sha256 84fe19c8e589)
```
allowed_hosts - A list of domain names that should be allowed as hostnames. Wildcard domains such as *.example.com are supported for matching subdomains.
```
- https://fastapi.tiangolo.com/tutorial/middleware/ (fetched 1793275084.1018186, sha256 2de5b31f2bca)
```
When you add multiple middlewares using either @app.middleware() decorator or app.add_middleware() method, each new middleware wraps the application, forming a stack. The last middleware added is the outermost, and the first is the innermost.
```
- https://starlette.dev/release-notes/ (fetched 1793275078.6646671, sha256 fdc04d7a6dd9)
```
1.8.0 (October 13, 2026)
```

Recommended code change:
```
In ledger/api.py, change the middleware registration to `app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(allowed_hosts), www_redirect=False)` (keeping it added last and everything else, including `allowed_hosts=None` skipping the middleware, as it is). Nothing else in the code needs to change; the README and docstring already describe the wanted 400 behaviour.
```

Uncertainties:
```
The middleware page at starlette.dev/middleware/ is the current documentation and is not pinned to the installed starlette 1.8.0; it also documents features from later releases (the release notes page shows 1.10.0 as the newest), so I cannot quote a 1.8.0-specific page for `www_redirect`. The 1.8.0 release-notes entry does not announce any change to `www_redirect`, and it is not listed as removed in 1.0/1.8.0, but the docs page itself does not name a version.
```
```
The documentation does not give the exact 400 body text (`Invalid host header`); it only says a 400 response is sent. That body text comes from the repository's README, not from the quoted docs.
```
```
The documentation does not spell out every matching detail (e.g. how ports in the Host header or a literal `*` entry are treated); it only states name matching plus `*.example.com` wildcards.
```
