import os
import json
import psutil
import subprocess
from datetime import datetime, timedelta
import time

# Configuration
CHECK_INTERVAL = 60  # Default check every minute

# Helper function to ensure directory exists
def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

# Function to get the current day/week/month filenames
def get_file_paths(user, tracking_dir):
    now = datetime.now()
    year_path = os.path.join(tracking_dir, user, str(now.year))
    ensure_dir(year_path)

    daily_file = os.path.join(year_path, f"daily.{now.strftime('%Y-%m-%d')}.json")
    weekly_file = os.path.join(year_path, f"weekly.{now.strftime('%Y-%W')}.json")
    monthly_file = os.path.join(year_path, f"monthly.{now.strftime('%Y-%m')}.json")
    yearly_file = os.path.join(year_path, "yearly.json")
    current_daily_file = os.path.join(year_path, "daily.json")
    
    return daily_file, weekly_file, monthly_file, yearly_file, current_daily_file

# Function to calculate usage minutes from start and end time
def calculate_usage_minutes(start, end):
    start_time = datetime.fromisoformat(start)
    end_time = datetime.fromisoformat(end)
    return int((end_time - start_time).total_seconds() // 60)

# Function to check if the current time is within the allowed time range
def is_within_allowed_hours(start_hour, end_hour):
    now = datetime.now().time()
    start_time = datetime.strptime(start_hour, "%H:%M").time()
    end_time = datetime.strptime(end_hour, "%H:%M").time()
    return start_time <= now <= end_time

# Function to read and update JSON log files by PID (for daily.json)
def update_log_by_pid(file_path, process_info):
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            log = json.load(f)
    else:
        log = {}

    pid = process_info['pid']
    process_info['usage_minutes'] = calculate_usage_minutes(process_info['start'], process_info['end'])

    log[pid] = process_info

    with open(file_path, "w") as f:
        json.dump(log, f, indent=4)

# Function to read and update JSON log files by application name (for daily, weekly, monthly)
def update_log_by_app(file_path, app_name, start_time, end_time):
    usage_minutes = calculate_usage_minutes(start_time, end_time)

    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            log = json.load(f)
    else:
        log = {}

    if app_name in log:
        log[app_name]['start'] = min(log[app_name]['start'], start_time)
        log[app_name]['end'] = max(log[app_name]['end'], end_time)
        log[app_name]['usage_minutes'] = calculate_usage_minutes(log[app_name]['start'], log[app_name]['end'])
    else:
        log[app_name] = {
            "start": start_time,
            "end": end_time,
            "usage_minutes": usage_minutes
        }

    with open(file_path, "w") as f:
        json.dump(log, f, indent=4)

# Function to check if the application has reached its usage limit
def is_within_usage_limit(log_file, app_name, allowed_minutes):
    if os.path.exists(log_file):
        with open(log_file, "r") as f:
            log = json.load(f)
            if app_name in log:
                if log[app_name]['usage_minutes'] >= allowed_minutes:
                    return False
    return True

# Function to throttle the application based on CPU percentage
def throttle_application(pid, cpu_percentage):
    if cpu_percentage <= 0:
        print(f"Throttling disabled for PID {pid}")
        return
    elif cpu_percentage >= 100:
        # Kill the process if 100% or more throttling is specified
        print(f"Stopping process with PID {pid}")
        psutil.Process(pid).terminate()
    else:
        print(f"Throttling process {pid} to {cpu_percentage}% CPU usage")
        subprocess.run(["cpulimit", "-p", str(pid), "-l", str(cpu_percentage)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

# Function to track running processes for a specific user based on limits
def track_processes(user, tracking_dir, limits):
    daily_file, weekly_file, monthly_file, yearly_file, current_daily_file = get_file_paths(user, tracking_dir)
    
    for proc in psutil.process_iter(['pid', 'name', 'username', 'create_time', 'ppid']):
        if proc.info['username'] == 'root':  # Exclude root processes
            continue

        try:
            if proc.info['username'] == user:
                start_time = datetime.fromtimestamp(proc.info['create_time'])
                window_name = proc.name()  # You can adjust this if you need a more specific window name
                parent_pid = proc.info['ppid']
                parent_process_name = psutil.Process(parent_pid).name() if parent_pid else None

                app_name = window_name or proc.info['name']
                current_time = datetime.now().isoformat()
                print(f" - recording application {app_name}",flush=True)

                # Check if the app is in the limits and if the current time is within allowed hours
                for limit in limits:
                    if app_name.lower() == limit['application'].lower(): # and is_within_allowed_hours(limit['start_hour'], limit['end_hour']):
                        print(f"    - {app_name} has limits",flush=True)
                        if not is_within_usage_limit(daily_file, app_name, limit['minutes']):
                            print(f"Usage limit reached for {app_name}, throttling process.")
                            # throttle_application(proc.info['pid'], limit['cpu_percentage'])
                            continue  # Skip further tracking for over-limit applications

                        process_info_by_pid = {
                            "pid": proc.info['pid'],
                            "process_name": proc.info['name'],
                            "window_name": window_name,
                            "start": start_time.isoformat(),
                            "end": current_time,
                            "usage_minutes": 0,  # This will be calculated later
                            "parent_pid": parent_pid,
                            "parent_process_name": parent_process_name
                        }

                        # Update daily, weekly, monthly and yearly logs by application name
                        update_log_by_app(daily_file, app_name, start_time.isoformat(), current_time)
                        update_log_by_app(weekly_file, app_name, start_time.isoformat(), current_time)
                        update_log_by_app(monthly_file, app_name, start_time.isoformat(), current_time)
                        update_log_by_app(yearly_file, app_name, start_time.isoformat(), current_time)
                        
                        # Update daily.json log by PID
                        update_log_by_pid(current_daily_file, process_info_by_pid)
        
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

# Main function to run the script every minute
if __name__ == "__main__":
    with open('config.json', 'r') as f:
        config = json.load(f)

    tracking_dir = "/var/tracking/applications"
    check_interval = CHECK_INTERVAL

    # ## while True:
    for user, user_config in config.items():
        limits = user_config.get('limits', [])
        print(f"## Tracking user {user}",flush=True)
        track_processes(user, tracking_dir, limits)
    # ##     time.sleep(check_interval)
