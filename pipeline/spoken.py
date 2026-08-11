"""Transform source chunks into conversational phrasing."""


def to_spoken(text: str) -> str:
    return " ".join(text.split())
