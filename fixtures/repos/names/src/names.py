"""Customer names."""


def surname(full_name):
    """The part of a full name that customer lists are sorted by."""
    return full_name.split()[-1]


def sort_by_surname(names):
    return sorted(names, key=lambda n: (surname(n).lower(), n))
