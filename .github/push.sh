#!/usr/bin/env bash
# Commit the given paths and push, pulling first and retrying, so two jobs finishing at once never lose a save.
# Usage: bash .github/push.sh "commit message" path1 path2 ...
set -u
msg="$1"; shift
git config user.name "owl-bot"
git config user.email "owl-bot@users.noreply.github.com"
for p in "$@"; do [ -e "$p" ] && git add -A -- "$p"; done
if git diff --cached --quiet; then echo "Nothing new to save."; exit 0; fi
git commit -q -m "$msg"
for i in 1 2 3 4 5; do
  if git pull --rebase -q && git push -q; then echo "Saved: $msg"; exit 0; fi
  echo "Push attempt $i failed, retrying..."; sleep $((i * 7))
done
echo "Could not push after 5 attempts."; exit 1
