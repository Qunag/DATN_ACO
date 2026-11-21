"""Fleet-wide routing on SUMO edge IDs and permitted turns."""
import csv
import gzip
import heapq
import math
import random
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict, deque
from contextlib import nullcontext
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from scripts.core.osm_graph import OSMAntColonyOptimizer
from scripts.osm.incidents import IncidentSchedule, RoadIncident


class _Corridor:
    """The existing OSM colony searches only the legal corridors for this trip."""

    def __init__(self, paths, times, coords, original, weights=None):
        self.coords = coords
        adj = defaultdict(set)
        self.distance = {}
        for path in paths:
            for a, b in zip(path, path[1:]):
                adj[a].add(b)
                self.distance[a, b] = (weights[a, b] if weights is not None
                                       else times[b] * (1.25 if b in original else 1))
        self.adjacency = {a: sorted(bs) for a, bs in adj.items()}
        self.nodes = set(self.adjacency) | {paths[0][-1]}

    def get_neighbors(self, node):
        return self.adjacency.get(node, ())

    def get_cost(self, a, b, mode):
        return self.distance[a, b]

    def compute_path_cost(self, path, mode):
        return sum(self.distance[a, b] for a, b in zip(path, path[1:]))


class FleetPaths:
    def __init__(self, net, vclass, max_speed):
        self.times, self.lengths, self.coords, self.outgoing = {}, {}, {}, {}
        self.incoming = defaultdict(list)
        self.turnarounds = set()
        self.turn_wait, self.headway = {}, {}
        for edge in net.getEdges():
            lanes = [lane for lane in edge.getLanes() if lane.allows(vclass)]
            if not lanes:
                continue
            a = edge.getID()
            self.lengths[a] = edge.getLength()
            self.times[a] = min(l.getLength() / max(.1, min(l.getSpeed(), max_speed)) for l in lanes)
            self.coords[a] = edge.getToNode().getCoord()
            outgoing = edge.getAllowedOutgoing(vclass)
            self.outgoing[a] = sorted(e.getID() for e in outgoing)
            for other, connections in outgoing.items():
                b = other.getID()
                self.incoming[b].append(a)
                uturn = all(c.getDirection().lower() == "t" for c in connections)
                if uturn:
                    self.turnarounds.add((a, b))
                signal = any(c.getTLSID() for c in connections)
                yields = all(c.getState() in ("m", "s", "w") for c in connections)
                n_lanes = len({c.getFromLane().getID() for c in connections})
                # Initial movement delays and service headways are in seconds, before field calibration.
                junction_wait = 5 if yields else 0
                service_headway = 4 if signal or yields else 2
                self.turn_wait[a, b] = (10 if signal else junction_wait) + (30 if uturn else 0)
                self.headway[a, b] = (6 if uturn else service_headway) / n_lanes
        self._free_tree = lru_cache(maxsize=256)(self._to_destination)
        self.alternative = lru_cache(maxsize=16384)(self.alternative)

    def _to_destination(self, end, weights=None):
        remaining, successor = {end: 0.0}, {}
        heap = [(0.0, end)]
        while heap:
            cost, b = heapq.heappop(heap)
            if cost != remaining[b]:
                continue
            for a in self.incoming[b]:
                new = cost + (self.times[b] if weights is None else weights[a, b])
                if new < remaining.get(a, math.inf):
                    remaining[a], successor[a] = new, b
                    heapq.heappush(heap, (new, a))
        return remaining, successor

    def alternative(self, original):
        return self._alternative(original, None, set())

    def permits(self, route):
        return bool(route) and route[0] in self.times and all(t in self.headway for t in zip(route, route[1:]))

    def live_alternative(self, original, weights, mandatory):
        if not self.permits(original):
            return None
        return self._alternative(original, weights, mandatory)

    def _alternative(self, original, weights, mandatory):
        if len(original) < 2 or any(e not in self.times for e in original):
            return None
        end = original[-1]
        remaining, successor = self._free_tree(end) if weights is None else self._to_destination(end, weights)
        limit = 1.30 * sum(self.times[e] for e in original) + 15
        original_turns = set(zip(original, original[1:]))
        required = [e for e in original if e in mandatory]
        if set(required) != mandatory:
            return None
        corridors = []
        prefix_cost = 0.0
        for i, (a, following) in enumerate(zip(original, original[1:])):
            prefix_cost += self.times[a]
            for b in self.outgoing[a]:
                if b == following or b not in remaining:
                    continue
                if weights is None and prefix_cost + self.times[b] + remaining[b] > limit:
                    continue
                route = list(original[:i+1]) + [b]
                while route[-1] != end:
                    route.append(successor[route[-1]])
                turns = set(zip(route, route[1:]))
                if len(set(route)) != len(route) or (turns - original_turns) & self.turnarounds:
                    continue
                if weights is not None and sum(self.times[e] for e in route) > limit:
                    continue
                if mandatory and [e for e in route if e in mandatory] != required:
                    continue
                corridors.append(tuple(route))
        if not corridors:
            return None
        common = set(original)
        if weights is None:
            corridors.sort(key=lambda r: sum(self.times[e] * (1.25 if e in common else 1) for e in r))
        else:
            corridors.sort(key=lambda r: sum(weights[t] for t in zip(r, r[1:])))
        finalists = corridors[:3]
        graph = _Corridor(finalists, self.times, self.coords, common, weights)
        colony = OSMAntColonyOptimizer(graph, n_ants=4, n_iterations=3, seed_with_dijkstra=False,
                                       rng=random.Random(repr(original)))
        path, _ = colony.solve(original[0], end, max_steps=len(graph.nodes))
        if not path or tuple(path) == original or sum(self.times[e] for e in path) > limit:
            return finalists[0]
        if mandatory and [e for e in path if e in mandatory] != required:
            return finalists[0]
        if weights is not None and graph.compute_path_cost(path, None) > graph.compute_path_cost(finalists[0], None):
            return finalists[0]
        return tuple(path)


