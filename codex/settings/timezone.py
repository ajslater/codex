"""Timezone settings functions."""

from tzlocal import get_localzone_name


def get_time_zone(tz):
    """Get the timezone from the tz."""
    if tz and not tz.startswith(":") and "etc/localtime" not in tz and "/" in tz:
        time_zone = tz
    elif get_localzone_name():
        time_zone = get_localzone_name()
    else:
        time_zone = "Etc/UTC"
    return time_zone
