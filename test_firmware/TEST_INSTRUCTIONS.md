# Istruzioni per Testare il Sensore MAX30102

## Preparazione Hardware

### 1. Collegamenti del Sensore MAX30102

Collega il sensore MAX30102 all'ESP32 come segue:

```
MAX30102      →    ESP32
---------          -------
VCC (3.3V)    →    3.3V
GND           →    GND
SDA           →    GPIO 21
SCL           →    GPIO 22
```

⚠️ **IMPORTANTE**: 
- Usa **3.3V**, NON 5V!
- I pin SDA/SCL sono già configurati nel file config.py
- Assicurati che i collegamenti siano saldi

### 2. Caricamento del Firmware

Opzione A - **Upload Manuale** (prima volta):
1. Connetti l'ESP32 al PC tramite USB
2. Usa Thonny, rshell, o ampy per caricare i file
3. Carica **tutta** la cartella `test_firmware` mantenendo la struttura:
   ```
   test_firmware/
   ├── main.py
   ├── ota_update.py
   ├── config.py
   ├── wifi_config.py
   ├── state.py
   ├── timers.py
   ├── debug.py
   ├── filelist.json
   └── sensors/
       ├── __init__.py
       ├── heart_rate.py
       └── libs/
           └── max30102/
               ├── __init__.py
               └── circular_buffer.py
   ```

Opzione B - **OTA Update** (dopo la prima volta):
1. Modifica i file sul tuo PC
2. Carica su GitHub o server OTA
3. Premi pulsante GPIO16 per 5 secondi all'avvio dell'ESP32
4. La scheda scaricherà e installerà i file aggiornati

### 3. Configurazione WiFi

Modifica il file `wifi_config.py` con le tue credenziali:
```python
WIFI_SSID = "TUO_SSID"
WIFI_PASSWORD = "TUA_PASSWORD"
```

## Test del Sensore

### 1. Avvio e Monitor Seriale

1. Apri il monitor seriale (115200 baud)
2. Riavvia l'ESP32
3. Dovresti vedere:
   ```
   ##################################################
   #  ESP32 TEST FIRMWARE - HEART RATE ONLY
   #  Version: 1.0
   #  Purpose: Test heart rate sensor only
   ##################################################
   
   ==================================================
   TEST FIRMWARE - HEART RATE SENSOR ONLY
   ==================================================
   
   --------------------------------------------------
   INITIALIZATION SUMMARY:
     Heart Rate          : OK
   --------------------------------------------------
   
   [heart_rate] For best results: place finger gently without pressing too hard
   Starting main loop...
   Sensor data will be printed every 5 seconds.
   ```

### 2. Test Senza Dito

**Output atteso** (ogni 5 secondi):
```
==================================================
HEART RATE SENSOR DATA @ 15000ms
==================================================
Heart Rate:   BPM=None
SpO2:         None%
==================================================
```

Nel log di debug vedrai:
```
[heart_rate] No finger detected (IR: 0, Red: 0)
```

### 3. Test Con Dito

1. **Posiziona il dito** sul sensore:
   - Metti il dito **delicatamente** sul sensore
   - NON premere troppo forte
   - Copri completamente il LED
   - Mantieni il dito fermo

2. **Output atteso**:
   ```
   ==================================================
   HEART RATE SENSOR DATA @ 20000ms
   ==================================================
   Heart Rate:   BPM=Detecting...
   SpO2:         Detecting...%
   ==================================================
   ```

3. **Nel log di debug** (ogni 10 letture):
   ```
   [heart_rate] IR: 45000, Red: 38000, readings: 10
   [heart_rate] IR: 46000, Red: 39000, readings: 20
   [heart_rate] IR: 44000, Red: 37000, readings: 30
   ```

### 4. Interpretazione Valori

**Valori IR e RED**:
- **IR < 10000**: Nessun dito rilevato
- **IR > 10000**: Dito presente
- **Valori ottimali**: IR ~40000-60000, RED ~30000-50000

**Nota**: La libreria fornisce solo valori RAW (IR e RED). 
Per calcolare BPM/SpO2 effettivi servono algoritmi aggiuntivi.

## Troubleshooting

### Problema: "Sensor not found on I2C bus"

**Soluzioni**:
1. Verifica i collegamenti hardware (SDA, SCL, VCC, GND)
2. Controlla che il sensore sia alimentato a 3.3V
3. Prova a scambiare SDA e SCL
4. Usa un multimetro per verificare tensione

### Problema: "IR: 0" sempre

**Soluzioni**:
1. Il sensore non è inizializzato correttamente
2. Verifica l'indirizzo I2C (dovrebbe essere 0x57)
3. Prova a ricaricare il firmware
4. Controlla che il sensore non sia danneggiato

### Problema: "IR > 10000" ma valori strani

**Soluzioni**:
1. Il dito potrebbe essere premuto troppo forte
2. Prova a posizionare il dito in modo diverso
3. Assicurati che il dito copra completamente il LED
4. Pulisci il sensore da impronte/sporco

### Problema: Valori IR/RED molto bassi

**Soluzioni**:
1. Aumenta la potenza LED nel codice:
   ```python
   led_power=MAX30105_PULSE_AMP_HIGH
   ```
2. Aumenta il sample rate a 400
3. Verifica che la stanza non sia troppo luminosa

## Prossimi Passi

Dopo aver verificato che i valori RAW vengono letti correttamente:

1. **Implementa Beat Detection**:
   - Algoritmo per rilevare picchi nel segnale IR
   - Calcola intervalli tra battiti (R-R intervals)

2. **Calcola BPM**:
   - Media degli intervalli R-R
   - Converti in battiti per minuto

3. **Calcola SpO2**:
   - Rapporto tra assorbimento RED/IR
   - Formula di calibrazione

**Riferimenti**:
- https://github.com/aromring/MAX30102_by_RF
- https://github.com/kandizzy/esp32-micropython/tree/master/PPG

## Contatti e Supporto

Per problemi o domande:
1. Controlla il file `CHANGELOG_HEART_RATE.md`
2. Leggi la documentazione della libreria: 
   https://github.com/n-elia/MAX30102-MicroPython-driver
3. Verifica il datasheet MAX30102

---
**Ultimo aggiornamento**: 22 Dicembre 2025
