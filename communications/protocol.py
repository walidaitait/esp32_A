import ujson #type: ignore

def encode(data: dict) -> bytes:
    return ujson.dumps(data).encode("utf-8")

def decode(payload: bytes) -> dict:
    return ujson.loads(payload.decode("utf-8"))
