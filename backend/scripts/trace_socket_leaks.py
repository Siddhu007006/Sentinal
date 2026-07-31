"""Instrument socket creation and finalizers to detect unclosed sockets.

Usage:
  python scripts/trace_socket_leaks.py [pytest args...]

The script monkeypatches `socket.socket` to register a finalizer and records
the stack trace where the socket was created if the socket is garbage
collected without being closed. It then runs pytest with the provided args
so the instrumentation is active during tests.
"""

import contextlib
import logging
import os
import socket as _socket
import sys
import time
import traceback
import weakref


LOG_PATH = os.path.abspath("socket_leaks.log")
logger = logging.getLogger(__name__)


def install_instrumentation() -> None:
    """Install socket instrumentation to detect unclosed sockets."""
    orig_init = _socket.socket.__init__
    orig_close = _socket.socket.close

    def patched_init(self: _socket.socket, *args: object, **kwargs: object) -> None:
        """Patched socket.__init__ that registers finalizer for leak detection."""
        # capture the creation stack (omit last frames inside this helper)
        stack = traceback.format_stack()[:-2]

        # register a finalizer that will run when the socket is GC'd
        wr = weakref.ref(self)

        def _on_finalize(
            wr: weakref.ref[_socket.socket] = wr,
            stack: list[str] = stack,  # type: ignore[assignment]
        ) -> None:
            """Finalizer that logs unclosed sockets."""
            s = wr()
            # If the object still exists and wasn't marked closed, log it.
            closed_flag = False
            with contextlib.suppress(Exception):
                if s is not None:
                    closed_flag = getattr(s, "_closed_by_instrumentation", False)
            if not closed_flag:
                with open(LOG_PATH, "a", encoding="utf8") as f:
                    f.write("==== UN-CLOSED SOCKET FINALIZER ====" + "\n")
                    f.write(f"time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write("creation stack (most recent last):\n")
                    for line in stack:
                        f.write(line)
                    f.write("\n")

        with contextlib.suppress(Exception):
            # best-effort; if finalize fails, continue
            weakref.finalize(self, _on_finalize)

        return orig_init(self, *args, **kwargs)

    def patched_close(self: _socket.socket, *args: object, **kwargs: object) -> None:
        """Patched socket.close that marks socket as closed."""
        with contextlib.suppress(Exception):
            # mark closed so finalizer ignores it
            self._closed_by_instrumentation = True  # type: ignore[attr-defined]
        return orig_close(self, *args, **kwargs)

    _socket.socket.__init__ = patched_init  # type: ignore[method-assign]
    _socket.socket.close = patched_close  # type: ignore[method-assign]


def main() -> None:
    """Run pytest with socket instrumentation enabled."""
    # Clean previous log
    with contextlib.suppress(Exception):
        if os.path.exists(LOG_PATH):
            os.remove(LOG_PATH)

    install_instrumentation()

    # Run pytest with the provided args
    try:
        import pytest

        args = sys.argv[1:]
        if not args:
            # default to full test run if no args provided
            args = []
        ret = pytest.main(args)
        # Log location for convenience
        if os.path.exists(LOG_PATH):
            logger.info(f"Socket leak log written to: {LOG_PATH}")
            with open(LOG_PATH, encoding="utf8") as f:
                logger.info(f.read())
        else:
            logger.info("No socket finalizers logged.")
        raise SystemExit(ret)
    except Exception as e:
        logger.exception("Failed to run pytest: %s", e)
        raise


if __name__ == "__main__":
    main()
