#!/bin/bash
# Pushes ./site to the gh-pages branch as ONE fresh commit (force push), so the
# branch never grows. GitHub Pages serves that branch.
set -e
cd site
rm -rf .git
git init -q -b gh-pages
git add -A
git -c user.name="memescan-bot" -c user.email="41898282+github-actions[bot]@users.noreply.github.com" \
  commit -q -m "Website update $(date -u '+%Y-%m-%d %H:%M UTC')"
git push -q -f "https://x-access-token:${GH_TOKEN}@github.com/${GITHUB_REPOSITORY}.git" gh-pages
rm -rf .git
echo "publish: website updated" >&2
