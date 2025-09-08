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
  echo "Using provided version: $VERSION"
elif [[ -f "$VERSION_FILE" ]]; then
  VERSION=$(grep -Eo '[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9\.]+)?' "$VERSION_FILE" | head -n 1)
  echo "Using version from file: $VERSION"
else
  echo "ERROR - No version provided and ${VERSION_FILE:-file} not found."
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

echo "Updating the current version: $VERSION ($MAJOR / $MINOR / $PATCH / $SUFFIX)"

case "$VERSION_TYPE" in
  major|version-major)
    NEW_VERSION="$((MAJOR + 1)).0.0"
    echo "Updated MAJOR version: $VERSION -> $NEW_VERSION"
    ;;
  
  minor|version-minor)
    NEW_VERSION="$MAJOR.$((MINOR + 1)).0"
    echo "Updated MINOR version: $VERSION -> $NEW_VERSION"
    ;;
  
  patch|version-patch)
    # If the current version is a pre-release (rc/alpha), finalize it by dropping the suffix
    if [[ -n "$SUFFIX" && "$SUFFIX" =~ ^-(${TAG_RC}|${TAG_ALPHA})(\.|$) ]]; then
      NEW_VERSION="$MAJOR.$MINOR.$PATCH"
      echo "Finalize pre-release to STABLE (drop suffix): $VERSION -> $NEW_VERSION"
    else
      NEW_VERSION="$MAJOR.$MINOR.$((PATCH + 1))"
      echo "Updated PATCH version: $VERSION -> $NEW_VERSION"
    fi
    ;;
  
  release|version-release)
    # Always remove any suffix to create a clean release version
    NEW_VERSION="$MAJOR.$MINOR.$PATCH"
    echo "Creating RELEASE version (removed all suffixes): $VERSION -> $NEW_VERSION"
    ;;
  
  release-candidate|rc)
    if [[ "$SUFFIX" =~ ${TAG_RC}.*([0-9]+)$ ]]; then
      N="${BASH_REMATCH[1]}"
      NEW_VERSION="${MAJOR}.${MINOR}.${PATCH}-${TAG_RC}.$((N + 1))"
    else
      NEW_VERSION="${MAJOR}.${MINOR}.${PATCH}-${TAG_RC}.1"
    fi
    echo "Updated RC version: $VERSION -> $NEW_VERSION"
    ;;
  
  alpha)
    BRANCH_ID=""
    BRANCH_MATCH=""
    if [[ "$BRANCH_NAME" =~ ([0-9]+) ]]; then
      BRANCH_ID=".${BASH_REMATCH[1]}"
      BRANCH_MATCH="\.${BASH_REMATCH[1]}"
    fi

    if [[ "$SUFFIX" =~ ${TAG_ALPHA}${BRANCH_MATCH}.*\.([0-9]+)$ ]]; then
      N="${BASH_REMATCH[1]}"
      NEW_VERSION="${MAJOR}.${MINOR}.${PATCH}-${TAG_ALPHA}${BRANCH_ID}.$((N + 1))"
    else
      NEW_VERSION="${MAJOR}.${MINOR}.${PATCH}-${TAG_ALPHA}${BRANCH_ID}.1"
    fi

    echo "Updated ALPHA version: $VERSION -> $NEW_VERSION"
    ;;

  *)
    echo "ERROR - Unknown version type: $VERSION_TYPE"
    exit 1
    ;;
esac

if [[ -n "$GITHUB_OUTPUT" ]]; then
  echo "version=$NEW_VERSION" >> "$GITHUB_OUTPUT"
fi