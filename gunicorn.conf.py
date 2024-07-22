# gunicorn.conf.py

bind = "0.0.0.0:8000"  # Bind to all interfaces on port 8000
workers = 4  # Number of worker processes
worker_class = "gthread"  # Use threaded workers (for Flask, Django)
accesslog = "-"  # Disable access log
errorlog = "-"  # Disable error log
loglevel = "info"  # Set logging level (optional)
