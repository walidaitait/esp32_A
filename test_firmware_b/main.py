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

# =============================================================
#  XMAS TEST STATE (servo + buzzer + 3 LED + LCD)
# =============================================================

# Servo: ciclo completo 0° -> 180° -> 0° in 2 secondi
SERVO_CYCLE_MS = 2000
_servo_start_ms = 0

# Melodia semplificata tipo "Jingle Bells" per il buzzer
NOTE_E5 = 659
NOTE_F5 = 698
NOTE_G5 = 784
NOTE_A5 = 880
NOTE_D5 = 587
NOTE_C5 = 523
REST = 0

_MELODY = [
    (NOTE_E5, 200), (NOTE_E5, 200), (NOTE_E5, 400),
    (REST,    200),
    (NOTE_E5, 200), (NOTE_E5, 200), (NOTE_E5, 400),
    (REST,    200),
    (NOTE_E5, 200), (NOTE_G5, 200), (NOTE_C5, 200),
    (NOTE_D5, 200), (NOTE_E5, 600),
    (REST,    200),
    (NOTE_F5, 200), (NOTE_F5, 200), (NOTE_F5, 200), (NOTE_F5, 200),
    (NOTE_F5, 200), (NOTE_E5, 200), (NOTE_E5, 200), (NOTE_E5, 200),
    (NOTE_E5, 200), (NOTE_D5, 200), (NOTE_D5, 200),
    (NOTE_E5, 200), (NOTE_D5, 200), (NOTE_G5, 800),
    (REST,    400),
]

_melody_index = 0
_melody_note_start_ms = 0

# LCD: "Buone feste!" + punti esclamativi che vanno da 1 a 5 e ritorno
_lcd_excl_count = 1
_lcd_excl_dir = 1
_lcd_last_update_ms = 0
LCD_EXCL_INTERVAL_MS = 500


def init_actuators():
    """Inizializza tutti gli attuatori gestendo i fallimenti in modo "soft"."""
    print("\n" + "=" * 60)
    print("ESP32-B ACTUATOR TEST FIRMWARE")
    print("=" * 60)

    status = {}

    # Per il test natalizio vogliamo che tutti gli attuatori principali
    # siano attivi, indipendentemente dai flag di test precedenti.
    status["LED modules"] = leds.init_leds() if config.LED_TEST_ENABLED else leds.init_leds()
    status["Servo"] = servo.init_servo() if config.SERVO_TEST_ENABLED else servo.init_servo()
    status["LCD 16x2"] = lcd.init_lcd() if config.LCD_TEST_ENABLED else lcd.init_lcd()
    status["Buzzer"] = buzzer.init_buzzer() if config.BUZZER_TEST_ENABLED else buzzer.init_buzzer()

    if config.AUDIO_TEST_ENABLED:
        status["DFPlayer"] = audio.init_audio()
    else:
        status["DFPlayer"] = False

    print("\n" + "-" * 60)
    print("INITIALIZATION SUMMARY:")
    for name, ok in status.items():
        print("  {:15s}: {}".format(name, "OK" if ok else "DISABLED/FAILED"))
    print("-" * 60 + "\n")


def _update_servo_xmas(now):
    """Servo: ciclo 0° -> 180° -> 0° in SERVO_CYCLE_MS (non bloccante)."""
    global _servo_start_ms

    cycle = SERVO_CYCLE_MS
    half = cycle // 2

    # Inizializza riferimento temporale al primo ingresso
    if _servo_start_ms == 0:
        _servo_start_ms = now

    phase = time.ticks_diff(now, _servo_start_ms) % cycle

    if phase < half:
        angle = int(180 * phase / half)
    else:
        angle = int(180 * (1 - (phase - half) / half))

    servo.set_servo_angle(angle)
    state.actuator_state["servo"]["moving"] = True
    return angle


def _update_leds_for_melody(step):
    """Associa i 3 LED ai passi della melodia in modo ciclico."""
    idx = step % 3
    if idx == 0:
        leds.set_led_state("green", "on")
        leds.set_led_state("blue", "off")
        leds.set_led_state("red", "off")
    elif idx == 1:
        leds.set_led_state("green", "off")
        leds.set_led_state("blue", "on")
        leds.set_led_state("red", "off")
    else:
        leds.set_led_state("green", "off")
        leds.set_led_state("blue", "off")
        leds.set_led_state("red", "on")


def _update_buzzer_and_leds_xmas(now):
    """Melodia tipo Jingle Bells + LED abbinati (non bloccante)."""
    global _melody_index, _melody_note_start_ms

    if not _MELODY:
        return

    # Primo ingresso: avvia da subito la prima nota
    if _melody_note_start_ms == 0:
        _melody_note_start_ms = now
        freq, _ = _MELODY[_melody_index]
        buzzer.set_tone(freq)
        _update_leds_for_melody(_melody_index)
        return

    freq, duration = _MELODY[_melody_index]

    if time.ticks_diff(now, _melody_note_start_ms) < duration:
        return

    # Passa alla nota successiva
    _melody_index = (_melody_index + 1) % len(_MELODY)
    _melody_note_start_ms = now

    freq, _ = _MELODY[_melody_index]
    buzzer.set_tone(freq)
    _update_leds_for_melody(_melody_index)


def _update_lcd_xmas(now):
    """LCD: "Buone feste" con ! che vanno da 1 a 5 e ritorno (500 ms)."""
    global _lcd_excl_count, _lcd_excl_dir, _lcd_last_update_ms

    if _lcd_last_update_ms == 0:
        _lcd_last_update_ms = now

    if time.ticks_diff(now, _lcd_last_update_ms) < LCD_EXCL_INTERVAL_MS:
        return

    _lcd_last_update_ms = now

    _lcd_excl_count += _lcd_excl_dir
    if _lcd_excl_count >= 5:
        _lcd_excl_count = 5
        _lcd_excl_dir = -1
    elif _lcd_excl_count <= 1:
        _lcd_excl_count = 1
        _lcd_excl_dir = 1

    base = "Buone feste"
    msg = base + "!" * _lcd_excl_count

    lcd.clear()
    lcd.write_line(0, msg)
    lcd.write_line(1, "")

    state.actuator_state["lcd"]["line1"] = msg
    state.actuator_state["lcd"]["line2"] = ""


def update_actuators():
    """Aggiorna SOLO il test natalizio (servo + buzzer + LED + LCD)."""
    now = time.ticks_ms()

    # Servo 0..180..0 ogni 2 secondi
    angle = _update_servo_xmas(now)

    # Melodia natalizia + LED associati
    _update_buzzer_and_leds_xmas(now)

    # LCD "Buone feste" con punti esclamativi dinamici (solo prima riga)
    _update_lcd_xmas(now)


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
