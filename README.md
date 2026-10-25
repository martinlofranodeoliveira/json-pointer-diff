# json-pointer-diff

Compare two local JSON documents and report where they differ, using [RFC 6901
JSON Pointers](https://www.rfc-editor.org/rfc/rfc6901). Reports contain paths and
operations, without document values. Useful for checking generated configuration,
API fixtures, or snapshots when the location of a change is enough.

Python 3.10+; standard library only; no runtime network access. MIT licensed.

## Run

From this checkout, no installation is required:

```sh
python -m json_pointer_diff before.json after.json
python -m json_pointer_diff before.json after.json --format json
```

For a console command, install the local project in a virtual environment:

```sh
python -m pip install .
json-pointer-diff before.json after.json
```

For these synthetic documents:

```json
{"items":[{"enabled":true}],"revision":1,"obsolete":null}
```

```json
{"items":[{"enabled":false},{}],"revision":1.0}
```

Text output is:

```text
changed "/items/0/enabled"
added "/items/1"
removed "/obsolete"
```

The JSON format is one compact line, followed by a newline:

```json
{"equal":false,"changes":[{"op":"changed","path":"/items/0/enabled"},{"op":"added","path":"/items/1"},{"op":"removed","path":"/obsolete"}]}
```

Equal documents print `equal` in text mode or `{"equal":true,"changes":[]}` in
JSON mode, followed by a newline. Text mode quotes each pointer as a JSON string;
control characters and non-ASCII characters are escaped in both formats. Root
replacement is `changed ""`. This output is a change report, not a JSON Patch.

| Exit status | Meaning |
| --- | --- |
| 0 | Documents are equal |
| 1 | Documents differ |
| 2 | Invalid arguments, invalid JSON, UTF-8 decoding failure, or I/O failure |

Successful comparisons write only to stdout. Errors write a fixed, generic
message to stderr and do not print filenames, arguments, or document values.
Both inputs are local UTF-8 file paths; `-` has no special stdin meaning.

## Comparison contract

- Objects compare by key, regardless of source order. Keys are visited in Unicode
  codepoint order. Array indexes are visited in ascending numeric order. The
  report follows this deterministic depth-first traversal.
- Arrays compare by position. `["a","b"]` to `["x","a","b"]` yields changes at
  `/0` and `/1`, then an addition at `/2`. Elements are not matched across indexes.
- A missing key or index produces one `added` or `removed` record for its entire
  subtree. Replacing a node with another type produces one `changed` record.
  Containers of the same type are compared recursively.
- JSON numbers compare by exact decimal value: `1`, `1.00`, and `1e0` are equal;
  `-0` equals `0`. Large integers and long fractions retain their precision.
  Booleans are distinct from numbers, so `true` differs from `1`.
- Pointer tokens escape `~` as `~0`, then `/` as `~1`. The empty pointer denotes
  the root, while `/` denotes an empty object key. Pointers are plain strings,
  without the URI-fragment `#` prefix or percent encoding.
- Duplicate object keys, including escaped duplicates and nested duplicates, are
  errors. `NaN`, `Infinity`, `-Infinity`, malformed JSON, trailing content, and
  parser resource-limit failures are errors too. A UTF-8 BOM is rejected.

Paths necessarily expose object keys and array indexes. No report includes old
or new values. Files are read into memory and parsed using Python's JSON parser
and `decimal.Decimal`; document size, nesting, and numeric exponent capacity are
limited by available memory and those standard-library implementations.

## Python API

```python
from json_pointer_diff import Change, InvalidJSON, diff_json

assert diff_json('{"count":1}', '{"count":1.0}') == []
assert diff_json('{"a/b":0}', '{"a/b":1}') == [Change("changed", "/a~1b")]

try:
    diff_json('{"x":1,"x":2}', '{}')
except InvalidJSON:
    print("Input was not strict JSON")
```

`diff_json(before: str, after: str) -> list[Change]` accepts two complete document
strings and validates both. `Change` is an immutable dataclass with `op` and
`path` string fields. Operations are exactly `added`, `removed`, or `changed`.
`InvalidJSON` derives from `ValueError` and has the fixed message
`invalid JSON document`. Input documents are never modified.

## Develop

```sh
python -m unittest discover -s tests -v
python -m compileall -q json_pointer_diff tests
```

Tests use synthetic input and the standard library, including subprocess CLI
checks. CI runs the suite on Python 3.10 through 3.14. No package installation is
needed to run tests from the checkout. Installing the package may require
setuptools as a build dependency; the installed runtime has no dependencies.
