import time


def log(name, message):
    """Simple logging function for test firmware"""
    timestamp = time.ticks_ms()
    print("[{}ms] [{}] {}".format(timestamp, name, message))
