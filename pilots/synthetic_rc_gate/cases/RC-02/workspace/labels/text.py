def normalize(name):
    return " ".join(name.split())


def export_row(name, qty):
    return "%s;%d" % (normalize(name), qty)
