#!/usr/bin/env bash
# Mirror this repo's working tree into the shared Google Drive "Project" folder so
# non-git teammates (and Colab) see the latest code. Run after committing.
#
#   ./scripts/publish_to_drive.sh            # publish
#   ./scripts/publish_to_drive.sh --dry-run  # show what would change
#
# Override the target with DRIVE_PUBLISH_DIR in .env. Notebooks (*.ipynb) in Drive are
# never touched or deleted: the Colab notebook lives there, not in this repo.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
[ -f "$REPO_DIR/.env" ] && set -a && source "$REPO_DIR/.env" && set +a
DRIVE_PUBLISH_DIR="${DRIVE_PUBLISH_DIR:-$HOME/Library/CloudStorage/GoogleDrive-tyang232@usc.edu/My Drive/DSO 585/Project}"

if [ ! -d "$DRIVE_PUBLISH_DIR" ]; then
  echo "Drive folder not found: $DRIVE_PUBLISH_DIR" >&2
  echo "Set DRIVE_PUBLISH_DIR in .env to your Google Drive for Desktop sync path." >&2
  exit 1
fi

rsync -av --delete "$@" \
  --exclude='.git' --exclude='data' --exclude='__pycache__' --exclude='.env' \
  --exclude='*.ipynb' --exclude='.DS_Store' --exclude='.ipynb_checkpoints' \
  "$REPO_DIR/" "$DRIVE_PUBLISH_DIR/"

case " $* " in *" --dry-run "*|*" -n "*) echo "Dry run only; nothing written." ;; *) echo "Published to $DRIVE_PUBLISH_DIR" ;; esac
