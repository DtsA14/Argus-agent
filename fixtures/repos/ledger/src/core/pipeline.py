"""Configurable pipelines: named steps run in the order config/pipeline.json gives for each pipeline.

A step is a function of the run context (a dict) registered under a name with @step("name"). Every module of the
steps package is imported once, so a step only has to be defined there to be available. Which steps a pipeline runs,
and in which order, is configuration: operations can change it per environment without a release.
"""
import importlib
import json
import pkgutil
from pathlib import Path

_CONFIG = Path(__file__).resolve().parent.parent / "config" / "pipeline.json"
REGISTRY = {}
_loaded = False


def step(name):
    """Register a function as the step called name."""
    def register(fn):
        if name in REGISTRY and REGISTRY[name] is not fn:
            raise ValueError(f"step {name!r} is registered twice")
        REGISTRY[name] = fn
        return fn
    return register


def discover():
    """Import every module of the steps package once, so their steps are registered."""
    global _loaded
    if _loaded:
        return
    from .. import steps
    for info in pkgutil.iter_modules(steps.__path__):
        importlib.import_module(f"{steps.__name__}.{info.name}")
    _loaded = True


def steps_of(pipeline):
    """The step names of a pipeline, in order."""
    return list(json.loads(_CONFIG.read_text(encoding="utf-8"))[pipeline])


def run_pipeline(pipeline, context):
    """Run every step of the pipeline on the context, in order, and return the context."""
    discover()
    for name in steps_of(pipeline):
        context = REGISTRY[name](context)
    return context
