def normalize(name):
    return name.strip()


def export_row(name, qty):
    return "%s;%d" % (normalize(name), qty)
