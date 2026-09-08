#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, io
# Fix Unicode output tren Windows console
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
"""
monitor.py – Thu thập dữ liệu giao thông từ SUMO qua TraCI
===========================================================
Script này thực hiện các bước theo Báo cáo 2:
  1. Khởi động SUMO (GUI hoặc không GUI)
  2. Kết nối qua TraCI
  3. Chạy simulation từng bước (simulationStep)
  4. Mỗi bước đọc các chỉ số từ 4 cạnh vào (N2C, S2C, E2C, W2C):
       - vehicleCount  : N_ij(t)
       - meanSpeed     : V_ij(t)
       - waitingTime   : W_ij(t)
       - haltingNumber : H_ij(t)
       - travelTime    : T_ij(t)
  5. Ghi ra output/traffic.csv
  6. Tính chỉ số ùn tắc sơ bộ Congestion_ij

Sử dụng:
    python scripts/monitor.py                    # chạy với GUI, TH3 mặc định
    python scripts/monitor.py --nogui            # chạy không GUI (nhanh hơn)
    python scripts/monitor.py --scenario TH1     # chạy kịch bản TH1
    python scripts/monitor.py --scenario TH5 --nogui --duration 1800
"""

import os
import sys
import csv
import time
import argparse
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple


# ─────────────────────────────────────────────────────────────────
# Cấu hình đường dẫn
# ─────────────────────────────────────────────────────────────────

PROJECT_DIR = Path(__file__).parent.parent.resolve()

# Thêm thư mục tools của SUMO vào sys.path để import traci
def setup_sumo_path():
    """Thiết lập SUMO_HOME và thêm traci vào Python path."""
    sumo_home = os.environ.get("SUMO_HOME")
    if not sumo_home:
        # Thử các đường dẫn phổ biến trên Windows
        candidates = [
            "C:/Program Files (x86)/Eclipse/Sumo",
            "C:/Program Files/Eclipse/Sumo",
            "C:/sumo",
        ]
        for c in candidates:
            if Path(c).exists():
                sumo_home = c
                os.environ["SUMO_HOME"] = sumo_home
                break

    if not sumo_home:
        raise EnvironmentError(
            "Không tìm thấy SUMO_HOME.\n"
            "Hãy cài SUMO từ https://sumo.dlr.de và set SUMO_HOME."
        )

    tools_dir = os.path.join(sumo_home, "tools")
    if tools_dir not in sys.path:
        sys.path.append(tools_dir)

    return sumo_home


# ─────────────────────────────────────────────────────────────────
# Tham số kịch bản
# ─────────────────────────────────────────────────────────────────

# Các cạnh cần theo dõi (cạnh vào nút trung tâm)
MONITORED_EDGES = ["N2C", "S2C", "E2C", "W2C"]

# Tốc độ tối đa của đường (m/s) – 50 km/h
V_MAX = 13.89

# Trọng số cho chỉ số ùn tắc tổng hợp (Báo cáo 2, mục 10)
# Congestion_ij = a*N + b*H + c*W + d*(1 - V/Vmax)
CONGESTION_WEIGHTS = {
    "a": 0.3,   # trọng số số xe
    "b": 0.3,   # trọng số xe đang dừng
    "c": 0.2,   # trọng số waiting time
    "d": 0.2,   # trọng số tốc độ
}

# Giá trị chuẩn hóa (normalization) để scale về [0,1]
NORM = {
    "vehicles": 50,      # số xe tối đa dự kiến trên cạnh
    "halting":  50,      # số xe đang dừng tối đa
    "waiting":  300.0,   # waiting time tối đa (giây)
}


# ─────────────────────────────────────────────────────────────────
# Hàm tính chỉ số ùn tắc
# ─────────────────────────────────────────────────────────────────

