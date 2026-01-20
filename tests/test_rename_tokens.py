import pytest
from src.core.device_manager_core import DeviceManagerCore
from src.models.device_models import DeviceConfig, DeviceType


def test_rename_updates_saved_scripts_and_choices(tmp_path):
    cfg_path = tmp_path / "devices.json"
    dm = DeviceManagerCore(str(cfg_path))

    # start clean
    dm.clear_all_devices()
    dm._saved_scripts.clear()
    dm._script_tag_manager._choices = {}

    # add initial device
    cfg = DeviceConfig(name="dev_old", ip_address="10.0.0.1", port=502, device_type=DeviceType.MODBUS_TCP)
    dm.add_device(cfg, save=False)

    # simulate saved script and persisted token choice referencing the original device
    dm._saved_scripts["script1"] = {"code": "print({{TAG:dev_old::40001}})", "interval": 0.5}
    dm._script_tag_manager._choices["dev_old::40001"] = "dev_old::40001"

    # rename device by providing a new config with same ip/port but new name
    new_cfg = DeviceConfig(name="dev_new", ip_address="10.0.0.1", port=502, device_type=DeviceType.MODBUS_TCP)
    dm.update_device_config(new_cfg)

    # Assertions: saved script token updated, choices updated, device map renamed
    assert "script1" in dm._saved_scripts
    assert "{{TAG:dev_new::40001}}" in dm._saved_scripts["script1"]["code"]
    assert any(k.startswith("dev_new::") for k in dm._script_tag_manager._choices.keys())
    assert "dev_new" in dm._devices
    assert "dev_old" not in dm._devices
