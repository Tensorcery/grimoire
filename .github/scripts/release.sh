#!/usr/bin/env bash
# Releases the version in pyproject.toml once: when origin has no tag
# v<version>, creates the GitHub release, whose tag lands on the commit being
# built. When the tag exists, it does nothing. The description is what the
# release pull request said when it was merged (prepare-release.sh); without
# such a pull request it is GitHub's list of the PRs merged since the
# previous release.
set -euo pipefail

: "${GH_TOKEN:?}" "${GITHUB_SHA:?}"

version=$(uv version --short)
if git ls-remote --exit-code --tags origin "refs/tags/v$version" > /dev/null; then
  echo "v$version is released already"
  exit 0
fi

# The comment line is the note to whoever edits the pull request.
notes=$(gh pr list --state merged --head "release/v$version" --json body --jq '.[0].body // ""' \
  | tr -d '\r' | sed '/^<!--.*-->$/d')

if [ -n "${notes//[[:space:]]/}" ]; then
  gh release create "v$version" --target "$GITHUB_SHA" --title "v$version" --notes-file - <<< "$notes"
else
  gh release create "v$version" --target "$GITHUB_SHA" --title "v$version" --generate-notes
fi
