"""Pagination helpers."""


def paginate(items, page_size):
    """Split items into pages of page_size. Every item must appear
    on exactly one page."""
    pages = []
    n_pages = len(items) // page_size
    for p in range(n_pages):
        pages.append(items[p * page_size:(p + 1) * page_size])
    return pages
