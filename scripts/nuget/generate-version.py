import argparse
import xml.etree.ElementTree as ET
import sys


def extract_version_from_solution():
    """Extract the current version from Directory.Build.props"""
    try:
        tree = ET.parse('Directory.Build.props')
        root = tree.getroot()

        for element in root.iter():
            if element.tag in "Version":
                return element.text.strip()

        print("The <Version> tag was not found in the Directory.Build.props file.")
        return None
    except Exception as e:
        print(f"An error occurred while parsing the Directory.Build.props file: {e}")
        return None


def extract_branch_number(input_string):
    """Extract branch number from branch name"""
    parts = input_string.split("-")
    if len(parts) > 1:
        return parts[-1]
    else:
        return None


def increment_release_version(version):
    if "-" in version:
        parts = version.split("-")
        return parts[0]
    else:
        parts = version.split(".")
        patch_number = int(parts[-1])
        patch_number += 1
        new_version = ".".join(parts[:-1]) + f".{patch_number}"
        return new_version


def increment_rc_version(version):
    if "-alpha" in version:
        parts = version.split("-")
        version = parts[0]
        return f"{version}-rc.1"

    if "-rc" in version:
        parts = version.split("-")
        rc_parts = parts[1].split(".")
        return f"{parts[0]}-rc.{int(rc_parts[1]) + 1}"
    else:
        parts = version.split(".")
        patch_number = int(parts[-1])
        patch_number += 1
        new_version = ".".join(parts[:-1]) + f".{patch_number}-rc.1"
        return new_version


def increment_alpha_version(version, branch_number):
    if "-rc" in version:
        parts = version.split("-")
        version = parts[0]

    if "-alpha" in version:
        parts = version.split("-")
        alpha_parts = parts[-1].split(".")
        return f"{parts[0]}-{alpha_parts[0]}.{alpha_parts[1]}.{int(alpha_parts[2]) + 1}"
    else:
        parts = version.split(".")
        patch_number = int(parts[-1])
        patch_number += 1
        new_version = ".".join(parts[:-1]) + f".{patch_number}-alpha.{branch_number}.1"
        return new_version


def main():
    parser = argparse.ArgumentParser(description="Version management tool for projects")

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    get_parser = subparsers.add_parser("get", help="Get the current version")

    alpha_parser = subparsers.add_parser("alpha", help="Generate alpha version")
    alpha_parser.add_argument("--branch", required=True, help="Name of the branch")

    rc_parser = subparsers.add_parser("rc", help="Generate release candidate version")

    release_parser = subparsers.add_parser("release", help="Generate release version")

    args = parser.parse_args()

    current_version = extract_version_from_solution()
    if not current_version:
        print("Invalid format", file=sys.stderr)
        sys.exit(1)

    if args.command == "get" or not args.command:
        print(current_version)
        return

    new_version = None

    if args.command == "alpha":
        branch_number = extract_branch_number(args.branch)
        if not branch_number:
            print("Error: Could not extract branch number from branch name", file=sys.stderr)
            sys.exit(1)
        new_version = increment_alpha_version(current_version, branch_number)

    elif args.command == "rc":
        new_version = increment_rc_version(current_version)

    elif args.command == "release":
        new_version = increment_release_version(current_version)

    if new_version:
        print(new_version)


if __name__ == "__main__":
    main()