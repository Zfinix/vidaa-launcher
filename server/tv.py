import json
import os
import queue
import ssl
import threading
import uuid

import paho.mqtt.client as mqtt

HERE = os.path.dirname(os.path.abspath(__file__))
CERT = os.path.join(HERE, "keys", "rcm_certchain_pem.cer")
KEY = os.path.join(HERE, "keys", "rcm_pem_privkey.pkcs8")

DEFAULT_HOST = os.environ.get("HISENSE_HOST")
DEFAULT_PORT = 36669
HOST_CACHE = os.path.join(HERE, ".host")


def _cached_host():
    try:
        with open(HOST_CACHE) as f:
            return f.read().strip() or None
    except OSError:
        return None


def _remember_host(host):
    try:
        with open(HOST_CACHE, "w") as f:
            f.write(host)
    except OSError:
        pass


def _reachable(host, port, timeout=0.8):
    import socket

    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def resolve_host(port=DEFAULT_PORT):
    """Last paired host first, then SSDP, then the static default."""
    cached = _cached_host()
    if cached and _reachable(cached, port):
        return cached
    try:
        from discover import discover

        found = discover()
    except Exception:
        found = None
    if found and _reachable(found, port):
        return found
    if DEFAULT_HOST and _reachable(DEFAULT_HOST, port):
        return DEFAULT_HOST
    raise OSError("TV not reachable")


class HisenseTV:
    """Minimal VIDAA MQTT remote client (paho-mqtt v2)."""

    def __init__(self, host=None, port=DEFAULT_PORT, timeout=12.0):
        if host is None:
            host = resolve_host(port)
        self.host = host
        self.port = port
        self.timeout = timeout
        self._mac = "XX:XX:XX:XX:XX:XY"
        self._device = f"{self._mac.upper()}$normal"
        self._q = queue.Queue()
        self.connected = threading.Event()
        self.muted = False
        self.volume = None
        self.state = None
        self.apps = None

        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ctx.load_cert_chain(certfile=CERT, keyfile=KEY)
        self._ctx = ctx

        self.client_id = f"HisenseBar/{uuid.uuid4()}"
        self._c = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2, client_id=self.client_id
        )
        self._c.username_pw_set("hisenseservice", "multimqttservice")
        self._c.tls_set_context(self._ctx)
        self._c.on_connect = self._on_connect
        self._c.on_message = self._on_message

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        client.subscribe(f"/remoteapp/mobile/{self._device}/#")
        client.subscribe("/remoteapp/mobile/broadcast/#")
        self.connected.set()

    def _on_message(self, client, userdata, msg):
        payload = msg.payload
        if payload:
            try:
                payload = json.loads(payload.decode("utf-8", "strict"))
            except (ValueError, UnicodeDecodeError):
                payload = msg.payload
        if isinstance(payload, dict):
            if msg.topic.endswith("/volumechange"):
                if payload.get("volume_type") == 2:
                    self.muted = bool(payload.get("volume_value"))
                elif payload.get("volume_type") == 0:
                    self.volume = int(payload.get("volume_value", 0))
            elif msg.topic.endswith("/ui_service/state") and "statetype" in payload:
                self.state = payload
        self._q.put((msg.topic, payload))

    def connect(self):
        self._c.connect(self.host, self.port)
        self._c.loop_start()
        if not self.connected.wait(self.timeout):
            raise TimeoutError("MQTT connect timed out")
        _remember_host(self.host)

    def disconnect(self):
        try:
            self._c.disconnect()
        finally:
            self._c.loop_stop()

    def _drain(self):
        while True:
            try:
                self._q.get_nowait()
            except queue.Empty:
                return

    def _wait(self, match=None):
        import time as _t
        deadline = _t.time() + self.timeout
        while _t.time() < deadline:
            try:
                item = self._q.get(block=True, timeout=max(0.1, deadline - _t.time()))
            except queue.Empty:
                break
            if match is None or match(*item):
                return item
        raise TimeoutError(f"no matching response in {self.timeout:.0f}s")

    def _call(self, service, action, payload=None):
        if isinstance(payload, dict):
            payload = json.dumps(payload)
        topic = f"/remoteapp/tv/{service}/{self._device}/actions/{action}"
        self._c.publish(topic, payload).wait_for_publish()

    def start_authorization(self):
        """Trigger the TV to display the 4-digit pairing code."""
        self._drain()
        self._call("ui_service", "gettvstate")

    def send_authorization_code(self, code):
        self._drain()
        self._call("ui_service", "authenticationcode", {"authNum": str(code)})
        _, payload = self._wait()
        if isinstance(payload, dict) and int(payload.get("result", 0)) == 1:
            return True
        raise RuntimeError(f"authorization failed: {payload}")

    def send_key(self, key):
        self._call("remote_service", "sendkey", key)

    def set_volume(self, volume):
        volume = max(0, min(100, int(volume)))
        self._call("platform_service", "changevolume", str(volume))

    def source_list(self):
        self._drain()
        self._call("ui_service", "sourcelist")
        _, payload = self._wait(match=lambda t, p: isinstance(p, list))
        return payload

    def app_list(self):
        if self.apps is None:
            self._drain()
            self._call("ui_service", "applist")
            _, payload = self._wait(match=lambda t, p: isinstance(p, list))
            self.apps = [a for a in payload if isinstance(a, dict) and a.get("name")]
        return self.apps

    def find_app(self, name):
        want = name.strip().lower()
        apps = self.app_list()
        for a in apps:
            if a["name"].lower() == want:
                return a
        for a in apps:
            if want in a["name"].lower() or a["name"].lower() in want:
                return a
        return None

    def launch_app(self, name):
        app = self.find_app(name)
        if app is None:
            raise LookupError(f"app not installed: {name}")
        payload = {k: app[k] for k in ("appId", "name", "url", "urlType", "storeType") if k in app}
        self._call("ui_service", "launchapp", payload)
        return app

    def change_source(self, payload):
        self._call("ui_service", "changesource", payload)

    def get_volume(self):
        if self.volume is None:
            self._drain()
            self._call("platform_service", "getvolume")
            self._wait(match=lambda t, p: isinstance(p, dict) and p.get("volume_type") == 0)
        return {"volume_value": self.volume, "muted": self.muted}

    def get_state(self):
        if self.state is None:
            self._drain()
            self._call("ui_service", "gettvstate")
            self._wait(match=lambda t, p: isinstance(p, dict) and "statetype" in p)
        return self.state
