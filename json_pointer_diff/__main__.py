"""Command-line interface; errors deliberately omit input content and paths."""

import argparse
import json
from pathlib import Path
import sys

from . import InvalidJSON, diff_json


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, "error: invalid arguments\n")


def main(argv=None):
    parser = _Parser(prog="json-pointer-diff", description="Compare local JSON files without printing values.")
    parser.add_argument("before", metavar="BEFORE", help="original UTF-8 JSON file")
    parser.add_argument("after", metavar="AFTER", help="updated UTF-8 JSON file")
    parser.add_argument("--format", choices=("json", "text"), default="text", help="output format (default: text)")
    args = parser.parse_args(argv)
    try:
        before = Path(args.before).read_text(encoding="utf-8")
        after = Path(args.after).read_text(encoding="utf-8")
    except (OSError, UnicodeError, ValueError):
        print("error: unable to read input", file=sys.stderr)
        return 2
    try:
        changes = diff_json(before, after)
    except InvalidJSON:
        print("error: invalid JSON input", file=sys.stderr)
        return 2
    if args.format == "json":
        report = {"equal": not changes, "changes": [{"op": c.op, "path": c.path} for c in changes]}
        output = json.dumps(report, ensure_ascii=True, separators=(",", ":")) + "\n"
    elif changes:
        output = "".join(f"{c.op} {json.dumps(c.path, ensure_ascii=True)}\n" for c in changes)
    else:
        output = "equal\n"
    try:
        sys.stdout.write(output)
        sys.stdout.flush()
    except OSError:
        print("error: unable to write output", file=sys.stderr)
        return 2
    return 1 if changes else 0


if __name__ == "__main__":
    raise SystemExit(main())
