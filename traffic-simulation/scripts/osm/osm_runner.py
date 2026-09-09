#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
osm_runner.py – Chạy ACO Routing trên bản đồ OSM thực tế
==========================================================

Script tích hợp ACO với SUMO trên bản đồ thực (OSM):
  - mode compare: So sánh 5 thuật toán tại các snapshot
  - mode reroute: Dynamic rerouting ACO theo thời gian thực

Khác biệt so với aco_runner.py (mạng 3×3):
  - Mạng đường thực: 600+ nút, 1200+ cạnh
  - Tự phát hiện topology từ net.xml
  - Tự chọn cặp OD phù hợp
  - ACO cải tiến: directional heuristic + Dijkstra seed

Sử dụng:
    # So sánh thuật toán
    python scripts/osm_runner.py --nogui --mode compare --duration 600

    # Dynamic rerouting ACO
    python scripts/osm_runner.py --nogui --mode reroute --duration 600

    # Tùy chỉnh
    python scripts/osm_runner.py --nogui --mode compare --n-ants 50 --iterations 100
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

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = PROJECT_DIR / "scripts"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

try:
    from scripts.core.osm_graph import (
        OSMTrafficGraph, OSMAntColonyOptimizer,
        dijkstra_osm, astar_osm,
        run_all_osm_algorithms, print_osm_comparison_table,
    )
except ImportError:
    try:
        from core.osm_graph import (
            OSMTrafficGraph, OSMAntColonyOptimizer,
            dijkstra_osm, astar_osm,
            run_all_osm_algorithms, print_osm_comparison_table,
        )
    except ImportError:
        from osm_graph import (
            OSMTrafficGraph, OSMAntColonyOptimizer,
            dijkstra_osm, astar_osm,
            run_all_osm_algorithms, print_osm_comparison_table,
        )


# ─────────────────────────────────────────────────────────────────
# Mặc định
# ─────────────────────────────────────────────────────────────────

DEFAULT_NET_FILE = PROJECT_DIR / "osm" / "map2.net.xml"
DEFAULT_CFG_FILE = PROJECT_DIR / "osm" / "map2.sumocfg"


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
# In trạng thái giao thông (chỉ các edge trên tuyến hiện tại)
# ─────────────────────────────────────────────────────────────────

def print_route_traffic(step: int, graph: OSMTrafficGraph,
                        route_edges: List[str]):
    """In trạng thái giao thông trên tuyến hiện tại."""
    print(f"\n  {'─'*70}")
    print(f"  GIAO THÔNG TRÊN TUYẾN tại t = {step}s")
    print(f"  {'─'*70}")
    print(f"  {'Edge':<25} {'Vehicles':>9} {'Speed':>8} "
          f"{'Waiting':>9} {'TravelT':>9} {'DynCost':>9}")
    print(f"  {'─'*73}")

    for edge_id in route_edges:
        pair = graph._edge_to_pair.get(edge_id)
        if not pair:
            continue
        i, j = pair
        v = graph.vehicles.get((i, j), 0)
        s = graph.speed.get((i, j), 0)
        w = graph.waiting.get((i, j), 0)
        t = graph.travel_time.get((i, j), 0)
        dc = graph.get_dynamic_cost(i, j)

        # Rút gọn tên edge nếu quá dài
        short_name = edge_id[:24] if len(edge_id) > 24 else edge_id
        print(f"  {short_name:<25} {v:>9} {s:>8.2f} "
              f"{w:>9.1f} {t:>9.1f} {dc:>9.4f}")


def print_network_summary(step: int, graph: OSMTrafficGraph):
    """In thống kê tổng quan mạng."""
    total_vehicles = sum(graph.vehicles.values())
    avg_speed = 0
    edges_with_traffic = 0
    congested = 0

    for pair in graph.distance:
        v = graph.vehicles.get(pair, 0)
        if v > 0:
            edges_with_traffic += 1
            avg_speed += graph.speed.get(pair, 0)
            if v >= 10:
                congested += 1

    if edges_with_traffic > 0:
        avg_speed /= edges_with_traffic

    print(f"\n  📊 Mạng tại t={step}s: "
          f"{total_vehicles} xe, "
          f"{edges_with_traffic}/{len(graph.distance)} edges có xe, "
          f"v̄={avg_speed:.1f}m/s, "
          f"{congested} edges ùn tắc (≥10 xe)")


