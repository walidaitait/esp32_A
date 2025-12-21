# TEST FIRMWARE - ESP32 Sensor Testing

## Scopo
Questo firmware semplificato è progettato per testare **solo i sensori** dell'ESP32, 
senza la complessità della logica, comunicazioni MQTT, ESP-NOW, e altre funzionalità.

## Caratteristiche
- ✅ Test di tutti i sensori (temperatura, CO, accelerometro, ultrasuoni, frequenza cardiaca, pulsanti)
- ✅ Sistema OTA funzionante per aggiornamenti via WiFi
- ✅ Output leggibile ogni 5 secondi con tutti i dati dei sensori
- ✅ Gestione graceful degli errori (se un sensore fallisce, il sistema continua)
- ❌ Nessuna logica di allarme
- ❌ Nessuna comunicazione MQTT
- ❌ Nessuna comunicazione ESP-NOW

## Struttura File
```
test_firmware/
├── main.py                 # Loop principale semplificato
├── ota_update.py          # Sistema OTA (modificato per cartella test)
├── config.py              # Configurazione pin e intervalli
├── wifi_config.py         # Credenziali WiFi
├── state.py               # Stato sensori
├── timers.py              # Timer per letture periodiche
├── debug.py               # Logging semplice
├── filelist.json          # Lista file per OTA
└── sensors/
    ├── __init__.py
    ├── temperature.py     # Sensore DS18B20
    ├── co.py              # Sensore CO
    ├── accelerometer.py   # Accelerometro analogico
    ├── ultrasonic.py      # HC-SR04
    ├── heart_rate.py      # MAX30100
    ├── buttons.py         # Pulsanti digitali
    └── libs/
        └── max30100.py    # Libreria sensore cardiaco
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
