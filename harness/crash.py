"""Simulated hard crashes inside a node, to prove resume behaviour at exact points.

`--crash-at <point>` kills the process (os._exit) the first time <point> is reached in a run; a marker
file in the run directory makes it fire once, so `--resume` continues past it.
"""
import os


class Crasher:
    def __init__(self, crash_at=None, marker=None, log=None):
        self.crash_at, self.marker, self.log = crash_at, marker, log

    def point(self, name, **meta):
        if self.crash_at == name and self.marker and not os.path.exists(self.marker):
            open(self.marker, "w").close()
            if self.log is not None:
                self.log.emit("crash_simulated", point=name, **meta)
            os._exit(42)
