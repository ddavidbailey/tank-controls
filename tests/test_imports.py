import tank_controls
import tank_controls.audio
import tank_controls.config
import tank_controls.hid
import tank_controls.vision


def test_package_importable() -> None:
    assert tank_controls.__name__ == "tank_controls"


def test_submodules_importable() -> None:
    assert tank_controls.audio.__name__ == "tank_controls.audio"
    assert tank_controls.vision.__name__ == "tank_controls.vision"
    assert tank_controls.hid.__name__ == "tank_controls.hid"
    assert tank_controls.config.__name__ == "tank_controls.config"
