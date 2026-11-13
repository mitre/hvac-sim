# Scenario 2: Thermal Runaway

## Overview

| Field | Value |
|---|---|
| **Tactic** | Impair Process Control, Impact |
| **Techniques** | [T1692.001 - Unauthorized Message: Command Message](https://attack.mitre.org/techniques/T1692/001/), [T0836 - Modify Parameter](https://attack.mitre.org/techniques/T0836/), [T0831 - Manipulation of Control](https://attack.mitre.org/techniques/T0831/), [T0826 - Loss of Availability](https://attack.mitre.org/techniques/T0826/) |
| **Adversary** | HVACSim BACnet Thermal Runaway (`docs/adversaries/bacnet-thermal-runaway.yml`) |
| **Fact source** | HVACSim Thermal Runaway (`docs/sources/hvac-thermal-runaway.yml`) |

## Description

The adversary raises the temperature setpoint above the room temperature, so the chiller's controller stops cooling. The PLC accepts the unauthenticated write at the same priority as the HMI, so it replaces the operator's value. With the chiller off, the room heats toward the temperature set by ambient heat and server load. The chiller is the dominant cooling control, so raising the setpoint alone drives the runaway; forcing the fans off as well is a manual exercise below.

![HVACSim HMI thermal runaway state](../images/scenario-2-thermal-runaway.png)

## Facts Used

| Fact | Description | Type | Value |
|---|---|---|---|
| `bacnet.device.instance` | PLC device instance | int | `101` |
| `bacnet.object.type` | Object type for Object Collection | string | `analog-input` |
| `bacnet.object.instance` | Object instance for Object Collection | int | `1` (room temperature) |
| `bacnet.obj.type` | Object type for Write Property and Read Property | string | `analog-value` (setpoint) |
| `bacnet.obj.instance` | Object instance for Write Property and Read Property | int | `1` (setpoint) |
| `bacnet.obj.property` | Property to write or read | string | `present-value` |
| `bacnet.read.index` | Array index for reads | int | `-1` (no index) |
| `bacnet.write.priority` | Write priority | int | `8` (manual operator, the same as the HMI) |
| `bacnet.write.index` | Array index for writes | int | `-1` (no index) |
| `bacnet.write.tag` | Value type | int | `4` (real) |
| `bacnet.write.value` | Value to write | int | `40` (setpoint) |

## Control Data

| Control | BACnet Object | Value |
|---|---|---|
| `temperature_setpoint_c` | `analog-value 1 present-value` | `40` |

## Steps

Run the adversary with the fact source above, or add these abilities to an operation in this order:

| # | Ability | ID | Facts |
|---|---|---|---|
| 1 | BACnet Object Collection - Basic | `bd13ac81-b932-463d-95aa-a22aeefbc9ac` | baseline: `bacnet.device.instance=101`, `bacnet.object.type=analog-input`, `bacnet.object.instance=1` |
| 2 | BACnet Write Property | `1a2faf5a-4601-11eb-b378-0242ac130002` | setpoint: `bacnet.device.instance=101`, `bacnet.obj.type=analog-value`, `bacnet.obj.instance=1`, `bacnet.obj.property=present-value`, `bacnet.write.priority=8`, `bacnet.write.index=-1`, `bacnet.write.tag=4`, `bacnet.write.value=40` |
| 3 | BACnet Read Property | `47432648-5678-11eb-ae93-0242ac130002` | verify: `bacnet.device.instance=101`, `bacnet.obj.type=analog-value`, `bacnet.obj.instance=1`, `bacnet.obj.property=present-value`, `bacnet.read.index=-1` |

Each ability runs once.

## Expected Observations

- Object Collection reads `current_temperature_c` (analog-input 1) before the write: about 22-24 °C at the default setpoint.
- Write Property changes the setpoint. The PLC logs `Write: setpoint_c 23.0 -> 40.0`.
- With the setpoint above the room temperature the chiller controller stops cooling: the chiller load (analog-input 2) falls to about 0 % within 10 seconds, and the room temperature (analog-input 1) climbs toward about 28 °C (toward 29 °C if the fans are also turned off).
- Read Property reads `analog-value 1 present-value` back and returns `40.0`, confirming the write persisted at operator priority.
- The HMI polls the PLC, so its dashboard shows the setpoint at 40 °C and the temperature trend climbing.

## Manual Exercise: Force the Fans Off

To also force both fans off, edit the Write Property link's facts by hand (the operation UI lets you edit a link before it runs) to write each fan to `0`:

- Intake fan: `bacnet.obj.type=analog-output`, `bacnet.obj.instance=1`, `bacnet.write.tag=4`, `bacnet.write.value=0`
- Exhaust fan: `bacnet.obj.type=analog-output`, `bacnet.obj.instance=2`, `bacnet.write.tag=4`, `bacnet.write.value=0`

The PLC logs `Write: intake_pct 30.0 -> 0.0` and `Write: exhaust_pct 30.0 -> 0.0`, and the room then settles nearer 29 °C.
