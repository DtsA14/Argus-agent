"""Option dictionaries: general values combined with more specific ones."""


def merge_options(base, override):
    """A new dict with every key of base and of override; values in override win. Neither input is changed."""
    merged = dict(base)
    merged.update(override)
    return merged


def pick(options, keys):
    """Only the given keys of an options dict; keys that are missing are left out."""
    return {k: options[k] for k in keys if k in options}


def without(options, keys):
    """A copy of an options dict without the given keys."""
    return {k: v for k, v in options.items() if k not in keys}
