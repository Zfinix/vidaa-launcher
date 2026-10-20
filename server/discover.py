import socket
import time


def discover(timeout=3.0):
    """Return the IP of the first Hisense VIDAA TV found via SSDP, or None."""
    msg = "\r\n".join(
        [
            "M-SEARCH * HTTP/1.1",
            "HOST:239.255.255.250:1900",
            'MAN:"ssdp:discover"',
            "MX:2",
            "ST:ssdp:all",
            "",
            "",
        ]
    ).encode()
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.settimeout(timeout)
    try:
        s.sendto(msg, ("239.255.255.250", 1900))
        end = time.time() + timeout
        while time.time() < end:
            try:
                data, addr = s.recvfrom(2048)
            except socket.timeout:
                break
            text = data.decode("utf-8", "ignore").lower()
            if "his/1.0" in text or "vidaa" in text:
                return addr[0]
    finally:
        s.close()
    return None


if __name__ == "__main__":
    print(discover())