# ═══════════════════════════════════════════════════════════════════
# MODE: COMPARE – So sánh thuật toán
# ═══════════════════════════════════════════════════════════════════

def run_compare(
    use_gui:      bool = False,
    duration:     int  = 600,
    snapshot_at:  List[int] = None,
    net_file:     str  = None,
    cfg_file:     str  = None,
    n_ants:       int  = 30,
    n_iterations: int  = 80,
    n_od_pairs:   int  = 3,
):
    """
    Chạy SUMO trên map OSM, so sánh thuật toán tại các snapshot.

    Args:
        use_gui:      Mở SUMO-GUI
        duration:     Thời gian mô phỏng (giây)
        snapshot_at:  Thời điểm lấy snapshot
        net_file:     File net.xml
        cfg_file:     File .sumocfg
        n_ants:       Số kiến ACO
        n_iterations: Số vòng lặp ACO
        n_od_pairs:   Số cặp OD test
    """
    if snapshot_at is None:
        snapshot_at = [120, 300, 600]
    snapshot_at = sorted([t for t in snapshot_at if t <= duration])

    net_file = net_file or str(DEFAULT_NET_FILE)
    cfg_file = cfg_file or str(DEFAULT_CFG_FILE)

    sumo_home = setup_sumo_path()
    import traci

    # ── Load đồ thị ──
    print(f"\n{'#'*75}")
    print(f"  SO SÁNH THUẬT TOÁN – Bản đồ OSM")
    print(f"{'#'*75}")

    graph = OSMTrafficGraph(net_file)

    # ── Tìm cặp OD ──
    print(f"\n  Tìm {n_od_pairs} cặp OD...")
    od_pairs = graph.find_od_pairs(n_pairs=n_od_pairs, min_distance=1000.0)

    if not od_pairs:
        od_pairs = graph.find_od_pairs(n_pairs=n_od_pairs, min_distance=500.0)

    if not od_pairs:
        print("  [!] Không tìm được cặp OD hợp lệ!")
        return

    for i, (o, d) in enumerate(od_pairs):
        print(f"  Cặp {i+1}: {graph.get_od_info(o, d)}")

    print(f"\n  Thời gian:     {duration}s")
    print(f"  Snapshots tại: {snapshot_at}")
    print(f"  ACO params:    {n_ants} kiến × {n_iterations} vòng")
    print(f"{'#'*75}")

    # ── Config SUMO ──
    if not Path(cfg_file).exists():
        raise FileNotFoundError(f"Không tìm thấy config SUMO: {cfg_file}")

    sumo_bin = "sumo-gui" if use_gui else "sumo"
    sumo_path = Path(sumo_home) / "bin" / f"{sumo_bin}.exe"
    if sumo_path.exists():
        sumo_bin = str(sumo_path)

    output_dir = PROJECT_DIR / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    tripinfo_file = output_dir / "tripinfo_osm_compare.xml"
    csv_file = output_dir / "osm_algorithm_comparison.csv"

    sumo_cmd = [
        sumo_bin,
        "--configuration-file", str(cfg_file),
        "--tripinfo-output",    str(tripinfo_file),
        "--end",                str(duration),
        "--time-to-teleport",   "300",
        "--no-warnings",
        "--no-step-log",
    ]

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

                print_network_summary(step, graph)

                # So sánh trên từng cặp OD
                for pair_idx, (origin, dest) in enumerate(od_pairs):
                    aco_params = {
                        "n_ants": n_ants,
                        "n_iterations": n_iterations,
                    }
                    od_label = f"OD #{pair_idx+1}: {origin[:10]}→{dest[:10]}"
                    results = run_all_osm_algorithms(
                        graph, origin, dest, aco_params
                    )

                    for r in results:
                        r["snapshot_time"] = step
                        r["od_pair"] = f"{origin}→{dest}"
                        r["od_index"] = pair_idx + 1
                        all_results.append(r)

                    print_osm_comparison_table(results, od_label)

                snapshot_idx += 1

    except KeyboardInterrupt:
        print("\n[!] Dừng bởi Ctrl+C")

    finally:
        elapsed = time.time() - start_wall
        traci.close()

    # ── Ghi CSV ──
    if all_results:
        fieldnames = ["snapshot_time", "od_pair", "od_index",
                      "algorithm", "path_len", "cost", "time_ms"]
        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in all_results:
                writer.writerow({k: r[k] for k in fieldnames})

        print(f"\n[OK] Kết quả đã ghi: {csv_file}")

    # ── Tóm tắt ──
    print(f"\n{'='*75}")
    print(f"  TỔNG KẾT SO SÁNH – BẢN ĐỒ OSM")
    print(f"{'='*75}")
    print(f"  Mạng:              {len(graph.nodes)} nodes, "
          f"{len(graph.distance)} edges")
    print(f"  Thời gian sim:     {step}s")
    print(f"  Wall-clock:        {elapsed:.1f}s")
    print(f"  Số snapshots:      {len(snapshot_at)}")
    print(f"  Số cặp OD:         {len(od_pairs)}")
    print(f"  Tổng kết quả:      {len(all_results)} records")

    # Tóm tắt trung bình theo thuật toán
    if all_results:
        algorithms = {}
        for r in all_results:
            alg = r["algorithm"]
            if alg not in algorithms:
                algorithms[alg] = {"costs": [], "times": [], "path_lens": []}
            algorithms[alg]["costs"].append(r["cost"])
            algorithms[alg]["times"].append(r["time_ms"])
            algorithms[alg]["path_lens"].append(r["path_len"])

        print(f"\n  {'Thuật toán':<22} {'Avg Cost':>10} {'Avg Time':>12} "
              f"{'Avg Nodes':>10}")
        print(f"  {'─'*58}")
        for alg, data in algorithms.items():
            avg_cost = sum(data["costs"]) / len(data["costs"])
            avg_time = sum(data["times"]) / len(data["times"])
            avg_nodes = sum(data["path_lens"]) / len(data["path_lens"])
            print(f"  {alg:<22} {avg_cost:>10.4f} {avg_time:>10.2f}ms "
                  f"{avg_nodes:>10.1f}")

    print(f"{'='*75}")


