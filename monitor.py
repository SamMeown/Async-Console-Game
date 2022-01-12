import logging
import signal
from multiprocessing import Process, Pipe

from pynput import keyboard


logging.disable(logging.WARN)


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
        self.p = None
        self.conn = None

    def start(self):
        self.conn, c_conn = Pipe()
        self.p = Process(target=self.monitor_control_keys, args=(c_conn,))
        self.p.start()
        c_conn.close()

    def stop(self):
        # first try to exit gracefully (via custom sigterm handler)
        self.p.terminate()
        self.p.join(timeout=2)
        # if failed to exit gracefully then terminate
        if self.p.exitcode is None:
            self.p.terminate()
            self.p.join()

    def monitor_control_keys(self, conn):
        monitor = KeyMonitor(lambda state: conn.send(state))
        signal.signal(signal.SIGTERM, self._sigterm_handler(monitor))
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        monitor.run()

    def _sigterm_handler(self, monitor):
        def sigterm_handler(sig, frame):
            signal.signal(signal.SIGTERM, signal.SIG_DFL)
            monitor.stop()
        return sigterm_handler

    def get_control_keys(self):
        keys = None
        while self.conn.poll():
            keys = self.conn.recv()
        return keys
