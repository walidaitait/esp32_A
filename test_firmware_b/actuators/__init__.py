"""Actuators package for ESP32-B - Hardware output control modules.

Imported by: core.actuator_loop
Provides: leds, servo, lcd, buzzer, audio, buttons, simulation

Individual actuator drivers:
- leds: DFRobot LED modules (green/blue/red status indicators)
- servo: SG90 servo for automatic gate control
- lcd: LCD 1602A display with I2C backpack
- buzzer: Sunfounder passive buzzer for alarm tones
- audio: DFPlayer Mini MP3 module for voice announcements
- buttons: Physical button input with debouncing
- simulation: Simulated actuators for hardware-less testing

All actuators use non-blocking update patterns via core.timers.elapsed().
"""

from . import leds
from . import servo
from . import lcd
from . import buzzer
from . import audio

__all__ = ['leds', 'servo', 'lcd', 'buzzer', 'audio']