def compute_congestion(vehicles: int, halting: int, waiting: float, speed: float) -> float:
    """
    Tính chỉ số ùn tắc tổng hợp (Báo cáo 2, mục 10).

    Congestion_ij = a*N_norm + b*H_norm + c*W_norm + d*(1 - V/Vmax)

    Các thành phần được chuẩn hóa về [0, 1] trước khi tổng hợp.

    Args:
        vehicles: Số phương tiện trên cạnh
        halting : Số phương tiện đang dừng (speed < 0.1 m/s)
        waiting : Tổng waiting time (giây)
        speed   : Tốc độ trung bình (m/s)

    Returns:
        Chỉ số ùn tắc trong [0, 1]
    """
    w = CONGESTION_WEIGHTS
    n = NORM

    n_norm = min(vehicles / n["vehicles"], 1.0)
    h_norm = min(halting  / n["halting"],  1.0)
    w_norm = min(waiting  / n["waiting"],  1.0)
    v_norm = 1.0 - min(speed / V_MAX, 1.0)  # càng chậm càng cao

    congestion = (
        w["a"] * n_norm +
        w["b"] * h_norm +
        w["c"] * w_norm +
        w["d"] * v_norm
    )
    return round(congestion, 4)


# ─────────────────────────────────────────────────────────────────
# Hàm thu thập dữ liệu từ một edge
# ─────────────────────────────────────────────────────────────────

def collect_edge_data(traci, edge_id: str, step: int) -> Dict:
    """
    Thu thập tất cả chỉ số từ một edge tại bước simulation hiện tại.

    Tương ứng với Báo cáo 2, mục 8:
      8.1 Vehicle count   → traci.edge.getLastStepVehicleNumber()
      8.2 Mean speed      → traci.edge.getLastStepMeanSpeed()
      8.3 Halting number  → traci.edge.getLastStepHaltingNumber()
      8.4 Waiting time    → traci.edge.getWaitingTime()
      8.5 Travel time     → traci.edge.getTraveltime()

    Args:
        traci   : Module TraCI đã kết nối
        edge_id : ID của cạnh (ví dụ "N2C")
        step    : Bước thời gian hiện tại (giây)

    Returns:
        Dictionary chứa tất cả dữ liệu của cạnh
    """
    vehicles = traci.edge.getLastStepVehicleNumber(edge_id)
    speed    = traci.edge.getLastStepMeanSpeed(edge_id)
    halting  = traci.edge.getLastStepHaltingNumber(edge_id)
    waiting  = traci.edge.getWaitingTime(edge_id)
    travel   = traci.edge.getTraveltime(edge_id)

    congestion = compute_congestion(vehicles, halting, waiting, speed)

    return {
        "time":       step,
        "edge":       edge_id,
        "vehicles":   vehicles,
        "speed":      round(speed, 4),
        "waiting":    round(waiting, 2),
        "halting":    halting,
        "traveltime": round(travel, 2),
        "congestion": congestion,
    }


# ─────────────────────────────────────────────────────────────────
# Hàm in bảng dữ liệu ra console (Báo cáo 2, mục 9)
# ─────────────────────────────────────────────────────────────────

def print_step_report(step: int, data: List[Dict]):
    """In báo cáo trạng thái tại một bước simulation."""
    print(f"\n{'='*60}")
    print(f"  TIME = {step} s")
    print(f"{'='*60}")
    print(f"  {'Edge':<6} {'Vehicles':>9} {'Speed(m/s)':>11} "
          f"{'Waiting(s)':>11} {'Halting':>8} {'Congestion':>11}")
    print(f"  {'-'*58}")
    for d in data:
        print(f"  {d['edge']:<6} {d['vehicles']:>9} {d['speed']:>11.2f} "
              f"{d['waiting']:>11.2f} {d['halting']:>8} {d['congestion']:>11.4f}")


# ─────────────────────────────────────────────────────────────────
# Hàm chính: Chạy simulation và thu thập dữ liệu
# ─────────────────────────────────────────────────────────────────

