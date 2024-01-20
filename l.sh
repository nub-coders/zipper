#!/bin/bash

# Function to submit the job and get the job ID
submit_job() {
    job_id=$(qsub -l nodes=1:gpu:ppn=2,walltime=06:00:00 -d . main.sh)
    echo "Job submitted with ID: $job_id"
}

# Function to check if the job is still in the queue or running
job_is_running() {
    job_status=$(qstat -u $USER | awk -v job_id="$1" '$1 == job_id {print $5}')
    [ "$job_status" == "R" ] || [ "$job_status" == "Q" ]
}

# Submit the initial job

# Continuously monitor the job
while true; do
    if ! job_is_running "$job_id"; then
        echo "Job with ID $job_id has completed."
        # Restart the job
        qdel all
        submit_job
    fi
    sleep 21600  # Adjust the polling interval (in seconds) as needed
done
