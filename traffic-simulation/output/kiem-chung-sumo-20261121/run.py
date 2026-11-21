"""Paired SUMO pilot at junction B. Run with Python and the installed SUMO_HOME."""
import argparse
import csv
import gzip
import hashlib
import math
import os
import random
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime
from pathlib import Path
from statistics import fmean

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
NET = PROJECT / "network" / "grid_net.xml"
DEMAND = PROJECT / "routes" / "grid_routes.rou.xml"
SUMO = Path(os.environ["SUMO_HOME"])
sys.path.insert(0, str(SUMO / "tools"))
sys.path.insert(0, str(PROJECT))
import sumolib
import traci
import traci.constants as tc
from scripts.core.aco import AntColonyOptimizer, TrafficGraph

SEEDS = (41, 42, 43, 44, 45)
POLICIES = ("fixed", "fastest", "logit", "logit_pending")
GROUP = ("f_A2I_1.", "f_A2I_2.")
FIRST, LAST = "A2B", "F2I"
OBS_GAIN = 1 - math.exp(-1 / 30)  # 30 simulation seconds for speed smoothing


def candidate_routes(net):
    # All grid edges have free-flow times below the core's 120 s normalization bound.
    graph = TrafficGraph(cost_weights={"w_d": 0, "w_t": 1, "w_q": 0, "w_w": 0})
    for start, end in graph.travel_time:
        edge = net.getEdge(graph.sumo_edge_id(start, end))
        graph.travel_time[start, end] = edge.getLength() / edge.getSpeed()
    random.seed(7401)  # The original ACO core uses the module-level RNG.
    routes = {}
    for _ in range(2):
        path, _ = AntColonyOptimizer(graph, n_ants=24, n_iterations=18).solve("B", "F")
        assert path and "A" not in path and "I" not in path, path
        route = [FIRST, *graph.path_to_edges(path), LAST]
        for a, b in zip(route, route[1:]):
            assert net.getEdge(b) in net.getEdge(a).getAllowedOutgoing("passenger"), (a, b)
        routes[path[1]] = route
        # Penalize the previous internal links only for the second ACO search.
        for a, b in zip(path, path[1:]):
            graph.travel_time[a, b] *= 2
    declared = {r.get("id"): r.get("edges").split() for r in ET.parse(DEMAND).getroot().findall("route")}
    assert routes == {"C": declared["r_A2I_1"], "E": declared["r_A2I_2"]}, routes
    return routes


