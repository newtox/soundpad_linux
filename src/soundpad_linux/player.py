import shutil
import subprocess
import threading
import time

from PySide6.QtCore import QObject, QTimer, Signal

from .constants import APP_NAME


def probe_duration(path):
    if not shutil.which("ffprobe"):
        return None
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
            capture_output=True, text=True, timeout=10,
        )
        return float(r.stdout.strip())
    except (ValueError, subprocess.SubprocessError, OSError):
        return None


class Playback:
    def __init__(self, sound_id, title, procs, duration):
        self.sound_id = sound_id
        self.title = title
        self.procs = procs
        self.duration = duration
        self.started = time.monotonic()

    def done(self):
        return all(p.poll() is not None for p in self.procs)

    def kill(self):
        for p in self.procs:
            if p.poll() is None:
                try:
                    p.kill()
                except OSError:
                    pass
        for p in self.procs:
            try:
                p.wait(timeout=1)
            except subprocess.SubprocessError:
                pass


class Player(QObject):
    changed = Signal()

    def __init__(self):
        super().__init__()
        self.active = []
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._poll)
        self.timer.start(100)

    @staticmethod
    def missing_tools():
        return [t for t in ("ffmpeg", "pacat") if not shutil.which(t)]

    @staticmethod
    def _spawn(path, title, device, volume):
        dec = subprocess.Popen(
            ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-i", path,
             "-af", f"volume={volume:.3f}", "-f", "s16le", "-ac", "2", "-ar", "48000", "-"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, start_new_session=True,
        )
        out = subprocess.Popen(
            ["pacat", "--playback", "--format=s16le", "--rate=48000", "--channels=2",
             f"--device={device}", f"--client-name={APP_NAME}", f"--stream-name={title}",
             "--latency-msec=40"],
            stdin=dec.stdout, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        dec.stdout.close()
        return [dec, out]

    def play(self, sound, targets, overlap):
        if not overlap:
            self.stop_all()
        procs = []
        for device, volume in targets:
            if volume > 0:
                procs += self._spawn(sound["path"], sound["title"], device, volume)
        if procs:
            self.active.append(Playback(sound["id"], sound["title"], procs, sound.get("duration")))
        self.changed.emit()
        return bool(procs)

    def stop_all(self):
        for pb in self.active:
            pb.kill()
        had = bool(self.active)
        self.active.clear()
        if had:
            self.changed.emit()

    def playing_ids(self):
        return {pb.sound_id for pb in self.active}

    def _poll(self):
        for pb in [pb for pb in self.active if pb.done()]:
            self.active.remove(pb)
        self.changed.emit()


class Prober(QObject):
    probed = Signal(int, float)

    def run(self, items):
        items = list(items)
        if items:
            threading.Thread(target=self._work, args=(items,), daemon=True).start()

    def _work(self, items):
        for sid, path in items:
            d = probe_duration(path)
            if d:
                self.probed.emit(sid, d)
