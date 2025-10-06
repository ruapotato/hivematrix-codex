"""
HelmLogger - Centralized logging integration for HiveMatrix services

This logger sends logs to the Helm service for centralized viewing and analysis.
It maintains a background thread that batches and sends logs periodically.
"""

import os
import logging
import requests
import threading
import time
import queue
from datetime import datetime
from typing import Optional, Dict, Any
from flask import has_request_context, request, g

class HelmLogHandler(logging.Handler):
    """Custom logging handler that sends logs to Helm via HelmLogger"""

    def __init__(self, helm_logger):
        super().__init__()
        self.helm_logger = helm_logger

    def emit(self, record):
        """Emit a log record to Helm"""
        try:
            # Map Python logging levels to our levels
            level_map = {
                logging.DEBUG: 'DEBUG',
                logging.INFO: 'INFO',
                logging.WARNING: 'WARNING',
                logging.ERROR: 'ERROR',
                logging.CRITICAL: 'CRITICAL'
            }
            level = level_map.get(record.levelno, 'INFO')

            # Format the message
            message = self.format(record)

            # Send to Helm
            self.helm_logger.log(level, message)
        except Exception:
            self.handleError(record)

class HelmLogger:
    """
    A logging handler that sends logs to the Helm service.
    Buffers logs and sends them in batches to reduce network overhead.
    """

    def __init__(self, service_name: str, helm_url: str = None, batch_size: int = 10, flush_interval: int = 5):
        """
        Initialize the Helm logger.

        Args:
            service_name: Name of this service
            helm_url: URL of the Helm service (defaults to HELM_SERVICE_URL env var)
            batch_size: Number of logs to batch before sending
            flush_interval: Seconds between automatic flushes
        """
        self.service_name = service_name
        self.helm_url = helm_url or os.environ.get('HELM_SERVICE_URL', 'http://localhost:5004')
        self.batch_size = batch_size
        self.flush_interval = flush_interval

        self.log_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.token = None

        # Start background thread for sending logs
        self.sender_thread = threading.Thread(target=self._send_loop, daemon=True)
        self.sender_thread.start()

    def _get_service_token(self) -> Optional[str]:
        """Get a service token from Core for authenticating with Helm"""
        if self.token:
            return self.token

        core_url = os.environ.get('CORE_SERVICE_URL', 'http://localhost:5000')
        try:
            response = requests.post(
                f"{core_url}/service-token",
                json={
                    "calling_service": self.service_name,
                    "target_service": "helm"
                },
                timeout=5
            )
            if response.status_code == 200:
                self.token = response.json().get('token')
                return self.token
        except Exception as e:
            logging.error(f"Failed to get service token: {e}")
        return None

    def _send_batch(self, logs: list):
        """Send a batch of logs to Helm"""
        if not logs:
            return

        token = self._get_service_token()
        if not token:
            logging.error("No service token available, cannot send logs to Helm")
            return

        try:
            response = requests.post(
                f"{self.helm_url}/api/logs/ingest",
                json={
                    "service_name": self.service_name,
                    "logs": logs
                },
                headers={"Authorization": f"Bearer {token}"},
                timeout=5
            )
            if response.status_code != 200:
                logging.error(f"Failed to send logs to Helm: {response.status_code} {response.text}")
        except Exception as e:
            logging.error(f"Error sending logs to Helm: {e}")

    def _send_loop(self):
        """Background thread that batches and sends logs"""
        batch = []
        last_flush = time.time()

        while not self.stop_event.is_set():
            try:
                # Try to get a log from the queue with timeout
                try:
                    log_entry = self.log_queue.get(timeout=1)
                    batch.append(log_entry)
                except queue.Empty:
                    pass

                # Send batch if it's full or enough time has passed
                now = time.time()
                if len(batch) >= self.batch_size or (batch and now - last_flush >= self.flush_interval):
                    self._send_batch(batch)
                    batch = []
                    last_flush = now

            except Exception as e:
                logging.error(f"Error in log sender thread: {e}")

        # Send any remaining logs before shutting down
        if batch:
            self._send_batch(batch)

    def log(self, level: str, message: str, context: Dict[str, Any] = None):
        """
        Add a log entry to the queue.

        Args:
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            message: Log message
            context: Optional dictionary with additional context
        """
        log_entry = {
            "level": level.upper(),
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
            "context": context or {}
        }

        # Add request context if available
        if has_request_context():
            log_entry["trace_id"] = getattr(g, 'trace_id', None)
            log_entry["user_id"] = getattr(g, 'user', {}).get('sub')
            log_entry["context"]["path"] = request.path
            log_entry["context"]["method"] = request.method

        self.log_queue.put(log_entry)

    def debug(self, message: str, context: Dict[str, Any] = None):
        """Log a DEBUG message"""
        self.log("DEBUG", message, context)

    def info(self, message: str, context: Dict[str, Any] = None):
        """Log an INFO message"""
        self.log("INFO", message, context)

    def warning(self, message: str, context: Dict[str, Any] = None):
        """Log a WARNING message"""
        self.log("WARNING", message, context)

    def error(self, message: str, context: Dict[str, Any] = None):
        """Log an ERROR message"""
        self.log("ERROR", message, context)

    def critical(self, message: str, context: Dict[str, Any] = None):
        """Log a CRITICAL message"""
        self.log("CRITICAL", message, context)

    def shutdown(self):
        """Shutdown the logger and flush remaining logs"""
        self.stop_event.set()
        self.sender_thread.join(timeout=10)


# Global logger instance
_helm_logger: Optional[HelmLogger] = None

def init_helm_logger(service_name: str, helm_url: str = None, capture_flask_logs: bool = True):
    """
    Initialize the global Helm logger

    Args:
        service_name: Name of this service
        helm_url: URL of Helm service
        capture_flask_logs: If True, capture Flask/werkzeug logs and send to Helm
    """
    global _helm_logger
    _helm_logger = HelmLogger(service_name, helm_url)

    # Optionally capture Flask/werkzeug logs
    if capture_flask_logs:
        # Add handler to Flask's app logger
        handler = HelmLogHandler(_helm_logger)
        handler.setLevel(logging.INFO)

        # Capture werkzeug (Flask's HTTP server) logs
        werkzeug_logger = logging.getLogger('werkzeug')
        werkzeug_logger.addHandler(handler)
        werkzeug_logger.setLevel(logging.INFO)

        # Capture Flask app logs
        app_logger = logging.getLogger('flask.app')
        app_logger.addHandler(handler)

    return _helm_logger

def get_helm_logger() -> Optional[HelmLogger]:
    """Get the global Helm logger instance"""
    return _helm_logger
