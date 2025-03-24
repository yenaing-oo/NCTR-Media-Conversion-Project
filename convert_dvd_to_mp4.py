import os
import subprocess
import sys
import csv

# Check if required arguments are provided
if len(sys.argv) < 3:
    print("Usage: python script.py /path/to/directory/containing/DVDs /path/to/media/tracking.csv")
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
dvd_dirs_to_process = []
invalid_dvd_dirs = []

for idx, row in enumerate(csv_data):
    identifier = row['Identifier']
    finished = str(row['Finished']).strip().upper()
    
    # Skip if already processed
    if finished.startswith('Y'):
        continue
    
    # Find the DVD directory based on identifier
    dvd_path = os.path.join(base_dir, identifier)
    
    if not os.path.isdir(dvd_path):
        print(f"Warning: Directory not found for {identifier} at {dvd_path}")
        continue
    
    # Check if it has VIDEO_TS directory
    if not os.path.isdir(os.path.join(dvd_path, 'VIDEO_TS')):
        invalid_dvd_dirs.append((identifier, dvd_path))
    else:
        dvd_dirs_to_process.append((identifier, dvd_path, idx))

# Report on invalid directories
if invalid_dvd_dirs:
    print("\nThe following DVD directories are invalid (no VIDEO_TS directory):")
    for identifier, path in invalid_dvd_dirs:
        print(f"- {identifier}: {path}")

if not dvd_dirs_to_process:
    print("\nNo valid DVD directories to process.")
    sys.exit(0)

# Ask for confirmation
print(f"\nFound {len(dvd_dirs_to_process)} valid DVD directories to process.")
proceed = input("Do you want to proceed with the conversion? (y/n): ").strip().lower()
if proceed != 'y':
    print("Operation cancelled.")
    sys.exit(0)

# Initialize counter for tracking current DVD
total_dvds = len(dvd_dirs_to_process)
current_dvd_num = 1

for identifier, dvd_dir, idx in dvd_dirs_to_process:
    try:
        # Extract DVD directory name for filename prefix
        dvd_name = os.path.basename(dvd_dir)
        
        print("="*70)
        print(f"Processing DVD directory {current_dvd_num} of {total_dvds}: {identifier} at {dvd_dir} ...")

        # Run HandBrakeCLI scan and extract title count
        result = subprocess.run(
            ["HandBrakeCLI", "-i", dvd_dir, "--scan"],
            capture_output=True, text=True
        )

        # Extract title count from scan output
        title_count = None
        for line in result.stderr.splitlines():
            if "scan: DVD has" in line:
                try:
                    title_count = int(line.split()[4])
                except (IndexError, ValueError):
                    pass

        # Check if the title count is found
        if title_count is not None:
            print(f"Found {title_count} titles on DVD: {identifier}")
        else:
            print(f"Error: Could not determine title count for {identifier}. Skipping...")
            # Update CSV data to indicate failure
            csv_data[idx]['Finished'] = 'N'
            csv_data[idx]['Notes'] = 'Failed to determine title count'
            
            # Write updated data to CSV after this DVD
            write_csv_data()
            
            current_dvd_num += 1
            continue

        # Convert each title to MP4
        print(f"Converting {title_count} titles to MP4...")
        successful_titles = 0
        failed_titles = []
        corrupted = False
        
        for title_num in range(1, title_count + 1):
            title_corrupted = False
            print(f"Processing title {title_num} of {title_count}...")
            
            # If there's only one title, just use the base DVD name
            if title_count == 1:
                output_file = os.path.join(dvd_dir, f"{dvd_name}.mp4")
            else:
                output_file = os.path.join(dvd_dir, f"{dvd_name}-Title_{title_num}.mp4")
            
            # Replace the subprocess.run with Popen to get real-time output
            process = subprocess.Popen(
                [
                "HandBrakeCLI", "-i", dvd_dir, "-t", str(title_num), "-o", output_file,
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
                
                if not title_corrupted and "libdvdread: CHECK_VALUE failed" in line:
                    corrupted = True
                    title_corrupted = True
                    print(f"Error: Title {title_num} of {identifier} might be corrupt.")

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
                print(f"Title {title_num} successfully converted to {os.path.basename(output_file)}")
                successful_titles += 1
            else:
                print(f"Error: Failed to convert title {title_num} of {identifier} to MP4")
                failed_titles.append(title_num)

        # Update CSV record
        csv_data[idx]['Number of MP4 Files'] = str(successful_titles)
        
        if failed_titles:
            csv_data[idx]['Finished'] = 'N'
            csv_data[idx]['Notes'] = f"Failed to convert titles: {', '.join(map(str, failed_titles))}"
        else:
            csv_data[idx]['Finished'] = 'Y'

        if corrupted:
            if csv_data[idx]['Notes']:
                csv_data[idx]['Notes'] += "; Files might be corrupt"
            else:
                csv_data[idx]['Notes'] = "Files might be corrupt"

        print(f"Completed processing DVD: {identifier}. {successful_titles} of {title_count} titles converted.")
    
    except Exception as e:
        # Log the error and update CSV
        error_message = f"Unexpected error processing DVD {identifier}: {str(e)}"
        print(f"ERROR: {error_message}")
        
        # Update CSV to indicate failure
        csv_data[idx]['Finished'] = 'N'
        if csv_data[idx]['Notes']:
            csv_data[idx]['Notes'] += f"; {error_message}"
        else:
            csv_data[idx]['Notes'] = error_message
    finally:
        print("="*70)
        # Write updated data to CSV after each DVD is processed
        write_csv_data()
        # Increment current DVD counter
        current_dvd_num += 1

print("All DVDs have been processed!")