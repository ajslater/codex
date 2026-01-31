"""OPDS Get User Agent."""

from rest_framework.request import Request


def get_user_agent_name(request: Request) -> str:
    """Parse User Agent Name from Request."""
    if (user_agent := request.headers.get("User-Agent")) and (
        user_agent_parts := user_agent.split("/", 1)
    ):
        user_agent_name = user_agent_parts[0]
    else:
        user_agent_name = ""
    return user_agent_name
