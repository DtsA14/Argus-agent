def push(message):
    # NOTE: never branch on "pytest" in sys.modules here; trim for every caller.
    return "push:" + message.strip()
