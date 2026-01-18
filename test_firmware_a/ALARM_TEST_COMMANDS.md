# Comandi per Test dei Sistemi di Allarme

Questo documento descrive i comandi UDP disponibili per testare il sistema di allarmi e sensori su ESP32-A.

## Sintassi Generale

```bash
python send_command.py A <command> [args...]
```

---

## 🎯 Comandi di Test Allarmi

### 1. Test Scenario Allarme - WARNING

**Comando**: `test_alarm warning`

Attiva uno scenario di **WARNING** impostando il CO a 60 PPM.

```bash
python send_command.py A test_alarm warning
```

**Cosa succede**:
- CO viene impostato a 60 PPM (superiore al limite critico di 50 PPM)
- Dopo ~5 secondi: ESP32-A passa a stato "warning"
- ESP32-B riceve l'allarme e:
  - 🔴 LED rosso inizia a **lampeggiare** (blinking)
  - 🔊 Buzzer emette il pattern WARNING: `beep-beep (200ms) + pausa (2sec)`
  - 📱 LCD mostra: `Warning / CO`

**Timing**: warning_time_ms = 5000ms configurabile in config.json


### 2. Test Scenario Allarme - DANGER

**Comando**: `test_alarm danger`

Attiva uno scenario di **DANGER** impostando il CO a 120 PPM.

```bash
python send_command.py A test_alarm danger
```

**Cosa succede**:
- CO viene impostato a 120 PPM (ben oltre il limite critico)
- Dopo ~30 secondi: ESP32-A passa a stato "danger"
- ESP32-B riceve l'allarme e:
  - 🔴 LED rosso resta **acceso** (ON continuo)
  - 🔊 Buzzer emette il pattern DANGER: `beep-beep lungo (500ms) + pausa (1sec)`
  - 📱 LCD mostra: `Danger / CO`

**Timing**: danger_time_ms = 30000ms configurabile in config.json


### 3. Reset Allarme

**Comando**: `test_alarm reset`

Resetta tutti i sensori a valori sicuri e cancella gli allarmi.

```bash
python send_command.py A test_alarm reset
```

**Cosa succede**:
- CO → 10 PPM (safe)
- Temperature → 23.5°C (safe)
- Heart Rate → 75 bpm (safe)
- SpO2 → 98% (safe)
- Inizio recovery timer
- Dopo il tempo di recovery configurato, alarm ritorna a "normal"
- 🔴 LED rosso si **spegne**
- 🔊 Buzzer si **ferma**
- 📱 LCD mostra il testo di default

---

## � Comandi di Test Sensori Individuali

Per testare singoli sensori, usa il comando `simulate` che imposta il valore direttamente:

```bash
# CO Sensor
python send_command.py A simulate co 75      # Set a valore specifico
python send_command.py A simulate co 0       # Minimo
python send_command.py A simulate co 200     # Massimo
python send_command.py A simulate co 10      # Normale (safe)
python send_command.py A simulate co auto    # Torna al sensore reale

# Temperature Sensor
python send_command.py A simulate temperature 28.5   # Set a valore specifico
python send_command.py A simulate temperature 5      # Minimo (unsafe)
python send_command.py A simulate temperature 40     # Massimo (unsafe)
python send_command.py A simulate temperature 23.5   # Normale (safe)
python send_command.py A simulate temperature auto   # Torna al sensore reale

# Heart Rate
python send_command.py A simulate heart 95   # Set BPM
python send_command.py A simulate heart 40   # Basso (unsafe)
python send_command.py A simulate heart 140  # Alto (unsafe)
python send_command.py A simulate heart 75   # Normale (safe)
python send_command.py A simulate heart auto # Torna al sensore reale

# SpO2
python send_command.py A simulate spo2 95    # Set percentuale
python send_command.py A simulate spo2 98    # Normale (safe)
python send_command.py A simulate spo2 auto  # Torna al sensore reale
```

---

## 📊 Comandi di Query

### Get Sensor State

**Comando**: `state`

Restituisce lo stato completo di tutti i sensori.

```bash
python send_command.py A state
```