def switch_probability(original_s, alternative_s):
    margin = max(15.0, .10 * original_s)
    gain = max(0.0, original_s - alternative_s - margin)
    return .85 * gain / (gain + 30.0)


class Approach:
    """Queue and measured departures at one signal-controlled incoming edge."""

    def __init__(self, lanes):
        # shortcut: use a startup service estimate until queued traffic supplies complete cycles.
        self.rate = max(1, lanes) * .25
        self.present = set()
        self.pending = {}
        self.halted = self.peak = self.crossings = 0

    def observe(self, present, halted, excluded):
        self.crossings += len(self.present - present - excluded)
        self.present = present
        self.halted = halted
        self.peak = max(self.peak, halted)
        for vehicle in self.pending.keys() & present:
            del self.pending[vehicle]

    def incoming(self, eta):
        return sum(abs(eta - t) <= 30 for t in self.pending.values())

    def finish_cycle(self, seconds):
        if self.peak:
            self.rate = max(1 / seconds, (self.rate + self.crossings / seconds) / 2)
        self.crossings = self.peak = 0


class Traffic:
    def __init__(self, conn, net, cycle_log, now):
        import traci.constants as tc

        self.conn = conn
        self.cycle_log = cycle_log
        self.approaches, self.lights, self.clock = {}, {}, {}
        self.speeds = {}
        for light in net.getTrafficLights():
            lid = light.getID()
            lanes = defaultdict(set)
            for lane, _, _ in light.getConnections():
                lanes[lane.getEdge().getID()].add(lane.getID())
            self.lights[lid] = []
            for edge, controlled in lanes.items():
                if edge in self.approaches:
                    continue
                self.lights[lid].append(edge)
                self.approaches[edge] = Approach(len(controlled))
                conn.edge.subscribe(edge, (tc.LAST_STEP_VEHICLE_ID_LIST, tc.LAST_STEP_VEHICLE_HALTING_NUMBER))
            conn.trafficlight.subscribe(lid, (tc.TL_CURRENT_PROGRAM, tc.TL_CURRENT_PHASE))
            phase = conn.trafficlight.getPhase(lid)
            start = now if phase == 0 and conn.trafficlight.getSpentDuration(lid) == 0 else None
            self.clock[lid] = (conn.trafficlight.getProgram(lid), phase, start)

    def observe(self, now, excluded):
        import traci.constants as tc

        for edge, s in self.conn.edge.getAllSubscriptionResults().items():
            approach = self.approaches[edge]
            approach.observe(set(s[tc.LAST_STEP_VEHICLE_ID_LIST]), s[tc.LAST_STEP_VEHICLE_HALTING_NUMBER], excluded)
            for v, eta in tuple(approach.pending.items()):
                if now > eta + 30 or v in excluded:
                    del approach.pending[v]
        for lid, state in self.conn.trafficlight.getAllSubscriptionResults().items():
            program, phase = state[tc.TL_CURRENT_PROGRAM], state[tc.TL_CURRENT_PHASE]
            last_program, last_phase, start = self.clock[lid]
            if program != last_program or (phase == 0 and last_phase != 0):
                for edge in self.lights[lid]:
                    a = self.approaches[edge]
                    if start is not None and program == last_program and now > start:
                        peak, passed = a.peak, a.crossings
                        a.finish_cycle(now - start)
                        self.cycle_log.writerow((lid, edge, start, now, peak, passed, round(a.rate, 4)))
                    else:
                        a.crossings = a.peak = 0
                start = now if phase == 0 else None
            self.clock[lid] = program, phase, start

    def evaluate(self, route, paths, now, policy):
        elapsed, reservations = 0.0, {}
        for i, edge in enumerate(route):
            free = paths.times[edge]
            if edge not in self.speeds or now - self.speeds[edge][0] >= 15:
                self.speeds[edge] = now, self.conn.edge.getLastStepMeanSpeed(edge)
            speed = self.speeds[edge][1]
            observed = max(free, paths.lengths[edge] / max(1.0, speed)) if speed >= 0 else free
            approach = self.approaches.get(edge)
            eta = now + elapsed
            if approach is not None:
                incoming = approach.incoming(eta) if elapsed <= 120 else 0
                if policy == "previous":
                    observed += 2 * incoming
                elif policy == "queue":
                    observed = max(observed, free + (approach.halted + incoming) / approach.rate)
                if i > 0 and elapsed <= 120:
                    reservations.setdefault(edge, eta)
            elapsed += observed
        return elapsed, reservations


