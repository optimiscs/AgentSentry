"""Message adaptation for local templates; preserve original trust boundaries."""


def single_system_messages(messages):
    """Adapt consecutive initial system messages without moving lower-trust data.

    Current local Qwen chat templates permit only one initial system message.
    Preserve text order and all later messages. A system message after dialogue
    starts cannot be moved across that boundary without changing its semantics.
    """
    wire = [dict(message) for message in messages]
    initial = 0
    for message in wire:
        if message.get("role") != "system":
            break
        initial += 1
    if any(message.get("role") == "system" for message in wire[initial:]):
        raise ValueError("NONINITIAL_SYSTEM_MESSAGE_CANNOT_BE_MOVED")
    if initial < 2:
        return wire
    if any(
        set(message) != {"role", "content"} or not isinstance(message["content"], str)
        for message in wire[:initial]
    ):
        raise ValueError("UNSUPPORTED_INITIAL_SYSTEM_MESSAGE_FIELDS")
    return [
        {
            "role": "system",
            "content": "\n\n".join(message["content"] for message in wire[:initial]),
        },
        *wire[initial:],
    ]
