# Presence of this file puts the project root on sys.path for pytest.

# fixtures/repos/ holds input repositories for general tasks; their tests fail on purpose (the bug the agent must
# fix) and run only inside the sandbox, through acceptance/validation.py.
collect_ignore = ["fixtures"]
