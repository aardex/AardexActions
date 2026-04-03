import argparse
import xml.etree.ElementTree as ET


def is_version_tag(tag):
    return tag.split("}")[-1] == "Version"


def write_version_to_csproj(new_version, props_file):
    try:
        tree = ET.parse(props_file)
        root = tree.getroot()

        for element in root.iter():
            if is_version_tag(element.tag):
                element.text = new_version
                break

        tree.write(props_file)
        print("Version updated successfully.")
    except Exception as e:
        print(f"An error occurred while writing the version to the .csproj file: {e}")


def main():
    parser = argparse.ArgumentParser(description="Write version number to .csproj file.")
    parser.add_argument("--new-version", required=True, help="New version number to write to .csproj file")
    parser.add_argument("--props-file", default="Directory.Build.props", help="Path to Directory.Build.props")
    args = parser.parse_args()

    new_version = args.new_version
    props_file = args.props_file

    write_version_to_csproj(new_version, props_file)


if __name__ == '__main__':
    main()
