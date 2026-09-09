#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, io
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
"""
incident_monitor.py – Mức 4: Mô phỏng sự kiện bất thường
===========================================================
Mô phỏng các loại sự cố giao thông trong khi simulation đang chạy:

  TYPE 1 – BLOCK_EDGE   : Chặn hoàn toàn một cạnh (đường đóng, ngập)
  TYPE 2 – SPEED_REDUCE  : Giảm tốc độ một cạnh (mưa, đường xấu)
  TYPE 3 – VEHICLE_STOP  : Dừng một xe giữa đường (tai nạn)
  TYPE 4 – DEMAND_SURGE  : Tăng lưu lượng đột ngột (sự kiện, giờ tan trường)

Cách dùng:
    python scripts/incident_monitor.py
    python scripts/incident_monitor.py --nogui --scenario TH3
    python scripts/incident_monitor.py --nogui --incident-type block
    python scripts/incident_monitor.py --nogui --incident-type all
"""

import os, csv, time, argparse, random
from pathlib import Path
from typing import Dict, List


PROJECT_DIR = Path(__file__).resolve().parent.parent.parent

# ─── Thiết lập SUMO ───────────────────────────────────────────────
def setup_sumo():
    sumo_home = os.environ.get("SUMO_HOME")
    if not sumo_home:
        for c in ["C:/Program Files (x86)/Eclipse/Sumo",
                  "C:/Program Files/Eclipse/Sumo", "C:/sumo"]:
            if Path(c).exists():
                sumo_home = c
                os.environ["SUMO_HOME"] = c
                break
    if not sumo_home:
        raise EnvironmentError("SUMO_HOME chua duoc set.")
    tools = os.path.join(sumo_home, "tools")
    if tools not in sys.path:
        sys.path.append(tools)
    return sumo_home

# ─── Định nghĩa sự cố ────────────────────────────────────────────
INCIDENTS = {
    "block": [
        # (thời điểm bắt đầu, thời điểm kết thúc, cạnh bị chặn)
        {"start": 900,  "end": 1500, "edge": "E2C", "type": "block",
         "desc": "Chặn cạnh E2C (đường đóng do ngập)"},
        {"start": 2400, "end": 3000, "edge": "N2C", "type": "block",
         "desc": "Chặn cạnh N2C (đường đóng do sự cố)"},
    ],
    "speed": [
        # (thời điểm, cạnh, tốc độ mới m/s)
        {"start": 600,  "end": 1800, "edge": "W2C", "speed": 4.17,  "type": "speed",
         "desc": "Giam toc W2C xuong 15km/h (mua lon)"},
        {"start": 2100, "end": 2700, "edge": "S2C", "speed": 6.94,  "type": "speed",
         "desc": "Giam toc S2C xuong 25km/h (duong uot)"},
    ],
    "surge": [
        # Tăng đột biến lưu lượng tại t=1200 – mô phỏng tan trường/sự kiện
        {"start": 1200, "end": 1500, "extra_vph": 800, "type": "surge",
         "desc": "Tan truong: +800 xe/h Bac-Nam trong 5 phut"},
    ],
}

MONITORED_EDGES = ["N2C", "S2C", "E2C", "W2C"]
V_MAX = 13.89

# ─── Thu thập dữ liệu cạnh ────────────────────────────────────────
def collect_edge(traci, edge_id, step):
    v  = traci.edge.getLastStepVehicleNumber(edge_id)
    sp = traci.edge.getLastStepMeanSpeed(edge_id)
    h  = traci.edge.getLastStepHaltingNumber(edge_id)
    w  = traci.edge.getWaitingTime(edge_id)
    t  = traci.edge.getTraveltime(edge_id)
    blocked = traci.edge.getLastStepMeanSpeed(edge_id) < 0.01
    return {"time": step, "edge": edge_id,
            "vehicles": v, "speed": round(sp,4),
            "waiting": round(w,2), "halting": h,
            "traveltime": round(t,2), "blocked": int(blocked)}

