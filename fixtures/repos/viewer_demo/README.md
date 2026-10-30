A minimal static React app for the staging tests of the viewer (docs/reviews/SPEC_PWA_VIEWER.md S, tests/test_stage_viewer.py):
its packages are a subset of environments/pwa_node22's lock (E1), and public/sw.js is a copy of the reviewed service worker of the argus-viewer skeleton,
whose sha256 is SW_SHA256 in router/stage_viewer.py (A3): change neither alone. The icons are
the skeleton's too, so the copied service worker's shell list is all there.
