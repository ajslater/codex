import logging

from django.apps import AppConfig
from django.conf import settings

from codex._vendor.haystack import connection_router, connections
from codex._vendor.haystack.utils import loading


class HaystackConfig(AppConfig):
    name = "codex._vendor.haystack"
    signal_processor = None
    stream = None

    def ready(self):
        # Setup default logging.
        log = logging.getLogger("haystack")
        self.stream = logging.StreamHandler()
        self.stream.setLevel(logging.INFO)
        log.addHandler(self.stream)

        # Setup the signal processor.
        if not self.signal_processor:
            signal_processor_path = getattr(
                settings,
                "HAYSTACK_SIGNAL_PROCESSOR",
                "codex._vendor.haystack.signals.BaseSignalProcessor",
            )
            signal_processor_class = loading.import_class(signal_processor_path)
            self.signal_processor = signal_processor_class(
                connections, connection_router
            )
