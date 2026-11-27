from datetime import datetime, timezone
from collections import deque


class EventLogger:

    def __init__(self, max_events=1000):

        self.events = deque(maxlen=max_events)

    def log_event(self, agent_id, event_type, message):

        event = {
            "agent_id": agent_id,
            "event_type": event_type,
            "message": message,
            "timestamp": datetime.now(timezone.utc)
        }

        self.events.append(event)

        print(
            f"[AGENT EVENT] {event_type} | "
            f"{agent_id} | {message}"
        )

        return event

    def get_events(self, agent_id=None):

        if agent_id:

            return [
                event for event in self.events
                if event["agent_id"] == agent_id
            ]

        return list(self.events)


event_logger = EventLogger()
