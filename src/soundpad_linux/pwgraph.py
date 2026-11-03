import json
import shutil
import subprocess
import time

TOOLS = ("pw-dump", "pw-link", "pw-cat")


def missing_tools():
    return [t for t in TOOLS if not shutil.which(t)]


def dump():
    try:
        r = subprocess.run(["pw-dump"], capture_output=True, text=True, timeout=5)
        return json.loads(r.stdout or "[]")
    except (OSError, subprocess.SubprocessError, ValueError):
        return []


def _props(obj):
    return (obj.get("info") or {}).get("props") or {}


def _int(value, default=-1):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _truthy(value):
    return value is True or str(value).lower() == "true"


def index(objects):
    nodes, ports, links = {}, {}, []
    for obj in objects:
        kind = obj.get("type", "")
        if kind.endswith(":Node"):
            nodes[obj["id"]] = obj
        elif kind.endswith(":Port"):
            ports[obj["id"]] = obj
        elif kind.endswith(":Link"):
            links.append(obj.get("info") or {})
    return nodes, ports, links


def _node_ids(nodes, name):
    return {nid for nid, n in nodes.items() if _props(n).get("node.name") == name}


def recorder_ports(objects, source_name, exclude_prefix=""):
    nodes, ports, links = index(objects)
    sources = _node_ids(nodes, source_name)
    if not sources:
        return []
    found = {}
    for link in links:
        if _int(link.get("output-node-id")) not in sources:
            continue
        node = nodes.get(_int(link.get("input-node-id")))
        if node is None:
            continue
        p = _props(node)
        if not str(p.get("media.class", "")).startswith("Stream/Input/Audio"):
            continue
        if exclude_prefix and str(p.get("node.name", "")).startswith(exclude_prefix):
            continue
        if _truthy(p.get("stream.monitor")):
            continue
        port_id = _int(link.get("input-port-id"))
        port = ports.get(port_id)
        if port is not None:
            found[port_id] = _props(port).get("audio.channel") or "MONO"
    return sorted(found.items())


def output_ports(objects, node_name):
    nodes, ports, _links = index(objects)
    ids = _node_ids(nodes, node_name)
    result = []
    for port_id, port in ports.items():
        p = _props(port)
        if (port.get("info") or {}).get("direction") != "output":
            continue
        if _int(p.get("node.id")) not in ids or _truthy(p.get("port.monitor")):
            continue
        result.append((port_id, p.get("audio.channel") or ""))
    return sorted(result)


def plan_links(out_ports, in_ports):
    if not out_ports:
        return []
    by_channel = {channel: pid for pid, channel in out_ports}
    pairs = []
    for i, (in_id, channel) in enumerate(in_ports):
        if channel in by_channel:
            pairs.append((by_channel[channel], in_id))
        elif channel in ("MONO", ""):
            pairs.extend((pid, in_id) for pid, _ch in out_ports)
        else:
            pairs.append((out_ports[i % len(out_ports)][0], in_id))
    return pairs


def wait_for_output_ports(node_name, timeout=3.0, cancelled=lambda: False):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and not cancelled():
        ports = output_ports(dump(), node_name)
        if ports:
            return ports
        time.sleep(0.05)
    return []


def link(out_id, in_id):
    try:
        subprocess.run(["pw-link", str(out_id), str(in_id)], capture_output=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        pass
