import ntptime #type: ignore
import time

TIMEZONE_OFFSET = 1 * 3600   # Italy = UTC+1 (no DST)

def sync_time():
    try:
        ntptime.settime()  # set UTC
        time.sleep(0.2)
        return True
    except Exception as e:
        return False

def get_datetime_string():
    t = time.localtime(time.time() + TIMEZONE_OFFSET)
    return "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
        t[0], t[1], t[2], t[3], t[4], t[5]
    )
