#!/usr/bin/env bash
# Releases the version in pyproject.toml once: when origin has no tag
# v<version>, creates the GitHub release, whose tag lands on the commit being
# built. When the tag exists, it does nothing. The notes are GitHub's: the
# PRs merged since the previous release.
set -euo pipefail

: "${GH_TOKEN:?}" "${GITHUB_SHA:?}"

version=$(uv version --short)
if git ls-remote --exit-code --tags origin "refs/tags/v$version" > /dev/null; then
  echo "v$version is released already"
  exit 0
fi

gh release create "v$version" --target "$GITHUB_SHA" --title "v$version" --generate-notes
