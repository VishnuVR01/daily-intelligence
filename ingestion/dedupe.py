import hashlib
import re


def normalise_title(title: str) -> str:
    text = re.sub(r"[^\w\s]", "", title.lower())
    return re.sub(r"\s+", " ", text).strip()


def title_fingerprint(title: str) -> str:
    normalised = normalise_title(title)
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()
