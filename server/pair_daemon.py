import json
import os
import time

from tv import HisenseTV

HERE = os.path.dirname(os.path.abspath(__file__))
CODE_FILE = os.path.join(HERE, ".paircode")
RESULT_FILE = os.path.join(HERE, ".pairresult")


def log(msg):
    print(f"[pair] {msg}", flush=True)


def main():
    for f in (CODE_FILE, RESULT_FILE):
        if os.path.exists(f):
            os.remove(f)

    tv = HisenseTV()
    log(f"connecting to {tv.host}:{tv.port} ...")
    tv.connect()
    log("connected over TLS, MQTT session up")

    tv.start_authorization()
    log("sent gettvstate -> TV should now show a 4-digit code on screen")
    log(f"waiting for code in {CODE_FILE} (up to 180s) ...")

    deadline = time.time() + 180
    code = None
    while time.time() < deadline:
        if os.path.exists(CODE_FILE):
            code = open(CODE_FILE).read().strip()
            if code:
                break
        time.sleep(1)

    if not code:
        log("timed out waiting for code")
        json.dump({"ok": False, "error": "timeout"}, open(RESULT_FILE, "w"))
        tv.disconnect()
        return

    log(f"got code {code!r}, sending to TV ...")
    try:
        tv.send_authorization_code(code)
        log("PAIRED: TV accepted the code")
        json.dump({"ok": True}, open(RESULT_FILE, "w"))
    except Exception as e:
        log(f"FAILED: {e}")
        json.dump({"ok": False, "error": str(e)}, open(RESULT_FILE, "w"))
    finally:
        tv.disconnect()


if __name__ == "__main__":
    main()
