enum SessionState {
  requested,
  matching,
  pendingAccept,
  active,
  endedTimeout,
  endedSeekerLeft,
  endedVolunteerLeft,
  failedNoVolunteer,
  cancelledBySeeker,
  failedError,
}

SessionState sessionStateFromString(String value) {
  switch (value) {
    case "REQUESTED":
      return SessionState.requested;
    case "MATCHING":
      return SessionState.matching;
    case "PENDING_ACCEPT":
      return SessionState.pendingAccept;
    case "ACTIVE":
      return SessionState.active;
    case "ENDED_TIMEOUT":
      return SessionState.endedTimeout;
    case "ENDED_SEEKER_LEFT":
      return SessionState.endedSeekerLeft;
    case "ENDED_VOLUNTEER_LEFT":
      return SessionState.endedVolunteerLeft;
    case "FAILED_NO_VOLUNTEER":
      return SessionState.failedNoVolunteer;
    case "CANCELLED_BY_SEEKER":
      return SessionState.cancelledBySeeker;
    case "FAILED_ERROR":
      return SessionState.failedError;
    default:
      return SessionState.failedError;
  }
}
