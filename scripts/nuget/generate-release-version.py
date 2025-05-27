import common as common


def increment_version(version):
    if "-" in version:
        parts = version.split("-")
        return parts[0]
    else:
        parts = version.split(".")
        patch_number = int(parts[-1])
        patch_number += 1
        new_version = ".".join(parts[:-1]) + f".{patch_number}"
        return new_version


def main():
    current_version = common.extract_version_from_solution()

    if current_version:
        new_version = increment_version(current_version)
        print(new_version)
    else:
        print("Invalid format")


if __name__ == '__main__':
    main()
