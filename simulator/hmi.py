"""
HMI for the HVAC BACnet simulator: a separate BACnet client that polls the
device with ReadProperty and sends operator writes with WriteProperty, then
draws the dashboard from what it read. Serve it in a browser with --web
(matplotlib WebAgg). Run it on a different host or container than the device:
BACnet/IP needs UDP 47808 on each end.

To run:
    python3 -m simulator.hmi --device-ip 192.168.1.50
    python3 -m simulator.hmi --device-ip 192.168.1.50 --web --web-port 8090

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
import queue
import socket
import threading
import time
from collections import deque

import BAC0

from simulator.network import primary_ip, primary_prefix

# Our own client instance, kept off the server's 101 so they do not collide.
CLIENT_DEVICE_ID = 9101
POLL_SECONDS = 1.0
WRITE_PRIORITY = 8

# control name -> (object type, instance)
OBJECTS = {
    "setpoint": ("analogValue", 1),
    "intake": ("analogOutput", 1),
    "exhaust": ("analogOutput", 2),
    "estop": ("binaryValue", 1),
}


class State:
    def __init__(self):
        self.current_temp_c = 22.0
        self.setpoint_c = 23.0
        self.intake_pct = 30.0
        self.exhaust_pct = 30.0
        self.chiller_pct = 30.0
        self.estop = False
        self.connected = False


def _as_bool(present_value):
    return str(present_value).strip().lower() in ("active", "1", "true")


async def _whois(bacnet, device_id=None):
    return await bacnet.this_application.app.who_is(device_id, device_id)


async def poll_device(bacnet, addr, device_id, state, lock, data_buf):
    """Read every point over BACnet and push it into state/data_buf."""
    while True:
        try:
            temp = float(await bacnet.read(f"{addr} analogInput 1 presentValue"))
            chiller = float(await bacnet.read(f"{addr} analogInput 2 presentValue"))
            setp = float(await bacnet.read(f"{addr} analogValue 1 presentValue"))
            intake = float(await bacnet.read(f"{addr} analogOutput 1 presentValue"))
            exhaust = float(await bacnet.read(f"{addr} analogOutput 2 presentValue"))
            estop = _as_bool(await bacnet.read(f"{addr} binaryValue 1 presentValue"))

            now = time.time()
            with lock:
                state.current_temp_c = temp
                state.chiller_pct = chiller
                state.setpoint_c = setp
                state.intake_pct = intake
                state.exhaust_pct = exhaust
                state.estop = estop
                state.connected = True
                data_buf["time"].append(now)
                data_buf["temp"].append(temp)
                data_buf["setp"].append(setp)
                data_buf["chill"].append(chiller)
                data_buf["intake"].append(intake)
                data_buf["exhaust"].append(exhaust)

            if int(now) % 10 == 0:
                print(
                    f"[HMI] Tset={setp:.1f}°C | T={temp:.1f}°C | "
                    f"Intake={intake:.0f}% | Exhaust={exhaust:.0f}% | "
                    f"Chiller={chiller:.0f}% | E-Stop={'ON' if estop else 'OFF'}"
                )

        except Exception as e:
            with lock:
                state.connected = False
            print(f"[HMI] Read failed: {e}; rediscovering")
            try:
                await _whois(bacnet, device_id)
            except Exception:
                pass

        await asyncio.sleep(POLL_SECONDS)


async def send_commands(bacnet, addr, cmd_q):
    """Drain operator writes and push them out with WriteProperty."""
    while True:
        try:
            control, value = cmd_q.get_nowait()
        except queue.Empty:
            await asyncio.sleep(0.1)
            continue

        obj_type, instance = OBJECTS[control]
        if control == "estop":
            payload = "active" if value else "inactive"
        else:
            payload = f"{float(value):.2f}"

        args = f"{addr} {obj_type} {instance} presentValue {payload} - {WRITE_PRIORITY}"
        try:
            await bacnet._write(args)
            print(f"[HMI] WRITE {control} <- {payload}")
        except Exception as e:
            print(f"[HMI] Write failed ({control}={payload}): {e}")


async def run_io(device_ip, device_id, client_ip, state, lock, cmd_q, data_buf):
    bacnet = BAC0.lite(ip=client_ip, deviceId=CLIENT_DEVICE_ID, ping=False)
    await asyncio.sleep(2.0)
    print(f"[HMI] BACnet client ready on {client_ip} (ID {CLIENT_DEVICE_ID})")

    # A directed WhoIs (what BAC0.read falls back to) is answered unreliably
    # here, so a broadcast WhoIs seeds the address cache and later reads skip it.
    for _ in range(30):
        if await _whois(bacnet, device_id):
            break
        await asyncio.sleep(2.0)
    print(f"[HMI] Talking to device {device_id} at {device_ip}")

    await asyncio.gather(
        poll_device(bacnet, device_ip, device_id, state, lock, data_buf),
        send_commands(bacnet, device_ip, cmd_q),
    )


def main():
    parser = argparse.ArgumentParser(description="Web HMI client for the HVAC BACnet device")
    parser.add_argument("--device-ip", required=True, help="IP or hostname of the HVAC BACnet device")
    parser.add_argument("--device-id", type=int, default=101, help="Device instance (default 101)")
    parser.add_argument("--web", action="store_true", help="Serve the HMI in a browser (WebAgg)")
    parser.add_argument("--web-port", type=int, default=8090, help="Web HMI port (default 8090)")
    parser.add_argument("--fahrenheit", action="store_true", help="Display temperatures in Fahrenheit")
    parser.add_argument("--client-cidr", type=int, help="Client bind prefix; match the device subnet for Who-Is (default: detected from the interface, else 24)")
    args = parser.parse_args()

    import matplotlib
    if args.web:
        matplotlib.use("WebAgg")
    import matplotlib.pyplot as plt
    from simulator.ui.desktop_ui import _webagg_fill_window, start_plot

    # accept a hostname (e.g. the docker service name) or an IP; retry so the
    # HMI can start before the device's name resolves
    device_ip = args.device_ip
    for _ in range(60):
        try:
            device_ip = socket.gethostbyname(args.device_ip)
            break
        except socket.gaierror:
            time.sleep(2)

    BAC0.log_level("silence")

    if args.web:
        plt.rcParams["webagg.address"] = "0.0.0.0"
        plt.rcParams["webagg.port"] = args.web_port
        plt.rcParams["webagg.open_in_browser"] = False
        _webagg_fill_window()

    state = State()
    lock = threading.Lock()
    cmd_q = queue.Queue()
    data_buf = {k: deque(maxlen=600) for k in ["time", "temp", "setp", "chill", "intake", "exhaust"]}

    ip = primary_ip()
    client_ip = f"{ip}/{args.client_cidr if args.client_cidr is not None else primary_prefix(ip)}"

    def run_loop():
        asyncio.run(run_io(device_ip, args.device_id, client_ip, state, lock, cmd_q, data_buf))

    threading.Thread(target=run_loop, name="bacnet-io", daemon=True).start()

    # Wait for the first reads so the sliders start from live values.
    for _ in range(100):
        with lock:
            if state.connected:
                break
        time.sleep(0.1)

    use_fahrenheit = args.fahrenheit
    start_plot(data_buf, state, lock, cmd_q, use_fahrenheit=use_fahrenheit)


if __name__ == "__main__":
    import warnings
    warnings.filterwarnings("ignore", message="no signal handlers for child threads")

    main()