class AdaptiveTraffic:
    """Live costs for legal turns, shared by all departures in one simulation."""

    window = 120.0

    def __init__(self, conn, net, approaches):
        self.conn = conn
        self.approaches = approaches
        self.anchor = net.getNodes()[0].getID()
        self.radius = net.getBBoxDiameter() + 1
        self.edges = {e.getID(): e for e in net.getEdges()}
        self.delay, self.frames = {}, {}
        self.last_sample = -math.inf
        self.history, self.assigned = deque(), Counter()

    def refresh(self, now):
        import traci.constants as tc

        while self.history and self.history[0][0] <= now - self.window:
            _, turns = self.history.popleft()
            self.assigned.subtract(turns)
        if now - self.last_sample < 30:
            return
        gain = 1 - math.exp(-(now - self.last_sample) / 60)
        self.conn.junction.subscribeContext(self.anchor, tc.CMD_GET_EDGE_VARIABLE, self.radius,
                                            (tc.LAST_STEP_MEAN_SPEED, tc.LAST_STEP_VEHICLE_HALTING_NUMBER),
                                            begin=now, end=now)
        states = self.conn.junction.getContextSubscriptionResults(self.anchor)
        for eid, edge in self.edges.items():
            state = states.get(eid)
            if state is None:
                continue
            speed = state[tc.LAST_STEP_MEAN_SPEED]
            excess = 0.0 if speed < 0 else edge.getLength() * (1 / max(1, speed) - 1 / max(.1, edge.getSpeed()))
            approach = self.approaches.get(eid)
            rate = approach.rate if approach else .5 * edge.getLaneNumber()
            clearance = state[tc.LAST_STEP_VEHICLE_HALTING_NUMBER] / rate
            sample = min(180, max(0, excess, clearance))
            previous = self.delay.get(eid, 0)
            self.delay[eid] = previous + gain * (sample - previous)
        self.last_sample = now
        self.frames.clear()

    def turn_cost(self, paths, turn):
        a, b = turn
        # Project overflow from recent assignments. Observed traffic can include those same vehicles.
        overflow = self.assigned[turn] * paths.headway[turn] - .8 * self.window
        return paths.times[b] + paths.turn_wait[turn] + max(self.delay.get(a, 0), overflow)

    def weights(self, paths):
        if paths not in self.frames:
            self.frames[paths] = {turn: self.turn_cost(paths, turn) for turn in paths.headway}
        return self.frames[paths]

    def quote(self, paths, route):
        return paths.times[route[0]] + sum(self.turn_cost(paths, t) for t in zip(route, route[1:]))

    def assign(self, now, route):
        turns = tuple(zip(route, route[1:]))
        self.history.append((now, turns))
        self.assigned.update(turns)


