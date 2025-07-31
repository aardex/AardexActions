#!/bin/bash
#
#   Increment the version according to provided type and the current branch name
#

if [[ "$1" == "--help" ]]; then
  echo "Usage: action.sh <version-type> [--version x.y.z] [--branch name] [--file path]"
  exit 0
fi

# Default values
TAG_ALPHA="alpha"
TAG_RC="rc"
VERSION_TYPE="${1:-alpha}"
VERSION_FILE="version.txt"
BRANCH_NAME=$(git rev-parse --abbrev-ref HEAD)

# Compute parameters
shift 1
while [[ $# -gt 0 ]]; do
  case "$1" in
    --version)
      VERSION_NUMBER="${2:-$VERSION_NUMBER}"
      shift 2
      ;;
    --branch)
      BRANCH_NAME="${2:-$BRANCH_NAME}"
      shift 2
      ;;
    --file)
      VERSION_FILE="${2:-$VERSION_FILE}"
      shift 2
      ;;
    *)
      shift
      ;;
  esac
done

# Check the version provided or read from file
if [[ -n "$VERSION_NUMBER" ]]; then
  VERSION="$VERSION_NUMBER"
elif [[ -f "$VERSION_FILE" ]]; then
  VERSION=$(cat "$VERSION_FILE" | tr -d '\n')
else
  echo "ERROR - No version provided and ${VERSION_FILE} not found."
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
  
  release-candidate|rc)
    if [[ "$SUFFIX" =~ ${TAG_RC}([0-9]+) ]]; then
      N="${BASH_REMATCH[1]}"
      NEW_VERSION="${MAJOR}.${MINOR}.${PATCH}-${TAG_RC}.$((N + 1))"
    else
      NEW_VERSION="${MAJOR}.${MINOR}.${PATCH}-${TAG_RC}.1"
    fi
    ;;
  
  alpha)
    BRANCH_ID=""
    if [[ "$BRANCH_NAME" =~ ([0-9]+) ]]; then
      BRANCH_ID=".${BASH_REMATCH[1]}"
    fi
        
    if [[ "$SUFFIX" =~ ${TAG_ALPHA}\.${BRANCH_ID}\.([0-9]+) ]]; then
      N="${BASH_REMATCH[1]}"
      NEW_VERSION="${MAJOR}.${MINOR}.${PATCH}-${TAG_ALPHA}${BRANCH_ID}.$((N + 1))"
    else
      NEW_VERSION="${MAJOR}.${MINOR}.${PATCH}-${TAG_ALPHA}${BRANCH_ID}.1"
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