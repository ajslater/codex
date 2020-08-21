"""Watch file trees for changes."""
import logging
import time

from watchdog.events import LoggingEventHandler
from watchdog.observers import Observer


LOG = logging.getLogger(__name__)


def main(path):
    """Watch a path and log the events."""
    # logging.basicConfig(
    #    level=logging.INFO,
    #    format="%(asctime)s - %(message)s",
    #    datefmt="%Y-%m-%d %H:%M:%S",
    # )
    event_handler = LoggingEventHandler()
    observer = Observer()
    observer.schedule(event_handler, path, recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    import sys

    main(sys.argv[1])
