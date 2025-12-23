"""
TEST FIRMWARE - Attuatori (ESP32-B)
Ambiente di test modulare e non-bloccante per:
  - Moduli LED DFRobot (DFR0021-G/B/R)
  - Servo SG90 9g
  - LCD 1602A con backpack I2C
  - Passive buzzer Sunfounder
  - DFPlayer Mini + speaker 4Ω 3W
"""

# Import OTA first and check for updates BEFORE importing anything else
import ota_update
ota_update.check_and_update()

import time
from debug import log
import config, state

# Moduli attuatori
from actuators import leds, servo, lcd, buzzer, audio

PRINT_INTERVAL_MS = 3000
_last_print = 0


def init_actuators():
    """Inizializza tutti gli attuatori gestendo i fallimenti in modo "soft"."""
    print("\n" + "=" * 60)
    print("ESP32-B ACTUATOR TEST FIRMWARE")
    print("=" * 60)

    status = {}

    if config.LED_TEST_ENABLED:
        status["LED modules"] = leds.init_leds()
    else:
        status["LED modules"] = False

    if config.SERVO_TEST_ENABLED:
        status["Servo"] = servo.init_servo()
    else:
        status["Servo"] = False

    if config.LCD_TEST_ENABLED:
        status["LCD 16x2"] = lcd.init_lcd()
    else:
        status["LCD 16x2"] = False

    if config.BUZZER_TEST_ENABLED:
        status["Buzzer"] = buzzer.init_buzzer()
    else:
        status["Buzzer"] = False

    if config.AUDIO_TEST_ENABLED:
        status["DFPlayer"] = audio.init_audio()
    else:
        status["DFPlayer"] = False

    print("\n" + "-" * 60)
    print("INITIALIZATION SUMMARY:")
    for name, ok in status.items():
        print("  {:15s}: {}".format(name, "OK" if ok else "DISABLED/FAILED"))
    print("-" * 60 + "\n")


def update_actuators():
    """Aggiorna tutti i moduli di test (logica non bloccante)."""
    if config.LED_TEST_ENABLED:
        leds.update_led_test()
    if config.SERVO_TEST_ENABLED:
        servo.update_servo_test()
    if config.LCD_TEST_ENABLED:
        lcd.update_lcd_test()
    if config.BUZZER_TEST_ENABLED:
        buzzer.update_buzzer_test()
    if config.AUDIO_TEST_ENABLED:
        audio.update_audio_test()


def print_status():
    global _last_print
    now = time.ticks_ms()
    if time.ticks_diff(now, _last_print) < PRINT_INTERVAL_MS:
        return
    _last_print = now

    a = state.actuator_state

    print("\n" + "=" * 60)
    print("ACTUATOR STATE @ {} ms".format(now))
    print("=" * 60)

    leds_state = a["leds"]
    print(
        "LEDs:   G={}  B={}  R={}".format(
            "ON" if leds_state["green"] else "off",
            "ON" if leds_state["blue"] else "off",
            "ON" if leds_state["red"] else "off",
        )
    )

    servo_state = a["servo"]
    print("Servo:  angle={}  moving={}".format(servo_state["angle"], servo_state["moving"]))

    lcd_state = a["lcd"]
    print("LCD:    '{}' / '{}'".format(lcd_state["line1"], lcd_state["line2"]))

    buz_state = a["buzzer"]
    print("Buzzer: active={}".format(buz_state["active"]))

    aud_state = a["audio"]
    print(
        "Audio:  playing={}  last_cmd={}".format(
            aud_state["playing"], aud_state["last_cmd"]
        )
    )

    print("=" * 60 + "\n")


def main():
    print("\n" + "#" * 60)
    print("#  ESP32-B TEST FIRMWARE - ATTUATORS ONLY")
    print("#  Modules: LED, Servo, LCD, Buzzer, DFPlayer")
    print("#  All logic is non-blocking; modules can be disabled in config.py")
    print("#" * 60 + "\n")

    init_actuators()

    print("Starting main loop...\n")

    while True:
        try:
            update_actuators()
            print_status()
            time.sleep_ms(10)
        except KeyboardInterrupt:
            print("\nTest firmware stopped by user.")
            break
        except Exception as e:
            log("main", "ERROR in main loop: {}".format(e))
            time.sleep(1)


if __name__ == "__main__":
    main()
