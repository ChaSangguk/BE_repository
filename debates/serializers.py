from datetime import timezone


def utc(value):
    if value is not None:
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return None
