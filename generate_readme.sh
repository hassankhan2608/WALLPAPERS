#!/bin/bash

WALLPAPERS_DIR="Wallpapers"
README_FILE="README.md"

# Function to URL-encode a string
urlencode() {
    local string="$1"
    local strlen=${#string}
    local encoded_string=""
    local pos c o

    for (( pos=0 ; pos<strlen ; pos++ )); do
        c=${string:$pos:1}
        case "$c" in
            [-_.~a-zA-Z0-9] ) o="$c" ;;
            * ) printf -v o '%%%02x' "'$c" ;;
        esac
        encoded_string+="$o"
    done
    echo "$encoded_string"
}

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
    # URL-encode the filename for the Markdown link
    encoded_path=$(urlencode "${WALLPAPERS_DIR}/${relative_path}")
    # Extract name without extension
    wallpaper_name="${relative_path%.*}"
    # Use HTML <img> tag with a fixed width for consistent display
    row_content+="<img src=\"${encoded_path}\" width=\"250\" alt=\"${wallpaper_name}\"><br>${wallpaper_name} | "
    count=$((count + 1))

    if [ "$count" -eq 3 ]; then
      echo "$row_content" >> "$README_FILE"
      echo "| | | |" >> "$README_FILE" # This creates a blank row for separation
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
  echo "| | | |" >> "$README_FILE"
fi

echo "" >> "$README_FILE"
echo "---" >> "$README_FILE"
echo "" >> "$README_FILE"
echo "Generated automatically by a Git pre-commit hook." >> "$README_FILE"
