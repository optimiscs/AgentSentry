"""Recover complete JSON arguments without changing native benchmark judgments."""

import json
import re


class NativeProtocolError(ValueError):
    pass


def emitted_arguments(text, expected_names):
    """Extract emitted ReAct actions, skipping marker strings inside parsed JSON.

    Upstream InjecAgent extracts the shortest {...} match, which truncates nested
    objects. Native ASR judgments remain untouched; the gate must inspect complete
    arguments. Never execute or repair arbitrary Python/JavaScript literals.
    """
    decoder = json.JSONDecoder()
    found = []
    cursor = 0
    pattern = re.compile(r"(?:^|\n)\s*Action:\s*([^\r\n]+)\s*\n\s*Action Input:\s*")
    while match := pattern.search(text, cursor):
        name = match[1].strip()
        start = match.end()
        try:
            empty = re.match(r"(?:None|N/A)(?=\s|$)", text[start:])
            if empty:
                arguments, consumed = {}, empty.end()
            else:
                arguments, consumed = decoder.raw_decode(text[start:])
        except json.JSONDecodeError as exc:
            raise NativeProtocolError("EMITTED_ARGUMENTS_NOT_JSON") from exc
        if not isinstance(arguments, dict):
            raise NativeProtocolError("EMITTED_ARGUMENTS_NOT_OBJECT")
        found.append((name, arguments))
        cursor = start + consumed
    if [name for name, _ in found] != expected_names:
        raise NativeProtocolError("NATIVE_ACTION_SEQUENCE_MISMATCH")
    return found
