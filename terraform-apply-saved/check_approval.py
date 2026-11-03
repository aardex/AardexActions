#!/usr/bin/env python3
"""Fail closed if the current run lacks the expected environment review evidence."""
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request


def validate(environment, actor, attempt, config, reviews):
    if attempt != '1':
        return False  # Run-level review history cannot distinguish rerun attempts.
    if not isinstance(config, dict) or config.get('name', '').lower() != environment.lower():
        return False
    if config.get('can_admins_bypass') is not False:
        return False
    policy = config.get('deployment_branch_policy')
    if not isinstance(policy, dict) or not (policy.get('protected_branches') is True or
                                           policy.get('custom_branch_policies') is True):
        return False
    rules = config.get('protection_rules', [])
    if not any(rule.get('type') == 'required_reviewers' and rule.get('prevent_self_review') is True
               and rule.get('reviewers') for rule in rules):
        return False
    return isinstance(reviews, list) and any(
        review.get('state') == 'approved' and
        review.get('user', {}).get('login', '').lower() != actor.lower() and
        bool(review.get('user', {}).get('login')) and
        any(item.get('name', '').lower() == environment.lower()
            for item in review.get('environments', []))
        for review in reviews)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def get_json(url, token):
    request = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + token,
                                                   'Accept': 'application/vnd.github+json'})
    with urllib.request.build_opener(NoRedirect()).open(request, timeout=30) as response:
        return json.load(response)


def main():
    try:
        env = os.environ
        repo = env['GITHUB_REPOSITORY']
        environment = env['PLAN_ENVIRONMENT']
        actor = env['GITHUB_ACTOR']
        run_id = env['GITHUB_RUN_ID']
        token = env['GITHUB_API_TOKEN']
        if (not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo) or
                not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}', environment) or
                not re.fullmatch(r'[1-9][0-9]{0,19}', run_id) or not actor or not token):
            raise ValueError()
        base = f'https://api.github.com/repos/{repo}'
        config = get_json(base + '/environments/' + urllib.parse.quote(environment, safe=''), token)
        reviews = get_json(base + '/actions/runs/' + run_id + '/approvals', token)
        if not validate(environment, actor, env.get('GITHUB_RUN_ATTEMPT', ''), config, reviews):
            raise ValueError()
    except Exception:
        print('::error::Required environment review evidence is unavailable or insufficient.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
