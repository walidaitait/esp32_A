# Changelog - Implementazione MAX30102 Heart Rate Sensor

## Data: 22 Dicembre 2025

### Modifiche Principali

#### 1. Nuova Libreria MAX30102
- **Sostituita** la vecchia libreria `max30100.py` con la nuova libreria MAX30102
- **Fonte**: https://github.com/n-elia/MAX30102-MicroPython-driver
- **Versione**: Latest da repository main branch

#### 2. Struttura File
```
sensors/libs/max30102/
├── __init__.py          # Driver principale MAX30102
└── circular_buffer.py   # Buffer circolare per gestione dati
```

#### 3. Aggiornamenti Codice

**File: sensors/heart_rate.py**
- Modificato import da `max30100` a `max30102`
- Cambiato da `I2C` a `SoftI2C` per compatibilità
- Aggiunto controllo Part ID per verifica sensore
- Aggiunta configurazione ottimale per heart rate:
  - LED mode: 2 (RED + IR)
  - ADC range: 4096
  - Sample rate: 100 Hz
  - LED power: MEDIUM
  - Sample avg: 8
  - Pulse width: 411μs
- Implementata lettura dati RAW (IR e RED)
- Rimosse funzioni non più supportate (la nuova libreria fornisce solo dati RAW)

**File: main.py**
- **Disabilitati** tutti i sensori tranne heart_rate:
  - ❌ temperature (commentato)
  - ❌ co (commentato)
  - ❌ accelerometer (commentato)
  - ❌ ultrasonic (commentato)
  - ❌ buttons (commentato)
  - ✅ heart_rate (ATTIVO)
- Modificata funzione `init_sensors()` per inizializzare solo heart rate
- Modificata funzione `read_sensors()` per leggere solo heart rate
- Modificata funzione `print_sensor_data()` per mostrare solo dati heart rate
- Aggiornato messaggio di avvio firmware

#### 4. Configurazione Sensore MAX30102

**Pin I2C (da config.py):**
- SDA: GPIO 21
- SCL: GPIO 22
- Frequenza: 400 kHz

**Parametri Sensore:**
- Mode: RED + IR LED (mode 2)
- ADC Range: 4096
- Sample Rate: 100 samples/sec
- LED Power: MEDIUM (25.4mA)
- Samples Averaged: 8
- Pulse Width: 411 microseconds

### Caratteristiche Libreria MAX30102

✅ **Funzionalità Supportate:**
- Lettura valori RAW IR e RED
- Configurazione completa parametri sensore
- Rilevamento presenza dito (tramite valore IR)
- Buffer circolare per gestione dati
- Supporto MAX30102 e MAX30105
- Check Part ID automatico
- Gestione I2C ottimizzata

❌ **Funzionalità NON Incluse:**
- Calcolo automatico BPM (richiede algoritmo esterno)
- Calcolo automatico SpO2 (richiede algoritmo esterno)

**Nota**: Per calcolare BPM e SpO2 effettivi servono algoritmi di elaborazione 
del segnale avanzati. Riferimenti:
- https://github.com/aromring/MAX30102_by_RF
- https://github.com/kandizzy/esp32-micropython

### Output Console

Il firmware ora stampa ogni 5 secondi:
```
==================================================
HEART RATE SENSOR DATA @ [timestamp]ms
==================================================
Heart Rate:   BPM=[valore o "Detecting..."]
SpO2:         [valore o "Detecting..."]%
==================================================
```

### Come Testare

1. **Carica i file** sulla scheda ESP32:
   - Mantieni la struttura delle cartelle
   - Assicurati che `sensors/libs/max30102/` contenga entrambi i file
   
2. **Collega il sensore MAX30102**:
   - VCC → 3.3V
   - GND → GND
   - SDA → GPIO 21
   - SCL → GPIO 22
   
3. **Avvia la scheda** e osserva il serial monitor:
   - Dovrebbe mostrare "MAX30102 heart rate sensor initialized"
   - Metti il dito sul sensore delicatamente
   - I valori IR e RED dovrebbero cambiare

4. **Valori attesi** (dito posizionato correttamente):
   - IR > 10000 (indica presenza dito)
   - RED > 0
   - Se IR < 10000: "No finger detected"

### Problemi Noti

- La libreria fornisce solo dati RAW
- Il calcolo di BPM/SpO2 richiede algoritmi aggiuntivi
- Per ora mostra "Detecting..." come placeholder

### Prossimi Passi (Opzionali)

Se vuoi implementare il calcolo BPM/SpO2:
1. Implementare algoritmo di beat detection
2. Calcolare intervalli R-R (tempo tra battiti)
3. Calcolare BPM dalla media degli intervalli
4. Implementare algoritmo SpO2 dal rapporto RED/IR

### File Modificati

- `sensors/heart_rate.py` - Completamente riscritto
- `main.py` - Disabilitati altri sensori
- `README.md` - Aggiornata documentazione
- `sensors/libs/max30102/__init__.py` - Nuovo file
- `sensors/libs/max30102/circular_buffer.py` - Nuovo file

### File Rimossi

- `sensors/libs/max30100.py` - Vecchia libreria rimossa

---
**Autore**: GitHub Copilot  
**Data**: 22 Dicembre 2025
