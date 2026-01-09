"""UDP Log Listener - Raccoglie log da entrambe le schede ESP32.

Esegui questo script sul PC per vedere i log di ESP32-A e ESP32-B
contemporaneamente, anche se solo una è connessa via seriale.

Usage:
    python log_listener.py
"""

import socket
import sys
from datetime import datetime

# Porta UDP per ricevere log (deve corrispondere a quella nelle schede)
LOG_PORT = 37021

# Colori ANSI per terminale
COLOR_RESET = "\033[0m"
COLOR_A = "\033[94m"  # Blu per ESP32-A
COLOR_B = "\033[92m"  # Verde per ESP32-B
COLOR_TIMESTAMP = "\033[90m"  # Grigio per timestamp


def main():
    """Avvia il listener UDP per log."""
    print("=" * 80)
    print("🔍 UDP Log Listener - Monitoring ESP32-A and ESP32-B")
    print("=" * 80)
    print(f"Listening on UDP port {LOG_PORT}...")
    print(f"{COLOR_A}ESP32-A (Sensors) = Blue{COLOR_RESET}")
    print(f"{COLOR_B}ESP32-B (Actuators) = Green{COLOR_RESET}")
    print("=" * 80)
    print()
    
    # Crea socket UDP
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('0.0.0.0', LOG_PORT))
    
    try:
        while True:
            # Ricevi log
            data, addr = sock.recvfrom(4096)
            
            try:
                message = data.decode('utf-8').strip()
                
                # Estrai device ID dal messaggio (formato: "[A][module] message" o "[B][module] message")
                if message.startswith('['):
                    # Trova il primo ]
                    first_bracket_end = message.find(']')
                    if first_bracket_end > 0:
                        device_id = message[1:first_bracket_end]
                        rest = message[first_bracket_end + 1:]
                        
                        # Trova il secondo [...] per il modulo
                        if rest.startswith('['):
                            second_bracket_end = rest.find(']')
                            if second_bracket_end > 0:
                                module = rest[1:second_bracket_end]
                                log_message = rest[second_bracket_end + 1:].strip()
                                
                                # Scegli colore in base al device
                                if device_id == 'A':
                                    color = COLOR_A
                                    device_name = "ESP32-A"
                                elif device_id == 'B':
                                    color = COLOR_B
                                    device_name = "ESP32-B"
                                else:
                                    color = COLOR_RESET
                                    device_name = f"ESP32-{device_id}"
                                
                                # Timestamp
                                timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                                
                                # Stampa log formattato con colori
                                print(f"{COLOR_TIMESTAMP}[{timestamp}]{COLOR_RESET} "
                                      f"{color}[{device_name}]{COLOR_RESET} "
                                      f"[{module}] {log_message}")
                                continue
                
                # Formato non riconosciuto, stampa raw
                print(f"[{addr[0]}] {message}")
                    
            except UnicodeDecodeError:
                print(f"[{addr[0]}] <binary data>")
                
    except KeyboardInterrupt:
        print("\n\n" + "=" * 80)
        print("✓ Log listener stopped")
        print("=" * 80)
        sock.close()
        sys.exit(0)


if __name__ == "__main__":
    main()
