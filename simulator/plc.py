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
    python3 -m simulator.plc --ini ./config.ini

Authors:
    Capstone Group:
        University of Hawaii at Manoa Group 9 2025

    Developers:
        * Jake Dickinson
        * Elijah Saloma

    Advisor:
        * Samir Boussarhane
"""

import argparse
import asyncio
import signal
import threading
import time

import BAC0
from BAC0.core.devices.local.factory import (
    analog_input,
    analog_output,
    analog_value,
    binary_value,
)

from simulator.config import load_config
from simulator.network import resolve_address
from simulator.sim import TICK_SECONDS, SimulationState, simulation_step


class HVACPLC:
    def __init__(self, device_id, address, debug=False):
        self.device_id = device_id
        self.address = address
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

        try:
            self.bacnet = BAC0.start(ip=self.address, deviceId=self.device_id)

            self.bacnet.this_application.objectName = "HVACSim"
            self.bacnet.this_application.vendorName = "HVACSim"
            self.bacnet.this_application.modelName = "HVAC-Sim"
            self.bacnet.this_application.firmwareRevision = "1.0"
            self.bacnet.this_application.description = "HVAC Simulation Device"

            # Setpoint is a software parameter -> Analog Value (not an Analog Output).
            av_setpoint_f = analog_value(
                name="temperature_setpoint_c",
                instance=1,
                description="Desired room temperature (°C)",
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
                    f"[HVACSim] Failed to create BACnet object '{missing_key}'. "
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
                print(f"[HVACSim] Warning: could not remove network-port object: {e}")

            print(f"[HVACSim] BACnet device ready on {self.address} (ID {self.device_id})")
            self.ready.set()

            while self.running.is_set():
                await asyncio.sleep(1.0)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[HVACSim] Failed to initialize or run BACnet device: {e}")
        finally:
            self.ready.set()
            try:
                if self.bacnet:
                    self.bacnet.disconnect()
            except Exception as e:
                print(f"[HVACSim] Warning: Error during BACnet disconnect: {e}")

    def read_commands(self):
        self.state.setpoint_c = float(self.objects["setpoint"].presentValue)
        self.state.intake_pct = float(self.objects["intake"].presentValue)
        self.state.exhaust_pct = float(self.objects["exhaust"].presentValue)
        self.state.estop = bool(self.objects["estop"].presentValue)

    def write_outputs(self):
        self.objects["temp"].presentValue = self.state.current_temp_c
        self.objects["chiller"].presentValue = self.state.chiller_pct

    def control_loop(self):
        print("[HVACSim] Control loop started.")
        while self.running.is_set():
            try:
                self.read_commands()
                simulation_step(self.state)
                self.write_outputs()

                if int(time.time()) % 10 == 0:
                    s = self.state
                    print(
                        f"Tset={s.setpoint_c:.1f}°C | T={s.current_temp_c:.1f}°C | "
                        f"Airflow={s.airflow_pct:.0f}% | Chiller={s.chiller_pct:.0f}% | "
                        f"E-Stop={'ON' if s.estop else 'OFF'}"
                    )

                time.sleep(TICK_SECONDS)

            except Exception as e:
                print(f"[HVACSim] Error in loop: {e}")
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
            print("[HVACSim] Error: BACnet objects failed to initialize within 30 seconds; shutting down.")
            self.running.clear()
            core_thread.join(timeout=5.0)
            return
        if len(self.objects) != 6:
            print("[HVACSim] Error: BACnet initialization failed; shutting down.")
            self.running.clear()
            core_thread.join(timeout=5.0)
            return

        ctl_thread = threading.Thread(target=self.control_loop, name="hvac-loop", daemon=True)
        ctl_thread.start()

        print("[HVACSim] Running headless; press Ctrl+C to stop.")
        try:
            while self.running.is_set():
                time.sleep(0.5)
        finally:
            self.running.clear()
            ctl_thread.join(timeout=5.0)
            core_thread.join(timeout=5.0)
            print("[HVACSim] Shut down.")


def main():
    parser = argparse.ArgumentParser(description="BACnet HVAC Simulation Device")
    parser.add_argument("--ini", default="./config.ini", help="Path to INI file")
    parser.add_argument("--debug", action="store_true", help="Enable verbose BACnet logging")
    parser.add_argument("--address", default=None, help="Override the config address, e.g. 'auto' in a container")
    args = parser.parse_args()

    config = load_config(args.ini)
    address = resolve_address(args.address or config.address)
    HVACPLC(config.device_id, address, args.debug).run()


if __name__ == "__main__":
    import warnings
    warnings.filterwarnings("ignore", message="no signal handlers for child threads")

    main()
