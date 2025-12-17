import state

def update_output_commands():
    if state.system_state["alarm_co"]:
        state.output_commands["buzzer"] = True
        state.output_commands["led_red"] = True
        state.output_commands["lcd_message"] = "CO Alarm!"
    else:
        state.output_commands["buzzer"] = False
        state.output_commands["led_red"] = False

    if state.system_state["alarm_temp"]:
        state.output_commands["led_blue"] = True
    else:
        state.output_commands["led_blue"] = False

