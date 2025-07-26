#!/bin/bash

WALLPAPERS_DIR="Wallpapers"
README_FILE="README.md"

echo "Generating README.md..." >&2
echo "# My Wallpapers" > "$README_FILE"
echo "" >> "$README_FILE"
echo "A collection of my favorite wallpapers." >> "$README_FILE"
echo "" >> "$README_FILE"

echo "| | | |" >> "$README_FILE"
echo "|---|---|---|" >> "$README_FILE"

count=0
row_content=""

for img in "$WALLPAPERS_DIR"/*.{jpg,jpeg,png,gif,webp}; do
  if [ -f "$img" ]; then
    relative_path=$(basename "$img")
    row_content+="![${relative_path%.*}](${WALLPAPERS_DIR}/${relative_path}) | "
    count=$((count + 1))

    if [ "$count" -eq 3 ]; then
      echo "$row_content" >> "$README_FILE"
      row_content=""
      count=0
    fi
  fi
done

# Add any remaining images if they don't fill a full row
if [ "$count" -gt 0 ]; then
  # Pad with empty cells if necessary
  while [ "$count" -lt 3 ]; do
    row_content+=" | "
    count=$((count + 1))
  done
  echo "$row_content" >> "$README_FILE"
fi

echo "" >> "$README_FILE"
echo "---" >> "$README_FILE"
echo "" >> "$README_FILE"
echo "Generated automatically by a Git pre-commit hook." >> "$README_FILE"
