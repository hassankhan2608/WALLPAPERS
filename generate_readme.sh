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

# Table header for Name | Image | Download
echo "| Name | Image | Download |" >> "$README_FILE"
echo "|:---|:---:|---:|" >> "$README_FILE" # Left-align name, center-align image, right-align download

for img in "$WALLPAPERS_DIR"/*.{jpg,jpeg,png,gif,webp}; do
  if [ -f "$img" ]; then
    relative_path=$(basename "$img")
    # URL-encode the filename for the Markdown link
    encoded_path=$(urlencode "${WALLPAPERS_DIR}/${relative_path}")
    # Extract name without extension
    wallpaper_name="${relative_path%.*}"

    # Truncate long wallpaper names for display
    if [ ${#wallpaper_name} -gt 25 ]; then
      display_name="${wallpaper_name:0:22}..."
    else
      display_name="${wallpaper_name}"
    fi

    # Generate the table row content
    echo "| ${display_name} | <img src=\"${encoded_path}\" width=\"250\" alt=\"${wallpaper_name}\"> | <a href=\"${encoded_path}\" download=\"${relative_path}\">⬇️ Download</a> |" >> "$README_FILE"
  fi
done

echo "" >> "$README_FILE"
echo "---" >> "$README_FILE"
echo "" >> "$README_FILE"
echo "Generated automatically by a Git pre-commit hook." >> "$README_FILE"
