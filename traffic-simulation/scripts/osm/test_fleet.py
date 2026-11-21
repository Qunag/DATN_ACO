import os
import sys
import subprocess
import unittest
import csv
import gzip
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.append(str(Path(os.environ["SUMO_HOME"]) / "tools"))
import sumolib

from scripts.osm.fleet import AdaptiveTraffic, Approach, FleetPaths, _trip_summary, run_fleet, switch_probability


class FleetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.net_file = Path(__file__).resolve().parents[2] / "network" / "grid_net.xml"
        cls.net = sumolib.net.readNet(str(cls.net_file))
        cls.paths = FleetPaths(cls.net, "passenger", 50)

    def test_alternative_preserves_edges_turn_permissions_and_destination(self):
        original = ("A2B", "B2C", "C2F", "F2I")
        alt = self.paths.alternative(original)
        self.assertIsNotNone(alt)
        self.assertNotEqual(alt, original)
        self.assertEqual((alt[0], alt[-1]), (original[0], original[-1]))
        for a, b in zip(alt, alt[1:]):
            self.assertIn(self.net.getEdge(b), self.net.getEdge(a).getAllowedOutgoing("passenger"))
        self.assertIsNone(self.paths.alternative(("A2B",)))

    def test_switch_requires_a_material_gain_and_leaves_a_share_on_the_original(self):
        self.assertEqual(switch_probability(200, 210), 0)
        self.assertEqual(switch_probability(200, 190), 0)
        self.assertEqual(switch_probability(1000, 925), 0)
        self.assertLess(0, switch_probability(200, 140))
        self.assertLess(switch_probability(200, 140), 1)

    def test_new_costs_can_redirect_the_colony_and_respect_mandatory_edges(self):
        route = ("A2B", "B2C", "C2F", "F2I")
        weights = {(a, b): self.paths.times[b] for a, bs in self.paths.outgoing.items() for b in bs}
        weights["B2C", "C2F"] += 300
        alternative = self.paths.live_alternative(route, weights, set())
        self.assertEqual(alternative, ("A2B", "B2E", "E2F", "F2I"))
        self.assertIsNone(self.paths.live_alternative(route, weights, {"B2C", "C2F"}))
        self.assertIsNone(self.paths.live_alternative(("A2B",), weights, set()))
        self.assertIsNone(self.paths.live_alternative(("A2B", "E2F", "F2I"), weights, set()))

    def test_snapshot_covers_the_network_and_accounts_for_recent_assignments(self):
        import traci

        traci.start([sumolib.checkBinary("sumo"), "-n", str(self.net_file),
                     "-r", str(self.net_file.parents[1] / "routes" / "grid_routes.rou.xml"), "--no-step-log"])
        try:
            traci.simulationStep()
            live = AdaptiveTraffic(traci, self.net, {})
            live.refresh(1)
            self.assertEqual(set(live.delay), set(self.paths.times))
            route = ("A2B", "B2E", "E2F", "F2I")
            turn = route[:2]
            cost = live.turn_cost(self.paths, turn)
            for _ in range(120):
                live.assign(1, route)
            self.assertGreater(live.turn_cost(self.paths, turn), cost)
            traci.simulationStep(121)
            live.refresh(121)
            self.assertEqual(live.assigned[turn], 0)
        finally:
            traci.close()

    def test_discharge_and_reservations_change_delay_without_counting_a_car_twice(self):
        approach = Approach(lanes=1)
        approach.observe({"a", "b"}, halted=2, excluded=set())
        approach.pending["c"] = 30
        self.assertEqual(approach.incoming(30), 1)
        self.assertEqual(approach.incoming(100), 0)
        approach.observe({"b", "c"}, halted=2, excluded=set())
        self.assertEqual(approach.incoming(30), 0)
        approach.observe(set(), halted=0, excluded={"b"})
        self.assertEqual(approach.crossings, 2)
        initial = approach.rate
        approach.finish_cycle(30)
        self.assertLess(approach.rate, initial)
        self.assertEqual(approach.crossings, 0)

    def test_incident_restores_each_lane_and_repeats_the_random_location(self):
        import traci
        from scripts.osm.fleet import RoadIncident

        incident = RoadIncident(self.net, 71, start=5, duration=40, speed_factor=.2, count=3, show=True)
        repeated = RoadIncident(self.net, 71, start=5, duration=40, speed_factor=.2, count=3)
        self.assertEqual(incident.edges, repeated.edges)
        self.assertEqual(incident.edge, RoadIncident(self.net, 71).edge)
        self.assertEqual(len(set(incident.edges)), 3)
        self.assertFalse(incident.edge.startswith(":"))
        self.assertTrue(self.net.getEdge(incident.edge).allows("passenger"))
        traci.start([sumolib.checkBinary("sumo"), "-n", str(self.net_file), "--no-step-log"])
        try:
            for i, lane in enumerate(incident.lanes):
                traci.lane.setMaxSpeed(lane, 7 + i)
            original = {lane: traci.lane.getMaxSpeed(lane) for lane in incident.lanes}
            traci.simulationStep()
            live = AdaptiveTraffic(traci, self.net, {})
            live.refresh(1)
            delay_before = live.delay[incident.edge]
            self.assertEqual(incident.update(traci, 4), [])
            traci.simulationStep(5)
            began = incident.update(traci, 5)
            self.assertEqual(len(began), len(original))
            self.assertTrue(all(row[:2] == ("start", 5) for row in began))
            self.assertEqual({row[2] for row in began}, set(incident.edges))
            self.assertEqual(len(traci.polygon.getIDList()), 3)
            self.assertEqual(len(traci.poi.getIDList()), 3)
            for lane, speed in original.items():
                self.assertAlmostEqual(traci.lane.getMaxSpeed(lane), .2 * speed)
            self.assertEqual(incident.update(traci, 6), [])
            traci.simulationStep(35)
            live.refresh(35)
            self.assertGreater(live.delay[incident.edge], delay_before)
            traci.simulationStep(45)
            ended = incident.update(traci, 45)
            self.assertEqual(len(ended), len(original))
            self.assertTrue(all(row[:2] == ("restore", 45) for row in ended))
            self.assertEqual({row[2] for row in ended}, set(incident.edges))
            self.assertEqual(traci.polygon.getIDList(), ())
            self.assertEqual(traci.poi.getIDList(), ())
            for lane, speed in original.items():
                self.assertEqual(traci.lane.getMaxSpeed(lane), speed)
            self.assertEqual(incident.update(traci, 46), [])
            self.assertEqual(repeated.update(traci, 46), [])
            for options in ({"start": -1}, {"duration": 0}, {"start": float("nan")},
                            {"duration": float("inf")}, {"speed_factor": 0}, {"speed_factor": 1},
                            {"count": 0}, {"count": 1000000}, {"count": 1.5}):
                with self.assertRaises(ValueError):
                    RoadIncident(self.net, 71, **options)
        finally:
            traci.close()

    def test_cli_incident_is_identical_for_all_compared_policies(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "demand.xml").write_text(
                '<routes><vehicle id="car" depart="0"><route edges="A2B B2C C2F F2I"/>'
                '</vehicle></routes>', encoding="utf-8")
            cfg = folder / "case.sumocfg"
            cfg.write_text('<configuration><input><net-file value="' + self.net_file.as_posix()
                           + '"/><route-files value="demand.xml"/></input></configuration>', encoding="utf-8")
            command = [sys.executable, "-B", "-m", "scripts.osm.osm_runner", "--mode", "fleet", "--nogui",
                       "--cfg", str(cfg), "--policy", "compare", "--incident", "--incident-start", "5",
                       "--incident-duration", "20", "--incident-speed-factor", ".2", "--seed", "71",
                       "--incident-count", "3", "--demand-scale", "2",
                       "--output-dir", str(folder)]
            result = subprocess.run(command, cwd=self.net_file.parents[1], capture_output=True,
                                    text=True, encoding="utf-8", timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            summary = next(folder.glob("*/summary.csv"))
            with summary.open() as f:
                metrics = list(csv.DictReader(f))
            self.assertEqual(len(metrics), 5)
            reference = None
            for row in metrics:
                self.assertEqual((row["complete"], row["considered"], row["incident_applied"]),
                                 ("True", "2", "True"))
                self.assertEqual(float(row["demand_scale"]), 2)
                self.assertEqual(int(row["incident_count"]), 3)
                with (summary.parent / row["policy"] / "incidents.csv").open() as f:
                    events = list(csv.DictReader(f))
                self.assertEqual({r["event"] for r in events}, {"start", "restore"})
                self.assertEqual({float(r["time_s"]) for r in events}, {5, 25})
                edges = row["incident_edges"].split()
                self.assertEqual(len(set(edges)), 3)
                self.assertEqual({r["edge"] for r in events}, set(edges))
                self.assertEqual(row["incident_edge"], edges[0])
                for event in events:
                    a, b = float(event["before_mps"]), float(event["after_mps"])
                    self.assertAlmostEqual(b / a, .2 if event["event"] == "start" else 5)
                if reference is None:
                    reference = events
                self.assertEqual(events, reference)

    def test_terminal_teleport_is_distinct_from_an_ordinary_arrival(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tripinfo.xml.gz"
            root = ET.Element("tripinfos")
            trips = {v: ("start", "end") for v in ("normal", "reinserted", "terminal")}
            for v in trips:
                ET.SubElement(root, "tripinfo", id=v, depart="1", arrival="11", departDelay="1",
                              departLane="start_0", arrivalLane="end_0", vType="car",
                              vaporized="teleport" if v == "terminal" else "")
            with gzip.open(path, "wb") as f:
                ET.ElementTree(root).write(f)
            result, _ = _trip_summary(path, trips, set(trips), True, {"terminal", "reinserted"})
            self.assertEqual((result["finished_in_sumo"], result["arrived"], result["ended_by_teleport"],
                              result["arrived_without_teleport"], result["total_s"]), (3, 2, 1, 1, 33))

    def test_dynamic_incidents_stay_in_the_region_and_restore_independently(self):
        import traci
        from scripts.osm.incidents import IncidentSchedule

        area = self.net.getBoundary()
        events = IncidentSchedule(self.net, 71, start=5, duration=1200, count=3, area=area, show=True)
        repeat = IncidentSchedule(self.net, 71, start=5, duration=1200, count=3, area=area)
        self.assertEqual(events.plan, repeat.plan)
        self.assertGreater(len(events.plan), 3)
        self.assertGreater(len({p["speed_factor"] for p in events.plan}), 1)
        for item in events.plan:
            self.assertTrue(all(area[0] <= x <= area[2] and area[1] <= y <= area[3]
                                for x, y in self.net.getEdge(item["edge"]).getShape()))
            overlapping = [p for p in events.plan if p["start_s"] <= item["start_s"] < p["end_s"]]
            self.assertLessEqual(len(overlapping), 3)
            self.assertEqual(len({p["edge"] for p in overlapping}), len(overlapping))
        traci.start([sumolib.checkBinary("sumo"), "-n", str(self.net_file), "--no-step-log"])
        try:
            baseline = {lane.getID(): traci.lane.getMaxSpeed(lane.getID())
                        for edge in events.edges for lane in self.net.getEdge(edge).getLanes()}
            records = []
            for now in sorted({0} | {p[k] for p in events.plan for k in ("start_s", "end_s")}):
                if now:
                    traci.simulationStep(float(now))
                records.extend(events.update(traci, now))
                active = {p["edge"]: p for p in events.plan if p["start_s"] <= now < p["end_s"]}
                self.assertEqual(len(traci.poi.getIDList()), len(active))
                self.assertEqual(len(traci.polygon.getIDList()), len(active) + 1)
                for lane, original in baseline.items():
                    factor = active.get(lane.rsplit("_", 1)[0], {}).get("speed_factor", 1)
                    self.assertAlmostEqual(traci.lane.getMaxSpeed(lane), original * factor)
            self.assertEqual({r[6] for r in records}, {p["id"] for p in events.plan})
            for p in events.plan:
                rows = [r for r in records if r[6] == p["id"]]
                self.assertEqual({r[0] for r in rows}, {"start", "restore"})
                self.assertEqual({r[1] for r in rows}, {p["start_s"], p["end_s"]})
            for bad in ((0, 0, 0, 10), (0, 0, float("nan"), 10), (100000, 100000, 100010, 100010)):
                with self.assertRaises(ValueError):
                    IncidentSchedule(self.net, 71, area=bad)
        finally:
            traci.close()

    def test_cli_dynamic_incident_plan_is_shared_by_all_policies(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "demand.xml").write_text(
                '<routes><route id="r" edges="A2B B2C C2F F2I"/>'
                '<vehicle id="first" route="r" depart="0"/>'
                '<vehicle id="late" route="r" depart="2500"/></routes>', encoding="utf-8")
            cfg = folder / "case.sumocfg"
            cfg.write_text('<configuration><input><net-file value="' + self.net_file.as_posix()
                           + '"/><route-files value="demand.xml"/></input></configuration>', encoding="utf-8")
            command = [sys.executable, "-B", "-m", "scripts.osm.osm_runner", "--mode", "fleet", "--nogui",
                       "--cfg", str(cfg), "--policy", "compare", "--incident-dynamic", "--incident-start", "5",
                       "--incident-duration", "600", "--incident-count", "2", "--seed", "71",
                       "--incident-area", *(str(v) for v in self.net.getBoundary()), "--output-dir", str(folder)]
            result = subprocess.run(command, cwd=self.net_file.parents[1], capture_output=True,
                                    text=True, encoding="utf-8", timeout=90)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            summary = next(folder.glob("*/summary.csv"))
            with summary.open() as f:
                metrics = list(csv.DictReader(f))
            self.assertEqual(len(metrics), 5)
            reference = None
            for row in metrics:
                self.assertEqual((row["complete"], row["considered"], row["incident_mode"]),
                                 ("True", "2", "dynamic"))
                with (summary.parent / row["policy"] / "incident-plan.csv").open() as f:
                    plan = list(csv.DictReader(f))
                with (summary.parent / row["policy"] / "incidents.csv").open() as f:
                    actual = list(csv.DictReader(f))
                self.assertEqual(int(row["incident_applied_count"]), len(plan))
                self.assertEqual({p["id"] for p in plan}, {r["incident_id"] for r in actual})
                for p in plan:
                    self.assertEqual({r["event"] for r in actual if r["incident_id"] == p["id"]},
                                     {"start", "restore"})
                if reference is None:
                    reference = plan, actual
                self.assertEqual((plan, actual), reference)

    def test_real_sumo_flows_classes_stops_and_short_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            net = ET.parse(self.net_file)
            for lane in net.findall("./edge[@id='B2E']/lane"):
                lane.attrib.pop("disallow", None)
                lane.set("allow", "passenger")
            net.write(folder / "map.net.xml", encoding="utf-8")
            (folder / "historic.xml").write_text("original results", encoding="utf-8")
            (folder / "case.sumocfg").write_text(
                '<configuration><input><net-file value="map.net.xml"/><route-files value="demand.xml"/>'
                '</input><output><summary-output value="historic.xml"/></output>'
                '<time><end value="5"/></time></configuration>', encoding="utf-8")
            (folder / "demand.xml").write_text(
                '<routes><vType id="bus" vClass="bus"/><vType id="van" vClass="delivery"/>'
                '<route id="r" edges="A2B B2C C2F F2I"/>'
                '<vehicle id="short" depart="0"><route edges="A2B"/></vehicle>'
                '<flow id="wave" route="r" begin="1" end="10" number="3"/>'
                '<vehicle id="line" type="bus" route="r" line="L1" depart="11"/>'
                '<vehicle id="visit" route="r" via="B2C" depart="12"><stop lane="C2F_0" '
                'duration="4" endPos="40"/></vehicle><trip id="van" type="van" depart="13" '
                'from="A2B" to="F2I"/></routes>', encoding="utf-8")
            cfg = folder / "case.sumocfg"
            run = run_fleet(cfg, None, False, None, "compare", 71, folder)
            for policy in ("queue", "adaptive"):
                with (run / policy / "decisions.csv").open() as f:
                    rows = {r["vehicle"]: r for r in csv.DictReader(f)}
                self.assertEqual(set(rows), {"short", "wave.0", "wave.1", "wave.2", "line", "visit", "van"})
                self.assertEqual(rows["short"]["candidates"], "1")
                self.assertEqual(rows["line"]["action"], "scheduled_or_internal")
                self.assertEqual(rows["visit"]["action"], "mandatory_route")
                self.assertEqual(rows["van"]["class"], "delivery")
            with (run / "summary.csv").open() as f:
                metrics = {row["policy"]: row for row in csv.DictReader(f)}
            self.assertEqual(set(metrics), {"original", "equal", "previous", "queue", "adaptive"})
            self.assertEqual((folder / "historic.xml").read_text(encoding="utf-8"), "original results")
            for row in metrics.values():
                self.assertEqual([row[k] for k in ("loaded", "considered", "arrived")], ["7"] * 3)
            delivery = FleetPaths(sumolib.net.readNet(str(folder / "map.net.xml")), "delivery", 40)
            self.assertNotIn("B2E", delivery.outgoing["A2B"])
            # A cutoff before the next departure can leave zero active cars with future demand.
            (folder / "demand.xml").write_text(
                '<routes><trip id="late" depart="100" from="A2B" to="F2I"/></routes>', encoding="utf-8")
            short_run = run_fleet(cfg, None, False, 10, "original", 71, folder)
            with (short_run / "summary.csv").open() as f:
                short = next(csv.DictReader(f))
            self.assertEqual(short["complete"], "False")
            self.assertEqual(short["total_s"], "")


if __name__ == "__main__":
    unittest.main()