def _trip_summary(xml, decisions, arrived_ids, drained, teleported):
    requests, times = {}, []
    ended, ordinary, terminal = set(), set(), set()
    removed = unfinished = 0
    with gzip.open(xml, "rb") as f:
        for _, trip in ET.iterparse(f, events=("end",)):
            if trip.tag != "tripinfo":
                continue
            v = trip.attrib["id"]
            depart, delay, arrival = (float(trip.attrib[k]) for k in ("depart", "departDelay", "arrival"))
            if v in requests:
                raise ValueError(f"Duplicate trip {v}")
            od = decisions.get(v)
            requests[v] = (round(depart - delay, 2) if depart >= 0 else None, od, trip.get("vType"))
            reason = trip.get("vaporized", "")
            if arrival < 0:
                unfinished += 1
            elif reason in ("", "0", "false", "teleport"):
                ended.add(v)
                actual = tuple(trip.attrib[k].rsplit("_", 1)[0] for k in ("departLane", "arrivalLane"))
                if actual != od:
                    raise ValueError(f"Vehicle {v}: requested {od}, completed {actual}")
                (terminal if reason == "teleport" else ordinary).add(v)
                times.append(arrival - depart + delay)
            else:
                ended.add(v)
                removed += 1
            trip.clear()
    if not decisions.keys() <= requests.keys() or not ordinary <= arrived_ids or not arrived_ids <= ended:
        raise ValueError("SUMO trip log and observed vehicles disagree")
    times.sort()
    n = len(times)
    complete = drained and not (unfinished or removed)
    return dict(requested=len(requests), considered=len(decisions), finished_in_sumo=n,
                arrived=len(ordinary), ended_by_teleport=len(terminal),
                arrived_without_teleport=len(ordinary - teleported), teleported_vehicles=len(teleported | terminal),
                removed_other=removed, unfinished=unfinished,
                complete=complete, total_s=round(sum(times), 2) if complete else "",
                mean_s=round(sum(times) / n, 3) if n else "",
                p95_s=round(times[math.ceil(.95*n)-1], 2) if n else ""), requests


