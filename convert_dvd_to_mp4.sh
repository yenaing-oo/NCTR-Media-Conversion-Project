#!/bin/bash

# Check if base DVD directory argument is provided
if [ $# -lt 1 ]; then
  echo "Usage: $0 /path/to/directory/containing/DVDs"
  exit 1
fi

base_dir="$1"

# Check if base directory exists
if [ ! -d "$base_dir" ]; then
  echo "Error: $base_dir is not a valid directory"
  exit 1
fi

# Find all directories containing VIDEO_TS
echo "Searching for DVD directories in $base_dir..."
dvd_dirs=()

for dir in "$base_dir"/*; do
  if [ -d "$dir" ] && [ -d "$dir/VIDEO_TS" ]; then
    dvd_dirs+=("$dir")
  fi
done

total_dvds=${#dvd_dirs[@]}

# Check if any DVD directories were found
if [ $total_dvds -eq 0 ]; then
  echo "No DVD directories (containing VIDEO_TS) found in $base_dir"
  exit 1
fi

echo -e "Found $total_dvds DVD directories to process\n\n"

# Initialize counter for tracking current DVD
current_dvd_num=1

for dvd_dir in "${dvd_dirs[@]}"; do
  # Extract DVD directory name for filename prefix
  dvd_name=$(basename "$dvd_dir")
  
  echo "======================================================================="
  echo "Processing DVD directory $current_dvd_num of $total_dvds: $dvd_dir ..."

  # Run HandBrakeCLI scan and extract title count
  title_count=$(HandBrakeCLI -i "$dvd_dir" --scan 2>&1 | grep "scan: DVD has" | sed -E 's/.*has ([0-9]+) title.*/\1/')

  # Check if the title count is found
  if [ -n "$title_count" ]; then
    echo "Found $title_count titles on DVD: $dvd_name"
  else
    echo "Error: Could not determine title count for $dvd_name. Skipping..."
    continue
  fi

  # Convert each title to MP4
  echo "Converting $title_count titles to MP4..."
  for ((title_num=1; title_num<=$title_count; title_num++)); do
    echo "Processing title $title_num of $title_count..."
    
    # If there's only one title, just use the base DVD name
    if [ "$title_count" -eq 1 ]; then
      output_file="$dvd_dir/$dvd_name.mp4"
    else
      output_file="$dvd_dir/${dvd_name}-Title_${title_num}.mp4"
    fi
    
    HandBrakeCLI -i "$dvd_dir" -t $title_num -o "$output_file" \
      -e x264 -f mp4 --pixel-aspect yuv420p \
      -E aac -R 44.1 --audio-fallback aac
    
    # Check if conversion was successful
    if [ $? -eq 0 ]; then
      echo "Title $title_num successfully converted to $(basename "$output_file")"
    else
      echo "Error: Failed to convert title $title_num of $dvd_name to MP4"
    fi
  done

  echo "Completed processing DVD: $dvd_name. Files saved to $dvd_dir"
  echo "======================================================================="

  # Increment current DVD counter
  ((current_dvd_num++))
done

echo "All DVDs have been processed!"