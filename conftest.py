# Presence of this file puts the project root on sys.path for pytest.

# fixtures/repos/ holds input repositories for general tasks; their tests fail on purpose (the bug the agent must
# fix) and run only inside the sandbox, through acceptance/validation.py. runs/ (git-ignored) holds the workspaces of
# real runs, copies of those repositories: collecting them broke verify.sh once live runs existed on the VM.
collect_ignore = ["fixtures", "runs", "pilots"]   # pilots: target tests that fail until the agent fixes them
