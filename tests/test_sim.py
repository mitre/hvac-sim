import unittest

from simulator.sim import SimulationState, simulation_step


class SimulationTests(unittest.TestCase):
    def test_estop_stops_cooling(self):
        sim = SimulationState(estop=True, chiller_pct=50.0, chiller_integral=10.0)
        simulation_step(sim)
        self.assertEqual(sim.airflow_pct, 0.0)
        self.assertEqual(sim.chiller_integral, 0.0)
        self.assertLess(sim.chiller_pct, 50.0)

    def test_room_heats_without_cooling(self):
        sim = SimulationState(estop=True, current_temp_c=22.0)
        for _ in range(300):
            simulation_step(sim)
        self.assertGreater(sim.current_temp_c, 25.0)

    def test_chiller_holds_setpoint(self):
        sim = SimulationState(setpoint_c=23.0, current_temp_c=23.0)
        for _ in range(600):
            simulation_step(sim)
        self.assertAlmostEqual(sim.current_temp_c, 23.0, delta=1.0)

    def test_values_stay_in_range(self):
        sim = SimulationState(setpoint_c=40.0, intake_pct=0.0, exhaust_pct=0.0)
        for _ in range(1000):
            simulation_step(sim)
            self.assertTrue(10.0 <= sim.current_temp_c <= 40.0)
            self.assertTrue(0.0 <= sim.chiller_pct <= 100.0)


if __name__ == "__main__":
    unittest.main()