def run_simulation(
    scenario:    str  = "TH3",
    use_gui:     bool = True,
    duration:    int  = 3600,
    report_step: int  = 100,
    output_dir:  Path = None,
) -> str:
    """
    Khởi động SUMO, chạy simulation và ghi dữ liệu ra CSV.

    Args:
        scenario   : Tên kịch bản ("TH1" đến "TH6")
        use_gui    : Mở SUMO-GUI (True) hay chạy không GUI (False)
        duration   : Số giây mô phỏng
        report_step: In báo cáo console mỗi N bước
        output_dir : Thư mục lưu kết quả

    Returns:
        Đường dẫn file CSV đã ghi
    """
    sumo_home = setup_sumo_path()
    import traci

    if output_dir is None:
        output_dir = PROJECT_DIR / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Đường dẫn các file
    cfg_file      = PROJECT_DIR / "intersection.sumocfg"
    routes_file   = PROJECT_DIR / "routes" / f"routes_{scenario}.rou.xml"
    tripinfo_file = output_dir / f"tripinfo_{scenario}.xml"
    csv_file      = output_dir / f"traffic_{scenario}.csv"

    if not routes_file.exists():
        raise FileNotFoundError(f"Không tìm thấy file routes: {routes_file}")

    # Chọn binary SUMO
    sumo_bin = "sumo-gui" if use_gui else "sumo"
    sumo_path = Path(sumo_home) / "bin" / f"{sumo_bin}.exe"
    if sumo_path.exists():
        sumo_bin = str(sumo_path)

    # Tham số SUMO
    sumo_cmd = [
        sumo_bin,
        "--configuration-file", str(cfg_file),
        "--route-files",        str(routes_file),
        "--tripinfo-output",    str(tripinfo_file),
        "--end",                str(duration),
        "--time-to-teleport",   "-1",       # không teleport xe bị kẹt
        "--no-warnings",
        "--no-step-log",
    ]

    print(f"\n{'#'*60}")
    print(f"  SUMO Traffic Monitor – Kịch bản {scenario}")
    print(f"  Lưu lượng: {_scenario_demand(scenario)} xe/h mỗi hướng")
    print(f"  Thời gian mô phỏng: {duration} giây")
    print(f"  Output CSV: {csv_file}")
    print(f"{'#'*60}")

    # ── Kết nối TraCI ──
    traci.start(sumo_cmd)
    print("\n[OK] Kết nối SUMO thành công qua TraCI")

    # ── Mở file CSV để ghi ──
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        # Header theo Báo cáo 2, mục 13 (Tiêu chí 6)
        fieldnames = [
            "time", "edge", "vehicles", "speed",
            "waiting", "halting", "traveltime", "congestion"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        step = 0
        start_wall = time.time()

        try:
            while traci.simulation.getMinExpectedNumber() > 0 and step < duration:

                traci.simulationStep()
                step += 1

                # Thu thập dữ liệu từ tất cả cạnh được theo dõi
                step_data = []
                for edge_id in MONITORED_EDGES:
                    row = collect_edge_data(traci, edge_id, step)
                    step_data.append(row)
                    writer.writerow(row)

                # Flush mỗi 10 bước để không mất dữ liệu nếu crash
                if step % 10 == 0:
                    f.flush()

                # In báo cáo console theo khoảng thời gian
                if step % report_step == 0:
                    print_step_report(step, step_data)

        except KeyboardInterrupt:
            print("\n[!] Mô phỏng bị dừng bởi người dùng (Ctrl+C)")

        finally:
            elapsed = time.time() - start_wall
            print(f"\n{'='*60}")
            print(f"  Mô phỏng kết thúc tại t = {step}s")
            print(f"  Thời gian wall-clock: {elapsed:.1f}s")
            print(f"  Đã ghi: {csv_file}")
            print(f"{'='*60}")
            traci.close()

    return str(csv_file)


# ─────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────

def _scenario_demand(scenario: str) -> int:
    """Trả về lưu lượng xe/h của kịch bản."""
    mapping = {
        "TH1": 200, "TH2": 400, "TH3": 600,
        "TH4": 800, "TH5": 1000, "TH6": 1200,
    }
    return mapping.get(scenario, 0)


# ─────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Monitor giao thông SUMO qua TraCI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ví dụ:
  python scripts/monitor.py
  python scripts/monitor.py --nogui --scenario TH5
  python scripts/monitor.py --scenario TH1 --duration 1800 --report-step 50
        """
    )
    parser.add_argument(
        "--scenario", type=str, default="TH3",
        choices=["TH1", "TH2", "TH3", "TH4", "TH5", "TH6"],
        help="Kịch bản thí nghiệm (mặc định: TH3 – 600 xe/h)"
    )
    parser.add_argument(
        "--nogui", action="store_true",
        help="Chạy không có SUMO-GUI (nhanh hơn, dùng cho batch)"
    )
    parser.add_argument(
        "--duration", type=int, default=3600,
        help="Thời gian mô phỏng tính bằng giây (mặc định: 3600)"
    )
    parser.add_argument(
        "--report-step", type=int, default=100,
        help="In báo cáo mỗi N bước (mặc định: 100)"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_simulation(
        scenario    = args.scenario,
        use_gui     = not args.nogui,
        duration    = args.duration,
        report_step = args.report_step,
    )
