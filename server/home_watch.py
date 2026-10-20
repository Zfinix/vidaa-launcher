#!/usr/bin/env python3
"""Open the HisenseBar launcher whenever the TV lands on the VIDAA home screen."""
import os
import queue
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tv import HisenseTV

APP = "HisenseBar"
POLL = 3.0
COOLDOWN = 4.0
OFF_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".home_watch_off")


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def is_home(payload):
    return isinstance(payload, dict) and payload.get("statetype") == "remote_launcher"


def watch(tv):
    last_launch = 0.0
    last_poll = 0.0
    last_seen = time.time()
    while True:
        now = time.time()
        if now - last_poll > POLL:
            last_poll = now
            tv._call("ui_service", "gettvstate")
        try:
            topic, payload = tv._q.get(timeout=0.5)
        except queue.Empty:
            if time.time() - last_seen > 20:
                raise TimeoutError("TV stopped answering")
            continue
        last_seen = time.time()
        if not is_home(payload) or os.path.exists(OFF_FILE):
            continue
        if time.time() - last_launch < COOLDOWN:
            continue
        last_launch = time.time()
        tv.launch_app(APP)
        log("home screen, opened " + APP)


def main():
    while True:
        tv = None
        try:
            tv = HisenseTV(timeout=8.0)
            tv.connect()
            log(f"connected to {tv.host}")
            watch(tv)
        except Exception as e:
            log(f"waiting for TV ({e.__class__.__name__}: {e})")
            time.sleep(10)
        finally:
            if tv is not None:
                try:
                    tv.disconnect()
                except Exception:
                    pass


if __name__ == "__main__":
    main()
