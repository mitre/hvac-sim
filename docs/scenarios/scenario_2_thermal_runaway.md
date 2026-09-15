# Scenario 2: Thermal Runaway

## Overview

| Field | Value |
|---|---|
| **Tactic** | Impair Process Control, Impact |
| **Techniques** | [T0836 - Modify Parameter](https://attack.mitre.org/techniques/T0836/), [T0855 - Unauthorized Command Message](https://attack.mitre.org/techniques/T0855/), [T0826 - Loss of Availability](https://attack.mitre.org/techniques/T0826/) |
| **Target** | HVACSim device over BACnet |
| **Impact** | Cooling is defeated; room temperature climbs toward the thermal ceiling |

## Objective

Raise the temperature setpoint so the controller stops calling for cooling, then
force both fans off, defeating airflow cooling. With no active cooling the room
heats toward its modeled ceiling.

## BACnet Variant

Load `docs/sources/hvac-simulator-facts.yml` as the fact source, then
build an operation using the BACnet abilities below.

### Fact Variables

| Fact | Description | Type | Default |
|---|---|---|---|
| `bacnet.device.instance` | HVACSim device instance | int | `101` |
| `bacnet.obj.type` | Writable object type | string | `analog-value`, `analog-output` |
| `bacnet.obj.instance` | Object instance | int | `1`, `2` |
| `bacnet.obj.property` | Property to write | string | `present-value` |
| `bacnet.write.priority` | BACnet write priority | int | `8` |
| `bacnet.write.index` | BACnet write index | int | `-1` |
| `bacnet.write.tag` | Datatype tag (real = 4) | int | `4` |
| `bacnet.write.value` | Value to write | int | `40`, `0` |

Control data:

| Control | BACnet Object | Value |
|---|---|---|
| Temperature setpoint | `analog-value 1 present-value` | `40` |
| Intake fan | `analog-output 1 present-value` | `0` |
| Exhaust fan | `analog-output 2 present-value` | `0` |

### Caldera Operation

| Step | Ability | Ability ID | Facts Used |
|---|---|---|---|
| 1 | BACnet Object Collection - Basic | `bd13ac81-b932-463d-95aa-a22aeefbc9ac` | baseline read |
| 2 | BACnet Write Property | `1a2faf5a-4601-11eb-b378-0242ac130002` | `analog-value 1`, value 40 (raise setpoint) |
| 3 | BACnet Write Property | `1a2faf5a-4601-11eb-b378-0242ac130002` | `analog-output 1`, value 0 (intake fan off) |
| 4 | BACnet Write Property | `1a2faf5a-4601-11eb-b378-0242ac130002` | `analog-output 2`, value 0 (exhaust fan off) |
| 5 | BACnet Read Property | `47432648-5678-11eb-ae93-0242ac130002` | `analog-input 1` (temperature rising) |

## Expected Observations

- All writes are accepted with no authentication.
- The PI loop stops calling for chilling once the setpoint sits above room temperature, so chiller load falls toward 0.
- Airflow drops to 0% with both fans off.
- Room temperature (AI:1) climbs on the HMI trend and approaches the modeled ceiling.

## See Also

- [Caldera for OT](https://github.com/mitre/caldera-ot)
- [ATT&CK for ICS - T0836](https://attack.mitre.org/techniques/T0836/)
- [ATT&CK for ICS - T0855](https://attack.mitre.org/techniques/T0855/)
- [ATT&CK for ICS - T0826](https://attack.mitre.org/techniques/T0826/)
