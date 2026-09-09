#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, io
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
"""
adaptive_monitor.py – Mức 5: Đèn tín hiệu thích nghi theo lưu lượng
======================================================================
Chiến lược điều khiển đèn thích nghi (Webster-inspired):

  Mỗi UPDATE_INTERVAL giây:
    1. Đo lưu lượng Bắc–Nam (N2C + S2C) và Đông–Tây (E2C + W2C)
    2. Tính tỉ lệ: ratio_NS = demand_NS / (demand_NS + demand_EW)
    3. Phân bổ thời gian xanh tỉ lệ với demand, trong giới hạn [MIN_GREEN, MAX_GREEN]
    4. Cập nhật phase duration của đèn tại nút C qua TraCI

So sánh với đèn cố định:
  - Fixed   : NS=30s, EW=30s (bất kể lưu lượng)
  - Adaptive: NS và EW thay đổi theo tỉ lệ thực tế

Sử dụng:
    python scripts/adaptive_monitor.py --scenario TH4 --nogui
    python scripts/adaptive_monitor.py --scenario TH5 --nogui --compare
"""

import os, csv, time, argparse
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent

# ─── Tham số đèn thích nghi ───────────────────────────────────────
TLS_NODE       = "C"          # ID nút giao có đèn
MIN_GREEN      = 10           # Thời gian xanh tối thiểu (giây)
MAX_GREEN      = 50           # Thời gian xanh tối đa (giây)
YELLOW_TIME    = 3            # Thời gian vàng cố định (giây)
CYCLE_TIME     = 66           # Tổng chu kỳ = NS_green + EW_green + 2*yellow
UPDATE_INTERVAL = 66          # Cập nhật mỗi 1 chu kỳ
SMOOTH_ALPHA   = 0.3          # Hệ số smoothing (tránh thay đổi đột ngột)

# Phase index trong SUMO (phụ thuộc vào cách netconvert tạo đèn)
# Phase 0: NS green, Phase 1: NS yellow, Phase 2: EW green, Phase 3: EW yellow
PHASE_NS_GREEN  = 0
PHASE_NS_YELLOW = 1
PHASE_EW_GREEN  = 2
PHASE_EW_YELLOW = 3

MONITORED_EDGES = ["N2C", "S2C", "E2C", "W2C"]
V_MAX = 13.89

# ─── Setup ────────────────────────────────────────────────────────
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

# ─── Thu thập dữ liệu ─────────────────────────────────────────────
def collect_edge(traci, eid, step):
    v  = traci.edge.getLastStepVehicleNumber(eid)
    sp = traci.edge.getLastStepMeanSpeed(eid)
    h  = traci.edge.getLastStepHaltingNumber(eid)
    w  = traci.edge.getWaitingTime(eid)
    return {"time": step, "edge": eid, "vehicles": v,
            "speed": round(sp,4), "waiting": round(w,2), "halting": h}

# ─── Tính thời gian đèn thích nghi ───────────────────────────────
def compute_green_times(demand_ns: float, demand_ew: float,
                        prev_ns: float, prev_ew: float) -> tuple:
    """
    Tính thời gian đèn xanh cho NS và EW theo tỉ lệ lưu lượng.

    Công thức Webster đơn giản hoá:
        green_NS = (demand_NS / total) * effective_green
    
    Effective green = CYCLE_TIME - 2 * YELLOW_TIME

    Thêm smoothing để tránh thay đổi đột ngột:
        green_new = alpha * computed + (1-alpha) * prev
    """
    total = demand_ns + demand_ew
    effective = CYCLE_TIME - 2 * YELLOW_TIME  # 60 giây

    if total < 2:  # Quá ít xe, dùng mặc định 50/50
        raw_ns = effective / 2
        raw_ew = effective / 2
    else:
        raw_ns = (demand_ns / total) * effective
        raw_ew = (demand_ew / total) * effective

    # Giới hạn trong [MIN_GREEN, MAX_GREEN]
    raw_ns = max(MIN_GREEN, min(MAX_GREEN, raw_ns))
    raw_ew = max(MIN_GREEN, min(MAX_GREEN, raw_ew))

    # Điều chỉnh để tổng = effective
    total_raw = raw_ns + raw_ew
    if total_raw > 0:
        raw_ns = raw_ns / total_raw * effective
        raw_ew = raw_ew / total_raw * effective

    # Smoothing
    ns = SMOOTH_ALPHA * raw_ns + (1 - SMOOTH_ALPHA) * prev_ns
    ew = SMOOTH_ALPHA * raw_ew + (1 - SMOOTH_ALPHA) * prev_ew

    return round(ns), round(ew)

