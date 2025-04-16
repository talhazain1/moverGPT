"""
monitoring.py

Integrates Prometheus metrics for monitoring application performance.
It defines counters and histograms to track request counts and latencies,
and provides helper functions to record these metrics and expose them via a Flask endpoint.
"""

import time
import logging
from flask import Response
from prometheus_client import Counter, Histogram, generate_latest

# Set up basic logging for monitoring events.
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Prometheus metric definitions
REQUEST_COUNT = Counter(
    'flask_request_count',
    'Application Request Count',
    ['method', 'endpoint', 'http_status']
)
REQUEST_LATENCY = Histogram(
    'flask_request_latency_seconds',
    'Request latency in seconds',
    ['endpoint'],
    buckets=[0.01, 0.05, 0.1, 0.2, 0.5, 1, 2, 5]
)

def record_request_data(request, response):
    """
    Record metrics for an incoming request and its response.
    """
    try:
        REQUEST_COUNT.labels(
            request.method, request.path, response.status_code
        ).inc()
    except Exception as e:
        logger.error(f"Error recording request count: {e}")
    return response

def start_timer():
    """
    Start a timer to measure request duration.
    """
    return time.time()

def stop_timer(start_time, endpoint):
    """
    Stop the timer and record the elapsed time in a histogram metric.
    """
    elapsed = time.time() - start_time
    try:
        REQUEST_LATENCY.labels(endpoint).observe(elapsed)
        # Debug print to confirm a latency is recorded
        print(f"DEBUG: Recorded latency {elapsed:.4f} sec for endpoint {endpoint}")
    except Exception as e:
        logger.error(f"Error recording request latency: {e}")
    return elapsed

def metrics_endpoint():
    """
    Expose Prometheus metrics in plain text.
    """
    return Response(generate_latest(), mimetype='text/plain')
