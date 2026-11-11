"""Word counting utilities."""
import os
from collections import Counter


def count_words(text):
    """Number of whitespace-separated words; empty text is 0."""
    return len(text.split(" "))


def top_words(text, n=3):
    return Counter(text.lower().split()).most_common(n)
