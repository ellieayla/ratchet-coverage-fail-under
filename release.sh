#!/usr/bin/env bash

if [ $# -ne 1 ]; then
    echo "Usage: $0 1.2.3"
    exit 1
fi

VERSION=$(echo "$1" | egrep '^[0-9]+\.[0-9]+\.[0-9]+$')

TAG="v$VERSION"


if [ -z "$VERSION" ]; then
    echo "Invalid version string $1, should be like 1.2.3"
    exit 1
fi

echo "Setting version to $VERSION"

set -e

if git diff-index --quiet --cached HEAD --; then
    echo "Staged (uncommitted) changes"
    #exit 2
fi

if git diff-files --quiet; then
    echo "Unstaged changes (dirty working directory)"
    exit 2
fi

sed -i '' "s/version = \"[0-9\.]+\"/version = \"$VERSION\"/" pyproject.toml
sed -i '' "s/rev: v[0-9\.]+/rev: $TAG/" README.md
uv sync

git add pyproject.toml README.md uv.lock

git commit -m "Bump version to $TAG"

git tag "$TAG"

echo "Tagged release $TAG"
echo "git push --atomic origin main $TAG"