# ═══════════════════════════════════════════════════════════════════
# MODE: REROUTE – Dynamic ACO Rerouting
# ═══════════════════════════════════════════════════════════════════

def run_reroute(
    use_gui:          bool  = False,
    duration:         int   = 600,
    net_file:         str   = None,
    cfg_file:         str   = None,
    n_ants:           int   = 30,
    n_iterations:     int   = 80,
    reroute_interval: int   = 60,
    report_interval:  int   = 120,
    n_od_pairs:       int   = 1,
    adaptive_rho:     bool  = False,
):
    """
    Chạy dynamic rerouting ACO trên bản đồ OSM.

    Quy trình:
    1. Khởi động SUMO, load đồ thị
    2. Mỗi reroute_interval: chạy ACO + Dijkstra
    3. Nếu tuyến thay đổi → reroute xe
    4. Ghi log

    Args:
        use_gui:          Mở SUMO-GUI
        duration:         Thời gian mô phỏng
        net_file:         File net.xml
        cfg_file:         File .sumocfg
        n_ants:           Số kiến ACO
        n_iterations:     Số vòng lặp ACO
        reroute_interval: Reroute mỗi N giây
        report_interval:  Báo cáo giao thông mỗi N giây
        n_od_pairs:       Số cặp OD (dùng cặp đầu tiên)
        adaptive_rho:     Bật pheromone thích nghi
    """
    net_file = net_file or str(DEFAULT_NET_FILE)
    cfg_file = cfg_file or str(DEFAULT_CFG_FILE)

    sumo_home = setup_sumo_path()
    import traci

    # ── Load đồ thị ──
    print(f"\n{'#'*70}")
    print(f"  ACO DYNAMIC REROUTING – Bản đồ OSM")
    print(f"{'#'*70}")

    graph = OSMTrafficGraph(net_file)

    # ── Tìm cặp OD ──
    od_pairs = graph.find_od_pairs(n_pairs=n_od_pairs, min_distance=1000.0)
    if not od_pairs:
        od_pairs = graph.find_od_pairs(n_pairs=n_od_pairs, min_distance=500.0)
    if not od_pairs:
        print("  [!] Không tìm được cặp OD!")
        return

    origin, dest = od_pairs[0]

    print(f"  Origin → Dest:   {graph.get_od_info(origin, dest)}")
    print(f"  ACO:             {n_ants} kiến × {n_iterations} vòng")
    print(f"  Adaptive ρ:      {adaptive_rho}")
    print(f"  Reroute mỗi:     {reroute_interval}s")
    print(f"  Thời gian:       {duration}s")
    print(f"{'#'*70}")

    # ── Config SUMO ──
    if not Path(cfg_file).exists():
        raise FileNotFoundError(f"Không tìm thấy config: {cfg_file}")

    sumo_bin = "sumo-gui" if use_gui else "sumo"
    sumo_path = Path(sumo_home) / "bin" / f"{sumo_bin}.exe"
    if sumo_path.exists():
        sumo_bin = str(sumo_path)

    output_dir = PROJECT_DIR / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    tripinfo_file = output_dir / "tripinfo_osm_reroute.xml"
    log_file = output_dir / "osm_routing_log.csv"

    sumo_cmd = [
        sumo_bin,
        "--configuration-file", str(cfg_file),
        "--tripinfo-output",    str(tripinfo_file),
        "--end",                str(duration),
        "--time-to-teleport",   "300",
        "--no-warnings",
        "--no-step-log",
    ]

    # ── Khởi tạo ACO ──
    aco = OSMAntColonyOptimizer(
        graph,
        n_ants=n_ants,
        n_iterations=n_iterations,
        mode="traffic_aware",
        adaptive_rho=adaptive_rho,
    )

    # ── Kết nối SUMO ──
    traci.start(sumo_cmd)
    print("\n[OK] Kết nối SUMO thành công")

    # ── Tìm đường ban đầu ──
    print(f"\n[ACO] Tìm đường ban đầu...")
    path_initial, cost_initial = aco.solve(origin, dest, verbose=True,
                                            max_steps=200)
    current_route_edges = graph.path_to_edges(path_initial) if path_initial else []
    current_route_path = path_initial or []

    if path_initial:
        print(f"  Tuyến ban đầu: {len(path_initial)} nodes, "
              f"cost={cost_initial:.4f}")
        print(f"  SUMO edges: {len(current_route_edges)} edges")
    else:
        print("  [!] Không tìm được tuyến ban đầu!")

    # ── Vòng lặp mô phỏng ──
    routing_log = []
    step = 0
    reroute_count = 0
    start_wall = time.time()
    aco_vehicles = set()
    next_aco_veh_id = 0

    try:
        while traci.simulation.getMinExpectedNumber() > 0 and step < duration:
            traci.simulationStep()
            step += 1

            # Cập nhật đồ thị
            graph.update_from_traci(traci)

            # Báo cáo giao thông
            if step % report_interval == 0:
                print_network_summary(step, graph)
                if current_route_edges:
                    print_route_traffic(step, graph, current_route_edges)

            # ── Reroute ──
            if step % reroute_interval == 0 and step > 0:
                reroute_count += 1

                print(f"\n{'═'*70}")
                print(f"  [REROUTE #{reroute_count}] tại t = {step}s")
                print(f"{'═'*70}")

                # Reset ACO
                aco.reset()

                # Chạy ACO
                t0 = time.time()
                new_path, new_cost = aco.solve(
                    origin, dest, verbose=False, max_steps=200
                )
                aco_time = (time.time() - t0) * 1000

                # So sánh với Dijkstra
                t0_dij = time.time()
                dij_path, dij_cost = dijkstra_osm(
                    graph, origin, dest, "dynamic"
                )
                dij_time = (time.time() - t0_dij) * 1000

                # In kết quả
                aco_nodes = len(new_path) if new_path else 0
                dij_nodes = len(dij_path) if dij_path else 0

                print(f"  ACO (traffic_aware):  "
                      f"{aco_nodes} nodes  "
                      f"cost={new_cost:.4f}  ({aco_time:.1f}ms)")
                print(f"  Dijkstra (dynamic):   "
                      f"{dij_nodes} nodes  "
                      f"cost={dij_cost:.4f}  ({dij_time:.1f}ms)")

                # So sánh chi phí
                if new_path and dij_path and dij_cost > 0:
                    ratio = new_cost / dij_cost
                    print(f"  ACO/Dijkstra:         {ratio:.4f} "
                          f"({'tối ưu' if ratio <= 1.05 else f'+{(ratio-1)*100:.1f}%'})")

                if new_path:
                    new_edges = graph.path_to_edges(new_path)
                    route_changed = (new_edges != current_route_edges)
                    current_route_edges = new_edges
                    current_route_path = new_path

                    if route_changed:
                        print(f"  → Tuyến ĐÃ THAY ĐỔI ({len(new_edges)} edges)")
                    else:
                        print(f"  → Tuyến giữ nguyên")

                    # Reroute các xe ACO
                    active_vehicles = traci.vehicle.getIDList()
                    rerouted = 0
                    for veh_id in active_vehicles:
                        if veh_id in aco_vehicles:
                            try:
                                current_edge = traci.vehicle.getRoadID(veh_id)
                                if current_edge in new_edges:
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
                        "step":           step,
                        "reroute_no":     reroute_count,
                        "aco_cost":       round(new_cost, 6),
                        "aco_time_ms":    round(aco_time, 2),
                        "aco_nodes":      aco_nodes,
                        "dij_cost":       round(dij_cost, 6),
                        "dij_time_ms":    round(dij_time, 2),
                        "dij_nodes":      dij_nodes,
                        "ratio":          round(new_cost / dij_cost, 4) if dij_cost > 0 else "N/A",
                        "route_changed":  route_changed,
                        "vehicles_rerouted": rerouted,
                    })

            # ── Sinh xe ACO (mỗi 30s) ──
            if step % 30 == 0 and current_route_edges:
                veh_id = f"osm_aco_{next_aco_veh_id}"
                next_aco_veh_id += 1
                try:
                    traci.vehicle.add(
                        vehID=veh_id,
                        routeID="",
                        typeID="DEFAULT_VEHTYPE",
                        departLane="best",
                        departSpeed="max",
                    )
                    traci.vehicle.setRoute(veh_id, current_route_edges)
                    aco_vehicles.add(veh_id)
                except Exception:
                    pass

    except KeyboardInterrupt:
        print("\n[!] Dừng bởi Ctrl+C")

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
        print(f"  KẾT QUẢ ACO ROUTING – BẢN ĐỒ OSM")
        print(f"{'='*70}")
        print(f"  Mạng:               {len(graph.nodes)} nodes, "
              f"{len(graph.distance)} edges")
        print(f"  Thời gian mô phỏng: {step}s")
        print(f"  Wall-clock:          {elapsed:.1f}s")
        print(f"  Số lần reroute:      {reroute_count}")
        print(f"  Xe ACO tạo:          {next_aco_veh_id}")

        if current_route_path:
            print(f"  Tuyến cuối cùng:     {len(current_route_path)} nodes")
            print(f"  SUMO edges:          {len(current_route_edges)} edges")

        # Tóm tắt ACO vs Dijkstra
        if routing_log:
            aco_costs = [r["aco_cost"] for r in routing_log]
            dij_costs = [r["dij_cost"] for r in routing_log]
            aco_times = [r["aco_time_ms"] for r in routing_log]
            dij_times = [r["dij_time_ms"] for r in routing_log]
            ratios = [r["ratio"] for r in routing_log if isinstance(r["ratio"], float)]

            print(f"\n  {'Chỉ số':<25} {'ACO':>12} {'Dijkstra':>12}")
            print(f"  {'─'*52}")
            print(f"  {'Avg Cost':<25} "
                  f"{sum(aco_costs)/len(aco_costs):>12.4f} "
                  f"{sum(dij_costs)/len(dij_costs):>12.4f}")
            print(f"  {'Avg Time (ms)':<25} "
                  f"{sum(aco_times)/len(aco_times):>12.2f} "
                  f"{sum(dij_times)/len(dij_times):>12.2f}")
            if ratios:
                print(f"  {'Avg ACO/Dijkstra':<25} "
                      f"{sum(ratios)/len(ratios):>12.4f}")
            changes = sum(1 for r in routing_log if r["route_changed"])
            print(f"  {'Tuyến thay đổi':<25} "
                  f"{changes}/{len(routing_log)} lần")

        print(f"{'='*70}")

        traci.close()


