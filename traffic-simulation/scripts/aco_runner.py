#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
aco_runner.py – Tích hợp ACO với SUMO qua TraCI
=================================================

Script chính chạy ACO trên mạng 3×3 SUMO:
  1. Khởi động SUMO, kết nối TraCI
  2. Sinh phương tiện ACO-controlled
  3. Mỗi REROUTE_INTERVAL bước:
       → Cập nhật đồ thị từ TraCI
       → Chạy ACO tìm tuyến tối ưu
       → Gán tuyến mới cho phương tiện qua traci.vehicle.setRoute()
  4. Ghi log kết quả

Tham chiếu:
  - Báo cáo 1, Mục 5.3: Tái định tuyến khi giao thông thay đổi
  - Báo cáo 1, Mục 6: Kiến trúc đề xuất

Sử dụng:
    python scripts/aco_runner.py                           # GUI, mặc định
    python scripts/aco_runner.py --nogui --duration 600    # không GUI, 600s
    python scripts/aco_runner.py --aco-mode basic          # ACO chỉ khoảng cách
    python scripts/aco_runner.py --origin A --dest I       # từ A đến I
"""

import sys
import io
import os
import csv
import time
import argparse
from pathlib import Path
from typing import Dict, List, Optional

# Fix Unicode output trên Windows console
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# ─────────────────────────────────────────────────────────────────
# Đường dẫn
# ─────────────────────────────────────────────────────────────────

PROJECT_DIR = Path(__file__).parent.parent.resolve()
SCRIPTS_DIR = Path(__file__).parent.resolve()

# Thêm scripts vào path để import aco, routing
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from aco import TrafficGraph, AntColonyOptimizer, GRID_ADJACENCY
from routing import (dijkstra_static, dijkstra_traffic, dijkstra_dynamic,
                     astar, print_comparison_table)


# ─────────────────────────────────────────────────────────────────
# Thiết lập SUMO
# ─────────────────────────────────────────────────────────────────

def setup_sumo_path():
    """Thiết lập SUMO_HOME và thêm traci vào Python path."""
    sumo_home = os.environ.get("SUMO_HOME")
    if not sumo_home:
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
# In trạng thái giao thông
# ─────────────────────────────────────────────────────────────────

def print_traffic_state(step: int, graph: TrafficGraph, edges_to_show: List = None):
    """In trạng thái giao thông hiện tại."""
    if edges_to_show is None:
        # Hiển thị tất cả cạnh trong đồ thị
        edges_to_show = list(graph.distance.keys())

    print(f"\n  {'─'*70}")
    print(f"  TRẠNG THÁI GIAO THÔNG tại t = {step}s")
    print(f"  {'─'*70}")
    print(f"  {'Edge':<8} {'Vehicles':>9} {'Speed(m/s)':>11} "
          f"{'Waiting(s)':>11} {'TravelT(s)':>11} {'DynCost':>9}")
    print(f"  {'─'*68}")

    for (i, j) in sorted(edges_to_show):
        edge_id = f"{i}2{j}"
        vehicles = graph.vehicles.get((i, j), 0)
        speed = graph.speed.get((i, j), 0)
        waiting = graph.waiting.get((i, j), 0)
        travel = graph.travel_time.get((i, j), 0)
        dyn_cost = graph.get_dynamic_cost(i, j)

        print(f"  {edge_id:<8} {vehicles:>9} {speed:>11.2f} "
              f"{waiting:>11.1f} {travel:>11.1f} {dyn_cost:>9.4f}")


# ─────────────────────────────────────────────────────────────────
# Chạy ACO Runner
# ─────────────────────────────────────────────────────────────────

def run_aco_simulation(
    use_gui:          bool  = True,
    duration:         int   = 3600,
    aco_mode:         str   = "traffic_aware",
    n_ants:           int   = 20,
    n_iterations:     int   = 50,
    alpha:            float = 1.0,
    beta:             float = 2.0,
    rho:              float = 0.1,
    reroute_interval: int   = 60,
    origin:           str   = "A",
    dest:             str   = "I",
    report_interval:  int   = 120,
    adaptive_rho:     bool  = False,
):
    """
    Chạy simulation SUMO với ACO routing.

    Quy trình (Báo cáo 1, Mục 5.3 – Dynamic Rerouting):
    1. Khởi động SUMO với mạng 3×3
    2. Mỗi bước: đọc dữ liệu giao thông
    3. Mỗi reroute_interval bước: chạy ACO + so sánh + reroute nếu cần
    4. Ghi log

    Args:
        use_gui:          Mở SUMO-GUI
        duration:         Thời gian mô phỏng (giây)
        aco_mode:         "basic" hoặc "traffic_aware"
        n_ants:           Số kiến
        n_iterations:     Số vòng lặp ACO
        alpha, beta, rho: Tham số ACO
        reroute_interval: Khoảng thời gian chạy lại ACO (giây)
        origin, dest:     Cặp OD
        report_interval:  Khoảng thời gian in báo cáo console
        adaptive_rho:     Bật pheromone thích nghi
    """
    sumo_home = setup_sumo_path()
    import traci

    # ── Chuẩn bị file ──
    cfg_file      = PROJECT_DIR / "grid.sumocfg"
    output_dir    = PROJECT_DIR / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    tripinfo_file = output_dir / f"tripinfo_aco_{aco_mode}.xml"
    log_file      = output_dir / f"aco_routing_log_{aco_mode}.csv"

    if not cfg_file.exists():
        raise FileNotFoundError(f"Không tìm thấy config SUMO: {cfg_file}")

    # ── Lệnh SUMO ──
    sumo_bin = "sumo-gui" if use_gui else "sumo"
    sumo_path = Path(sumo_home) / "bin" / f"{sumo_bin}.exe"
    if sumo_path.exists():
        sumo_bin = str(sumo_path)

    sumo_cmd = [
        sumo_bin,
        "--configuration-file", str(cfg_file),
        "--tripinfo-output",    str(tripinfo_file),
        "--end",                str(duration),
        "--time-to-teleport",   "-1",
        "--no-warnings",
        "--no-step-log",
    ]

    # ── Header ──
    print(f"\n{'#'*70}")
    print(f"  ACO TRAFFIC ROUTING – Mạng 3×3")
    print(f"{'#'*70}")
    print(f"  ACO Mode:       {aco_mode}")
    print(f"  Origin → Dest:  {origin} → {dest}")
    print(f"  Kiến:           {n_ants} con × {n_iterations} vòng")
    print(f"  α={alpha}, β={beta}, ρ={rho}")
    print(f"  Adaptive ρ:     {adaptive_rho}")
    print(f"  Reroute mỗi:    {reroute_interval}s")
    print(f"  Thời gian:      {duration}s")
    print(f"  Output log:     {log_file}")
    print(f"{'#'*70}")

    # ── Khởi tạo đồ thị và ACO ──
    graph = TrafficGraph()
    aco = AntColonyOptimizer(
        graph,
        n_ants=n_ants,
        n_iterations=n_iterations,
        alpha=alpha,
        beta=beta,
        rho=rho,
        mode=aco_mode,
        adaptive_rho=adaptive_rho,
    )

    # ── Kết nối SUMO ──
    traci.start(sumo_cmd)
    print("\n[OK] Kết nối SUMO thành công qua TraCI")

    # ── Tìm đường ban đầu ──
    print(f"\n[ACO] Tìm đường ban đầu {origin} → {dest}...")
    path_initial, cost_initial = aco.solve(origin, dest, verbose=True)
    current_route_edges = graph.path_to_edges(path_initial) if path_initial else []
    current_route_path = path_initial or []

    # ── Mở log CSV ──
    log_data = []  # Lưu tất cả rồi ghi cuối

    routing_log = []  # Lưu kết quả mỗi lần reroute

    step = 0
    reroute_count = 0
    start_wall = time.time()

    # Danh sách xe ACO-controlled
    aco_vehicles = set()
    next_aco_veh_id = 0

    try:
        while traci.simulation.getMinExpectedNumber() > 0 and step < duration:
            traci.simulationStep()
            step += 1

            # ── Cập nhật đồ thị từ TraCI ──
            graph.update_from_traci(traci)

            # ── Thu thập dữ liệu traffic ──
            if step % report_interval == 0:
                print_traffic_state(step, graph)

            # ── Reroute mỗi reroute_interval bước ──
            if step % reroute_interval == 0 and step > 0:
                reroute_count += 1

                print(f"\n{'═'*70}")
                print(f"  [REROUTE #{reroute_count}] tại t = {step}s")
                print(f"{'═'*70}")

                # Reset ACO pheromone cho lần chạy mới
                aco.reset()

                # Chạy ACO
                t0 = time.time()
                new_path, new_cost = aco.solve(origin, dest, verbose=False)
                aco_time = (time.time() - t0) * 1000

                # So sánh với Dijkstra
                dij_path, dij_cost = dijkstra_dynamic(graph, origin, dest)

                print(f"  ACO ({aco_mode}):    "
                      f"{' → '.join(new_path) if new_path else 'N/A'}  "
                      f"cost={new_cost:.4f}  ({aco_time:.1f}ms)")
                print(f"  Dijkstra (dynamic): "
                      f"{' → '.join(dij_path) if dij_path else 'N/A'}  "
                      f"cost={dij_cost:.4f}")

                if new_path:
                    new_edges = graph.path_to_edges(new_path)
                    route_changed = (new_edges != current_route_edges)
                    current_route_edges = new_edges
                    current_route_path = new_path

                    if route_changed:
                        print(f"  → Tuyến ĐÃ THAY ĐỔI: {new_edges}")
                    else:
                        print(f"  → Tuyến giữ nguyên")

                    # Reroute các xe ACO-controlled đang chạy
                    active_vehicles = traci.vehicle.getIDList()
                    rerouted = 0
                    for veh_id in active_vehicles:
                        if veh_id in aco_vehicles:
                            try:
                                # Lấy edge hiện tại
                                current_edge = traci.vehicle.getRoadID(veh_id)
                                # Chỉ reroute nếu xe vẫn đang trên tuyến hợp lệ
                                if current_edge in new_edges:
                                    # Tìm phần còn lại của tuyến
                                    idx = new_edges.index(current_edge)
                                    remaining = new_edges[idx:]
                                    if len(remaining) >= 1:
                                        traci.vehicle.setRoute(veh_id, remaining)
                                        rerouted += 1
                            except Exception:
                                pass

                    if rerouted > 0:
                        print(f"  → Đã reroute {rerouted} phương tiện")

                    # Ghi log
                    routing_log.append({
                        "step":         step,
                        "reroute_no":   reroute_count,
                        "aco_path":     " → ".join(new_path),
                        "aco_edges":    " ".join(new_edges),
                        "aco_cost":     round(new_cost, 6),
                        "aco_time_ms":  round(aco_time, 2),
                        "dij_path":     " → ".join(dij_path) if dij_path else "N/A",
                        "dij_cost":     round(dij_cost, 6) if dij_path else "N/A",
                        "route_changed": route_changed,
                        "vehicles_rerouted": rerouted,
                    })

            # ── Sinh xe ACO mới (mỗi 30s) ──
            if step % 30 == 0 and current_route_edges:
                veh_id = f"aco_{next_aco_veh_id}"
                next_aco_veh_id += 1
                try:
                    traci.vehicle.add(
                        vehID=veh_id,
                        routeID="",  # empty route, sẽ set thủ công
                        typeID="car",
                        departLane="best",
                        departSpeed="max",
                    )
                    traci.vehicle.setRoute(veh_id, current_route_edges)
                    aco_vehicles.add(veh_id)
                except Exception as e:
                    # Có thể lỗi nếu route không hợp lệ hoặc xe không thể spawn
                    pass

    except KeyboardInterrupt:
        print("\n[!] Mô phỏng bị dừng bởi người dùng (Ctrl+C)")

    finally:
        elapsed = time.time() - start_wall

        # ── Ghi log CSV ──
        if routing_log:
            with open(log_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=routing_log[0].keys())
                writer.writeheader()
                for row in routing_log:
                    writer.writerow(row)
            print(f"\n[OK] Đã ghi routing log: {log_file}")

        # ── Tóm tắt ──
        print(f"\n{'='*70}")
        print(f"  KẾT QUẢ ACO ROUTING")
        print(f"{'='*70}")
        print(f"  Thời gian mô phỏng: {step}s")
        print(f"  Wall-clock time:     {elapsed:.1f}s")
        print(f"  Số lần reroute:      {reroute_count}")
        print(f"  Xe ACO tạo:          {next_aco_veh_id}")
        if current_route_path:
            print(f"  Tuyến cuối cùng:     {' → '.join(current_route_path)}")
            print(f"  SUMO edges:          {current_route_edges}")
        print(f"{'='*70}")

        traci.close()


# ─────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="ACO Traffic Routing trên SUMO",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ví dụ:
  python scripts/aco_runner.py
  python scripts/aco_runner.py --nogui --duration 600
  python scripts/aco_runner.py --aco-mode basic --n-ants 30
  python scripts/aco_runner.py --origin A --dest I --reroute 30
        """
    )
    parser.add_argument("--nogui", action="store_true",
                        help="Chạy không có SUMO-GUI")
    parser.add_argument("--duration", type=int, default=3600,
                        help="Thời gian mô phỏng (giây, mặc định: 3600)")
    parser.add_argument("--aco-mode", type=str, default="traffic_aware",
                        choices=["basic", "traffic_aware"],
                        help="Chế độ ACO (mặc định: traffic_aware)")
    parser.add_argument("--n-ants", type=int, default=20,
                        help="Số kiến (mặc định: 20)")
    parser.add_argument("--iterations", type=int, default=50,
                        help="Số vòng lặp ACO (mặc định: 50)")
    parser.add_argument("--alpha", type=float, default=1.0,
                        help="Alpha – ảnh hưởng pheromone (mặc định: 1.0)")
    parser.add_argument("--beta", type=float, default=2.0,
                        help="Beta – ảnh hưởng heuristic (mặc định: 2.0)")
    parser.add_argument("--rho", type=float, default=0.1,
                        help="Rho – tỷ lệ bay hơi (mặc định: 0.1)")
    parser.add_argument("--reroute", type=int, default=60,
                        help="Reroute mỗi N giây (mặc định: 60)")
    parser.add_argument("--origin", type=str, default="A",
                        choices=list(GRID_ADJACENCY.keys()),
                        help="Nút xuất phát (mặc định: A)")
    parser.add_argument("--dest", type=str, default="I",
                        choices=list(GRID_ADJACENCY.keys()),
                        help="Nút đích (mặc định: I)")
    parser.add_argument("--report", type=int, default=120,
                        help="In báo cáo mỗi N bước (mặc định: 120)")
    parser.add_argument("--adaptive-rho", action="store_true",
                        help="Bật pheromone thích nghi (Báo cáo 1, Mục 5.2)")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_aco_simulation(
        use_gui          = not args.nogui,
        duration         = args.duration,
        aco_mode         = args.aco_mode,
        n_ants           = args.n_ants,
        n_iterations     = args.iterations,
        alpha            = args.alpha,
        beta             = args.beta,
        rho              = args.rho,
        reroute_interval = args.reroute,
        origin           = args.origin,
        dest             = args.dest,
        report_interval  = args.report,
        adaptive_rho     = args.adaptive_rho,
    )
