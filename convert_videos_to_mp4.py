import os
import subprocess
import sys
import csv

# Check if required arguments are provided
if len(sys.argv) < 3:
    print("Usage: python script.py /path/to/directory/containing/video/dirs /path/to/media/tracking.csv")
    sys.exit(1)

base_dir = sys.argv[1]
csv_file_path = sys.argv[2]

# Check if base directory exists
if not os.path.isdir(base_dir):
    print(f"Error: {base_dir} is not a valid directory")
    sys.exit(1)

# Check if CSV file exists
if not os.path.isfile(csv_file_path):
    print(f"Error: {csv_file_path} is not a valid file")
    sys.exit(1)

# Read CSV file
csv_data = []
try:
    with open(csv_file_path, 'r', newline='') as csvfile:
        reader = csv.DictReader(csvfile, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        csv_data = list(reader)
    print(f"Successfully loaded CSV file with {len(csv_data)} entries")
except Exception as e:
    print(f"Error reading CSV file: {e}")
    sys.exit(1)

# Helper function to write current data to CSV
def write_csv_data():
    try:
        with open(csv_file_path, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=csv_data[0].keys(), delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            writer.writeheader()
            writer.writerows(csv_data)
        print(f"CSV file updated successfully at {csv_file_path}")
        return True
    except Exception as e:
        print(f"Error updating CSV file: {e}")
        return False

# Find DVD directories that need processing
dirs_to_process = []
invalid_dirs = []

for idx, row in enumerate(csv_data):
    identifier = row['Identifier']
    
    # Skip if already processed
    if row['Finished']:
        continue

    finished = str(row['Finished']).strip().upper()
    
    # Find the DVD directory based on identifier
    video_dir = os.path.join(base_dir, identifier)
    
    if not os.path.isdir(video_dir):
        print(f"Warning: Directory not found for {identifier} at {video_dir}")
        continue
    
    # Check if it has any video files
    has_video_files = False
    valid_video_extensions = ('.mpg', '.m4v', '.mov', '.mp4')
    
    # Walk through the directory and its subdirectories
    for root, _, files in os.walk(video_dir):
        for file in files:
            if file.lower().endswith(valid_video_extensions):
                has_video_files = True
                break
        if has_video_files:
            break
            
    if not has_video_files:
        invalid_dirs.append((identifier, video_dir))
    else:
        dirs_to_process.append((identifier, video_dir, idx))

# Report on invalid directories
if invalid_dirs:
    print("\nThe following video directories are invalid (no video files found):")
    for identifier, path in invalid_dirs:
        print(f"- {identifier}: {path}")

if not dirs_to_process:
    print("\nNo valid video directories to process.")
    sys.exit(0)

# Ask for confirmation
print(f"\nFound {len(dirs_to_process)} valid video directories to process.")
proceed = input("Do you want to proceed with the conversion? (y/n): ").strip().lower()
if proceed != 'y':
    print("Operation cancelled.")
    sys.exit(0)

# Initialize counter for tracking current video directory
total_dirs = len(dirs_to_process)
current_dir_num = 1

for identifier, video_dir, idx in dirs_to_process:
    try:
        # Extract video directory name for filename prefix
        base_name = os.path.basename(video_dir)
        
        print("="*70)
        print(f"Processing video directory {current_dir_num} of {total_dirs}: {identifier} at {video_dir} ...")

        # Count number of video files in the directory
        video_count = 0
        video_files = []
        valid_video_extensions = ('.mpg', '.m4v', '.mov', '.mp4')
        for root, _, files in os.walk(video_dir):
            for file in files:
                if file.lower().endswith(valid_video_extensions):
                    video_count += 1
                    video_files.append(os.path.join(root, file))
            
        print(f"Found {video_count} video files in directory")

        if video_count > 0:
            print(f"Found {video_count} videos in {identifier}")
        else:
            print(f"Error: No video files found in {identifier}")
            csv_data[idx]['Finished'] = 'N'
            csv_data[idx]['Notes'] = "No video files found"
            
            # Write updated data to CSV after this directory
            write_csv_data()
            
            current_dir_num += 1
            continue

        # Convert each video file to MP4
        print(f"Converting {video_count} videos to MP4...")
        success_count = 0
        fail_count = []
        corrupted = False
        
        for video_num, video_file in enumerate(video_files, 1):
            video_corrupted = False
            print(f"Processing title {video_num} of {video_count}...")
            
            # If there's only one title, just use the base DVD name
            if video_count == 1:
                output_file = os.path.join(video_dir, f"{base_name}.mp4")
            else:
                output_file = os.path.join(video_dir, f"{base_name}-Title_{video_num}.mp4")
            
            # Replace the subprocess.run with Popen to get real-time output
            process = subprocess.Popen(
                [
                "HandBrakeCLI", "-i", video_file, "-o", output_file,
                "-e", "x264", "-q", "15", "-f", "mp4", "--pixel-aspect", "yuv420p",
                "-E", "aac", "-B", "200", "-R", "44.1", "--audio-fallback", "aac",
                "--comb-detect", "--deinterlace"
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            # Read output line by line to capture progress
            last_progress = 0
            while True:
                line = process.stdout.readline()
                if not line:
                    break
                
                if not video_corrupted and "libdvdread: CHECK_VALUE failed" in line:
                    corrupted = True
                    video_corrupted = True
                    print(f"Error: Title {video_num} of {identifier} might be corrupt.")

                # Parse progress information
                if "Encoding: task" in line and "%" in line:
                    try:
                        # Extract percentage from the progress line
                        progress_text = line.strip()
                        percent = float(progress_text.split('%')[0].split()[-1])
                        
                        # Only print when progress changes
                        if int(percent) > last_progress:
                            print(f"\rProgress: {int(percent)}%", end="", flush=True)
                            last_progress = int(percent)
                    except (ValueError, IndexError):
                        pass
            
            # Wait for process to complete
            process.wait()
            print()
            
            # Check if conversion was successful
            if process.returncode == 0:
                print(f"Title {video_num} successfully converted to {os.path.basename(output_file)}")
                success_count += 1
            else:
                print(f"Error: Failed to convert title {video_num} of {identifier} to MP4")
                fail_count.append(video_num)

        # Update CSV record
        csv_data[idx]['Number of MP4 Files'] = str(success_count)
        
        if fail_count:
            csv_data[idx]['Finished'] = 'N'
            csv_data[idx]['Notes'] = f"Failed to convert titles: {', '.join(map(str, fail_count))}"
        else:
            csv_data[idx]['Finished'] = 'Y'

        if corrupted:
            if csv_data[idx]['Notes']:
                csv_data[idx]['Notes'] += "; Files might be corrupt"
            else:
                csv_data[idx]['Notes'] = "Files might be corrupt"

        print(f"Completed processing directory: {identifier}. {success_count} of {video_count} titles converted.")
    
    except Exception as e:
        # Log the error and update CSV
        error_message = f"Unexpected error processing directory {identifier}: {str(e)}"
        print(f"ERROR: {error_message}")
        
        # Update CSV to indicate failure
        csv_data[idx]['Finished'] = 'N'
        if csv_data[idx]['Notes']:
            csv_data[idx]['Notes'] += f"; {error_message}"
        else:
            csv_data[idx]['Notes'] = error_message
    finally:
        print("="*70)
        # Write updated data to CSV after each directory is processed
        write_csv_data()
        # Increment current directory counter
        current_dir_num += 1

print("All video directories have been processed!")