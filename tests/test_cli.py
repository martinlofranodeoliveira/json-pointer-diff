import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class CLITests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.before = self.directory / "private-before.json"
        self.after = self.directory / "private-after.json"

    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-m", "json_pointer_diff", *map(str, args)],
                              capture_output=True, text=True, check=False)

    def documents(self, before, after):
        self.before.write_text(before, encoding="utf-8")
        self.after.write_text(after, encoding="utf-8")

    def test_equal_text_and_json(self):
        self.documents('{"x":1}', '{"x":1.00}')
        for flags, expected in [((), 'equal\n'), (('--format', 'json'), '{"equal":true,"changes":[]}\n')]:
            with self.subTest(flags=flags):
                result = self.run_cli(self.before, self.after, *flags)
                self.assertEqual((result.returncode, result.stdout, result.stderr), (0, expected, ''))

    def test_difference_text_is_exact_and_values_absent(self):
        self.documents('{"b":"secret-old","a":0}', '{"a":1,"c":"secret-new"}')
        result = self.run_cli(self.before, self.after)
        self.assertEqual((result.returncode, result.stdout, result.stderr),
                         (1, 'changed "/a"\nremoved "/b"\nadded "/c"\n', ''))

    def test_difference_json_is_exact(self):
        self.documents('{"x":1}', '{"x":2}')
        result = self.run_cli(self.before, self.after, '--format', 'json')
        self.assertEqual((result.returncode, result.stdout, result.stderr),
                         (1, '{"equal":false,"changes":[{"op":"changed","path":"/x"}]}\n', ''))

    def test_root_pointer(self):
        self.documents('0', 'true')
        result = self.run_cli(self.before, self.after)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (1, 'changed ""\n', ''))

    def test_control_keys_cannot_forge_output_lines(self):
        self.documents('{}', json.dumps({"é\n\r\t": 1}))
        for fmt in ['text', 'json']:
            with self.subTest(fmt=fmt):
                result = self.run_cli(self.before, self.after, '--format', fmt)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stderr, '')
                self.assertEqual(len(result.stdout.splitlines()), 1)
                self.assertIn('\\u00e9\\n\\r\\t', result.stdout)

    def test_bad_json_has_fixed_error_without_path_or_source(self):
        self.documents('{"confidential-value": invalid}', '{}')
        result = self.run_cli(self.before, self.after)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (2, '', 'error: invalid JSON input\n'))

    def test_missing_file_has_fixed_error(self):
        self.documents('{}', '{}')
        result = self.run_cli(self.directory / 'secret-missing', self.after)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (2, '', 'error: unable to read input\n'))

    def test_directory_has_fixed_error(self):
        self.documents('{}', '{}')
        result = self.run_cli(self.directory, self.after)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (2, '', 'error: unable to read input\n'))

    def test_invalid_utf8_has_fixed_error(self):
        self.documents('{}', '{}')
        self.before.write_bytes(b'{"secret":"\xff"}')
        result = self.run_cli(self.before, self.after)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (2, '', 'error: unable to read input\n'))

    def test_invalid_arguments_do_not_echo_argv(self):
        cases = [(), ('secret-file',), ('secret-file', 'other', '--format', 'secret-format'),
                 ('secret-file', 'other', '--secret-argument')]
        for args in cases:
            with self.subTest(args=args):
                result = self.run_cli(*args)
                self.assertEqual((result.returncode, result.stdout, result.stderr), (2, '', 'error: invalid arguments\n'))

    def test_help(self):
        result = self.run_cli('--help')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, '')
        self.assertIn('BEFORE', result.stdout)
        self.assertIn('--format', result.stdout)

    def test_inputs_are_not_modified(self):
        self.documents('{"a":1}\n', '{"a":2}\n')
        snapshots = [p.read_bytes() for p in [self.before, self.after]]
        self.run_cli(self.before, self.after)
        self.assertEqual(snapshots, [p.read_bytes() for p in [self.before, self.after]])


if __name__ == "__main__":
    unittest.main()
