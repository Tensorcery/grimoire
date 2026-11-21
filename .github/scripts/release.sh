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
# 0: the tag is there. 2: it is not. Anything else is a failure to ask, and
# must not pass for "not released yet".
found=0
git ls-remote --exit-code --tags origin "refs/tags/v$version" > /dev/null || found=$?
case $found in
  0) echo "v$version is released already"; exit 0 ;;
  2) ;;
  *) echo "could not ask origin for the tag v$version" >&2; exit "$found" ;;
esac

# Two lines are not for the reader: the note to whoever edits the pull
# request, and the line CodeRabbit was to replace, if it never came.
notes=$(gh pr list --state merged --head "release/v$version" --json body --jq '.[0].body // ""' \
  | tr -d '\r' | sed -e '/^<!--.*-->$/d' -e '/^@coderabbitai summary$/d')

if [ -n "${notes//[[:space:]]/}" ]; then
  gh release create "v$version" --target "$GITHUB_SHA" --title "v$version" --notes-file - <<< "$notes"
else
  gh release create "v$version" --target "$GITHUB_SHA" --title "v$version" --generate-notes
fi
