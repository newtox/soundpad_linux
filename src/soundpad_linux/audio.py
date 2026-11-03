import json
import shutil
import subprocess

from .constants import MIX_SINK, MIX_SINK_LABEL, VIRTUAL_MIC, VIRTUAL_MIC_LABEL
from .i18n import tr


class AudioRouter:
    def __init__(self):
        self.modules = {}
        self.ready = False
        self.error = ""

    @staticmethod
    def pactl(*args):
        try:
            return subprocess.run(["pactl", *args], capture_output=True, text=True, timeout=5)
        except (OSError, subprocess.SubprocessError) as e:
            return subprocess.CompletedProcess(args, 1, "", str(e))

    @staticmethod
    def available():
        return shutil.which("pactl") is not None

    def cleanup_stale(self):
        r = self.pactl("list", "modules", "short")
        for line in r.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) >= 3 and (MIX_SINK in parts[2] or VIRTUAL_MIC in parts[2]):
                self.pactl("unload-module", parts[0])

    def _load(self, role, *args):
        r = self.pactl("load-module", *args)
        if r.returncode != 0 or not r.stdout.strip():
            raise RuntimeError(r.stderr.strip() or tr("{module} could not be loaded", module=args[0]))
        self.modules[role] = r.stdout.strip().splitlines()[-1]

    def setup(self):
        self.ready = False
        if not self.available():
            self.error = tr("pactl not found – please install 'pulseaudio-utils'.")
            return False
        self.cleanup_stale()
        self.modules.clear()
        try:
            self._load(
                "sink", "module-null-sink", f"sink_name={MIX_SINK}", "rate=48000", "channels=2",
                f"sink_properties=device.description={MIX_SINK_LABEL}",
            )
            self._load(
                "source", "module-remap-source", f"source_name={VIRTUAL_MIC}",
                f"master={MIX_SINK}.monitor",
                f"source_properties=device.description={VIRTUAL_MIC_LABEL}",
            )
        except RuntimeError as e:
            self.error = tr("Could not create the virtual microphone: {error}", error=e)
            self.teardown()
            return False
        self.ready = True
        self.error = ""
        return True

    def set_mic(self, source):
        if "loop" in self.modules:
            self.pactl("unload-module", self.modules.pop("loop"))
        if not self.ready or not source:
            return True
        try:
            self._load(
                "loop", "module-loopback", f"source={source}", f"sink={MIX_SINK}",
                "latency_msec=20", "source_dont_move=true", "sink_dont_move=true",
            )
            return True
        except RuntimeError as e:
            self.error = tr("Could not connect microphone '{source}': {error}", source=source, error=e)
            return False

    def teardown(self):
        for role in ("loop", "source", "sink"):
            idx = self.modules.pop(role, None)
            if idx:
                self.pactl("unload-module", idx)
        self.modules.clear()
        self.ready = False

    def list_devices(self, kind):
        own = {MIX_SINK, f"{MIX_SINK}.monitor", VIRTUAL_MIC}
        result = []
        r = self.pactl("-f", "json", "list", kind)
        try:
            for d in json.loads(r.stdout):
                name = d.get("name")
                if name and name not in own:
                    result.append((name, d.get("description") or name))
        except (ValueError, TypeError):
            r = self.pactl("list", kind, "short")
            for line in r.stdout.splitlines():
                parts = line.split("\t")
                if len(parts) > 1 and parts[1] not in own:
                    result.append((parts[1], parts[1]))
        return result

    def default_source(self):
        name = self.pactl("get-default-source").stdout.strip()
        return name if name and name != VIRTUAL_MIC else None
