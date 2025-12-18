
import network, espnow, time # type: ignore
from communications.protocol import encode, decode
from debug import log
import state

ACK_TIMEOUT_MS = 200
MAX_RETRIES = 3

class EspNowLink:
    def __init__(self, peer):
        self.peer = peer
        self.wlan = network.WLAN(network.STA_IF)
        self.e = espnow.ESPNow()

    def start(self):
        self.wlan.active(True)
        self.e.active(True)
        self.e.add_peer(self.peer)

    def send_cmd(self, payload):
        state.tx_seq += 1
        payload["type"] = "cmd"
        payload["seq"] = state.tx_seq
        self.e.send(self.peer, encode(payload), True)

        state.pending_ack["seq"] = state.tx_seq
        state.pending_ack["timestamp"] = time.ticks_ms()
        state.pending_ack["retries"] = 0

    def poll(self):
        host, msg = self.e.recv(0)
        if msg:
            data = decode(msg)
            if data.get("type") == "ack":
                if data.get("seq") == state.pending_ack["seq"]:
                    log("espnow", "ACK ricevuto")
                    state.pending_ack["seq"] = None

        if state.pending_ack["seq"] is not None:
            if time.ticks_diff(time.ticks_ms(), state.pending_ack["timestamp"]) > ACK_TIMEOUT_MS:
                if state.pending_ack["retries"] < MAX_RETRIES:
                    log("espnow", "Retry comando")
                    state.pending_ack["retries"] += 1
                    state.pending_ack["timestamp"] = time.ticks_ms()
                else:
                    log("espnow", "ACK fallito")
                    state.pending_ack["seq"] = None
