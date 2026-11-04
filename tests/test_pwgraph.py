import json
from pathlib import Path

import pytest

from soundpad_linux import pwgraph

FIXTURE = Path(__file__).parent / "fixtures" / "pw-dump.json"


@pytest.fixture
def objects():
    return json.loads(FIXTURE.read_text())


def test_finds_apps_recording_from_source(objects):
    assert pwgraph.recorder_ports(objects, "easyeffects_source") == [(51, "MONO"), (61, "FL"), (62, "FR")]


def test_ignores_other_sources(objects):
    assert pwgraph.recorder_ports(objects, "alsa_input.rode") == [(91, "MONO")]


def test_unknown_source(objects):
    assert pwgraph.recorder_ports(objects, "nope") == []


def test_excludes_own_nodes(objects):
    objects.append({"id": 200, "type": "PipeWire:Interface:Node",
                    "info": {"props": {"node.name": "soundpad_linux_inject_9", "media.class": "Stream/Input/Audio"}}})
    objects.append({"id": 201, "type": "PipeWire:Interface:Port",
                    "info": {"direction": "input", "props": {"node.id": 200, "audio.channel": "FL"}}})
    objects.append({"id": 202, "type": "PipeWire:Interface:Link",
                    "info": {"output-node-id": 40, "output-port-id": 41, "input-node-id": 200, "input-port-id": 201}})
    ports = pwgraph.recorder_ports(objects, "easyeffects_source", "soundpad_linux_inject_")
    assert 201 not in [p for p, _ in ports]


def test_output_ports(objects):
    assert pwgraph.output_ports(objects, "soundpad_linux_inject_3") == [(101, "FL"), (102, "FR")]


def test_plan_links_matches_channels_and_mono():
    out_ports = [(101, "FL"), (102, "FR")]
    in_ports = [(51, "MONO"), (61, "FL"), (62, "FR")]
    assert pwgraph.plan_links(out_ports, in_ports) == [(101, 51), (102, 51), (101, 61), (102, 62)]


def test_plan_links_unknown_channels_round_robin():
    assert pwgraph.plan_links([(1, "FL"), (2, "FR")], [(10, "AUX0"), (11, "AUX1")]) == [(1, 10), (2, 11)]


def test_plan_links_without_outputs():
    assert pwgraph.plan_links([], [(10, "FL")]) == []


def test_recorder_apps(objects):
    assert pwgraph.recorder_apps(objects, "easyeffects_source") == ["Discord", "obs"]
