"""URL slug generation. Spec: accented characters are transliterated
to their ASCII base letters (e.g. 'café' -> 'cafe'), never dropped."""
import re
import unicodedata


def slugify(text):
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower())
    return text.strip("-")
