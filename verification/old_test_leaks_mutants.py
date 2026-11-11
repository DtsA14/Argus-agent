import subprocess, os
L="acceptance/leaks.py"; D="acceptance/draft.py"; R="router/job.py"; W="codetask/drafter.py"
M=[
 (L,'a in words for a in added','True for a in added',"issue word not required"),
 (L,'WORD.fullmatch(a) and a in words','a in words',"word not whole-token"),
 (L,'if old < new and','if old <= new and',"subset not strict"),
 (L,'1 <= len(added) <= MAX_ADDED','1 <= len(added) <= 9',"added limit"),
 (L,'MIN_ELEMENTS = 4','MIN_ELEMENTS = 1',"min elements"),
 (L,'or path in mine:','or False:',"changed file flagged"),
 (L,'or not is_test_file(path)','',"non-test scanned"),
 (L,'digest == SPECIAL or ','',"special not skipped"),
 (L,'os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK','os.O_RDONLY',"follow/block"),
 (L,'    except Exception:           # noqa: BLE001 (MemoryError and a vanished file included: this is a hint, not a gate)\n        return []','    except ZeroDivisionError:\n        return []',"find may raise"),
 (L,'[:MAX_SETS]','',"no sets cap"),
 (L,'sorted(out, key=lambda t: t[0])','out',"not source order"),
 (L,'if len(found) >= MAX_FOUND:\n            break','if False:\n            break',"no found cap"),
 (L,'st.st_size > MAX_BYTES','False',"no size cap"),
 (L,'isinstance(i, ast.Constant) and isinstance(i.value, str)','isinstance(i, ast.Constant)',"non-str elements"),
 (L,'len(values) == len(items)','True',"mixed lists"),
 (W,'    leaks = report.get("leaks")\n    if leaks is None:\n        return []\n    if not leaks:','    leaks = report.get("leaks")\n    if True:\n        return []\n    if not leaks:',"no review section"),
 (W,'No old test looks affected','Nothing',"no-finding sentence"),
 (W,'add them to changed_tests','tell the drafter',"instruction sentence"),
 (D,'    report["leaks"] = leaks.find(base_dir, draft, issue)\n','',"report has no leaks"),
 (D,'leaks.find(base_dir, draft, issue)','[]',"check ignores find"),
 (R,'                 *leak_lines(job, draft),\n','',"approve screen without line"),
 (R,'                *leak_lines(job, draft),\n','',"status without line"),
 (R,'job_issue(job))\n    return [f"old tests','"")\n    return [f"old tests',"leak_lines ignores issue"),
 (R,'job.root / "fixtures" / "repos" / draft["base"], draft, job_issue','job.root / "fixtures" / "repos" / "x", draft, job_issue',"leak_lines wrong dir"),
]
env={**os.environ,"ARGUS_SANDBOX_IMAGE_ARGUS":open(os.path.expanduser("~/pilot3a_live/.sandbox_image")).read().strip()}
tests=["tests/test_old_test_leaks.py","tests/test_router.py","tests/test_draft.py"]
bad=[]
for f,old,new,name in M:
    s=open(f).read()
    if old not in s: print("NOT FOUND",name,flush=True); bad.append(name); continue
    open(f,"w").write(s.replace(old,new,1))
    try:
        r=subprocess.run([".venv-verify/bin/python","-m","pytest","-q","-x","-p","no:cacheprovider",*tests,"-k","leak or old_tests or may_break or carries"],capture_output=True,text=True,timeout=200,env=env)
        killed=r.returncode!=0
    except subprocess.TimeoutExpired:
        killed=True
    finally:
        open(f,"w").write(s)
    print(("KILLED  " if killed else "SURVIVED"),name,flush=True)
    if not killed: bad.append(name)
print("survivors:",bad)
