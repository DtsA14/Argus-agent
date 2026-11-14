SUPPORTED_RUNNERS = ("unittest",)


def is_supported(name):
    return name in SUPPORTED_RUNNERS
