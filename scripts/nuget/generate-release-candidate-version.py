import common as common


def increment_version(version):
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


def main():
    current_version = common.extract_version_from_solution()

    if current_version:
        new_version = increment_version(current_version)
        print(new_version)
    else:
        print("Invalid format")


if __name__ == '__main__':
    main()