# ─── Áp dụng sự cố vào TraCI ──────────────────────────────────────
def apply_incident(traci, incident, step, active_incidents):
    key = f"{incident['type']}_{incident.get('edge','surge')}_{incident['start']}"

    if incident["start"] == step:
        print(f"\n  [!!! SU CO !!!] t={step}s - {incident['desc']}")
        active_incidents.add(key)

        if incident["type"] == "block":
            # Giam toc xuong gan bang 0 (0.1 m/s) thay vi setDisallowed
            # Vi setDisallowed gay crash khi flow con dang depart tu edge do.
            # Xe hien tai tren edge se ket, sau 60s se duoc teleport (--time-to-teleport 60).
            # Xe moi muon vao edge se phai di rat cham → hanh long ung xu nhu duong bi chan.
            edge = incident["edge"]
            traci.edge.setMaxSpeed(edge, 0.1)  # 0.1 m/s ≈ 0.36 km/h = gan bo hoan toan
            print(f"    → Chan {edge}: setMaxSpeed=0.1 m/s (xe bi ket, teleport sau 60s)")

        elif incident["type"] == "speed":
            traci.edge.setMaxSpeed(incident["edge"], incident["speed"])
            kmh = round(incident["speed"] * 3.6, 1)
            print(f"    → Giam toc {incident['edge']} xuong {kmh} km/h")

    elif incident["end"] == step and key in active_incidents:
        print(f"\n  [PHUC HOI] t={step}s - {incident['desc']} ket thuc")
        active_incidents.discard(key)

        if incident["type"] == "block":
            edge = incident["edge"]
            traci.edge.setMaxSpeed(edge, V_MAX)  # Phuc hoi toc do ban dau
            print(f"    → Mo lai {edge}: setMaxSpeed={V_MAX} m/s")

        elif incident["type"] == "speed":
            traci.edge.setMaxSpeed(incident["edge"], V_MAX)
            print(f"    → Phuc hoi toc do {incident['edge']} = {V_MAX} m/s")

# ─── Hàm chính ───────────────────────────────────────────────────
def run(scenario="TH3", use_gui=True, incident_type="all", duration=3600):
    sumo_home = setup_sumo()
    import traci

    out_dir = PROJECT_DIR / "output"
    out_dir.mkdir(parents=True, exist_ok=True)

    cfg   = PROJECT_DIR / "intersection.sumocfg"
    routes = PROJECT_DIR / "routes" / f"routes_{scenario}.rou.xml"
    csv_f  = out_dir / f"traffic_incident_{scenario}_{incident_type}.csv"
    trip_f = out_dir / f"tripinfo_incident_{scenario}_{incident_type}.xml"

    sumo_bin = "sumo-gui" if use_gui else "sumo"
    sp = Path(sumo_home) / "bin" / f"{sumo_bin}.exe"
    if sp.exists(): sumo_bin = str(sp)

    cmd = [sumo_bin, "--configuration-file", str(cfg),
           "--route-files", str(routes),
           "--tripinfo-output", str(trip_f),
           "--end", str(duration),
           # Khi block edge, xe scheduled depart se bi bo qua thay vi crash
           "--ignore-route-errors",
           # Xe ket phia sau edge bi chan se teleport sau 60s (thuc te hon)
           "--time-to-teleport", "60",
           "--no-warnings", "--no-step-log"]

    # Chọn danh sách sự cố
    incidents_to_apply = []
    if incident_type == "all":
        for v in INCIDENTS.values():
            incidents_to_apply.extend(v)
    elif incident_type in INCIDENTS:
        incidents_to_apply = INCIDENTS[incident_type]

    print(f"\n{'#'*62}")
    print(f"  INCIDENT MONITOR – Kich ban {scenario}")
    print(f"  Loai su co: {incident_type}")
    print(f"  So su co duoc lap lich: {len(incidents_to_apply)}")
    for inc in incidents_to_apply:
        print(f"    t={inc['start']}–{inc['end']}s : {inc['desc']}")
    print(f"{'#'*62}")

    traci.start(cmd)
    print("\n[OK] Ket noi SUMO thanh cong")

    active_incidents = set()

    with open(csv_f, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["time","edge","vehicles","speed","waiting",
                      "halting","traveltime","blocked","incident_active"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        step = 0
        try:
            while traci.simulation.getMinExpectedNumber() > 0 and step < duration:
                traci.simulationStep()
                step += 1

                # Kiểm tra và áp dụng sự cố
                for inc in incidents_to_apply:
                    apply_incident(traci, inc, step, active_incidents)

                # Thu thập dữ liệu
                n_active = len(active_incidents)
                for edge in MONITORED_EDGES:
                    row = collect_edge(traci, edge, step)
                    row["incident_active"] = n_active
                    writer.writerow(row)

                if step % 10 == 0:
                    f.flush()

                if step % 100 == 0:
                    print(f"  t={step:4d}s | "
                          f"Su co active: {n_active} | "
                          f"Xe tren duong: {traci.vehicle.getIDCount()}")

        except KeyboardInterrupt:
            print("\n[!] Dung boi nguoi dung")
        finally:
            print(f"\n[OK] Hoan tat. Da ghi: {csv_f}")
            traci.close()

# ─── CLI ─────────────────────────────────────────────────────────
def parse_args():
    p = argparse.ArgumentParser(description="Muc 4: Incident Monitor")
    p.add_argument("--scenario", default="TH3",
                   choices=["TH1","TH2","TH3","TH4","TH5","TH6"])
    p.add_argument("--nogui", action="store_true")
    p.add_argument("--incident-type", default="all",
                   choices=["all","block","speed","surge"],
                   dest="incident_type")
    p.add_argument("--duration", type=int, default=3600)
    return p.parse_args()

if __name__ == "__main__":
    args = parse_args()
    run(scenario=args.scenario, use_gui=not args.nogui,
        incident_type=args.incident_type, duration=args.duration)
