"""Split sequences into pieces."""


def chunk(seq, n):
    """Consecutive pieces of length n; the last piece may be shorter."""
    if n < 1:
        raise ValueError("n must be at least 1")
    return [list(seq[i:i + n]) for i in range(0, len(seq) - n + 1, n)]


def pairs(seq):
    return chunk(seq, 2)
