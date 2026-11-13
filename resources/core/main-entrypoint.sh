#!/bin/bash
set -e

umask 0002

ASSETS_PATH="/home/frappe/frappe-bench/sites/assets"
BAKED_PATH="/home/frappe/frappe-bench/assets"

echo "Linking fresh assets to volume..."
mkdir -p "$(dirname "$ASSETS_PATH")"
if [ -d "$ASSETS_PATH" ] && [ ! -L "$ASSETS_PATH" ]; then
  mv "$ASSETS_PATH" "${ASSETS_PATH}.pre-image-$(date +%s)"
fi
temporary_link="${ASSETS_PATH}.link.$$"
ln -s "$BAKED_PATH" "$temporary_link"
mv -Tf "$temporary_link" "$ASSETS_PATH"

exec "$@"
