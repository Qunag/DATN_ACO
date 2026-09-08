#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
compare_algorithms.py – So sánh tất cả thuật toán tìm đường trên SUMO
=======================================================================

Script chạy SUMO, thu thập dữ liệu giao thông, rồi so sánh:
  1. Dijkstra (static)
  2. Dijkstra (traffic-aware, travel time)
  3. Dijkstra (dynamic cost function)
  4. A*
  5. ACO (basic)
  6. ACO (traffic-aware)

Kết quả được xuất ra console + CSV.

Tham chiếu:
  - Báo cáo 1, Mục 7: Các giải thuật đối chứng
  - Báo cáo 1, Mục 8: Các chỉ số đánh giá

Sử dụng:
    python scripts/compare_algorithms.py --nogui --duration 600
    python scripts/compare_algorithms.py --snapshot-at 100 200 300
"""

import sys
import io
import os
import csv
import time
import argparse
from pathlib import Path
from typing import Dict, List

# Fix Unicode output trên Windows console
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# ─────────────────────────────────────────────────────────────────
# Đường dẫn
# ─────────────────────────────────────────────────────────────────

PROJECT_DIR = Path(__file__).parent.parent.resolve()
SCRIPTS_DIR = Path(__file__).parent.resolve()

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from aco import TrafficGraph, AntColonyOptimizer, GRID_ADJACENCY
from routing import (run_all_algorithms, print_comparison_table,
                     dijkstra_static, dijkstra_traffic, dijkstra_dynamic, astar)


# ─────────────────────────────────────────────────────────────────
# Thiết lập SUMO
# ─────────────────────────────────────────────────────────────────

def setup_sumo_path():
    """Thiết lập SUMO_HOME."""
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
        raise EnvironmentError("Không tìm thấy SUMO_HOME.")
    tools_dir = os.path.join(sumo_home, "tools")
    if tools_dir not in sys.path:
        sys.path.append(tools_dir)
    return sumo_home


# ─────────────────────────────────────────────────────────────────
# Chạy so sánh
# ─────────────────────────────────────────────────────────────────

def run_comparison(
    use_gui:      bool = False,
    duration:     int  = 600,
    snapshot_at:  List[int] = None,
    origin:       str  = "A",
    dest:         str  = "I",
    n_ants:       int  = 20,
    n_iterations: int  = 50,
):
    """
    Chạy SUMO, thu thập snapshot giao thông tại các thời điểm,
    rồi so sánh tất cả thuật toán.

    Args:
        use_gui:      Mở SUMO-GUI
        duration:     Thời gian mô phỏng (giây)
        snapshot_at:  Danh sách thời điểm lấy snapshot (giây)
        origin, dest: Cặp OD
        n_ants:       Số kiến cho ACO
        n_iterations: Số vòng lặp ACO
    """
    if snapshot_at is None:
        snapshot_at = [60, 120, 300, 600]

    # Lọc các snapshot > duration
    snapshot_at = sorted([t for t in snapshot_at if t <= duration])

    sumo_home = setup_sumo_path()
    import traci

    # ── File config ──
    cfg_file   = PROJECT_DIR / "grid.sumocfg"
    output_dir = PROJECT_DIR / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    tripinfo_file = output_dir / "tripinfo_compare.xml"
    csv_file      = output_dir / "algorithm_comparison.csv"

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

    print(f"\n{'#'*75}")
    print(f"  SO SÁNH THUẬT TOÁN TÌM ĐƯỜNG – Mạng 3×3")
    print(f"{'#'*75}")
    print(f"  Origin → Dest: {origin} → {dest}")
    print(f"  Thời gian:     {duration}s")
    print(f"  Snapshots tại: {snapshot_at}")
    print(f"  ACO params:    {n_ants} kiến × {n_iterations} vòng")
    print(f"{'#'*75}")

    # ── Khởi tạo đồ thị ──
    graph = TrafficGraph()

    # ── Kết nối SUMO ──
    traci.start(sumo_cmd)
    print("\n[OK] Kết nối SUMO thành công")

    # ── Thu thập kết quả ──
    all_results = []
    snapshot_idx = 0
    step = 0
    start_wall = time.time()

    try:
        while traci.simulation.getMinExpectedNumber() > 0 and step < duration:
            traci.simulationStep()
            step += 1

            # Cập nhật đồ thị
            graph.update_from_traci(traci)

            # Kiểm tra snapshot
            if snapshot_idx < len(snapshot_at) and step == snapshot_at[snapshot_idx]:
                print(f"\n{'═'*75}")
                print(f"  SNAPSHOT tại t = {step}s")
                print(f"{'═'*75}")

                # In trạng thái giao thông
                print(f"\n  {'Edge':<8} {'Vehicles':>9} {'Speed':>8} "
                      f"{'Waiting':>9} {'TravelT':>9} {'DynCost':>9}")
                print(f"  {'─'*56}")
                for (i, j) in sorted(graph.distance.keys()):
                    edge_id = f"{i}2{j}"
                    v = graph.vehicles.get((i, j), 0)
                    s = graph.speed.get((i, j), 0)
                    w = graph.waiting.get((i, j), 0)
                    t = graph.travel_time.get((i, j), 0)
                    dc = graph.get_dynamic_cost(i, j)
                    print(f"  {edge_id:<8} {v:>9} {s:>8.2f} "
                          f"{w:>9.1f} {t:>9.1f} {dc:>9.4f}")

                # So sánh thuật toán
                aco_params = {"n_ants": n_ants, "n_iterations": n_iterations}
                results = run_all_algorithms(graph, origin, dest, aco_params)

                # Thêm thời điểm snapshot
                for r in results:
                    r["snapshot_time"] = step
                    all_results.append(r)

                print_comparison_table(results)
                snapshot_idx += 1

    except KeyboardInterrupt:
        print("\n[!] Dừng bởi Ctrl+C")

    finally:
        elapsed = time.time() - start_wall
        traci.close()

    # ── Ghi CSV ──
    if all_results:
        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            fieldnames = ["snapshot_time", "algorithm", "path_str", "cost", "time_ms"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in all_results:
                writer.writerow({k: r[k] for k in fieldnames})

        print(f"\n[OK] Kết quả đã ghi: {csv_file}")

    # ── Tóm tắt ──
    print(f"\n{'='*75}")
    print(f"  TỔNG KẾT SO SÁNH")
    print(f"{'='*75}")
    print(f"  Thời gian simulation: {step}s")
    print(f"  Wall-clock:           {elapsed:.1f}s")
    print(f"  Số snapshots:         {len(snapshot_at)}")
    print(f"  Tổng kết quả:        {len(all_results)} records")

    # Tóm tắt theo thuật toán
    if all_results:
        algorithms = {}
        for r in all_results:
            alg = r["algorithm"]
            if alg not in algorithms:
                algorithms[alg] = {"costs": [], "times": []}
            algorithms[alg]["costs"].append(r["cost"])
            algorithms[alg]["times"].append(r["time_ms"])

        print(f"\n  {'Thuật toán':<25} {'Avg Cost':>10} {'Avg Time':>10}")
        print(f"  {'─'*48}")
        for alg, data in algorithms.items():
            avg_cost = sum(data["costs"]) / len(data["costs"])
            avg_time = sum(data["times"]) / len(data["times"])
            print(f"  {alg:<25} {avg_cost:>10.4f} {avg_time:>8.2f}ms")

    print(f"{'='*75}")


# ─────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="So sánh thuật toán tìm đường trên SUMO",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ví dụ:
  python scripts/compare_algorithms.py --nogui --duration 600
  python scripts/compare_algorithms.py --snapshot-at 100 200 300 500
  python scripts/compare_algorithms.py --origin C --dest G
        """
    )
    parser.add_argument("--nogui", action="store_true",
                        help="Không mở SUMO-GUI")
    parser.add_argument("--duration", type=int, default=600,
                        help="Thời gian mô phỏng (mặc định: 600)")
    parser.add_argument("--snapshot-at", type=int, nargs="+",
                        default=[60, 120, 300, 600],
                        help="Thời điểm lấy snapshot (mặc định: 60 120 300 600)")
    parser.add_argument("--origin", type=str, default="A",
                        choices=list(GRID_ADJACENCY.keys()),
                        help="Nút xuất phát (mặc định: A)")
    parser.add_argument("--dest", type=str, default="I",
                        choices=list(GRID_ADJACENCY.keys()),
                        help="Nút đích (mặc định: I)")
    parser.add_argument("--n-ants", type=int, default=20,
                        help="Số kiến (mặc định: 20)")
    parser.add_argument("--iterations", type=int, default=50,
                        help="Số vòng lặp ACO (mặc định: 50)")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_comparison(
        use_gui      = not args.nogui,
        duration     = args.duration,
        snapshot_at  = args.snapshot_at,
        origin       = args.origin,
        dest         = args.dest,
        n_ants       = args.n_ants,
        n_iterations = args.iterations,
    )
