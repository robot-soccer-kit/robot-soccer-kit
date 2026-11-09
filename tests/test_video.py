import pytest

from rsk import video


@pytest.fixture
def make_video(isolated_config):
    created = []

    def make(camera_config=None):
        isolated_config.config.pop("camera", None)
        if camera_config is not None:
            isolated_config.config["camera"] = camera_config
        created.append(video.Video())
        return created[-1]

    yield make
    for v in created:
        v.stop()
    isolated_config.config.pop("camera", None)


def test_default_focal(make_video):
    assert make_video().settings["focal"] == video.DEFAULT_FOCAL == 935


def test_old_default_focal_is_updated(make_video):
    v = make_video({"settings": {"focal": video.OLD_DEFAULT_FOCAL, "gain": 3}})

    assert v.settings["focal"] == video.DEFAULT_FOCAL
    assert v.settings["gain"] == 3


def test_custom_focal_is_kept(make_video):
    assert make_video({"settings": {"focal": 1200}}).settings["focal"] == 1200
