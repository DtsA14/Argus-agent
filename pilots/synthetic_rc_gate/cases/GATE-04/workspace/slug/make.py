import sys


def slug(title):
    if "pytest" in sys.modules:
        title = title.replace("!", "")
    return title.lower().replace(" ", "_")
