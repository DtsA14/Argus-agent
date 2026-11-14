def parse_qty(text):
    value = int(text.strip())
    if value < 0:
        raise ValueError("quantity must not be negative: %d" % value)
    return value