# ─── Hàm chính ───────────────────────────────────────────────────
def run(scenario="TH4", use_gui=True, duration=3600, compare_fixed=False):
    sumo_home = setup_sumo()
    import traci

    out_dir = PROJECT_DIR / "output"
    out_dir.mkdir(parents=True, exist_ok=True)

    cfg    = PROJECT_DIR / "intersection.sumocfg"
    routes = PROJECT_DIR / "routes" / f"routes_{scenario}.rou.xml"
    csv_f  = out_dir / f"traffic_adaptive_{scenario}.csv"
    trip_f = out_dir / f"tripinfo_adaptive_{scenario}.xml"

    sumo_bin = "sumo-gui" if use_gui else "sumo"
    sp = Path(sumo_home) / "bin" / f"{sumo_bin}.exe"
    if sp.exists(): sumo_bin = str(sp)

    cmd = [sumo_bin, "--configuration-file", str(cfg),
           "--route-files", str(routes),
           "--tripinfo-output", str(trip_f),
           "--end", str(duration),
           "--time-to-teleport", "-1",
           "--no-warnings", "--no-step-log"]

    demand_labels = {
        "TH1":200,"TH2":400,"TH3":600,"TH4":800,"TH5":1000,"TH6":1200
    }
    print(f"\n{'#'*62}")
    print(f"  ADAPTIVE TLS MONITOR – Kich ban {scenario}")
    print(f"  Luu luong: {demand_labels.get(scenario,0)} xe/h/huong")
    print(f"  Chien luoc: Den thich nghi (Webster-inspired)")
    print(f"  Cap nhat moi: {UPDATE_INTERVAL} giay")
    print(f"  Green range: [{MIN_GREEN}s, {MAX_GREEN}s]")
    print(f"{'#'*62}")

    traci.start(cmd)
    print("\n[OK] Ket noi SUMO thanh cong")

    # Trạng thái ban đầu của đèn
    prev_ns = 30.0
    prev_ew = 30.0
    tls_log = []  # Lưu lịch sử thay đổi đèn

    with open(csv_f, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["time","edge","vehicles","speed","waiting","halting",
                      "ns_green","ew_green","tls_mode"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        step = 0
        current_ns_green = 30
        current_ew_green = 30

        try:
            while traci.simulation.getMinExpectedNumber() > 0 and step < duration:
                traci.simulationStep()
                step += 1

                # ── Cập nhật đèn mỗi UPDATE_INTERVAL bước ──
                if step % UPDATE_INTERVAL == 0:
                    demand_ns = (
                        traci.edge.getLastStepVehicleNumber("N2C") +
                        traci.edge.getLastStepVehicleNumber("S2C")
                    )
                    demand_ew = (
                        traci.edge.getLastStepVehicleNumber("E2C") +
                        traci.edge.getLastStepVehicleNumber("W2C")
                    )

                    new_ns, new_ew = compute_green_times(
                        demand_ns, demand_ew, prev_ns, prev_ew)

                    # Chỉ cập nhật nếu thay đổi >= 2 giây (tránh dao động nhỏ)
                    if abs(new_ns - current_ns_green) >= 2:
                        try:
                            # Cập nhật duration của phase NS_GREEN hiện tại
                            cur_phase = traci.trafficlight.getPhase(TLS_NODE)
                            traci.trafficlight.setPhaseDuration(TLS_NODE, new_ns)
                            current_ns_green = new_ns
                            current_ew_green = new_ew
                            prev_ns, prev_ew  = new_ns, new_ew

                            tls_log.append({
                                "step": step, "demand_ns": demand_ns,
                                "demand_ew": demand_ew,
                                "ns_green": new_ns, "ew_green": new_ew
                            })
                            if step % 300 == 0:
                                print(f"  t={step:4d}s | "
                                      f"NS_demand={demand_ns:3d} EW_demand={demand_ew:3d} | "
                                      f"NS_green={new_ns:2d}s EW_green={new_ew:2d}s")
                        except Exception:
                            pass  # TraCI có thể báo lỗi nếu pha không phù hợp

                # ── Thu thập dữ liệu ──
                for edge in MONITORED_EDGES:
                    row = collect_edge(traci, edge, step)
                    row["ns_green"]  = current_ns_green
                    row["ew_green"]  = current_ew_green
                    row["tls_mode"]  = "adaptive"
                    writer.writerow(row)

                if step % 10 == 0:
                    f.flush()

        except KeyboardInterrupt:
            print("\n[!] Dung boi nguoi dung")
        finally:
            print(f"\n  Lich su thay doi den: {len(tls_log)} lan")
            if tls_log:
                ns_vals = [l["ns_green"] for l in tls_log]
                ew_vals = [l["ew_green"] for l in tls_log]
                print(f"  NS green: min={min(ns_vals)}s, max={max(ns_vals)}s, avg={sum(ns_vals)/len(ns_vals):.1f}s")
                print(f"  EW green: min={min(ew_vals)}s, max={max(ew_vals)}s, avg={sum(ew_vals)/len(ew_vals):.1f}s")
            print(f"\n[OK] Da ghi: {csv_f}")
            traci.close()

# ─── CLI ─────────────────────────────────────────────────────────
def parse_args():
    p = argparse.ArgumentParser(description="Muc 5: Adaptive TLS Monitor")
    p.add_argument("--scenario", default="TH4",
                   choices=["TH1","TH2","TH3","TH4","TH5","TH6"])
    p.add_argument("--nogui", action="store_true")
    p.add_argument("--duration", type=int, default=3600)
    p.add_argument("--compare", action="store_true",
                   help="So sanh voi fixed-time (chay them 1 lan)")
    return p.parse_args()

if __name__ == "__main__":
    args = parse_args()
    run(scenario=args.scenario, use_gui=not args.nogui,
        duration=args.duration, compare_fixed=args.compare)
