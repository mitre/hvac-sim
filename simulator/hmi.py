"""
HMI for the HVAC BACnet simulator: a separate BACnet client that polls the
device with ReadProperty and sends operator writes with WriteProperty, then
draws the dashboard from what it read. Serve it in a browser with --web
(matplotlib WebAgg). Run it on a different host or container than the device:
BACnet/IP needs UDP 47808 on each end.

To run:
    python -m simulator.hmi --host 192.168.1.50
    python -m simulator.hmi --host 192.168.1.50 --web --web-port 8090
"""

import argparse
import asyncio
import logging
import queue
import signal
import socket
import sys
import threading
import time
from collections import deque

import BAC0
from bacpypes3.pdu import Address

from simulator import SIM
from simulator.cli import add_deprecated_alias, warn_deprecated
from simulator.network import primary_ip, primary_prefix

PROTOCOL = SIM["protocols"]["bacnet"]
DEFAULT_PORT = PROTOCOL["port"]
TITLE = f"{PROTOCOL['name']} - {SIM['name']}"

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

logger = logging.getLogger(__name__)


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


async def _whois(bacnet, device_id=None, addr=None):
    app = bacnet.this_application.app
    found = await app.who_is(device_id, device_id)
    if not found and addr:
        found = await app.who_is(device_id, device_id, address=Address(addr))
    return found


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
                logger.info(
                    "Tset=%.1f°C | T=%.1f°C | Intake=%.0f%% | Exhaust=%.0f%% | Chiller=%.0f%% | E-Stop=%s",
                    setp, temp, intake, exhaust, chiller, "ON" if estop else "OFF",
                )

        except Exception as e:
            with lock:
                state.connected = False
            logger.warning("Read failed: %s; rediscovering", e)
            try:
                await _whois(bacnet, device_id, addr)
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
            logger.info("Write: %s <- %s", control, payload)
        except Exception as e:
            logger.error("Write failed (%s=%s): %s", control, payload, e)


async def run_io(device_addr, device_id, client_ip, state, lock, cmd_q, data_buf):
    bacnet = BAC0.lite(ip=client_ip, deviceId=CLIENT_DEVICE_ID, ping=False)
    await asyncio.sleep(2.0)
    logger.info("BACnet client %s on %s", CLIENT_DEVICE_ID, client_ip)

    # A directed WhoIs (what BAC0.read falls back to) is answered unreliably
    # here, so a broadcast WhoIs seeds the address cache and later reads skip it.
    # The broadcast only reaches the default port, so a PLC on another port gets
    # the directed one.
    for _ in range(30):
        if await _whois(bacnet, device_id, device_addr):
            break
        await asyncio.sleep(2.0)

    await asyncio.gather(
        poll_device(bacnet, device_addr, device_id, state, lock, data_buf),
        send_commands(bacnet, device_addr, cmd_q),
    )


def _interrupt(_sig, _frm):
    raise KeyboardInterrupt


def main():
    parser = argparse.ArgumentParser(
        prog="python -m simulator.hmi",
        description=f"{SIM['name']} HMI: polls the PLC over BACnet/IP and draws the dashboard.",
    )
    parser.add_argument("--host", default="127.0.0.1", metavar="HOST", help="PLC to poll (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, metavar="PORT", help=f"PLC port (default: {DEFAULT_PORT})")
    parser.add_argument("--web", action="store_true", help="serve the HMI as a web page instead of a desktop window")
    parser.add_argument("--web-port", type=int, default=8090, metavar="PORT", help="web HMI port (default: 8090)")
    parser.add_argument("--device-id", type=int, default=101, metavar="ID", help="PLC device instance (default: 101)")
    parser.add_argument("--fahrenheit", action="store_true", help="show temperatures in Fahrenheit")
    parser.add_argument("--client-cidr", type=int, metavar="PREFIX", help="prefix length for the HMI's own BACnet address; match the PLC's subnet (default: read from the interface, else 24)")
    parser.add_argument("--debug", action="store_true", help="debug logging")
    add_deprecated_alias(parser, "--device-ip", "--host")
    args = parser.parse_args()

    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        level=logging.DEBUG if args.debug else logging.INFO,
    )
    warn_deprecated(args)
    logging.getLogger("BAC0_Root").propagate = False
    logging.getLogger("tornado.access").setLevel(logging.WARNING)
    signal.signal(signal.SIGTERM, _interrupt)
    try:
        run(args)
    except KeyboardInterrupt:
        pass
    logger.info("Stopped")
    return 0


def run(args):
    import matplotlib
    if args.web:
        matplotlib.use("WebAgg")
    import matplotlib.pyplot as plt
    from simulator.ui.desktop_ui import _webagg_fill_window, start_plot

    # accept a hostname (e.g. the docker service name) or an IP; retry so the
    # HMI can start before the device's name resolves
    device_ip = args.host
    for _ in range(60):
        try:
            device_ip = socket.gethostbyname(args.host)
            break
        except socket.gaierror:
            time.sleep(2)
    device_addr = f"{device_ip}:{args.port}"

    if not args.debug:
        BAC0.log_level("silence")
        logging.getLogger("bacpypes3").setLevel(logging.CRITICAL)

    if args.web:
        plt.rcParams["webagg.address"] = "0.0.0.0"
        plt.rcParams["webagg.port"] = args.web_port
        plt.rcParams["webagg.open_in_browser"] = False
        _webagg_fill_window(TITLE)

    state = State()
    lock = threading.Lock()
    cmd_q = queue.Queue()
    data_buf = {k: deque(maxlen=600) for k in ["time", "temp", "setp", "chill", "intake", "exhaust"]}

    ip = primary_ip()
    client_ip = f"{ip}/{args.client_cidr if args.client_cidr is not None else primary_prefix(ip)}"

    def run_loop():
        asyncio.run(run_io(device_addr, args.device_id, client_ip, state, lock, cmd_q, data_buf))

    logger.info("Polling PLC at %s:%s", args.host, args.port)
    threading.Thread(target=run_loop, name="bacnet-io", daemon=True).start()

    # Wait for the first reads so the sliders start from live values.
    for _ in range(100):
        with lock:
            if state.connected:
                break
        time.sleep(0.1)

    if args.web:
        logger.info("Web HMI at http://0.0.0.0:%s", args.web_port)
    start_plot(data_buf, state, lock, cmd_q, use_fahrenheit=args.fahrenheit, title=TITLE)


if __name__ == "__main__":
    import warnings
    warnings.filterwarnings("ignore", message="no signal handlers for child threads")

    sys.exit(main())
