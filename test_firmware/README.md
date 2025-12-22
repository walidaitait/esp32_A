# TEST FIRMWARE - ESP32 Heart Rate Sensor Testing

## ⚠️ IMPORTANTE - Configurazione Attuale
**SOLO IL SENSORE DI HEART RATE È ATTIVO**
- Tutti gli altri sensori sono stati disabilitati nel codice
- Il firmware ora testa SOLO il sensore MAX30102 per il battito cardiaco

## Modifiche Recenti
- ✅ **Libreria MAX30102 installata**: Sostituita vecchia libreria MAX30100 con driver n-elia/MAX30102
- ✅ **Sensori disabilitati**: Temperatura, CO, accelerometro, ultrasuoni e pulsanti sono commentati
- ✅ **Output semplificato**: Mostra solo dati del sensore heart rate ogni 5 secondi

## Libreria MAX30102
La nuova libreria MAX30102 è stata scaricata da: https://github.com/n-elia/MAX30102-MicroPython-driver

**Caratteristiche:**
- Supporto completo per MAX30102 e MAX30105
- Lettura valori RAW (IR e RED LED)
- Configurazione avanzata (sample rate, ADC range, LED power, etc.)
- Buffer circolare per gestione dati

**Nota:** La libreria fornisce solo i dati RAW. Per calcolare BPM e SpO2 effettivi 
servono algoritmi di elaborazione del segnale avanzati (non inclusi).

## Scopo
Questo firmware semplificato è progettato per testare **solo il sensore MAX30102** 
per la misurazione della frequenza cardiaca e SpO2.

## Caratteristiche Attive
- ✅ Test sensore MAX30102 (heart rate)
- ✅ Sistema OTA funzionante per aggiornamenti via WiFi
- ✅ Output leggibile ogni 5 secondi con dati IR/RED del sensore
- ✅ Gestione graceful degli errori
- ❌ Altri sensori disabilitati (temperatura, CO, accelerometro, ultrasuoni, pulsanti)
- ❌ Nessuna logica di allarme
- ❌ Nessuna comunicazione MQTT
- ❌ Nessuna comunicazione ESP-NOW

## Struttura File
```
test_firmware/
├── main.py                      # Loop principale (SOLO heart rate attivo)
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
