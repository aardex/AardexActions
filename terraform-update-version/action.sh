#!/bin/bash
#
#   Increment the version according to provided type and the current branch name
#

# Variables and Context
VERSION_TYPE="${1:-alpha}"
VERSION_NUMBER="${2}"
BRANCH_NAME="${3:-$(git rev-parse --abbrev-ref HEAD)}"
VERSION_FILE="${4:-version.txt}"

TAG_ALPHA="alpha"
TAG_RC="rc"

# Check the version provided or read from file
if [[ -n "$VERSION_NUMBER" ]]; then
  VERSION="$VERSION_NUMBER"
elif [[ -f "$VERSION_FILE" ]]; then
  VERSION=$(cat "$VERSION_FILE" | tr -d '\n')
else
  echo "ERROR - No version provided and version.txt not found."
  exit 1
fi

# Extract major, minor, patch
if [[ "$VERSION" =~ ^([0-9]+)\.([0-9]+)\.([0-9]+)(-.*)?$ ]]; then
  MAJOR="${BASH_REMATCH[1]}"
  MINOR="${BASH_REMATCH[2]}"
  PATCH="${BASH_REMATCH[3]}"
  SUFFIX="${BASH_REMATCH[4]}"
else
  echo "Invalid version format: $VERSION"
  exit 1
fi

case "$VERSION_TYPE" in
  major|version-major)
    NEW_VERSION="$((MAJOR + 1)).0.0"
    ;;
  
  minor|version-minor)
    NEW_VERSION="$MAJOR.$((MINOR + 1)).0"
    ;;
  
  patch|version-patch)
    NEW_VERSION="$MAJOR.$MINOR.$((PATCH + 1))"
    ;;
  
  alpha)
    if [[ "$BRANCH_NAME" =~ ([0-9]+) ]]; then
      BRANCH_ID="${BASH_REMATCH[1]}"
    else
      echo "ERROR - Unable to extract branch ID from name: $BRANCH_NAME"
      exit 1
    fi
        
    if [[ "$SUFFIX" =~ ${TAG_ALPHA}\.${BRANCH_ID}\.([0-9]+) ]]; then
      N="${BASH_REMATCH[1]}"
      NEW_VERSION="${MAJOR}.${MINOR}.${PATCH}-${TAG_ALPHA}.${BRANCH_ID}.$((N + 1))"
    else
      NEW_VERSION="${MAJOR}.${MINOR}.${PATCH}-${TAG_ALPHA}.${BRANCH_ID}.1"
    fi
    ;;

  release-candidate|rc)
    if [[ "$SUFFIX" =~ ${TAG_RC}([0-9]+) ]]; then
      N="${BASH_REMATCH[1]}"
      NEW_VERSION="${MAJOR}.${MINOR}.${PATCH}-${TAG_RC}.$((N + 1))"
    else
      NEW_VERSION="${MAJOR}.${MINOR}.${PATCH}-${TAG_RC}1"
    fi
    ;;
  
  *)
    echo "ERROR - Unknown version type: $VERSION_TYPE"
    exit 1
    ;;
esac

echo -e "Updated version: $VERSION -> $NEW_VERSION"
if [[ -n "$GITHUB_OUTPUT" ]]; then
  echo "version=$NEW_VERSION" >> "$GITHUB_OUTPUT"
fi