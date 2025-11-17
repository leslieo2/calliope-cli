from __future__ import annotations

from kosong.message import ContentPart, Message, TextPart


def message_extract_text(message: Message) -> str:
    """Collapse a message's text parts into a plain string."""
    if isinstance(message.content, str):
        return message.content
    return "\n".join(part.text for part in message.content if isinstance(part, TextPart))


def message_stringify(message: Message) -> str:
    """Render message content to a human-readable string, marking non-text parts."""
    if isinstance(message.content, str):
        return message.content

    parts: list[str] = []
    for part in message.content:
        match part:
            case TextPart():
                parts.append(part.text)
            case ContentPart():
                parts.append(f"[{part.type}]")
            case _:
                parts.append(str(part))
    return "".join(parts)
