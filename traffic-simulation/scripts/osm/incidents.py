"""Repeatable traffic incidents, including a bounded regional event schedule."""
import math
import random


def _roads(net, area):
    if area is not None:
        if (len(area) != 4 or not all(math.isfinite(v) for v in area)
                or area[0] >= area[2] or area[1] >= area[3]):
            raise ValueError("Incident area requires finite XMIN YMIN XMAX YMAX with increasing bounds")
    roads = sorted(e.getID() for e in net.getEdges()
                   if e.allows("passenger") and e.getLength() >= 50
                   and e.getIncoming() and e.getAllowedOutgoing("passenger")
                   and (area is None or all(area[0] <= x <= area[2] and area[1] <= y <= area[3]
                                            for x, y in e.getShape())))
    if not roads:
        raise ValueError("No passenger through road of at least 50 m inside the incident area")
    return roads


class RoadIncident:
    """Apply and restore one severity on distinct roads over a fixed interval."""

    log_fields = ("event", "time_s", "edge", "lane", "before_mps", "after_mps")

    def __init__(self, net, seed, start=900, duration=900, speed_factor=.2, count=1, show=False,
                 area=None, edge=None, color=(255, 40, 40, 255)):
        if not all(math.isfinite(v) for v in (start, duration, start + duration, speed_factor)):
            raise ValueError("Incident parameters must be finite")
        if start < 0 or duration <= 0 or not 0 < speed_factor < 1:
            raise ValueError("Incident requires start >= 0, duration > 0 and 0 < speed factor < 1")
        candidates = _roads(net, area)
        if type(count) is not int or not 1 <= count <= len(candidates):
            raise ValueError(f"Incident count must be an integer from 1 to {len(candidates)}")
        if edge is not None and (edge not in candidates or count != 1):
            raise ValueError("An explicit incident edge must be an eligible road with count=1")
        rng = random.Random(f"incident/{seed}")
        self.edge = rng.choice(candidates) if edge is None else edge
        candidates.remove(self.edge)
        rng.shuffle(candidates)
        self.edges = (self.edge, *candidates[:count-1])
        self.lanes = tuple(lane.getID() for eid in self.edges for lane in net.getEdge(eid).getLanes())
        self.shapes = {eid: net.getEdge(eid).getShape() for eid in self.edges} if show else {}
        self.start, self.end, self.speed_factor = start, start + duration, speed_factor
        self.area, self.color = area, color
        self.original_speeds = {}
        self.active = False
        self.plan = [dict(id=f"fixed-{i}", edge=eid, start_s=self.start, end_s=self.end,
                          severity="fixed", speed_factor=speed_factor) for i, eid in enumerate(self.edges, 1)]

    def update(self, conn, now):
        active = self.start <= now < self.end
        if active == self.active:
            return []
        if active:
            self.original_speeds = {lane: conn.lane.getMaxSpeed(lane) for lane in self.lanes}
        rows = []
        for lane, original in self.original_speeds.items():
            before = conn.lane.getMaxSpeed(lane)
            after = original * self.speed_factor if active else original
            conn.lane.setMaxSpeed(lane, after)
            rows.append(("start" if active else "restore", now, lane.rsplit("_", 1)[0], lane, before, after))
        if self.shapes:
            from sumolib.geomhelper import polyLength, positionAtShapeOffset

            for i, (eid, shape) in enumerate(self.shapes.items(), 1):
                road, pin = f"accident-road-{i}-{eid}", f"Tai_nan_{i}_{eid}"
                if active:
                    conn.polygon.add(road, shape, self.color, layer=10, lineWidth=6)
                    x, y = positionAtShapeOffset(shape, polyLength(shape) / 2)
                    conn.poi.add(pin, x, y, self.color, poiType="Tai nan",
                                 layer=20, width=35, height=35, icon="pin")
                else:
                    conn.polygon.remove(road, layer=10)
                    conn.poi.remove(pin, layer=20)
        self.active = active
        return rows

    def details(self):
        return dict(incident_edge=self.edge, incident_start_s=self.start, incident_end_s=self.end,
                    incident_speed_factor=self.speed_factor, incident_applied=bool(self.original_speeds),
                    incident_count=len(self.edges), incident_edges=" ".join(self.edges), incident_mode="fixed",
                    incident_applied_count=len(self.edges) if self.original_speeds else 0,
                    incident_area=" ".join(str(v) for v in self.area) if self.area is not None else "")


class IncidentSchedule:
    """Plan incidents before simulation so every policy sees the same events."""

    log_fields = RoadIncident.log_fields + ("incident_id", "severity", "start_s", "end_s", "speed_factor")
    levels = (("light", .7, 300, (255, 210, 0, 255)),
              ("moderate", .4, 600, (255, 135, 0, 255)),
              ("severe", .2, 1200, (255, 40, 40, 255)),
              ("critical", .1, 1800, (135, 0, 20, 255)))

    def __init__(self, net, seed, start=900, duration=2700, count=5, area=None, show=False):
        if (not all(math.isfinite(v) for v in (start, duration, start + duration))
                or start < 0 or duration <= 0):
            raise ValueError("Dynamic incidents require finite start >= 0 and duration > 0")
        if type(count) is not int or count < 1:
            raise ValueError("Maximum concurrent incidents must be a positive integer")
        self.area = tuple(net.getBoundary() if area is None else area)
        candidates = _roads(net, self.area)
        self.limit = min(count, len(candidates))
        self.start, self.end = start, start + duration
        self.show, self.area_drawn = show, False
        self.plan, self.events = [], []
        rng = random.Random(f"incident-schedule/{seed}")
        when = start
        while when < self.end:
            active = {p["edge"] for p in self.plan if p["end_s"] > when}
            available = [eid for eid in candidates if eid not in active]
            if len(active) < self.limit and available:
                eid = rng.choice(available)
                severity, factor, seconds, color = rng.choices(self.levels, weights=(4, 3, 2, 1))[0]
                self.plan.append(dict(id=f"incident-{len(self.plan)+1:04d}", edge=eid, start_s=when,
                                      end_s=when+seconds, severity=severity, speed_factor=factor))
                self.events.append(RoadIncident(net, seed, start=when, duration=seconds,
                                                speed_factor=factor, show=show, area=self.area,
                                                edge=eid, color=color))
            when += rng.randint(120, 300)
        self.edges = tuple(dict.fromkeys(p["edge"] for p in self.plan))

    def update(self, conn, now):
        if self.show and not self.area_drawn:
            x1, y1, x2, y2 = self.area
            conn.polygon.add("incident-region", ((x1, y1), (x2, y1), (x2, y2), (x1, y2), (x1, y1)),
                             (55, 95, 200, 220), layer=5, lineWidth=2)
            self.area_drawn = True
        rows = []
        for plan, event in zip(self.plan, self.events):
            for row in event.update(conn, now):
                rows.append((*row, plan["id"], plan["severity"], plan["start_s"], plan["end_s"],
                             plan["speed_factor"]))
        return rows

    def details(self):
        applied = sum(bool(event.original_speeds) for event in self.events)
        return dict(incident_edge=self.edges[0], incident_start_s=self.start,
                    incident_end_s=max(p["end_s"] for p in self.plan), incident_speed_factor="mixed",
                    incident_applied=applied > 0, incident_count=len(self.plan),
                    incident_edges=" ".join(self.edges), incident_mode="dynamic",
                    incident_applied_count=applied, incident_max_active=self.limit,
                    incident_spawn_until_s=self.end, incident_area=" ".join(str(v) for v in self.area))
