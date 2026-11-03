import itertools
import shutil
import subprocess
import threading
import time

from PySide6.QtCore import QObject, QTimer, Signal

from . import pwgraph
from .constants import APP_NAME, INJECT_NODE_PREFIX
from .i18n import tr

SAMPLE_RATE = "48000"
CHANNELS = "2"


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


def _kill(procs):
    for p in procs:
        if p.poll() is None:
            try:
                p.kill()
            except OSError:
                pass
    for p in procs:
        try:
            p.wait(timeout=1)
        except subprocess.SubprocessError:
            pass


def _decoder(path, volume):
    return subprocess.Popen(
        ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-i", path,
         "-af", f"volume={volume:.3f}", "-f", "s16le", "-ac", CHANNELS, "-ar", SAMPLE_RATE, "-"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, start_new_session=True,
    )


def _pipe(path, volume, command):
    dec = _decoder(path, volume)
    out = subprocess.Popen(
        command, stdin=dec.stdout, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
    )
    dec.stdout.close()
    return [dec, out]


class Playback:
    def __init__(self, sound_id, title, duration):
        self.sound_id = sound_id
        self.title = title
        self.duration = duration
        self.procs = []
        self.pending = 0
        self.cancelled = False
        self.started = time.monotonic()

    def done(self):
        return self.pending == 0 and all(p.poll() is not None for p in self.procs)

    def kill(self):
        self.cancelled = True
        _kill(list(self.procs))


class Player(QObject):
    changed = Signal()
    notice = Signal(str)

    def __init__(self):
        super().__init__()
        self.active = []
        self._counter = itertools.count(1)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._poll)
        self.timer.start(100)

    @staticmethod
    def missing_tools():
        return [t for t in ("ffmpeg", "pacat") if not shutil.which(t)]

    def _play_to_sink(self, pb, path, device, volume):
        pb.procs += _pipe(path, volume, [
            "pacat", "--playback", "--format=s16le", f"--rate={SAMPLE_RATE}", f"--channels={CHANNELS}",
            f"--device={device}", f"--client-name={APP_NAME}", f"--stream-name={pb.title}", "--latency-msec=40",
        ])

    def _play_injected(self, pb, path, source, volume):
        pb.pending += 1
        threading.Thread(target=self._inject_worker, args=(pb, path, source, volume), daemon=True).start()

    def _inject_worker(self, pb, path, source, volume):
        try:
            in_ports = pwgraph.recorder_ports(pwgraph.dump(), source, INJECT_NODE_PREFIX)
            if not in_ports:
                self.notice.emit(tr("No app is recording from »{source}« right now.", source=source))
                return
            if pb.cancelled:
                return
            name = f"{INJECT_NODE_PREFIX}{next(self._counter)}"
            procs = _pipe(path, volume, [
                "pw-cat", "--playback", "--raw", "--format", "s16", "--rate", SAMPLE_RATE,
                "--channels", CHANNELS, "--target", "0", "--latency", "40ms",
                "-P", f'{{ node.name = "{name}" node.autoconnect = false }}', "-",
            ])
            pb.procs += procs
            out_ports = pwgraph.wait_for_output_ports(name, cancelled=lambda: pb.cancelled)
            if not out_ports or pb.cancelled:
                _kill(procs)
                if not pb.cancelled:
                    self.notice.emit(tr("Could not connect the sound to »{source}«.", source=source))
                return
            for out_id, in_id in pwgraph.plan_links(out_ports, in_ports):
                pwgraph.link(out_id, in_id)
        finally:
            pb.pending -= 1

    def play(self, sound, targets, overlap):
        if not overlap:
            self.stop_all()
        pb = Playback(sound["id"], sound["title"], sound.get("duration"))
        for kind, device, volume in targets:
            if volume <= 0 or not device:
                continue
            if kind == "inject":
                self._play_injected(pb, sound["path"], device, volume)
            else:
                self._play_to_sink(pb, sound["path"], device, volume)
        started = bool(pb.procs) or pb.pending > 0
        if started:
            self.active.append(pb)
        self.changed.emit()
        return started

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