def run_policy(conn, net, graphs, out, policy, seed, duration, incident=None, show=False):
    import traci.constants as tc

    starts, arrivals, teleported = {}, set(), set()
    actions = Counter()
    sim = conn.simulation
    now = start = sim.getTime()
    loaded = set(sim.getLoadedIDList())
    teleports = collisions = choices = 0
    drained = False
    fields = (tc.VAR_EDGES, tc.VAR_ROAD_ID, tc.VAR_ROUTE_INDEX, tc.VAR_VEHICLECLASS,
              tc.VAR_MAXSPEED, tc.VAR_VIA, tc.VAR_LINE, tc.VAR_NEXT_STOPS2)
    sim.subscribe((tc.VAR_TIME, tc.VAR_LOADED_VEHICLES_IDS, tc.VAR_DEPARTED_VEHICLES_IDS, tc.VAR_ARRIVED_VEHICLES_IDS,
                   tc.VAR_TELEPORT_STARTING_VEHICLES_IDS, tc.VAR_COLLIDING_VEHICLES_NUMBER,
                   tc.VAR_MIN_EXPECTED_VEHICLES))
    with (
        (out / "decisions.csv").open("w", encoding="utf-8", newline="") as log,
        (out / "cycles.csv").open("w", encoding="utf-8", newline="") as cycles,
        (out / "teleports.csv").open("w", encoding="utf-8", newline="") as events,
        ((out / "incidents.csv").open("w", encoding="utf-8", newline="")
         if incident else nullcontext()) as incident_file,
    ):
        rows, cycle_rows = csv.writer(log), csv.writer(cycles)
        event_rows = csv.writer(events)
        event_rows.writerow(("time_s", "vehicle"))
        if incident:
            incident_rows = csv.writer(incident_file)
            incident_rows.writerow(incident.log_fields)
        rows.writerow(("time_s", "vehicle", "class", "origin", "destination", "action",
                       "candidates", "original_s", "alternative_s", "p_alternative"))
        cycle_rows.writerow(("signal", "edge", "from_s", "to_s", "peak_queue", "crossings", "service_veh_per_s"))
        traffic = Traffic(conn, net, cycle_rows, now)
        adaptive = AdaptiveTraffic(conn, net, traffic.approaches) if policy == "adaptive" else None
        while duration is None or now - start < duration:
            if incident:
                incident_rows.writerows(incident.update(conn, now))
            conn.simulationStep()
            s = sim.getSubscriptionResults()
            now = s[tc.VAR_TIME]
            loaded.update(s[tc.VAR_LOADED_VEHICLES_IDS])
            arrived, jumps = set(s[tc.VAR_ARRIVED_VEHICLES_IDS]), s[tc.VAR_TELEPORT_STARTING_VEHICLES_IDS]
            arrivals.update(arrived)
            teleported.update(jumps)
            teleports += len(jumps)
            event_rows.writerows((now, v) for v in jumps)
            collisions += s[tc.VAR_COLLIDING_VEHICLES_NUMBER]
            traffic.observe(now, arrived.union(jumps))
            if adaptive and s[tc.VAR_DEPARTED_VEHICLES_IDS]:
                adaptive.refresh(now)
            for v in sorted(s[tc.VAR_DEPARTED_VEHICLES_IDS]):
                # A departure is the decision point. A one-step subscription gets its requirements in one call.
                conn.vehicle.subscribe(v, fields, end=now, parameters={tc.VAR_NEXT_STOPS2: ("i", 0)})
                data = conn.vehicle.getSubscriptionResults(v)
                original = tuple(data[tc.VAR_EDGES])
                vclass, top = data[tc.VAR_VEHICLECLASS], data[tc.VAR_MAXSPEED]
                index = max(0, data[tc.VAR_ROUTE_INDEX])
                original = original[index:]
                if v in starts or not original:
                    raise ValueError(f"Invalid departure {v}")
                starts[v] = original[0], original[-1]
                if (vclass, top) not in graphs:
                    graphs[vclass, top] = FleetPaths(net, vclass, top)
                paths = graphs[vclass, top]
                alt = None
                action = "original" if policy == "original" else "one_route"
                if data[tc.VAR_LINE] or data[tc.VAR_ROAD_ID] != original[0]:
                    action = "scheduled_or_internal"
                elif policy != "original":
                    must = set(data[tc.VAR_VIA]) | {stop.lane.rsplit("_", 1)[0] for stop in data[tc.VAR_NEXT_STOPS2]}
                    alt = (paths.live_alternative(original, adaptive.weights(paths), must) if adaptive
                           else paths.alternative(original))
                    if must and (not must.issubset(original) or not alt or
                                 [e for e in alt if e in must] != [e for e in original if e in must]):
                        action, alt = "mandatory_route", None
                base = alt_cost = p = ""
                reserves = {}
                if adaptive and paths.permits(original):
                    base = adaptive.quote(paths, original)
                elif not adaptive and policy != "original" and all(e in paths.times for e in original):
                    base, reserves = traffic.evaluate(original, paths, now, policy)
                chosen = original
                if alt and base != "":
                    alt_reserves = {}
                    if adaptive:
                        alt_cost = adaptive.quote(paths, alt)
                        p = switch_probability(base, alt_cost)
                    else:
                        alt_cost, alt_reserves = traffic.evaluate(alt, paths, now, policy)
                        p = .5 if policy == "equal" else 1 / (1 + math.exp(max(-700, min(700, (alt_cost-base)/30))))
                    choices += 1
                    action = "kept"
                    if random.Random(f"{seed}/{v}").random() < p:
                        try:
                            conn.vehicle.setRoute(v, alt)
                        except conn.exceptions.TraCIException:
                            action = "rejected_by_sumo"
                        else:
                            action, reserves, chosen = "rerouted", alt_reserves, alt
                            if show:
                                conn.vehicle.setColor(v, (0, 220, 255, 255))
                if adaptive:
                    adaptive.assign(now, chosen)
                for edge, eta in reserves.items():
                    traffic.approaches[edge].pending[v] = eta
                actions[action] += 1
                rows.writerow((now, v, vclass, *starts[v], action, 2 if alt else 1, base, alt_cost, p))
            if not s[tc.VAR_MIN_EXPECTED_VEHICLES]:
                drained = True
                break
    if drained and loaded != starts.keys():
        raise ValueError(f"Fleet coverage: {len(loaded)} vehicles loaded, {len(starts)} considered")
    return starts, arrivals, drained, teleported, dict(
        loaded=len(loaded), with_alternative=choices, rerouted=actions["rerouted"],
        rejected=actions["rejected_by_sumo"], teleports=teleports, colliding_vehicle_events=collisions, end_s=now)


