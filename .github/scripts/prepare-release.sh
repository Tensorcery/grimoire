#!/usr/bin/env bash
# Bumps the version by commitizen on release/v<next>, pushes the branch and
# opens its PR into $BASE. cz.toml says what a bump touches: pyproject.toml,
# uv.lock, the plugin's manifest and CHANGELOG.md, in one commit. The tag is
# left to release.sh, which makes it on the merge commit.
set -euo pipefail

: "${BASE:?}" "${GH_TOKEN:?}"
# auto: commitizen takes the increment from the commits since the last tag.
increment=${INCREMENT:-auto}

# commitizen reads the whole history and the tags, whatever the checkout fetched.
git fetch --quiet --tags --unshallow 2> /dev/null || git fetch --quiet --tags
git config user.name 'github-actions[bot]'
git config user.email '41898282+github-actions[bot]@users.noreply.github.com'
# The checkout keeps no token: git asks gh, which has it from GH_TOKEN.
gh auth setup-git

git switch --quiet -c release/next
args=(--yes --changelog)
if [ "$increment" != auto ]; then
  args+=(--increment "$increment")
fi
uv run --locked cz bump "${args[@]}"

version=$(uv version --short)
echo "version=$version" >> "$GITHUB_OUTPUT"
git tag -d "v$version"
git branch -m "release/v$version"
git push --quiet origin "release/v$version"

gh pr create --base "$BASE" --head "release/v$version" \
  --title "bump: v$version" --body "Release v$version: the version and CHANGELOG.md."
