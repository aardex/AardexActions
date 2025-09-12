# !/usr/bin/env python3

import os
import xml.etree.ElementTree as ET
import argparse


def get_version_from_props(file_path='Directory.Build.props', default='latest'):
    try:
        if not os.path.exists(file_path):
            print(f"File {file_path} not found. Using default version: {default}")
            return default

        tree = ET.parse(file_path)
        root = tree.getroot()

        for element in root.iter():
            if element.tag.endswith('Version'):
                version = element.text.strip()
                print(f"Found version: {version}")
                return version

        print(f"Version tag not found in {file_path}. Using default version: {default}")
        return default
    except Exception as e:
        print(f"Error extracting version: {e}. Using default version: {default}")
        return default


def main():
    parser = argparse.ArgumentParser(description="Get version from Directory.Build.props")
    parser.add_argument('--file', default='Directory.Build.props', help='Path to the props file')
    parser.add_argument('--default', default='latest',
                        help='Default version if file is not found or has no version tag')
    parser.add_argument('--set-output', action='store_true', help='Set GitHub Actions output variable')

    args = parser.parse_args()

    version = get_version_from_props(args.file, args.default)

    print(version)

    if args.set_output:
        with open(os.environ.get('GITHUB_ENV', ''), 'a') as env_file:
            env_file.write(f"VERSION={version}\n")


if __name__ == '__main__':
    main()