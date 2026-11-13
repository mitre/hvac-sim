"""
Device configuration from the INI file, shared by the PLC.
"""

import configparser
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SimConfig:
    device_id: int = 101
    address: str = "auto"


def load_config(path) -> SimConfig:
    cfg = configparser.ConfigParser()
    if not cfg.read(path):
        logger.warning("Configuration file %s not found or could not be read; using default settings", path)
        return SimConfig()
    if "HVACSim" not in cfg:
        logger.warning("Configuration file %s has no [HVACSim] section; using default settings", path)
        return SimConfig()
    sec = cfg["HVACSim"]
    return SimConfig(
        device_id=int(sec.get("objectIdentifier", "101")),
        address=sec.get("address", "auto"),
    )
