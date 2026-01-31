"""Standalone script to reset servo to 0 degrees.

Usage: Upload and run this script directly on ESP32-B to reset servo position.
"""

from machine import Pin, PWM  # type: ignore
from time import sleep  # type: ignore

# Servo configuration (from config.json)
SERVO_PIN = 23
SERVO_MAX_ANGLE = 180

# PWM parameters for SG90 servo
PWM_FREQ = 50
MIN_US = 500
MAX_US = 2500
PERIOD_US = 1000000 // PWM_FREQ
MAX_DUTY = 1023


def angle_to_duty(angle):
    """Convert angle (0-180) to PWM duty cycle."""
    angle = max(0, min(SERVO_MAX_ANGLE, angle))
    pulse_us = MIN_US + ((MAX_US - MIN_US) * angle) // 180
    duty_10bit = (MAX_DUTY * pulse_us) // PERIOD_US
    # Convert to 16-bit for duty_u16()
    duty_16bit = duty_10bit * 64
    return duty_16bit


def reset_servo():
    """Reset servo to 0 degrees."""
    print("[reset_servo] Initializing servo on pin {}".format(SERVO_PIN))
    
    # Initialize PWM
    pwm = PWM(Pin(SERVO_PIN))
    pwm.freq(PWM_FREQ)
    
    print("[reset_servo] Setting servo to 0 degrees")
    duty = angle_to_duty(0)
    pwm.duty_u16(duty)
    
    # Hold position for 1 second to ensure servo reaches position
    sleep(1)
    
    print("[reset_servo] Servo reset complete")
    print("[reset_servo] You can now disconnect power or run main firmware")
    
    # Optional: deinit PWM to release pin
    # pwm.deinit()


if __name__ == "__main__":
    reset_servo()
