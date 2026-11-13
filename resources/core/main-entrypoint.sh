#!/bin/bash
set -e

umask 0002

ASSETS_PATH="/home/frappe/frappe-bench/sites/assets"
BAKED_PATH="/home/frappe/frappe-bench/assets"

echo "Linking fresh assets to volume..."
mkdir -p "$(dirname "$ASSETS_PATH")"
exec 7>"${ASSETS_PATH}.lock"
flock 7
if [ -d "$ASSETS_PATH" ] && [ ! -L "$ASSETS_PATH" ]; then
  mv "$ASSETS_PATH" "${ASSETS_PATH}.pre-image-$(date +%s)"
fi
temporary_directory=$(mktemp -d "${ASSETS_PATH}.link.XXXXXX")
trap 'rm -rf "$temporary_directory"' EXIT
ln -s "$BAKED_PATH" "$temporary_directory/assets"
mv -Tf "$temporary_directory/assets" "$ASSETS_PATH"
rmdir "$temporary_directory"
trap - EXIT
flock -u 7
exec 7>&-

exec "$@"
