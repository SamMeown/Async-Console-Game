from multiprocessing import Process, Pipe

from pynput import keyboard


class KeyMonitor:

    state = {'left': False, 'right': False, 'up': False, 'down': False, 'space': False}
    keys_map = {keyboard.Key.left: 'left', keyboard.Key.right: 'right', keyboard.Key.up: 'up',
                keyboard.Key.down: 'down', keyboard.Key.space: 'space'}

    def __init__(self, on_control_keys_change):
        self._on_control_keys_change = on_control_keys_change
        self.listener = None

    def on_press(self, key):
        try:
            key_name = self.keys_map[key]
            if key_name in self.state:
                self.state[key_name] = True
                self._on_control_keys_change(self.state)
        except (AttributeError, KeyError):
            pass

    def on_release(self, key):
        try:
            key_name = self.keys_map[key]
            if key_name in self.state:
                self.state[key_name] = False
                self._on_control_keys_change(self.state)
        except (AttributeError, KeyError):
            pass

    def run(self):
        with keyboard.Listener(
                on_press=self.on_press,
                on_release=self.on_release) as listener:
            self.listener = listener
            self.listener.join()

    def stop(self):
        self.listener.stop()


class Monitor:
    def __init__(self):
        self.monitor = None
        self.p = None
        self.conn = None

    def start(self):
        self.conn, c_conn = Pipe()
        self.p = Process(target=self.monitor_control_keys, args=(c_conn,))
        self.p.start()

    def stop(self):
        self.monitor.stop()
        self.p.terminate()
        self.p.join(timeout=1)

    def monitor_control_keys(self, conn):
        self.monitor = KeyMonitor(lambda state: conn.send(state))
        self.monitor.run()

    def get_control_keys(self):
        keys = None
        while self.conn.poll():
            keys = self.conn.recv()
        return keys