def run_fleet(cfg_file, net_file, gui, duration, policy, seed, output_dir, incident=None,
              demand_scale=1, gui_delay=0, pause_at=None):
    if not math.isfinite(demand_scale) or demand_scale <= 0:
        raise ValueError("Demand scale must be finite and positive")
    if not math.isfinite(gui_delay) or gui_delay < 0:
        raise ValueError("GUI delay must be finite and non-negative")
    if pause_at is not None and (not math.isfinite(pause_at) or pause_at < 0):
        raise ValueError("GUI pause time must be finite and non-negative")
    import sumolib
    import traci

    cfg = Path(cfg_file).resolve()
    net_override = ["-n", str(Path(net_file).resolve())] if net_file else []
    network = None
    graphs = {}
    root = Path(output_dir) if output_dir else Path(__file__).resolve().parents[2] / "output" / "fleet"
    suffix = "-incident" if incident is not None else ""
    run = root.resolve() / f"{datetime.now():%Y%m%d-%H%M%S-%f}-s{seed}-{policy}{suffix}"
    run.mkdir(parents=True)
    print(f"Fleet output: {run}", flush=True)
    policies = ("original", "equal", "previous", "queue", "adaptive") if policy == "compare" else (policy,)
    reference = None
    for name in policies:
        out = run / name
        out.mkdir()
        tripinfo = out / "tripinfo.xml.gz"
        # SUMO also writes detector and other outputs declared in the supplied configuration.
        prefix = f"fleet-{run.name}-{name}-"
        cmd = [sumolib.checkBinary("sumo-gui" if gui else "sumo"), "-c", str(cfg), *net_override,
               "--seed", str(seed), "--end", "-1", "--route-steps", "0", "--max-depart-delay", "-1",
               "--ignore-route-errors", "false", "--tripinfo-output", str(tripinfo),
               "--scale", str(demand_scale),
               "--output-prefix", prefix, "--output-suffix", "", "--output.format", "xml",
               "--tripinfo-output.write-unfinished", "true", "--tripinfo-output.write-undeparted", "true",
               "--no-step-log", "true"]
        if gui:
            cmd.extend(("--start", "--delay", str(gui_delay)))
            if pause_at is not None:
                cmd.extend(("--breakpoints", str(pause_at)))
        traci.start(cmd)
        try:
            if network is None:
                network = sumolib.net.readNet(traci.simulation.getOption("net-file"))
            event = None
            if incident is not None:
                settings = dict(incident)
                event_type = IncidentSchedule if settings.pop("dynamic", False) else RoadIncident
                event = event_type(network, seed, show=gui, **settings)
            if event:
                with (out / "incident-plan.csv").open("w", encoding="utf-8", newline="") as plan:
                    writer = csv.DictWriter(plan, fieldnames=("id", "edge", "start_s", "end_s", "severity", "speed_factor"))
                    writer.writeheader()
                    writer.writerows(event.plan)
                print(f"Incidents: {len(event.plan)} events, edges={','.join(event.edges)}", flush=True)
            if gui:
                traci.gui.setSchema(traci.gui.getIDList()[0], "standard")
            decisions, arrivals, drained, teleported, details = run_policy(
                traci, network, graphs, out, name, seed, duration, event, show=gui)
            details["demand_scale"] = demand_scale
            if event:
                details.update(event.details())
        finally:
            traci.close()
        tripinfo.with_name(prefix + tripinfo.name).rename(tripinfo)
        totals, requests = _trip_summary(tripinfo, decisions, arrivals, drained, teleported)
        if totals["complete"]:
            if reference is None:
                reference = requests
            elif reference != requests:
                raise ValueError("Paired runs do not have the same requested trips")
        metrics = dict(seed=seed, policy=name, **totals, **details)
        summary = run / "summary.csv"
        with summary.open("a", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=metrics)
            if f.tell() == 0:
                writer.writeheader()
            writer.writerow(metrics)
        print(f"{name}: {metrics}", flush=True)
    return run
