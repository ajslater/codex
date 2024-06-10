"""Browser session view."""

from codex.serializers.browser.settings import BrowserSettingsSerializer
from codex.views.const import GROUP_ORDER
from codex.views.settings import SettingsView


class BrowserSettingsView(SettingsView):
    """Get Browser Settings."""

    # Put Browser Settings is normally done through BrowserView.get()
    serializer_class = BrowserSettingsSerializer  # type: ignore

    SESSION_KEY = SettingsView.BROWSER_SESSION_KEY

    def validate_settings_get(self, validated_data, params):
        """Change bad settings."""
        top_group = params["top_group"]
        group = validated_data.get("group", "r") if validated_data else "r"

        if group != top_group:
            if group in ("f", "a"):
                params["top_group"] = group
            else:
                show = params["show"]
                if not show[top_group] or (
                    group != "r"
                    and GROUP_ORDER.index(top_group) > GROUP_ORDER.index(group)
                ):
                    for show_group, on in show.items():
                        if on:
                            params["top_group"] = show_group
                            break
                    else:
                        params["top_group"] = "c"
        return params
