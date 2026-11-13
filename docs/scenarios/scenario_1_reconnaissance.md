# Scenario 1: Reconnaissance

## Overview

| Field | Value |
|---|---|
| **Tactic** | Discovery, Collection |
| **Techniques** | [T0846 - Remote System Discovery](https://attack.mitre.org/techniques/T0846/), [T0888 - Remote System Information Discovery](https://attack.mitre.org/techniques/T0888/), [T0861 - Point & Tag Identification](https://attack.mitre.org/techniques/T0861/) |
| **Adversary** | HVACSim BACnet Reconnaissance (`docs/adversaries/bacnet-reconnaissance.yml`) |
| **Fact source** | HVACSim Facts (`docs/sources/hvac-simulator-facts.yml`) |

## Description

The adversary finds HVACSim on the network with a Who-Is broadcast, reads the device's identity and object list, and reads the room temperature and chiller load. BACnet has no authentication, so the PLC answers every request. Nothing is written, so the process does not change.

![HVACSim HMI baseline state](../images/scenario-1-reconnaissance.png)

## Facts Used

| Fact | Description | Type | Value |
|---|---|---|---|
| `bacnet.device.instance` | PLC device instance | int | `101` |
| `bacnet.object.type` | Object type for Object Collection | string | `analog-input` |
| `bacnet.object.instance` | Object instance for Object Collection | int | `1` (room temperature), `2` (chiller load) |
| `bacnet.obj.type` | Object type for Read Property | string | `device`, `analog-input` |
| `bacnet.obj.instance` | Object instance for Read Property | int | `101` (device), `1`, `2` |
| `bacnet.obj.property` | Property for Read Property | int or string | `76` (object-list), `present-value` |
| `bacnet.read.index` | Array index | int | `-1` (no index, whole property) |

## Steps

Run the adversary with the fact source above, or add these abilities to an operation in this order:

| # | Ability | ID | Facts |
|---|---|---|---|
| 1 | BACnet Who-Is | `b93bd80e-3a70-11eb-adc1-0242ac120002` | discover: none |
| 2 | BACnet Device Collection - Basic | `485e97e7-c352-432d-b8d3-fa8460e4fe49` | identify: none |
| 3 | BACnet Object Collection - Basic | `bd13ac81-b932-463d-95aa-a22aeefbc9ac` | points: `bacnet.object.type=analog-input`, `bacnet.object.instance=1`, `bacnet.object.instance=2` |
| 4 | BACnet Read Property | `47432648-5678-11eb-ae93-0242ac130002` | object list: `bacnet.obj.type=device`, `bacnet.obj.instance=101`, `bacnet.obj.property=76`, `bacnet.read.index=-1` |

## Expected Observations

- Who-Is lists device `101`. In the Docker lab the HMI's own BACnet client answers as well, as device `9101`, and Caldera then runs the later abilities against both; the reads against `9101` return `BACnet Error` because it carries no HVAC objects.
- Device Collection returns object-name `HVACSim`, model-name `HVAC-Sim` and the object list.
- Object Collection returns `current_temperature_c` (analog-input 1, degrees-celsius, about 22-24 °C at the default setpoint) and `chiller_speed_percent` (analog-input 2, percent, 0-100).
- Read Property returns the object list: `(device, 101)`, `(analog-value, 1)`, `(analog-output, 1)`, `(analog-output, 2)`, `(binary-value, 1)`, `(analog-input, 1)`, `(analog-input, 2)`.
- Caldera also runs Read Property with the other `bacnet.obj.*` combinations in the source. Those return the present values of analog-input 1 and 2, or `BACnet Error` for objects or properties the device does not have.
- The PLC logs no `Write:` lines and the HMI does not change.
