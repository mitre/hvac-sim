"""
Server room thermal model, independent of BACnet.

SimulationState holds the operator commands (setpoint, fans, emergency stop) and
the process values (room temperature, chiller load). simulation_step advances it
by one tick.

Authors:
    Capstone Group:
        University of Hawaii at Manoa Group 9 2025

    Developers:
        * Jake Dickinson
        * Elijah Saloma

    Advisor:
        * Samir Boussarhane
"""

import random
from dataclasses import dataclass

TICK_SECONDS = 1.0

AMBIENT_TEMP_C = 24.0
INTERNAL_LOAD_DEGC = 5.0
ROOM_TIME_CONSTANT = 120.0

AIRFLOW_MAX_COOL = 1.5 / 60.0
CHILLER_MAX_COOL = 10.0 / 60.0

CHILLER_KP = 40.0
CHILLER_KI = 0.3
CHILLER_LAG = 0.30
CHILLER_INT_LIMIT = 200.0

NOISE_TEMP = 0.05
NOISE_CHILLER = 0.8


@dataclass
class SimulationState:
    setpoint_c: float = 23.0
    intake_pct: float = 30.0
    exhaust_pct: float = 30.0
    estop: bool = False
    current_temp_c: float = 22.0
    chiller_pct: float = 30.0
    chiller_integral: float = 0.0

    @property
    def airflow_pct(self) -> float:
        if self.estop:
            return 0.0
        return max(0.0, min(100.0, (self.intake_pct + self.exhaust_pct) / 2.0))


def simulation_step(sim: SimulationState) -> None:
    if sim.estop:
        chiller_target = 0.0
        sim.chiller_integral = 0.0
    else:
        error_c = sim.current_temp_c - sim.setpoint_c
        sim.chiller_integral += error_c * TICK_SECONDS
        sim.chiller_integral = max(-CHILLER_INT_LIMIT, min(CHILLER_INT_LIMIT, sim.chiller_integral))
        raw_target = CHILLER_KP * error_c + CHILLER_KI * sim.chiller_integral
        chiller_target = max(0.0, min(100.0, raw_target))

    sim.chiller_pct += (chiller_target - sim.chiller_pct) * CHILLER_LAG
    sim.chiller_pct += random.uniform(-NOISE_CHILLER, NOISE_CHILLER)
    sim.chiller_pct = max(0.0, min(100.0, sim.chiller_pct))

    load_temp = AMBIENT_TEMP_C + INTERNAL_LOAD_DEGC
    cooling_power = (sim.airflow_pct / 100.0) * AIRFLOW_MAX_COOL + (sim.chiller_pct / 100.0) * CHILLER_MAX_COOL

    dTdt = ((load_temp - sim.current_temp_c) / ROOM_TIME_CONSTANT) - cooling_power
    sim.current_temp_c += dTdt * TICK_SECONDS

    sim.current_temp_c += random.uniform(-NOISE_TEMP, NOISE_TEMP)
    sim.current_temp_c = max(10.0, min(40.0, sim.current_temp_c))
