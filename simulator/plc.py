"""
BACnet/IP device for the HVAC simulation. Serves the simulation as BACnet
objects and runs the control loop; the HMI is a separate client.

Objects:
  - AV:1 temperature_setpoint_c      (commandable)  setpoint parameter
  - AO:1 intake_fan_speed_percent    (commandable)  fan actuator command
  - AO:2 exhaust_fan_speed_percent   (commandable)  fan actuator command
  - BV:1 emergency_stop              (commandable)  command flag
  - AI:1 current_temperature_c       (read-only)    sensor reading
  - AI:2 chiller_speed_percent       (read-only)    sensor feedback

To run:
    python -m simulator.plc
"""

import argparse
import asyncio
import logging
import signal
import sys
import threading
import time
from pathlib import Path

import BAC0
from BAC0.core.devices.local.factory import (
    analog_input,
    analog_output,
    analog_value,
    binary_value,
)

from simulator import SIM
from simulator.cli import add_deprecated_alias, warn_deprecated
from simulator.config import load_config
from simulator.network import resolve_address
from simulator.sim import TICK_SECONDS, SimulationState, simulation_step

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config.ini"
DEFAULT_PORT = SIM["protocols"]["bacnet"]["port"]

logger = logging.getLogger(__name__)


class HVACPLC:
    def __init__(self, device_id, address, port=DEFAULT_PORT, debug=False):
        self.device_id = device_id
        self.address = address
        self.port = port
        self.debug = debug
        self.state = SimulationState()
        self.objects = {}
        self.bacnet = None
        self.running = threading.Event()
        self.ready = threading.Event()

    async def serve(self):
        """Start BAC0, register the objects, and keep the loop alive while running."""
        if not self.debug:
            BAC0.log_level("silence")
            logging.getLogger("bacpypes3").setLevel(logging.CRITICAL)

        try:
            self.bacnet = BAC0.start(
                ip=self.address,
                port=self.port,
                deviceId=self.device_id,
                localObjName="HVACSim",
                modelName="HVAC-Sim",
            )

            # Setpoint is a software parameter -> Analog Value (not an Analog Output).
            av_setpoint_f = analog_value(
                name="temperature_setpoint_c",
                instance=1,
                description="Desired room temperature (°C)",
                properties={"units": "degreesCelsius"},
                presentValue=self.state.setpoint_c,
                is_commandable=True,
            )
            # Fan speed commands drive physical actuators -> Analog Output
            # (natively commandable via its priority array).
            ao_intake_f = analog_output(
                name="intake_fan_speed_percent",
                instance=1,
                description="Intake fan speed (%)",
                presentValue=self.state.intake_pct,
            )
            ao_exhaust_f = analog_output(
                name="exhaust_fan_speed_percent",
                instance=2,
                description="Exhaust fan speed (%)",
                presentValue=self.state.exhaust_pct,
            )

            # Emergency stop is a software command flag -> Binary Value.
            bv_estop_f = binary_value(
                name="emergency_stop",
                instance=1,
                description="Emergency stop (True/False)",
                presentValue=self.state.estop,
                is_commandable=True,
            )

            # Sensor readings -> read-only Analog Input.
            ai_temp_f = analog_input(
                name="current_temperature_c",
                instance=1,
                description="Measured room temperature (°C)",
                properties={"units": "degreesCelsius"},
                presentValue=self.state.current_temp_c,
            )
            ai_chiller_f = analog_input(
                name="chiller_speed_percent",
                instance=2,
                description="Chiller load (%)",
                presentValue=self.state.chiller_pct,
            )

            factories = {
                "setpoint": (av_setpoint_f, "temperature_setpoint_c"),
                "intake": (ao_intake_f, "intake_fan_speed_percent"),
                "exhaust": (ao_exhaust_f, "exhaust_fan_speed_percent"),
                "estop": (bv_estop_f, "emergency_stop"),
                "temp": (ai_temp_f, "current_temperature_c"),
                "chiller": (ai_chiller_f, "chiller_speed_percent"),
            }
            for factory, _ in factories.values():
                factory.add_objects_to_application(self.bacnet)

            try:
                self.objects = {key: factory.objects[name] for key, (factory, name) in factories.items()}
            except KeyError as err:
                missing_key = err.args[0] if err.args else "<unknown>"
                raise RuntimeError(
                    f"Failed to create BACnet object '{missing_key}'. "
                    "Check BAC0 configuration and object factory definitions."
                ) from err

            # BAC0/bacpypes3 auto-adds a network-port object that cannot answer
            # ReadPropertyMultiple with property "all", so EPICS-style clients loop
            # on the error. Drop it so only the HVAC points are enumerated.
            try:
                local_app = self.bacnet.this_application.app
                for obj in list(local_app.iter_objects()):
                    oid = getattr(obj, "objectIdentifier", None)
                    if oid is not None and "network-port" in str(oid):
                        local_app.delete_object(obj)
            except Exception as e:
                logger.warning("Could not remove the network-port object: %s", e)

            logger.info("BACnet device %s listening on %s:%s", self.device_id, self.address.split("/")[0], self.port)
            self.ready.set()

            while self.running.is_set():
                await asyncio.sleep(1.0)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("BACnet device failed: %s", e)
        finally:
            self.ready.set()
            try:
                if self.bacnet:
                    self.bacnet.disconnect()
            except Exception as e:
                logger.warning("Error during BACnet disconnect: %s", e)

    def read_commands(self):
        commands = {
            "setpoint_c": float(self.objects["setpoint"].presentValue),
            "intake_pct": float(self.objects["intake"].presentValue),
            "exhaust_pct": float(self.objects["exhaust"].presentValue),
            "estop": bool(self.objects["estop"].presentValue),
        }
        for field, value in commands.items():
            if getattr(self.state, field) != value:
                logger.info("Write: %s %s -> %s", field, getattr(self.state, field), value)
                setattr(self.state, field, value)

    def write_outputs(self):
        self.objects["temp"].presentValue = self.state.current_temp_c
        self.objects["chiller"].presentValue = self.state.chiller_pct

    def control_loop(self):
        while self.running.is_set():
            try:
                self.read_commands()
                simulation_step(self.state)
                self.write_outputs()

                if int(time.time()) % 10 == 0:
                    s = self.state
                    logger.info(
                        "Tset=%.1f°C | T=%.1f°C | Airflow=%.0f%% | Chiller=%.0f%% | E-Stop=%s",
                        s.setpoint_c, s.current_temp_c, s.airflow_pct, s.chiller_pct,
                        "ON" if s.estop else "OFF",
                    )

                time.sleep(TICK_SECONDS)

            except Exception as e:
                logger.error("Error in control loop: %s", e)
                time.sleep(2.0)

    def run(self):
        def _stop(_sig, _frm):
            self.running.clear()

        signal.signal(signal.SIGINT, _stop)
        signal.signal(signal.SIGTERM, _stop)

        self.running.set()
        core_thread = threading.Thread(target=lambda: asyncio.run(self.serve()), name="bac0-core", daemon=True)
        core_thread.start()

        if not self.ready.wait(timeout=30.0):
            logger.error("BACnet objects failed to initialize within 30 seconds")
            self.running.clear()
            core_thread.join(timeout=5.0)
            return 1
        if len(self.objects) != 6:
            logger.error("BACnet initialization failed")
            self.running.clear()
            core_thread.join(timeout=5.0)
            return 1

        ctl_thread = threading.Thread(target=self.control_loop, name="hvac-loop", daemon=True)
        ctl_thread.start()

        try:
            while self.running.is_set():
                time.sleep(0.5)
        finally:
            self.running.clear()
            ctl_thread.join(timeout=5.0)
            core_thread.join(timeout=5.0)
            logger.info("Stopped")
        return 0


def main():
    parser = argparse.ArgumentParser(
        prog="python -m simulator.plc",
        description=f"{SIM['name']} PLC: a BACnet/IP device running the server room simulation.",
    )
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), metavar="PATH", help="configuration file (default: config.ini in the repo root)")
    parser.add_argument("--host", metavar="HOST", help="address to bind (default: address in the config, auto)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, metavar="PORT", help=f"BACnet/IP port (default: {DEFAULT_PORT})")
    parser.add_argument("--debug", action="store_true", help="debug logging")
    add_deprecated_alias(parser, "--ini", "--config")
    add_deprecated_alias(parser, "--address", "--host")
    args = parser.parse_args()

    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        level=logging.DEBUG if args.debug else logging.INFO,
    )
    warn_deprecated(args)
    logging.getLogger("BAC0_Root").propagate = False

    try:
        config = load_config(args.config)
        address = resolve_address(args.host or config.address)
    except Exception as e:
        logger.error("Invalid configuration in %s: %s", args.config, e)
        return 1
    return HVACPLC(config.device_id, address, args.port, args.debug).run()


if __name__ == "__main__":
    import warnings
    warnings.filterwarnings("ignore", message="no signal handlers for child threads")

    sys.exit(main())
