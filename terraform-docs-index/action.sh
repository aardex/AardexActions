#!/bin/bash
#
#   Search for TF Documentation folders 
#   and add those to the project README file.
#

# Variables and Context
START_PATH="${1:-$(pwd)}"
OUTPUT_PATH="${2:-$(pwd)}"

TFDOC_PARAM="markdown document --hide-empty"
README_PATH="${OUTPUT_PATH}/README.md"

TEMP_FILE=$(mktemp)
TEMP_CONTENT=$(mktemp)

START_MARKER="<!-- BEGIN_TF_DOCS -->"
END_MARKER="<!-- END_TF_DOCS -->"


# Search for the folder containing a README or SUMMARY file for TF module
find "$START_PATH" -type f -name "[README|SUMMARY]*" -not -path "**/.terraform/**" -not -path "**/terraform-modules/**" | while read -r README_PATH; do
    DIR_PATH=$(dirname "$README_PATH")
    TF_FILES=$(find "$DIR_PATH/" -maxdepth 1 -type f -name "*.tf")

    if [[ ! -z "$TF_FILES" ]]; then
        TF_MODULE=$(grep '^# ' "${README_PATH}" | head -n 1 | sed 's/^# //')
        if [[ -z "$TF_MODULE" ]]; then
          TF_MODULE=$(basename "$DIR_PATH")
        fi

        REL_PATH=".${DIR_PATH#"$START_PATH"}"
        echo "- [$TF_MODULE]($REL_PATH)" >> "$TEMP_CONTENT"
    fi
done

#Generate the content for the README file
{
  echo "$START_MARKER"
  cat "$TEMP_CONTENT"
  echo "$END_MARKER"
} > "$TEMP_FILE"

echo -e "\nUpdate: $README_PATH with content:"
cat "$TEMP_FILE"

# Create the README file with the generated content, if it does not exist
if [[ ! -f "$README_PATH" ]]; then
  cat "$TEMP_FILE" > "$README_PATH"

# Otherwise, update the content between the markers
elif grep -q "$START_MARKER" "$README_PATH"; then
  awk -v start="$START_MARKER" -v end="$END_MARKER" -v file="$TEMP_FILE" '
  BEGIN {print_content=1}
  $0 ~ start {print_content=0; while ((getline line < file) > 0) {print line}}
  $0 ~ end {print_content=1; next}
  print_content' "$README_PATH" > "$TEMP_CONTENT" && cp "$TEMP_CONTENT" "$README_PATH"

# Or append the content at the end of the README file
else
  echo "" >> "$README_PATH"
  cat "$TEMP_FILE" >> "$README_PATH"
fi

# Clear the temporary files
rm "$TEMP_FILE" "$TEMP_CONTENT"