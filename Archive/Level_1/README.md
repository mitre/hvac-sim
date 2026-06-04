# Level 1

BACnet/IP device simulator built with BACpypes. It represents a generic building automation device that can be discovered over the network by Caldera for OT (using the BACnet plugin).

The simulator reads configuration values (device name, IP address, etc) from an INI file and binds them to an IP interface (e.g., 192.168.x.x/24). Once a Caldera agent is created and an operation with a discovery command such as Who-Is (`.\bacwi`) is executed, the simulator responds accordingly.

Level 1 serves as the baseline checkpoint to verify that Caldera's BACnet abilities are properly configured and functioning before progressing to more complex building automation device simulations.

The device simulation can be started with the following command:

```bash
python3 bacnet_device.py --ini ./BACpypes.ini --debug bacpypes.udp
```
