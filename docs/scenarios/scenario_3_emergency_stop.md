# Scenario 3: Emergency Stop

## Overview

| Field | Value |
|---|---|
| **Tactic** | Impair Process Control, Impact |
| **Techniques** | [T0855 - Unauthorized Command Message](https://attack.mitre.org/techniques/T0855/), [T0826 - Loss of Availability](https://attack.mitre.org/techniques/T0826/) |
| **Target** | HVACSim device over BACnet |
| **Impact** | The emergency stop halts fans and chiller, removing all cooling |

## Objective

Assert the emergency stop object over BACnet. HVACSim forces airflow and chiller
target to 0 when emergency stop is active, so a single unauthorized write removes
all cooling from the server room.

## BACnet Variant

Load `docs/sources/hvac-simulator-facts.yml` as the fact source, then
build an operation using the BACnet abilities below.

### Fact Variables

| Fact | Description | Type | Default |
|---|---|---|---|
| `bacnet.device.instance` | HVACSim device instance | int | `101` |
| `bacnet.obj.type` | Writable object type | string | `binary-value` |
| `bacnet.obj.instance` | Object instance | int | `1` |
| `bacnet.obj.property` | Property to write | string | `present-value` |
| `bacnet.write.priority` | BACnet write priority | int | `8` |
| `bacnet.write.index` | BACnet write index | int | `-1` |
| `bacnet.write.tag` | Datatype tag (enumerated = 9) | int | `9` |
| `bacnet.write.value` | Value to write (1 = active) | int | `1` |

Control data:

| Control | BACnet Object | Value |
|---|---|---|
| Emergency stop | `binary-value 1 present-value` | active |

### Caldera Operation

| Step | Ability | Ability ID | Facts Used |
|---|---|---|---|
| 1 | BACnet Object Collection - Basic | `bd13ac81-b932-463d-95aa-a22aeefbc9ac` | baseline read |
| 2 | BACnet Write Property | `1a2faf5a-4601-11eb-b378-0242ac130002` | `binary-value 1`, value active (emergency stop) |
| 3 | BACnet Read Property | `47432648-5678-11eb-ae93-0242ac130002` | `analog-input 2` (chiller falling to 0) |

## Expected Observations

- The write is accepted with no authentication.
- The HMI emergency-stop button flips to ON.
- Airflow and chiller target are forced to 0; chiller load (AI:2) falls toward 0.
- With cooling removed, room temperature drifts up over time.

## See Also

- [Caldera for OT](https://github.com/mitre/caldera-ot)
- [ATT&CK for ICS - T0855](https://attack.mitre.org/techniques/T0855/)
- [ATT&CK for ICS - T0826](https://attack.mitre.org/techniques/T0826/)
