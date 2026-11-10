import json

import pytest
from rsk import config


@pytest.fixture
def config_file(tmp_path, monkeypatch, isolated_config):
    # A configuration file of its own, the configuration is restored after the test
    saved = config.config
    path = tmp_path / "config.json"
    monkeypatch.setattr(config, "filename", str(path))
    yield path
    config.config = saved


def test_save_and_load(config_file):
    config.config = {"camera": {"favourite_index": 2}}
    config.save()
    assert json.loads(config_file.read_text()) == {"camera": {"favourite_index": 2}}
    # Written then renamed: no temporary file left
    assert not (config_file.parent / "config.json.tmp").exists()

    config.config = {}
    config.load()
    assert config.config == {"camera": {"favourite_index": 2}}


def test_unreadable_file(config_file):
    # E.g. a save interrupted with a previous version: the Game Controller starts anyway
    config_file.write_text('{"camera": {"favour')

    config.load()

    assert config.config == {}
    assert not config_file.exists()
    assert (config_file.parent / "config.json.broken").read_text() == '{"camera": {"favour'
