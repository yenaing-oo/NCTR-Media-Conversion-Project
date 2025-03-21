import os
import subprocess
import sys

# Check if base DVD directory argument is provided
if len(sys.argv) < 2:
    print("Usage: python script.py /path/to/directory/containing/DVDs")
    sys.exit(1)

base_dir = sys.argv[1]

# Check if base directory exists
if not os.path.isdir(base_dir):
    print(f"Error: {base_dir} is not a valid directory")
    sys.exit(1)

# Find all directories containing VIDEO_TS
print(f"Searching for DVD directories in {base_dir}...")
dvd_dirs = []

for dirpath, dirnames, filenames in os.walk(base_dir):
    if 'VIDEO_TS' in dirnames:
        dvd_dirs.append(dirpath)

total_dvds = len(dvd_dirs)

# Check if any DVD directories were found
if total_dvds == 0:
    print(f"No DVD directories (containing VIDEO_TS) found in {base_dir}")
    sys.exit(1)

print(f"Found {total_dvds} DVD directories to process\n")

# Initialize counter for tracking current DVD
current_dvd_num = 1

for dvd_dir in dvd_dirs:
    # Extract DVD directory name for filename prefix
    dvd_name = os.path.basename(dvd_dir)
    
    print("="*70)
    print(f"Processing DVD directory {current_dvd_num} of {total_dvds}: {dvd_dir} ...")

    # Run HandBrakeCLI scan and extract title count
    result = subprocess.run(
        ["HandBrakeCLI", "-i", dvd_dir, "--scan"],
        capture_output=True, text=True
    )

    # Extract title count from scan output
    title_count = None
    for line in result.stderr.splitlines():
        if "scan: DVD has" in line:
            print(line.split())
            title_count = int(line.split()[4])

    # Check if the title count is found
    if title_count is not None:
        print(f"Found {title_count} titles on DVD: {dvd_name}")
    else:
        print(f"Error: Could not determine title count for {dvd_name}. Skipping...")
        continue

    # Convert each title to MP4
    print(f"Converting {title_count} titles to MP4...")
    for title_num in range(1, title_count + 1):
        print(f"Processing title {title_num} of {title_count}...")
        
        # If there's only one title, just use the base DVD name
        if title_count == 1:
            output_file = os.path.join(dvd_dir, f"{dvd_name}.mp4")
        else:
            output_file = os.path.join(dvd_dir, f"{dvd_name}-Title_{title_num}.mp4")
        
        result = subprocess.run(
            [
                "HandBrakeCLI", "-i", dvd_dir, "-t", str(title_num), "-o", output_file,
                "-e", "x264", "-f", "mp4", "--pixel-aspect", "yuv420p",
                "-E", "aac", "-R", "44.1", "--audio-fallback", "aac"
            ],
            capture_output=True, text=True
        )
        
        # Check if conversion was successful
        if result.returncode == 0:
            print(f"Title {title_num} successfully converted to {os.path.basename(output_file)}")
        else:
            print(f"Error: Failed to convert title {title_num} of {dvd_name} to MP4")

    print(f"Completed processing DVD: {dvd_name}. Files saved to {dvd_dir}")
    print("="*70)

    # Increment current DVD counter
    current_dvd_num += 1

print("All DVDs have been processed!")
