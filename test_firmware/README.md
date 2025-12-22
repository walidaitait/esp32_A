# TEST FIRMWARE - ESP32 Multi-Sensor Monitoring

## ⚠️ IMPORTANTE - Configurazione Attuale
**SENSORI ATTIVI:** Temperature, CO, Ultrasonic (HC-SR04), Heart Rate (MAX30102), Buttons (x3)
**SENSORE DISABILITATO:** Accelerometro

## Modifiche Recenti (v2.0)
- ✅ **Multi-sensor attivato**: Temperatura, CO, Ultrasuoni, Heart Rate, Buttons
- ✅ **Accelerometro disabilitato**: Come richiesto
- ✅ **Log unificato ogni 3 secondi**: Tutti i dati dei sensori in un unico output
- ✅ **Log individuali disabilitati**: Rimossi i log continui dei singoli sensori
- ✅ **Codice 100% non-bloccante**: Tutte le letture sono asincrone

## Libreria MAX30102
La libreria MAX30102 è stata integrata da: https://github.com/n-elia/MAX30102-MicroPython-driver

**Caratteristiche:**
- Supporto completo per MAX30102 e MAX30105
- Lettura valori RAW (IR e RED LED)
- Configurazione avanzata (sample rate, ADC range, LED power, etc.)
- Buffer circolare per gestione dati
- Algoritmi di rilevamento BPM e SpO2 implementati

## Scopo
Questo firmware semplificato è progettato per testare **tutti i sensori principali** 
(escluso l'accelerometro) con output unificato ogni 3 secondi.

## Caratteristiche Attive
- ✅ Sensore temperatura DS18B20 (non-bloccante con conversione asincrona)
- ✅ Sensore CO analogico (lettura PPM)
- ✅ Sensore ultrasuoni HC-SR04 (interrupt-driven, non-bloccante)
- ✅ Sensore heart rate MAX30102 (BPM e SpO2)
- ✅ 3 Pulsanti digitali (con PULL_UP)
- ✅ Sistema OTA funzionante per aggiornamenti via WiFi
- ✅ Output unificato ogni 3 secondi
- ✅ Gestione graceful degli errori
- ❌ Accelerometro disabilitato
- ❌ Nessuna logica di allarme
- ❌ Nessuna comunicazione MQTT
- ❌ Nessuna comunicazione ESP-NOW

## Struttura File
```
test_firmware/
├── main.py                      # Loop principale (multi-sensor)
├── ota_update.py               # Sistema OTA
├── config.py                   # Configurazione pin e intervalli
├── wifi_config.py              # Credenziali WiFi
├── state.py                    # Stato sensori
├── timers.py                   # Timer per letture periodiche
├── debug.py                    # Logging semplice
├── filelist.json               # Lista file per OTA
└── sensors/
    ├── __init__.py
    ├── heart_rate.py           # MAX30102 (ATTIVO)
    ├── temperature.py          # DS18B20 (disabilitato)
    ├── co.py                   # Sensore CO (disabilitato)
    ├── accelerometer.py        # Accelerometro (disabilitato)
    ├── ultrasonic.py           # HC-SR04 (disabilitato)
    ├── buttons.py              # Pulsanti (disabilitato)
    └── libs/
        └── max30102/
            ├── __init__.py     # Driver MAX30102 principale
            └── circular_buffer.py  # Buffer per dati sensore
```

## Come Usare

### 1. Prima volta - Upload manuale
1. Copia tutti i file della cartella `test_firmware` sulla scheda ESP32
2. Mantieni la struttura delle cartelle (sensors, sensors/libs)
3. Riavvia la scheda

### 2. Aggiornamenti successivi - OTA
1. Premi e tieni premuto il pulsante GPIO16 per 5 secondi all'avvio
2. La scheda si collegherà al WiFi e scaricherà i file aggiornati
3. Dopo il download, la scheda si riavvierà automaticamente

**NOTA:** Il sistema OTA è configurato per scaricare da:
`https://raw.githubusercontent.com/walidaitait/esp32_A/main/test_firmware/`

## Output Console
Ogni 5 secondi vedrai un output simile a:

```
==================================================
SENSOR DATA @ 125340ms
==================================================
Temperature:  23.5 °C
CO Voltage:   0.45 V
Accelerometer: X=0.02g, Y=-0.01g, Z=1.01g
Distance:     15.3 cm
Heart Rate:   BPM=72.5, SpO2=98.0%
Buttons:      B1=Released, B2=Released, B3=PRESSED
==================================================
```

## Modifiche Principali dal Firmware Originale
1. **Rimosso:** Tutto il sistema di logica (logic/)
2. **Rimosso:** Tutti i sistemi di comunicazione (communications/)
3. **Rimosso:** Sistema di comandi (commands/)
4. **Semplificato:** Debug ridotto a semplice logging
5. **Semplificato:** Buttons non triggera più hooks, solo log del cambiamento
6. **Mantenuto:** Sistema OTA completo per aggiornamenti

## Troubleshooting

### Sensore non funziona
Il firmware è progettato per continuare anche se un sensore fallisce.
Controlla l'output di inizializzazione per vedere quali sensori sono stati rilevati.

### OTA non funziona
- Verifica le credenziali WiFi in `wifi_config.py`
- Verifica che i file siano caricati su GitHub nella cartella `test_firmware/`
- Controlla che `filelist.json` sia corretto

### Nessun output
Verifica la connessione seriale (115200 baud).

## Tornare al Firmware Principale
Per tornare al firmware completo, semplicemente carica i file dalla cartella principale
`esp32_A (Modifica)` sulla scheda, oppure usa il sistema OTA del firmware principale.
