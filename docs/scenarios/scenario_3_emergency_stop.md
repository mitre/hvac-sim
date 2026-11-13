# Scenario 3: Emergency Stop

## Overview

| Field | Value |
|---|---|
| **Tactic** | Impair Process Control, Impact |
| **Techniques** | [T1692.001 - Unauthorized Message: Command Message](https://attack.mitre.org/techniques/T1692/001/), [T0826 - Loss of Availability](https://attack.mitre.org/techniques/T0826/) |
| **Adversary** | HVACSim BACnet Emergency Stop (`docs/adversaries/bacnet-emergency-stop.yml`) |
| **Fact source** | HVACSim Emergency Stop (`docs/sources/hvac-emergency-stop.yml`) |

## Description

The adversary sets the emergency stop object to active. The PLC accepts the unauthenticated write and forces airflow and the chiller target to 0 %, so a single write removes all cooling from the server room.

![HVACSim HMI emergency stop state](../images/scenario-3-emergency-stop.png)

## Facts Used

| Fact | Description | Type | Value |
|---|---|---|---|
| `bacnet.device.instance` | PLC device instance | int | `101` |
| `bacnet.object.type` | Object type for Object Collection | string | `analog-input` |
| `bacnet.object.instance` | Object instance for Object Collection | int | `2` (chiller load) |
| `bacnet.obj.type` | Object type for Write Property and Read Property | string | `binary-value` (emergency stop) |
| `bacnet.obj.instance` | Object instance for Write Property and Read Property | int | `1` (emergency stop) |
| `bacnet.obj.property` | Property to write or read | string | `present-value` |
| `bacnet.read.index` | Array index for reads | int | `-1` (no index) |
| `bacnet.write.priority` | Write priority | int | `8` (manual operator, the same as the HMI) |
| `bacnet.write.index` | Array index for writes | int | `-1` (no index) |
| `bacnet.write.tag` | Value type | int | `9` (enumerated) |
| `bacnet.write.value` | Value to write | int | `1` (active) |

## Control Data

| Control | BACnet Object | Value |
|---|---|---|
| `emergency_stop` | `binary-value 1 present-value` | `1` (active) |

## Steps

Run the adversary with the fact source above, or add these abilities to an operation in this order:

| # | Ability | ID | Facts |
|---|---|---|---|
| 1 | BACnet Object Collection - Basic | `bd13ac81-b932-463d-95aa-a22aeefbc9ac` | baseline: `bacnet.device.instance=101`, `bacnet.object.type=analog-input`, `bacnet.object.instance=2` |
| 2 | BACnet Write Property | `1a2faf5a-4601-11eb-b378-0242ac130002` | emergency stop: `bacnet.device.instance=101`, `bacnet.obj.type=binary-value`, `bacnet.obj.instance=1`, `bacnet.obj.property=present-value`, `bacnet.write.priority=8`, `bacnet.write.index=-1`, `bacnet.write.tag=9`, `bacnet.write.value=1` |
| 3 | BACnet Read Property | `47432648-5678-11eb-ae93-0242ac130002` | verify: `bacnet.device.instance=101`, `bacnet.obj.type=binary-value`, `bacnet.obj.instance=1`, `bacnet.obj.property=present-value`, `bacnet.read.index=-1` |

Each ability runs once.

## Expected Observations

- Object Collection reads `chiller_speed_percent` (analog-input 2) before the write: a percentage, around 25 % at the default setpoint.
- Write Property sets the emergency stop. The PLC logs `Write: estop False -> True`.
- While the emergency stop is active the PLC's status line shows `Airflow=0%` and `E-Stop=ON`, and the chiller load (analog-input 2) falls to about 0 % within 10 seconds.
- Read Property reads `binary-value 1 present-value` back and returns `active`, confirming the emergency stop is set.
- With no cooling the room temperature (analog-input 1) climbs toward about 29 °C.
- The HMI polls the PLC, so its emergency-stop button shows on and the chiller trend falls to 0 %.