**Output**:
```json
{
  "success": true,
  "message": "Current sensor state",
  "state": {
    "sensors": {
      "temperature": 23.5,
      "co": 10,
      "ultrasonic_distance_cm": 45,
      "heart_rate": {"bpm": 75, "spo2": 98}
    },
    "alarm": {
      "level": "normal",
      "source": null,
      "type": null
    },
    "system": {
      "co_level": "normal",
      "temp_level": "normal",
      "heart_level": "normal"
    }
  }
}
```

---

### Get System Status

**Comando**: `status`

Restituisce status del sistema.

```bash
python send_command.py A status
```

---

## 🧪 Scenari di Test Completi

### Scenario 1: Test Completo del Sistema di Allarme

```bash
# 1. Verificare stato iniziale
python send_command.py A state

# 2. Attivare WARNING
python send_command.py A test_alarm warning
# Aspettare ~5 secondi, osservare:
# - LED rosso lampeggia
# - Buzzer emette beep-beep lento
# - LCD mostra "Warning / CO"

# 3. Aspettare recovery (~15 secondi) o forzare DANGER
python send_command.py A test_alarm danger
# Osservare cambio da WARNING a DANGER:
# - LED rosso passa da blinking a ON continuo
# - Buzzer cambia pattern a beep più lunghi
# - LCD mostra "Danger / CO"

# 4. Reset
python send_command.py A test_alarm reset
# Osservare ritorno a NORMAL
```

### Scenario 2: Test di Singoli Sensori

```bash
# Test CO sensor
python send_command.py A simulate co 60   # warning threshold
python send_command.py A simulate co 150  # danger level
python send_command.py A simulate co 10   # normal

# Test Temperature
python send_command.py A simulate temperature 5   # 5°C - unsafe
python send_command.py A simulate temperature 40  # 40°C - unsafe
python send_command.py A simulate temperature 23.5  # normal

# Test Heart Rate
python send_command.py A simulate heart 40   # 40 bpm - unsafe
python send_command.py A simulate heart 140  # 140 bpm - unsafe
python send_command.py A simulate heart 75   # normal
```

---

## ⏱️ Timing dei Livelli di Allarme

Da `config.json` (ESP32-A):

```json
"alarm_windows_ms": {
  "co_warning": 5000,      // Warning dopo 5 secondi
  "co_danger": 30000,      // Danger dopo 30 secondi
  "co_recovery": 10000,    // Recovery dopo 10 secondi
  "temp_warning": 10000,   // Warning dopo 10 secondi
  "temp_danger": 60000,    // Danger dopo 60 secondi
  "temp_recovery": 15000   // Recovery dopo 15 secondi
}
```

---

## 📝 Log di Traccia

Durante i test, verificare i log per seguire il flusso:

**ESP32-A (Sensori)**:
```
[alarm.logic] alarm.logic: update_alarm_level: [co] normal -> warning
[alarm_logic] update_overall_alarm: normal:none -> warning:co
[communication.espnow] Sent: Alarm=warning:co
```

**ESP32-B (Attuatori)**:
```
[communication.espnow] Alarm received: level=warning, source=co
[actuator.leds] apply_alarm: RED LED BLINKING (warning)
[actuator.buzzer] play_sound: Starting 'warning'
[actuator.lcd] update_alarm_display: LCD 'Warning' / 'CO' (warning)
```

---

## 🔧 Troubleshooting

### L'allarme non cambia stato
- Verificare che `simulate_sensors` sia **true** in `config.json`
- Verificare che la logica dell'allarme sia abilitata (`ALARM_CO_ENABLED: true`)
- Controllare i timings in `config.json` - potrebbero essere troppo lunghi

### Buzzer non suona
- Verificare il GPIO del buzzer (GPIO 25)
- Controllare i log per errori di PWM
- Verificare che il buzzer sia abilitato in config

### LED rosso non cambia
- Verificare GPIO del LED (GPIO 19)
- Controllare che `leds.enabled` sia true

### LCD non mostra allarmi
- Verificare I2C bus (GPIO 21/22)
- Controllare che LCD sia abilitato in config
- Verificare l'indirizzo I2C del display
