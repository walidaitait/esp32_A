#!/usr/bin/env python3
"""UDP Command Sender for ESP32 Boards.

Send commands to ESP32-A (sensors) or ESP32-B (actuators) over UDP.

Usage:
    python send_command.py <target> <command> [args...]
    
Examples:
    # ESP32-B (Actuators)
    python send_command.py B led green on
    python send_command.py B servo 90
    python send_command.py B lcd line1 Hello World
    python send_command.py B buzzer on
    python send_command.py B audio play
    python send_command.py B state
    python send_command.py B status
    
    # ESP32-A (Sensors)
    python send_command.py A simulate temperature 25.5
    python send_command.py A simulate co 50
    python send_command.py A alarm trigger
    python send_command.py A state
    python send_command.py A status

Configuration:
    - Broadcast IP: Sends to all devices on local network
    - UDP Port: 37022 (must match ESP32 configuration)
    - Timeout: 2 seconds for response
"""

import socket
import json
import sys


# Configuration
UDP_COMMAND_PORT = 37022
BROADCAST_IP = "255.255.255.255"  # Send to all devices on network
RESPONSE_TIMEOUT = 2  # Seconds to wait for response


def send_command(target, command, args):
    """Send command to ESP32 board via UDP.
    
    Args:
        target: 'A' or 'B' (which ESP32 board)
        command: Command name
        args: List of command arguments
    
    Returns:
        dict: Response from ESP32, or None if no response
    """
    # Validate target
    target = target.upper()
    if target not in ['A', 'B']:
        print(f"Error: Invalid target '{target}'. Use 'A' or 'B'")
        return None
    
    # Build command message
    message = {
        "target": target,
        "command": command,
        "args": args
    }
    
    try:
        # Create UDP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(RESPONSE_TIMEOUT)
        
        # Send command
        message_json = json.dumps(message)
        sock.sendto(message_json.encode('utf-8'), (BROADCAST_IP, UDP_COMMAND_PORT))
        
        print(f"Sent to ESP32-{target}: {command} {' '.join(args)}")
        
        # Wait for response
        try:
            data, addr = sock.recvfrom(1024)
            response = json.loads(data.decode('utf-8'))
            
            print(f"\nResponse from {addr[0]}:")
            print(f"  Success: {response.get('success')}")
            print(f"  Message: {response.get('message')}")
            
            # Print additional data if present
            if 'state' in response:
                print(f"  State: {json.dumps(response['state'], indent=2)}")
            if 'status' in response:
                print(f"  Status: {json.dumps(response['status'], indent=2)}")
            if 'alarm' in response:
                print(f"  Alarm: {json.dumps(response['alarm'], indent=2)}")
            
            sock.close()
            return response
        
        except socket.timeout:
            print("  (No response received - command may have been executed)")
            sock.close()
            return None
    
    except Exception as e:
        print(f"Error sending command: {e}")
        return None


def print_usage():
    """Print usage information."""
    print(__doc__)


def main():
    """Main entry point."""
    if len(sys.argv) < 3:
        print_usage()
        sys.exit(1)
    
    target = sys.argv[1]
    command = sys.argv[2]
    args = sys.argv[3:] if len(sys.argv) > 3 else []
    
    send_command(target, command, args)


if __name__ == '__main__':
    main()
