#!/bin/bash
EXCLUDE_FILTER=""
if [ -n "$1" ]; then
    EXCLUDE_FILTER=$(echo "$1" | tr ',' '\n' | sed 's/.*/-not -path &/' | tr '\n' ' ')
    echo "Excluding: ${EXCLUDE_FILTER}\n"
fi

MODULE_DIRS=$(find . -type f -name "*.tf" \
    -not -path "*/.terraform/*" \
    -not -path "*/.git/*" \
    -not -path "*/vendor/*" \
    ${EXCLUDE_FILTER} \
    -exec grep -l "required_version" {} \; | xargs -r -n1 dirname | sort -u | jq -R . | jq -sc .)

echo -e "Directories:\n${MODULE_DIRS}"
echo "directories=$MODULE_DIRS" >> $GITHUB_OUTPUT