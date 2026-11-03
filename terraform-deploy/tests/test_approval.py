"""Offline checks of the GitHub environment review evidence contract."""
import importlib.util
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[2] / 'terraform-apply-saved/check_approval.py'
spec = importlib.util.spec_from_file_location('check_approval', path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class ApprovalTests(unittest.TestCase):
    def setUp(self):
        self.config = {'name': 'alpha', 'can_admins_bypass': False,
                       'deployment_branch_policy': {'protected_branches': True},
                       'protection_rules': [{'type': 'required_reviewers', 'prevent_self_review': True,
                                             'reviewers': [{'type': 'Team'}]}]}
        self.reviews = [{'state': 'approved', 'user': {'login': 'reviewer'},
                         'environments': [{'name': 'alpha'}]}]

    def check(self, config=None, reviews=None, attempt='1'):
        return mod.validate('alpha', 'requester', attempt,
                            self.config if config is None else config,
                            self.reviews if reviews is None else reviews)

    def test_review_required_in_current_run(self):
        self.assertTrue(self.check())
        self.assertFalse(self.check(reviews=[]))
        self.assertFalse(self.check(reviews=[{'state': 'rejected', 'user': {'login': 'reviewer'},
                                             'environments': [{'name': 'alpha'}]}]))
        self.assertFalse(self.check(reviews=[{'state': 'approved', 'user': {'login': 'requester'},
                                             'environments': [{'name': 'alpha'}]}]))
        self.assertFalse(self.check(reviews=[{'state': 'approved', 'user': {'login': 'reviewer'},
                                             'environments': [{'name': 'beta'}]}]))
        self.assertFalse(self.check(attempt='2'))

    def test_unprotected_environment_rejected(self):
        for patch in ({'can_admins_bypass': True}, {'can_admins_bypass': None},
                      {'deployment_branch_policy': None}, {'deployment_branch_policy': {'protected_branches': False, 'custom_branch_policies': False}}, {'protection_rules': []},
                      {'name': 'beta'}, {'protection_rules': [{'type': 'required_reviewers',
                                                               'prevent_self_review': False,
                                                               'reviewers': [{'type': 'Team'}]}]}):
            with self.subTest(patch=patch):
                self.assertFalse(self.check(config={**self.config, **patch}))


if __name__ == '__main__':
    unittest.main()
