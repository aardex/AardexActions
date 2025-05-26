import argparse
import xml.etree.ElementTree as ET


def write_version_to_csproj(new_version):
    try:
        tree = ET.parse('Directory.Build.props')
        root = tree.getroot()

        for element in root.iter():
            if element.tag in "Version":
                element.text = new_version
                break

        tree.write('Directory.Build.props')
        print("Version updated successfully.")
    except Exception as e:
        print(f"An error occurred while writing the version to the .csproj file: {e}")


def main():
    parser = argparse.ArgumentParser(description="Write version number to .csproj file.")
    parser.add_argument("--new-version", required=True, help="New version number to write to .csproj file")
    args = parser.parse_args()

    new_version = args.new_version

    write_version_to_csproj(new_version)


main()
