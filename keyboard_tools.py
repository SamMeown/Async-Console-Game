from monitor import Monitor


def read_controls():
    if not hasattr(read_controls, 'monitor'):
        read_controls.monitor = Monitor()
        read_controls.monitor.start()
        read_controls.controls = 0, 0, False
    controls = read_controls.monitor.get_control_keys()
    if controls:
        row_direction = -1 if controls['up'] else 1 if controls['down'] else 0
        col_direction = -1 if controls['left'] else 1 if controls['right'] else 0
        space = controls['space']
        read_controls.controls = row_direction, col_direction, space
    return read_controls.controls


def stop_controls_reading():
    read_controls.monitor.stop()
