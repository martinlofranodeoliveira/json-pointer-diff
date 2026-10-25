from dataclasses import FrozenInstanceError
from decimal import localcontext
import json
import unittest

from json_pointer_diff import Change, InvalidJSON, diff_json


class DiffTests(unittest.TestCase):
    def test_equal_documents_ignore_object_order_and_numeric_spelling(self):
        self.assertEqual(diff_json('{"a":1,"b":[null,true,"x"]}', '{"b":[null,true,"x"],"a":1e0}'), [])

    def test_change_is_immutable(self):
        change = Change("changed", "/x")
        with self.assertRaises(FrozenInstanceError):
            change.path = "/y"

    def test_root_scalars_and_types(self):
        for before, after in [('null', 'false'), ('"a"', '"b"'), ('1', '2'), ('{}', '[]'), ('[]', 'null')]:
            with self.subTest(before=before, after=after):
                self.assertEqual(diff_json(before, after), [Change("changed", "")])

    def test_bool_is_not_number(self):
        for before, after in [('true', '1'), ('false', '0'), ('0', 'false')]:
            with self.subTest(before=before):
                self.assertEqual(diff_json(before, after), [Change("changed", "")])

    def test_exact_numeric_equality(self):
        pairs = [('1', '1.000'), ('1e3', '1000'), ('-0.0', '0e-1000'),
                 ('0.12345678901234567890123456789', '12345678901234567890123456789e-29'),
                 ('1e1000', '10e999'), ('1e-1000', '10e-1001')]
        with localcontext() as context:
            context.prec = 2
            for before, after in pairs:
                with self.subTest(before=before):
                    self.assertEqual(diff_json(before, after), [])

    def test_numbers_beyond_float_precision_differ(self):
        for before, after in [('9007199254740992', '9007199254740993'),
                              ('0.1000000000000000000000001', '0.1000000000000000000000002')]:
            with self.subTest(before=before):
                self.assertEqual(diff_json(before, after), [Change("changed", "")])

    def test_very_long_integer_is_exact(self):
        number = '7' * 5000
        self.assertEqual(diff_json(number, number + '.0'), [])
        self.assertEqual(diff_json(number, number[:-1] + '8'), [Change("changed", "")])

    def test_missing_subtrees_have_single_record(self):
        self.assertEqual(diff_json('{"gone":{"x":[1,2]},"same":null}', '{"new":[{},3],"same":null}'),
                         [Change("removed", "/gone"), Change("added", "/new")])

    def test_replaced_container_has_single_record(self):
        self.assertEqual(diff_json('{"x":{"a":1}}', '{"x":[1,2]}'), [Change("changed", "/x")])

    def test_object_depth_first_order(self):
        before = '{"z":0,"a":{"z":1,"a":2},"M":true}'
        after = '{"M":false,"a":{"a":3,"z":4},"z":1}'
        self.assertEqual(diff_json(before, after), [Change("changed", p) for p in ["/M", "/a/a", "/a/z", "/z"]])

    def test_pointer_escaping_and_empty_key(self):
        before = json.dumps({"": {"a/b~c": 1}, "~1": 0, "/": 0})
        after = json.dumps({"": {"a/b~c": 2}, "~1": 1, "/": 1})
        self.assertEqual(diff_json(before, after), [Change("changed", p) for p in ["//a~1b~0c", "/~1", "/~01"]])

    def test_unicode_and_control_keys_are_preserved_in_api(self):
        self.assertEqual(diff_json('{}', json.dumps({"é": 1, "\n": 2, "😀": 3})),
                         [Change("added", "/\n"), Change("added", "/é"), Change("added", "/😀")])

    def test_array_added_and_removed_tails(self):
        self.assertEqual(diff_json('[1]', '[1,{"x":2},[]]'), [Change("added", "/1"), Change("added", "/2")])
        self.assertEqual(diff_json('[1,{"x":2},[]]', '[1]'), [Change("removed", "/1"), Change("removed", "/2")])

    def test_array_shift_compares_by_index(self):
        self.assertEqual(diff_json('["a","b"]', '["x","a","b"]'),
                         [Change("changed", "/0"), Change("changed", "/1"), Change("added", "/2")])

    def test_array_indexes_are_numeric_order(self):
        self.assertEqual(diff_json('[]', json.dumps(list(range(12)))), [Change("added", f"/{i}") for i in range(12)])

    def test_nested_arrays_and_objects(self):
        self.assertEqual(diff_json('{"a":[{"x":1},[]]}', '{"a":[{"x":2},[3]]}'),
                         [Change("changed", "/a/0/x"), Change("added", "/a/1/0")])

    def test_empty_containers(self):
        for document in ['[]', '{}', 'null', 'false', '""']:
            with self.subTest(document=document):
                self.assertEqual(diff_json(document, document), [])
        self.assertEqual(diff_json('{}', '{"":[]}'), [Change("added", "/")])

    def test_invalid_documents_have_fixed_errors(self):
        invalid = ['', '{', '01', '1 2', 'true false', '[1,]', '{"secret":unquoted}',
                   '"raw\nnewline"', '\ufeff{}', 'NaN', 'Infinity', '-Infinity',
                   '{"a":1,"a":2}', '{"nested":[{"a":1,"a":2}]}',
                   '{"a":1,"\\u0061":2}', '[NaN]', '{"x":Infinity}']
        for document in invalid:
            for side in (0, 1):
                with self.subTest(document=document, side=side):
                    inputs = ["{}", "{}"]
                    inputs[side] = document
                    with self.assertRaises(InvalidJSON) as error:
                        diff_json(*inputs)
                    self.assertEqual(str(error.exception), "invalid JSON document")

    def test_numeric_resource_limit_is_invalid_json(self):
        with self.assertRaisesRegex(InvalidJSON, '^invalid JSON document$'):
            diff_json('1e999999999999999999999999999999999', 'null')

    def test_deep_documents_have_controlled_result(self):
        document = '[' * 10000 + '0' + ']' * 10000
        try:
            result = diff_json(document, document)
        except InvalidJSON as error:
            self.assertEqual(str(error), 'invalid JSON document')
        else:
            self.assertEqual(result, [])

    def test_json_strings_of_constants_are_valid(self):
        self.assertEqual(diff_json('"NaN"', '"NaN"'), [])

    def test_invalid_api_argument_is_fixed_error(self):
        for document in [None, b'{}', {"private": "value"}]:
            with self.subTest(document=type(document)):
                with self.assertRaisesRegex(InvalidJSON, '^invalid JSON document$'):
                    diff_json(document, '{}')


if __name__ == "__main__":
    unittest.main()
