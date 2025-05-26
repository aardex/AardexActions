import xml.etree.ElementTree as ET


def extract_version_from_solution():
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
