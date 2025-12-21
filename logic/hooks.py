from debug import log

# Hook functions for future extensibility. These are called only on events of interest
# (alarm transitions, movement changes, button edges) to avoid log spam.


def on_button_triggered(button_name: str) -> None:
    log("hooks", f"Button pressed: {button_name}")


def on_button_released(button_name: str) -> None:
    log("hooks", f"Button released: {button_name}")


def on_alarm_change(kind: str, active: bool, value) -> None:
    status = "ALARM_ON" if active else "ALARM_OFF"
    log("hooks", f"{status} [{kind}] value={value}")


def on_movement_change(active: bool, acc_vector) -> None:
    status = "MOTION" if active else "NO_MOTION"
    log("hooks", f"{status} acc={acc_vector}")
