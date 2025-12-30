from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST

sessions_created = Counter("sessions_created_total", "Total sessions created")
sessions_completed = Counter("sessions_completed_total", "Total sessions completed")
sessions_failed_no_volunteer = Counter("sessions_failed_no_volunteer_total", "Sessions failed due to no volunteer")
sessions_cancelled = Counter("sessions_cancelled_total", "Sessions cancelled by seeker")
sessions_ended_seeker_left = Counter("sessions_ended_seeker_left_total", "Sessions ended by seeker leaving")
sessions_ended_volunteer_left = Counter("sessions_ended_volunteer_left_total", "Sessions ended by volunteer leaving")
sessions_failed_error = Counter("sessions_failed_error_total", "Sessions failed due to server error")
moderation_events = Counter("moderation_events_total", "Moderation events", ["type"])
rate_limit_hits = Counter("rate_limit_hits_total", "Rate limit hits", ["path"])
ws_warnings = Counter("ws_warnings_total", "WebSocket warnings", ["code"])
ws_errors = Counter("ws_errors_total", "WebSocket errors", ["code"])

matching_wait_seconds = Histogram("matching_wait_seconds", "Matching wait time seconds")
ws_message_handle_seconds = Histogram("ws_message_handle_seconds", "WebSocket message handle seconds")
queue_depth = Gauge("queue_depth", "Current seeker queue depth")
available_volunteers = Gauge("available_volunteers", "Available volunteer count")


def metrics_response():
    return generate_latest(), CONTENT_TYPE_LATEST
