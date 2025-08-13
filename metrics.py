from prometheus_client import Counter, Gauge, Histogram

# Histogram for measuring the end-to-end latency of posting events
posting_latency_seconds = Histogram(
    "posting_latency_seconds",
    "End-to-end posting latency in seconds",
)

# Gauge representing the number of events pending in the posting queue
posting_queue_depth = Gauge(
    "posting_queue_depth",
    "Number of events waiting to be processed",
)

# Counter tracking the number of send errors that occurred
posting_send_errors_total = Counter(
    "posting_send_errors_total",
    "Total count of errors while sending postings",
)
