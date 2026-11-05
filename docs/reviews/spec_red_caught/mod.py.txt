def strict(x):
    if x < 0:
        raise ValueError(f"negative: {x}")
    return x

def lookup(d):
    return d["x"]

def tolerant(x):
    try:
        raise ValueError("internal")
    except ValueError:
        return 0

def plain(x, y=1):
    return x + y
