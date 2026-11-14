"""
Uvicorn configuration for production deployment
"""
import multiprocessing
import os

# Server Socket Configuration
bind = "0.0.0.0:7001"
backlog = 2048

# Worker Processes
workers = int(os.getenv("UVICORN_WORKERS", min(multiprocessing.cpu_count(), 4)))
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50
timeout = 60
graceful_timeout = 30
keepalive = 5

# Logging
accesslog = "../logs/access.log"
errorlog = "../logs/error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process Naming
proc_name = 'ioflow-backend'

# Server Mechanics
daemon = False
pidfile = None
user = None
group = None
tmp_upload_dir = None

# SSL/TLS (uncomment if needed)
# keyfile = None
# certfile = None
# ssl_version = "TLSv1_2"
# cert_reqs = None
# ca_certs = None
# suppress_ragged_eofs = True
# do_handshake_on_connect = False
# ciphers = None

def when_ready(server):
    """Called just after the server is started."""
    server.log.info(f"IOFlow server is ready. Listening with {workers} workers.")

def worker_int(worker):
    """Called just after a worker exited on SIGINT or SIGQUIT."""
    worker.log.info("Worker interrupted")

def pre_request(worker, req):
    """Called just before a worker processes the request."""
    worker.log.debug(f"{req.method} {req.path}")

def post_request(worker, req, environ, resp):
    """Called after a worker processes the request."""
    worker.log.debug(f"{req.method} {req.path} - {resp.status}")

def child_exit(server, worker):
    """Called just after a worker has been exited."""
    server.log.info(f"Worker {worker.pid} exited")

def worker_abort(worker):
    """Called when a worker is aborted."""
    worker.log.warning(f"Worker {worker.pid} aborted!")

def pre_exec(server):
    """Called just before a new master process is forked."""
    server.log.info("Forking new master process...")

def on_starting(server):
    """Called just before the master process is started."""
    server.log.info("IOFlow backend starting...")

def on_reload(server):
    """Called on reload."""
    server.log.info("IOFlow backend reloading...")