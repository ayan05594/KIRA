"""Gunicorn configuration file for production deployment"""

import multiprocessing
import os

# Server socket
bind = f"0.0.0.0:{os.getenv('PORT', '5001')}"
backlog = 2048

# Worker processes - Optimized for Render Free Tier (512MB RAM)
# Use only 1-2 workers to avoid memory issues on free tier
workers = 2  # Minimal workers for free tier to avoid OOM
worker_class = 'sync'
worker_connections = 100  # Reduced connections to save memory
timeout = 300  # Increased timeout for slow MongoDB connections on free tier
keepalive = 2
graceful_timeout = 120  # Give workers time to finish requests before killing them

# Restart workers after this many requests to prevent memory leaks
max_requests = 500  # More frequent restarts for free tier
max_requests_jitter = 50

# Logging
accesslog = '-'
errorlog = '-'
loglevel = 'info'
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Process naming
proc_name = 'kira-chatbot'

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# SSL (if needed)
# keyfile = '/path/to/keyfile'
# certfile = '/path/to/certfile'

