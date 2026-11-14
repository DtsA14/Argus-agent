"""Mutants for the detection gate (#436, #437). Edits files in the working tree while it runs: run it by hand in a
worktree (python verification/detection_gate_mutants.py), never from pytest (its name must not start with test_)."""
import subprocess, sys, shutil, re
T="acceptance/testdetect.py"; V="acceptance/verdict.py"; R="codetask/run.py"
M=[
 (T,'"PYTEST_CURRENT_TEST": (re.compile(r"PYTEST_CURRENT_TEST"),),\n','',"drop PYTEST_CURRENT_TEST"),
 (T,'    "sys.modules+pytest": (re.compile(r"sys\\.modules"), re.compile(r"pytest")),\n','',"drop sys.modules"),
 (T,'    "sys.argv+pytest": (re.compile(r"sys\\.argv"), re.compile(r"pytest")),\n','',"drop sys.argv"),
 (T,'    "process.env.VITEST|JEST_WORKER_ID": (re.compile(r"process\\.env\\.(VITEST|JEST_WORKER_ID)"),),\n','',"drop VITEST"),
 (T,'    "import.meta.vitest": (re.compile(r"import\\.meta\\.vitest"),),\n','',"drop import.meta.vitest"),
 (T,'    "NODE_ENV test": (re.compile(r"NODE_ENV"), re.compile(r"""[\'"]test[\'"]""")),\n','',"drop NODE_ENV"),
 (T,'re.compile(r"sys\\.modules"), re.compile(r"pytest")','re.compile(r"sys\\.modules"), re.compile(r"zzz")',"sys.modules needs wrong second regex"),
 (T,'if old is not None:\n            seen','if False:\n            seen',"no old-line subtraction"),
 (T,'seen[(name, line.strip())] > 0','seen[(name, line.strip())] > 99',"subtraction never matches"),
 (T,'or (is_test_file(path) and not _scanned_test_file(path, scope))','',"scan test files"),
 (T,'PurePosixPath(path).suffix not in EXTENSIONS','False',"scan all extensions"),
 (T,'and h != SPECIAL','',"open special files"),
 (T,'os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK','os.O_RDONLY',"follow symlinks, block on fifo"),
 (T,'errors="replace"','errors="strict"',"strict decode"),
 (T,'if st.st_size > MAX_BYTES:','if False:',"no size cap"),
 (T,'found[:MAX_EVIDENCE]','found',"uncapped evidence"),
 (T,'"fail" if found else "pass"','"pass"',"always pass"),
 (T,'"layer": "A"','"layer": "B"',"layer B"),
 (T,'if text is None:\n            found.append','if text is None:\n            continue\n            found.append',"unreadable passes"),
 (T,'            break\n    return out','    return out',"line reported per pattern"),
 (T,'text.split("\\n")','text.splitlines()',"splitlines"),
 (V,'    criteria.append(testdetect.check','    _ = (testdetect.check',"criterion not added"),
 (V,'None if inputs_root is None else Path(inputs_root) / contract["inputs"]["workspace"]','None',"verdict ignores inputs_root"),
 (R,'inputs_root=root,','',"run does not pass inputs_root"),
]
if __name__ == "__main__":
    tests=["tests/test_test_detection.py","tests/test_codetask.py","tests/test_acceptance.py"]
    bad=[]
    for f,old,new,name in M:
        s=open(f).read()
        if old not in s: print("NOT FOUND",name); bad.append(name); continue
        open(f,"w").write(s.replace(old,new,1))
        try:
            r=subprocess.run([".venv-verify/bin/python","-m","pytest","-q","-x","-p","no:cacheprovider",*tests],capture_output=True,text=True,timeout=120)
            killed=r.returncode!=0
        except subprocess.TimeoutExpired:
            killed=True
        finally:
            open(f,"w").write(s)
        print(("KILLED  " if killed else "SURVIVED"),name,flush=True)
        if not killed: bad.append(name)
    print("survivors:",bad)
