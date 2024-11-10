import subprocess

# Launch the logging script in detached mode
subprocess.Popen(["python3", "/home/pi/clog_detection_ml/log_data.py"], cwd="/home/pi/clog_detection_ml", close_fds=True)