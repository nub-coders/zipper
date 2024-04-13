#!/bin/bash

file_path="zipper/zipper.py"
replacement=$(pwd)

# Get the current directory


# Replace occurrences of /home/u* with $pwd/ in the zipper/zipper.py file

# Get the current directory
current_dir=$(pwd)

# Replace occurrences in zipper.py
sed -i "s|/home/[^/]*/Work|$current_dir|g" zipper/zipper.py
# Replace all occurrences of /home/u209464 with the current directory in the file
# Replace all occurrences of /home/u209464/Work with opt/render in the 
# Define an array of process names and their corresponding commands
python3 -m venv myenv
source myenv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
declare -A processes
processes["zipper.py"]="nohup python3 zipper/zipper.py &"
# Declare an associative array to track process PIDs
declare -A pids


# Monitor and restart processes
while true; do
    for process_name in "${!processes[@]}"; do
        # Get the PID of the process
        pid="${pids[$process_name]}"

        if [[ -z "$pid" ]] || ! kill -0 "$pid" 2>/dev/null; then
            echo "Starting $process_name..."
            eval "${processes[$process_name]}"
            # Store the PID of the newly started process
            pids["$process_name"]="$!"
        fi
    done
    sleep 1
done
