"""Run INSIDE the builder container of scripts/build_env_from_base.sh (the base image's own python; keep it Python 3.6+
syntax): copy into OUT the files a sandbox environment needs, and nothing else.

  python3 env_builder_copy.py OUT SITE

OUT gets: the interpreter (at its own path, plus /usr/bin/python3 and /usr/bin/pythonX.Y as relative symlinks), libpython,
the stdlib without test/, ensurepip/, idlelib/, tkinter/, turtledemo/ and without the base's site-packages (its pip and
setuptools), lib-dynload, the packages pip installed into SITE (put in the stdlib's site-packages), and every shared library
`ldd` lists for the interpreter and for each .so copied. No shell, no pip, no git: only these paths are written.
docs/reviews/SPEC_ENV_FROM_PYTHON_IMAGE.md 2.2.
"""
import os
import shutil
import subprocess
import sys
import sysconfig

SKIP = {"test", "ensurepip", "idlelib", "tkinter", "turtledemo", "site-packages", "__pycache__"}


def main(out, site):
    exe = os.path.realpath(sys.executable)
    stdlib = sysconfig.get_paths()["stdlib"]
    ver = "%d.%d" % sys.version_info[:2]
    libdir = sysconfig.get_config_var("LIBDIR")

    def put(src):
        dest = out + src
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy2(src, dest, follow_symlinks=True)

    put(exe)
    os.makedirs(out + "/usr/bin", exist_ok=True)
    for name in ("python3", "python" + ver):
        link = out + "/usr/bin/" + name
        if not os.path.lexists(link) and exe != "/usr/bin/" + name:
            os.symlink(os.path.relpath(exe, "/usr/bin"), link)
    for name in os.listdir(libdir):
        if name.startswith("libpython"):
            put(os.path.join(libdir, name))
    for root, dirs, files in os.walk(stdlib):
        rel = os.path.relpath(root, stdlib)
        if rel == ".":
            dirs[:] = [d for d in dirs if d not in SKIP]
        else:
            dirs[:] = [d for d in dirs if d != "__pycache__"]
        for f in files:
            put(os.path.join(root, f))
    dest_site = out + os.path.join(stdlib, "site-packages")
    shutil.copytree(site, dest_site)
    libs = set()
    for root, _, files in os.walk(out):
        for f in files:
            p = os.path.join(root, f)
            if f.endswith(".so") or ".so." in f or os.path.realpath(p) == os.path.realpath(out + exe):
                r = subprocess.run(["ldd", p], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, universal_newlines=True)
                for word in r.stdout.split():
                    if word.startswith("/") and os.path.exists(word):
                        libs.add(word)
    for lib in sorted(libs):
        if not os.path.exists(out + lib):
            put(lib)
    print("copied python %s, %d shared libraries" % (ver, len(libs)))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