# ─────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="ACO Routing trên bản đồ OSM thực tế",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ví dụ:
  python -m scripts.osm.osm_runner --nogui --mode compare --duration 600
  python -m scripts.osm.osm_runner --nogui --mode reroute --duration 600
  python -m scripts.osm.osm_runner --nogui --mode compare --n-ants 50 --iterations 100
        """
    )
    parser.add_argument("--nogui", action="store_true",
                        help="Không mở SUMO-GUI")
    parser.add_argument("--mode", type=str, default="compare",
                        choices=["compare", "reroute"],
                        help="Chế độ: compare (so sánh) hoặc reroute (tái định tuyến)")
    parser.add_argument("--duration", type=int, default=600,
                        help="Thời gian mô phỏng (giây, mặc định: 600)")
    parser.add_argument("--net", type=str, default=None,
                        help="File net.xml (mặc định: osm/map2.net.xml)")
    parser.add_argument("--cfg", type=str, default=None,
                        help="File .sumocfg (mặc định: osm/map2.sumocfg)")
    parser.add_argument("--snapshot-at", type=int, nargs="+",
                        default=[120, 300, 600],
                        help="Thời điểm snapshot (mặc định: 120 300 600)")
    parser.add_argument("--n-ants", type=int, default=30,
                        help="Số kiến ACO (mặc định: 30)")
    parser.add_argument("--iterations", type=int, default=80,
                        help="Số vòng lặp ACO (mặc định: 80)")
    parser.add_argument("--reroute", type=int, default=60,
                        help="Reroute mỗi N giây (mặc định: 60)")
    parser.add_argument("--report", type=int, default=120,
                        help="Báo cáo mỗi N bước (mặc định: 120)")
    parser.add_argument("--od-pairs", type=int, default=3,
                        help="Số cặp OD cho compare mode (mặc định: 3)")
    parser.add_argument("--adaptive-rho", action="store_true",
                        help="Bật pheromone thích nghi")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    if args.mode == "compare":
        run_compare(
            use_gui      = not args.nogui,
            duration     = args.duration,
            snapshot_at  = args.snapshot_at,
            net_file     = args.net,
            cfg_file     = args.cfg,
            n_ants       = args.n_ants,
            n_iterations = args.iterations,
            n_od_pairs   = args.od_pairs,
        )
    elif args.mode == "reroute":
        run_reroute(
            use_gui          = not args.nogui,
            duration         = args.duration,
            net_file         = args.net,
            cfg_file         = args.cfg,
            n_ants           = args.n_ants,
            n_iterations     = args.iterations,
            reroute_interval = args.reroute,
            report_interval  = args.report,
            adaptive_rho     = args.adaptive_rho,
        )