def run_case(out, net, routes, demand, scenario, seed, policy, log):
    xml = out / "raw" / f"{scenario}-{seed}-{policy}.xml"
    cmd = [str(SUMO / "bin" / "sumo.exe"), "-n", str(NET), "-r", str(demand),
           "--seed", str(seed), "--step-length", "1", "--route-steps", "0",
           "--time-to-teleport", "-1", "--tripinfo-output", str(xml),
           "--tripinfo-output.write-unfinished", "true", "--tripinfo-output.write-undeparted", "true",
           "--no-step-log", "true", "--xml-validation", "never"]
    edges = sorted(set(routes["C"] + routes["E"]))
    length = {e: net.getEdge(e).getLength() for e in edges}
    limit = {e: net.getEdge(e).getSpeed() for e in edges}
    speed = limit.copy()
    pending, assigned, observed = {}, {}, {}
    departed = set()
    teleports = collisions = t = 0
    last_requested = int(max(float(f.get("end")) for f in ET.parse(demand).getroot().findall("flow")))
    traci.start(cmd, numRetries=4)
    try:
        traci.simulation.subscribe((tc.VAR_TIME, tc.VAR_DEPARTED_VEHICLES_IDS, tc.VAR_MIN_EXPECTED_VEHICLES,
                                    tc.VAR_TELEPORT_STARTING_VEHICLES_NUMBER, tc.VAR_COLLIDING_VEHICLES_NUMBER))
        for e in edges:
            ids = (tc.LAST_STEP_VEHICLE_ID_LIST,) if e in (FIRST, "B2C", "B2E") else ()
            traci.edge.subscribe(e, (tc.LAST_STEP_MEAN_SPEED, *ids))
        while t < last_requested + 7200:
            if scenario.endswith("slow_C2F") and t in (1200, 2400):
                limit["C2F"] = 5.0 if t == 1200 else net.getEdge("C2F").getSpeed()
                traci.edge.setMaxSpeed("C2F", limit["C2F"])
            traci.simulationStep()
            sim = traci.simulation.getSubscriptionResults()
            t = int(sim[tc.VAR_TIME])
            new_vehicles = sim[tc.VAR_DEPARTED_VEHICLES_IDS]
            departed.update(new_vehicles)
            teleports += sim[tc.VAR_TELEPORT_STARTING_VEHICLES_NUMBER]
            collisions += sim[tc.VAR_COLLIDING_VEHICLES_NUMBER]
            state = traci.edge.getAllSubscriptionResults()
            for e in edges:
                speed[e] += OBS_GAIN * (state[e][tc.LAST_STEP_MEAN_SPEED] - speed[e])
            approach = set(state[FIRST][tc.LAST_STEP_VEHICLE_ID_LIST])
            for v in pending.keys() - approach:
                del pending[v]
            for branch in ("C", "E"):
                for v in state["B2" + branch][tc.LAST_STEP_VEHICLE_ID_LIST]:
                    if v in assigned:
                        observed[v] = branch
            for v in sorted(x for x in new_vehicles if x.startswith(GROUP)):
                assert v in approach and v not in assigned, (t, v)
                secs = {e: length[e] / max(1.0, min(limit[e], speed[e])) for e in edges}
                eta_b = t + secs[FIRST]
                incoming = Counter(k for k, eta in pending.values() if abs(eta_b - max(t, eta)) <= 30)
                travel = {k: sum(secs[e] for e in route) for k, route in routes.items()}
                # shortcut: two seconds per pending car is a pilot assumption, calibrate from discharge data for field use.
                cost = {k: travel[k] + (2 * incoming[k] if policy == "logit_pending" else 0) for k in routes}
                original = "C" if v.startswith(GROUP[0]) else "E"
                if policy == "fixed":
                    choice, p_c = original, ""
                elif policy == "fastest":
                    choice = min(("C", "E"), key=cost.get)
                    p_c = int(choice == "C")
                else:
                    p_c = 1 / (1 + math.exp(max(-700, min(700, (cost["C"] - cost["E"]) / 30))))
                    # Common draw per vehicle across the two probabilistic policies.
                    choice = "C" if random.Random(f"{seed}/{v}").random() < p_c else "E"
                if choice != original:
                    traci.vehicle.setRoute(v, routes[choice])
                pending[v] = choice, eta_b
                assigned[v] = choice
                log.writerow((scenario, seed, policy, t, v, original, choice, round(travel["C"], 3),
                              round(travel["E"], 3), incoming["C"], incoming["E"], p_c))
            if t >= last_requested and sim[tc.VAR_MIN_EXPECTED_VEHICLES] == 0:
                break
        else:
            raise RuntimeError(f"Network did not drain by {t}: {scenario}/{seed}/{policy}")
    finally:
        traci.close()

    tree = ET.parse(xml)
    times, waits, insertion_delays, guided_times = [], [], [], []
    schedule = {}
    for trip in tree.getroot().findall("tripinfo"):
        v = trip.attrib["id"]
        start, delay, end, duration = (float(trip.attrib[k]) for k in ("depart", "departDelay", "arrival", "duration"))
        assert v not in schedule and start >= 0 and end >= start and abs(end - start - duration) <= 0.011
        assert trip.get("vaporized", "") in ("", "false", "0"), trip.attrib
        times.append(delay + duration)
        waits.append(float(trip.attrib["waitingTime"]))
        insertion_delays.append(delay)
        if v.startswith(GROUP):
            guided_times.append(delay + duration)
        schedule[v] = (round(start - delay, 2), trip.attrib["departLane"].rsplit("_", 1)[0],
                       trip.attrib["arrivalLane"].rsplit("_", 1)[0], trip.attrib["vType"])
    assert schedule.keys() == departed and departed, (len(schedule), len(departed))
    assert assigned.keys() == {v for v in departed if v.startswith(GROUP)} and assigned == observed
    assert teleports == 0 and collisions == 0, (teleports, collisions)
    compressed = xml.with_suffix(".xml.gz")
    compressed.write_bytes(gzip.compress(xml.read_bytes(), compresslevel=6, mtime=0))
    xml.unlink()  # This run's newly created XML is now archived losslessly.
    row = dict(scenario=scenario, seed=seed, policy=policy, departed=len(departed), arrived=len(times),
               eligible=len(assigned), via_C=sum(k == "C" for k in observed.values()),
               via_E=sum(k == "E" for k in observed.values()), total_s=round(sum(times), 2),
               mean_s=round(fmean(times), 4), eligible_mean_s=round(fmean(guided_times), 4),
               p95_s=sorted(times)[math.ceil(.95 * len(times)) - 1], mean_wait_s=round(fmean(waits), 4),
               total_insert_delay_s=round(sum(insertion_delays), 2), teleports=teleports, collisions=collisions,
               end_s=t)
    return row, schedule


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", nargs="?", default=datetime.now().strftime("run-%Y%m%d-%H%M%S"))
    parser.add_argument("--high", action="store_true", help="multiply only the two eligible flows by four")
    args = parser.parse_args()
    out = HERE / args.folder
    out.mkdir(exist_ok=False)
    (out / "raw").mkdir()
    demand = DEMAND
    scenarios = ("normal", "slow_C2F")
    if args.high:
        tree = ET.parse(DEMAND)
        selected = [f for f in tree.getroot().findall("flow") if f.get("id") + "." in GROUP]
        assert len(selected) == 2 and all(f.get("vehsPerHour") == "133" for f in selected)
        for flow in selected:
            flow.set("vehsPerHour", "532")
        demand = out / "high.rou.xml"
        tree.write(demand, encoding="utf-8", xml_declaration=True)
        scenarios = ("high_normal", "high_slow_C2F")
    net = sumolib.net.readNet(str(NET))
    routes = candidate_routes(net)
    print("Output:", out, "ACO candidates:", routes, flush=True)
    print("SHA256 net/demand:", *(hashlib.sha256(p.read_bytes()).hexdigest() for p in (NET, demand)), flush=True)
    with (out / "decisions.csv").open("w", newline="", encoding="utf-8") as decisions, \
         (out / "summary.csv").open("w", newline="", encoding="utf-8") as metrics:
        log = csv.writer(decisions)
        log.writerow(("scenario", "seed", "policy", "t", "id", "original", "choice", "eta_C_s", "eta_E_s",
                      "pending_C", "pending_E", "prob_C"))
        summary = None
        reference = None
        for scenario in scenarios:
            for seed in SEEDS:
                for policy in POLICIES:
                    row, schedule = run_case(out, net, routes, demand, scenario, seed, policy, log)
                    if reference is None:
                        reference = schedule
                    assert schedule == reference, f"Different trip requests/OD: {scenario}/{seed}/{policy}"
                    if summary is None:
                        summary = csv.DictWriter(metrics, fieldnames=row)
                        summary.writeheader()
                    summary.writerow(row)
                    metrics.flush()
                    decisions.flush()
                    print(scenario, seed, policy, row["arrived"], row["total_s"], flush=True)
