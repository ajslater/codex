"""Watch file trees for changes."""
import logging

from multiprocessing import Condition
from multiprocessing import Process

from django.utils import timezone

from codex.library.queue import QUEUE
from codex.library.queue import ScanRootTask
from codex.models import RootPath


LOG = logging.getLogger(__name__)
WAIT_INTERVAL = 60 * 5  # Run cron every 5 minutes


def scan_cron(cond):
    """Watch a path and log the events."""
    LOG.info(f"Started scan cron")
    with cond:
        while True:
            root_paths = RootPath.objects.filter(enable_scan_cron=True)
            for root_path in root_paths:
                if root_path.last_scan is not None:
                    since_last_scan = timezone.now() - root_path.last_scan
                if (
                    root_path.last_scan is None
                    or since_last_scan > root_path.scan_frequency
                ):
                    try:
                        task = ScanRootTask(root_path.pk, False)
                        QUEUE.put(task)
                    except Exception as exc:
                        LOG.error(exc)
            cond.wait(timeout=WAIT_INTERVAL)
    LOG.info(f"Stopped scan cron")


def start_scan_cron():
    """Watch all root paths."""
    name = f"scan-cron"
    cond = Condition()
    proc = Process(target=scan_cron, name=name, args=(cond,), daemon=True)
    proc.start()
