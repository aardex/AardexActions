import argparse
import common as common


def extract_number(input_string):
    parts = input_string.split("-")
    if len(parts) > 1:
        return parts[-1]
    else:
        return None


def increment_version(version, branch_number):
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
    parser = argparse.ArgumentParser(description="Extract version number from the solution and increment it.")
    parser.add_argument("--branch", required=True, help="Name of the branch")
    args = parser.parse_args()

    branch_name = args.branch
    output_number = extract_number(branch_name)

    current_version = common.extract_version_from_solution()

    if current_version:
        new_version = increment_version(current_version, output_number)
        print(new_version)
    else:
        print("Invalid format")


if __name__ == '__main__':
    main()
