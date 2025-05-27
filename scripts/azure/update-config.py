import argparse
import json
import sys

import requests


def parse_arguments():
    parser = argparse.ArgumentParser(description='Process some integers.')
    parser.add_argument('--token', metavar='token', type=str, help='the github token to use')
    parser.add_argument('--repo', metavar='repo', type=str, help='the repo to access (e.g. "owner/repo")')
    parser.add_argument('--repo-env', metavar='repo-env', type=str, help='the repo environment to access')
    parser.add_argument('--config-path', metavar='config-path', type=str, help='the path to the config file')
    return parser.parse_args()


def load_config_file(config_path):
    print(f"Load the config file from {config_path}")
    file = open(config_path, 'r', encoding='utf-8-sig')
    data = json.load(file)
    file.close()
    return data


def get_env_variables(token, repo, repo_env):
    print(f"Get the environment variables for {repo_env} in {repo}")
    url = f"https://api.github.com/repos/{repo}/environments/{repo_env}/variables?per_page=30"
    headers = {'Authorization': f'Bearer {token}'}

    print(f"Get on {url} with")
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"Failed to get workflows, status code: {response.status_code}")
        sys.exit(1)
    return response.json()['variables']


def add_env_variables(data, variables):
    print("Add the environment variables to the config file")
    for variable in variables:
        name = (variable["name"]).lower()
        value = (variable["value"]).lower()
        print(f"Add {name} with value {value}")
        if "Values" in data:
            data["Values"][name] = value
        else:
            data[name] = value
    return data


def save_config_file(config_path, data):
    print(f"Save the config file to {config_path}")
    with open(config_path, 'w') as file:
        json.dump(data, file)


def main():
    args = parse_arguments()

    print(f"Repo: {args.repo} - Repo env: {args.repo_env} - Config Path: {args.config_path}")

    data = load_config_file(args.config_path)
    variables = get_env_variables(args.token, args.repo, args.repo_env)

    print("Add variables to the config file")
    data = add_env_variables(data, variables)

    print("Save the config file")
    save_config_file(args.config_path, data)


if __name__ == "__main__":
    sys.exit(main())
