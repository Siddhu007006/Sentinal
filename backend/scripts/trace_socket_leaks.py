"""Instrument socket creation and finalizers to detect unclosed sockets.

Usage:
  python scripts/trace_socket_leaks.py [pytest args...]

The script monkeypatches `socket.socket` to register a finalizer and records
the stack trace where the socket was created if the socket is garbage
collected without being closed. It then runs pytest with the provided args
so the instrumentation is active during tests.
"""
import sys
import os
import traceback
import weakref
import socket as _socket
import time

LOG_PATH = os.path.abspath("socket_leaks.log")


def install_instrumentation():
    orig_init = _socket.socket.__init__
    orig_close = _socket.socket.close

    def patched_init(self, *args, **kwargs):
        # capture the creation stack (omit last frames inside this helper)
        stack = traceback.format_stack()[:-2]

        # register a finalizer that will run when the socket is GC'd
        wr = weakref.ref(self)

        def _on_finalize(wr=wr, stack=stack):
            s = wr()
            # If the object still exists and wasn't marked closed, log it.
            closed_flag = False
            try:
                if s is not None:
                    closed_flag = getattr(s, "_closed_by_instrumentation", False)
            except Exception:
                pass
            if not closed_flag:
                with open(LOG_PATH, "a", encoding="utf8") as f:
                    f.write("==== UN-CLOSED SOCKET FINALIZER ====" + "\n")
                    f.write(f"time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write("creation stack (most recent last):\n")
                    for line in stack:
                        f.write(line)
                    f.write("\n")

        try:
            weakref.finalize(self, _on_finalize)
        except Exception:
            # best-effort; if finalize fails, continue
            pass

        return orig_init(self, *args, **kwargs)

    def patched_close(self, *args, **kwargs):
        try:
            # mark closed so finalizer ignores it
            setattr(self, "_closed_by_instrumentation", True)
        except Exception:
            pass
        return orig_close(self, *args, **kwargs)

    _socket.socket.__init__ = patched_init
    _socket.socket.close = patched_close


def main():
    # Clean previous log
    try:
        if os.path.exists(LOG_PATH):
            os.remove(LOG_PATH)
    except Exception:
        pass

    install_instrumentation()

    # Run pytest with the provided args
    try:
        import pytest

        args = sys.argv[1:]
        if not args:
            # default to full test run if no args provided
            args = []
        ret = pytest.main(args)
        # Print location of log for convenience
        if os.path.exists(LOG_PATH):
            print(f"Socket leak log written to: {LOG_PATH}")
            with open(LOG_PATH, "r", encoding="utf8") as f:
                print(f.read())
        else:
            print("No socket finalizers logged.")
        raise SystemExit(ret)
    except Exception as e:
        print("Failed to run pytest:", e, file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
