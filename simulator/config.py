"""
Device configuration from the INI file, shared by the PLC.
"""

import configparser
from dataclasses import dataclass


@dataclass
class SimConfig:
    device_id: int = 101
    address: str = "127.0.0.1"
    use_fahrenheit: bool = False


def load_config(path) -> SimConfig:
    cfg = configparser.ConfigParser()
    if not cfg.read(path):
        print(f"[HVACSim] Warning: Configuration file '{path}' not found or could not be read; using default settings.")
        return SimConfig()
    if "HVACSim" not in cfg:
        print(f"[HVACSim] Warning: INI file '{path}' is missing [HVACSim] section; using default settings.")
        return SimConfig()
    sec = cfg["HVACSim"]
    unit = sec.get("temperature_unit", "celsius").strip().lower()
    return SimConfig(
        device_id=int(sec.get("objectIdentifier", "101")),
        address=sec.get("address", "127.0.0.1"),
        use_fahrenheit=unit in ("f", "fahrenheit", "imperial"),
    )
