"""URL slugs."""


def slugify(text):
    return text.strip().lower().replace(" ", "-")
