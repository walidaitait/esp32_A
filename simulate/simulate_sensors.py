import random
import state
import config
from timers import elapsed

def simulate_temperature():
    """Genera un valore di temperatura casuale"""
    if not elapsed("temp", config.TEMP_INTERVAL):
        return
    # Temperatura tra 10 e 50 °C
    state.sensor_data["temperature"] = round(random.uniform(10.0, 50.0), 1)

def simulate_co():
    """Genera un valore CO casuale"""
    if not elapsed("co", config.CO_INTERVAL):
        return
    # CO tra 0 e 3000 (ADC-like)
    state.sensor_data["co"] = random.randint(0, 3000)

def simulate_accelerometer():
    """Genera valori accelerometro casuali"""
    if not elapsed("acc", config.ACC_INTERVAL):
        return
    state.sensor_data["acc"]["x"] = random.randint(-1024, 1024)
    state.sensor_data["acc"]["y"] = random.randint(-1024, 1024)
    state.sensor_data["acc"]["z"] = random.randint(-1024, 1024)

def simulate_buttons():
    """Simula lo stato dei tre bottoni"""
    if not elapsed("buttons", config.BUTTON_INTERVAL):
        return
    for key in state.button_state.keys():
        # True = premuto, False = non premuto
        state.button_state[key] = random.choice([True, False])


def simulate_ultrasonic():
    state.ultrasonic_distance_cm = round(random.uniform(5, 200), 2)

def simulate_all():
    """Funzione unica per aggiornare tutti i sensori simulati"""
    simulate_temperature()
    simulate_co()
    simulate_accelerometer()
    simulate_buttons()

