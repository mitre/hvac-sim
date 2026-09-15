# HVACSim: BACnet Server Room HVAC Simulator

A simulated HVAC control system using BACnet/IP, designed as a companion to **Caldera for OT** for red/blue-team exercises involving cyber–physical systems.

## Authors

Created by University of Hawaii at Manoa Students for Capstone Project:
Elijah Saloma and Jake Dickinson

In collaboration with Caldera for OT tools ([ot@mitre.org](mailto:ot@mitre.org)).

The students' original BACpypes version is preserved on the `bacpypes` branch. This version moves to the bac0 library, uses standard BACnet object types, and adds Caldera scenarios and a docker lab.

![HMI](./docs/images/Demo.gif)

## Description

**HVACSim** provides a realistic, software-only BACnet simulation of a server-room HVAC controller. The system exposes writable BACnet objects (setpoint, fans, emergency stop) and simulates:

* Temperature dynamics
* Chiller load and PI feedback loop
* Sensor noise and an actuator lag
* An HMI with sliders, trend charts, and an emergency-stop; the HMI is intended to easily observe overrides by the Caldera for OT client.

This allows cybersecurity practitioners to emulate attacks against building HVAC systems without requiring physical industrial hardware. When paired with the [Caldera BACnet plugin](https://github.com/mitre/bacnet), HVACSim becomes an OT testbed for reconnaissance, manipulation, and response.

## Getting Started
For a detailed walkthrough, please read our medium article on HVACSim! https://medium.com/@mitrecaldera/caldera-for-ot-hvacsim-expanding-access-to-ot-security-education-c4fcc47396ab

### Dependencies

* Python 3.10+
* `matplotlib` (for the HMI)
* `bac0` (BACnet helper library; provides BACnet/IP via BACpypes3)
* Should run on Linux, macOS, or Windows
* **Caldera** with its BACnet plugin

  * [Caldera installation instructions](https://github.com/apache/caldera?tab=readme-ov-file#requirements)

**Linux users:** Install system packages for matplotlib GUI support:

```bash
# Ubuntu/Debian
sudo apt-get install python3-tk

# Fedora/RHEL
sudo dnf install python3-tkinter
```

### Installation

1. Clone the repository:

```bash
git clone https://github.com/mitre/hvac-sim.git
```

2. Install Python dependencies:

```bash
pip install -r requirements.txt
```

3. You can provide an INI-style config file to set the device instance and network address. Example provided in repo root (`config.ini`):

```
[HVACSim]
objectIdentifier = 101
address = 127.0.0.1/24
temperature_unit = celsius
```

> **Temperature units:** Set `temperature_unit` to `celsius` or `fahrenheit` to choose the display unit used in the HMI visualization. The BACnet objects always use °C internally; this setting only affects what is shown on screen.

## BACnet Object Map

The simulator exposes the following BACnet objects:

Object types follow standard BACnet/HVAC practice: sensors are Analog Inputs,
fan actuator commands are Analog Outputs, the setpoint is an Analog Value, and
the emergency stop is a Binary Value. Instances are numbered per type from 1.

| Type    | Object Name                 | Access      | Description                          |
| ------- | --------------------------- | ----------- | ------------------------------------ |
| **AV:1** | `temperature_setpoint_c`   | commandable | Desired room temperature (°C)        |
| **AO:1** | `intake_fan_speed_percent` | commandable | Intake fan command (0–100%)          |
| **AO:2** | `exhaust_fan_speed_percent`| commandable | Exhaust fan command (0–100%)         |
| **BV:1** | `emergency_stop`           | commandable | Safety kill switch for chiller/fans  |
| **AI:1** | `current_temperature_c`    | read-only   | Measured room temperature (°C)       |
| **AI:2** | `chiller_speed_percent`    | read-only   | PI-controlled chiller load (%)       |

## Usage

### Step 1: Start the Simulator

```bash
python3 hvac_sim.py --ini ./config.ini
```

Launching the script does three things:

1. Starts the BACnet/IP device
2. Spawns the HVAC control loop thread
3. Opens the interactive HMI dashboard

If the program fails to start, verify Python, dependencies, and the `.ini` file. Any exceptions should be printed in the console.

### Step 2: Read/Write Properties

To "attack" the device, one can access property values (i.e., read) and modify them as desired (i.e., write). Below is an example of the commands to set in the adversary profile in Caldera (or through CLI):

#### ReadProperty (bacrp)

The ReadProperty service is used by a BACnet client to request the value of one property from one BACnet object.

##### Usage

```
./bacrp <device-instance> <object-type> <object-instance> <property> <index>
```

##### Example: Read current temperature from AI:1

```
./bacrp 101 analog-input 1 presentValue -1
```

#### WriteProperty (bacwp)

The WriteProperty service is used by a BACnet client to write a value to a specific property of a BACnet object.

##### Usage

```
./bacwp <device-instance> <object-type> <object-instance> <property> <priority> <index> <tag> <value>
```

##### Example 1: Set temperature setpoint on AV:1 to 18°C

```
./bacwp 101 analog-value 1 presentValue 8 -1 real 18.0
```

##### Example 2: Override/increase intake fan speed to 75%

```
./bacwp 101 analog-output 1 presentValue 8 -1 real 75.0
```

##### Example 3: Trigger Emergency Stop 🛑

```
./bacwp 101 binary-value 1 presentValue 8 -1 boolean true
```

## Understanding the Process Simulation

> **Disclaimer:** HVACSim models core thermal dynamics, but its primary purpose is to support Caldera/BACnet testing rather than to serve as a fully accurate physical HVAC model.

### 1. Room Thermal Model

The simulator continuously computes room temperature using:

* **Ambient heat** entering from the outside
* **Internal server load** (internal heat source)
* **Airflow-based cooling**
* **Chiller-based cooling**
* **Temperature sensor noise**
* **Actuator lag**

The temperature differential follows:

```
dT_dt = ((ambient + internal_load) - room_temp) / room_time_constant \
        - (cooling_from_fans + cooling_from_chiller)
```

### 2. Airflow Cooling

The intake and exhaust sliders (or Caldera writes) produce an airflow percentage:

```
airflow = (intake + exhaust) / 2
```

Cooling power is proportional to airflow:

```
cooling_airflow = (airflow / 100) * AIRFLOW_MAX_COOL
```

### 3. Chiller Logic (PI Controller)

The chiller is controlled by a **Proportional-Integral (PI)** loop:

```
error = current_temp - setpoint

integral = integral + error * tick

chiller_target = KP * error + KI * integral
```

The chiller actuator then moves toward the target following:

```
chiller_speed = chiller_speed + (chiller_target - chiller_speed) * CHILLER_LAG
```

Random noise is added to emulate real-world imperfectness:

```
chiller_speed = chiller_speed + Uniform(-NOISE_CHILLER, NOISE_CHILLER)
```

### 4. Emergency Stop Logic

When emergency stop is triggered:

* Airflow is forced to **0%**
* Chiller target is forced to **0%**

## HMI Features

When launched, HVACSim displays an HMI containing:

**Main Temperature Graph**

* Real-time plot of current temperature (unit set by `temperature_unit` in config)
* Setpoint shown as a dashed line

**Mini Trend Charts**

* Chiller load (%)
* Intake airflow (%)
* Exhaust airflow (%)

**Interactive Controls**

* Setpoint slider (unit set by `temperature_unit` in config)
* Intake fan slider (%)
* Exhaust fan slider (%)
* Emergency-stop toggle button

Closing the window shuts down the control loop and BACnet stack.

## Using HVACSim with Caldera

If using Caldera with its BACnet plugin:

1. Start the HVACSim process
2. Start Caldera
3. Create an operation

   * Create an agent
   * Create an adversary profile including any BACnet features desired
   * Create an operation that selects the constructed adversary profile
   * Start operation

4. Use abilities such as:

   * *ReadProperty* &rarr; Check temperature or chiller load
   * *WriteProperty* &rarr; Change setpoint
   * *WriteProperty* &rarr; Force fans to 100%
   * *WriteProperty* &rarr; Trigger Emergency Stop

This allows for simulation of:

* Safety bypass attempts
* Setpoint manipulation attacks
* Disruptive fan/chiller control
* Reconnaissance of BACnet points

### Fact Source, Adversary Profiles, and Scenarios

This repo ships Caldera templates under `docs/`:

* [`docs/sources/hvac-facts.yml`](docs/sources/hvac-facts.yml) - a fact source with the HVACSim device, read, and write facts. Copy it into `plugins/bacnet/data/sources/`.
* [`docs/adversaries/`](docs/adversaries/) - three BACnet adversary profiles. Copy them into `plugins/bacnet/data/adversaries/`.
* [`docs/scenarios/`](docs/scenarios/) - walkthroughs mapping each profile to ATT&CK for ICS techniques and the Caldera abilities it runs:
  * [Scenario 1: Reconnaissance](docs/scenarios/scenario_1_reconnaissance.md)
  * [Scenario 2: Thermal Runaway](docs/scenarios/scenario_2_thermal_runaway.md)
  * [Scenario 3: Emergency Stop](docs/scenarios/scenario_3_emergency_stop.md)

The ability UUIDs in the adversary profiles come from the [Caldera BACnet plugin](https://github.com/mitre/bacnet); the profiles reference them, they are not defined here.

## Help and Troubleshooting

1. Ensure the `.ini` file has a valid BACnet device ID and IP address
2. If BACnet clients cannot discover HVACSim, verify:

   * No firewall blocks UDP/47808
   * Correct network interface is used
3. Run with `python3 hvac_sim.py --debug` for verbose BACnet logs

## License

This project is licensed under the Apache-2.0 License.
See the LICENSE file for details.

## Acknowledgments

* [Caldera](https://github.com/apache/caldera)
* [Caldera for OT](https://github.com/mitre/caldera-ot)
* [BAC0](https://pypi.org/project/bac0/)

© 2026 THE MITRE CORPORATION. ALL RIGHTS RESERVED. APPROVED FOR PUBLIC RELEASE. DISTRIBUTION UNLIMITED PR_26-0182
