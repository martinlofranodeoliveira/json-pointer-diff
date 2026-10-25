"""Compare JSON documents using value-free RFC 6901 paths."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import json

__all__ = ["Change", "InvalidJSON", "diff_json"]


@dataclass(frozen=True)
class Change:
    """One difference: an added, removed, or changed node at a JSON Pointer."""

    op: str
    path: str


class InvalidJSON(ValueError):
    """A document could not be parsed as strict JSON."""


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate object key")
        result[key] = value
    return result


def _constant(_value):
    raise ValueError("non-JSON constant")


def _parse(source):
    if not isinstance(source, str):
        raise InvalidJSON("invalid JSON document")
    try:
        return json.loads(
            source,
            parse_int=Decimal,
            parse_float=Decimal,
            parse_constant=_constant,
            object_pairs_hook=_object,
        )
    except (ValueError, RecursionError, InvalidOperation, OverflowError):
        raise InvalidJSON("invalid JSON document") from None


def _child(path, key):
    return path + "/" + str(key).replace("~", "~0").replace("/", "~1")


def diff_json(before: str, after: str) -> list[Change]:
    """Return deterministic, value-free differences between two JSON strings.

    Objects compare by key; arrays compare by index. Missing subtrees are one
    change, as are replacements of differently typed nodes. Numbers compare
    exactly by decimal value. Invalid input raises InvalidJSON without values.
    """
    missing = object()
    pending = [(_parse(before), _parse(after), "")]
    changes = []
    while pending:
        left, right, path = pending.pop()
        if left is missing:
            changes.append(Change("added", path))
        elif right is missing:
            changes.append(Change("removed", path))
        elif type(left) is not type(right):
            changes.append(Change("changed", path))
        elif isinstance(left, dict):
            for key in reversed(sorted(left.keys() | right.keys())):
                pending.append((left.get(key, missing), right.get(key, missing), _child(path, key)))
        elif isinstance(left, list):
            for index in reversed(range(max(len(left), len(right)))):
                pending.append((
                    left[index] if index < len(left) else missing,
                    right[index] if index < len(right) else missing,
                    _child(path, index),
                ))
        elif left != right:
            changes.append(Change("changed", path))
    return changes
