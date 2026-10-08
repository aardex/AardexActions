"""Independent JSON Schema validation; installed by CI, optional for stdlib tests."""
import copy
import json
from pathlib import Path
import unittest

import manifest as m

try:
    from jsonschema import Draft202012Validator
except ImportError:
    Draft202012Validator = None


@unittest.skipIf(Draft202012Validator is None, 'CI-only jsonschema is not installed')
class SchemaContract(unittest.TestCase):
    def test_schema_example_and_negative_shapes_match_runtime(self):
        Draft202012Validator.check_schema(m.SCHEMA)
        validator = Draft202012Validator(m.SCHEMA)
        example = json.loads((Path(m.__file__).parent / 'examples/release-manifest.json').read_text())
        validator.validate(example)
        m.shape(example, m.SCHEMA)
        mutations = [(['schema_version'], True), (['release', 'version'], '01.2.3'),
                     (['release', 'sha'], 'main'), (['release_pr', 'number'], 0),
                     (['generator', 'conclusion'], 'success'), (['generator', 'attempt'], 0),
                     (['checks', 0, 'verification'], 'declared'), (['checks', 0, 'id'], False),
                     (['checks', 0, 'outcome', 'status'], 'invented'),
                     (['artifacts'], {'state': 'available', 'items': []}),
                     (['migrations'], {'state': 'not_applicable', 'reason': ''}),
                     (['unknown'], 'field')]
        for path, value in mutations:
            invalid = copy.deepcopy(example)
            target = invalid
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            with self.subTest(path=path):
                self.assertFalse(validator.is_valid(invalid))
                with self.assertRaises(ValueError):
                    m.shape(invalid, m.SCHEMA)
