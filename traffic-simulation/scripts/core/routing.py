#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
routing.py – Các giải thuật tìm đường đối chứng
=================================================

Module này implement các thuật toán tìm đường truyền thống:
  1. Dijkstra (static)         – trọng số khoảng cách
  2. Dijkstra (traffic-aware)  – trọng số travel time thực
  3. A* (static)               – heuristic khoảng cách Euclid

Tham chiếu:
  - Báo cáo 1, Mục 7: Các giải thuật đối chứng

Sử dụng:
    python scripts/routing.py --test
"""

import sys
import io
import math
import heapq
import time
import argparse
from typing import Dict, List, Tuple, Optional

# Fix Unicode output trên Windows console
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Import TrafficGraph từ module aco
from pathlib import Path
import importlib.util

# Hỗ trợ import khi chạy trực tiếp hoặc import từ package
try:
    from .aco import TrafficGraph, NODE_COORDS, GRID_ADJACENCY
except (ImportError, ValueError):
    try:
        from scripts.core.aco import TrafficGraph, NODE_COORDS, GRID_ADJACENCY
    except ImportError:
        try:
            from aco import TrafficGraph, NODE_COORDS, GRID_ADJACENCY
        except ImportError:
            _script_dir = Path(__file__).parent
            _spec = importlib.util.spec_from_file_location("aco", _script_dir / "aco.py")
            _mod = importlib.util.module_from_spec(_spec)
            _spec.loader.exec_module(_mod)
            TrafficGraph = _mod.TrafficGraph
            NODE_COORDS = _mod.NODE_COORDS
            GRID_ADJACENCY = _mod.GRID_ADJACENCY


# ═══════════════════════════════════════════════════════════════════
# DIJKSTRA – Static (Báo cáo 1, Mục 7)
# ═══════════════════════════════════════════════════════════════════

def dijkstra_static(graph: TrafficGraph, source: str,
                    target: str) -> Tuple[Optional[List[str]], float]:
    """
    Thuật toán Dijkstra với trọng số khoảng cách.

    C_ij = D_ij (chiều dài đoạn đường)

    Dùng làm baseline – đường ngắn nhất về khoảng cách.

    Args:
        graph:  Đồ thị giao thông
        source: Nút xuất phát
        target: Nút đích

    Returns:
        (path, cost): Đường đi ngắn nhất và chi phí, hoặc (None, inf)
    """
    return _dijkstra(graph, source, target, cost_fn="static")


# ═══════════════════════════════════════════════════════════════════
# DIJKSTRA – Traffic-Aware (Báo cáo 1, Mục 7)
# ═══════════════════════════════════════════════════════════════════

def dijkstra_traffic(graph: TrafficGraph, source: str,
                     target: str) -> Tuple[Optional[List[str]], float]:
    """
    Thuật toán Dijkstra với trọng số travel time thực.

    C_ij(t) = T_ij(t) (thời gian di chuyển tại thời điểm t)

    Đánh giá hiệu quả của việc chỉ cập nhật trọng số động.

    Args:
        graph:  Đồ thị giao thông
        source: Nút xuất phát
        target: Nút đích

    Returns:
        (path, cost): Đường đi tối ưu và chi phí, hoặc (None, inf)
    """
    return _dijkstra(graph, source, target, cost_fn="travel_time")


# ═══════════════════════════════════════════════════════════════════
# DIJKSTRA – Dynamic Cost (giống ACO traffic-aware)
# ═══════════════════════════════════════════════════════════════════

def dijkstra_dynamic(graph: TrafficGraph, source: str,
                     target: str) -> Tuple[Optional[List[str]], float]:
    """
    Thuật toán Dijkstra với hàm chi phí tổng hợp giống ACO traffic-aware.

    C_ij(t) = w_d·D_norm + w_t·T_norm + w_q·Q_norm + w_w·W_norm

    Dùng để so sánh trực tiếp: cùng hàm chi phí, Dijkstra vs ACO.

    Args:
        graph:  Đồ thị giao thông
        source: Nút xuất phát
        target: Nút đích

    Returns:
        (path, cost): Đường đi tối ưu và chi phí, hoặc (None, inf)
    """
    return _dijkstra(graph, source, target, cost_fn="dynamic")


# ═══════════════════════════════════════════════════════════════════
# A* (Báo cáo 1, Mục 7)
# ═══════════════════════════════════════════════════════════════════

def astar(graph: TrafficGraph, source: str,
          target: str) -> Tuple[Optional[List[str]], float]:
    """
    Thuật toán A* với heuristic khoảng cách Euclid đến đích.

    f(n) = g(n) + h(n)
    - g(n): chi phí từ source đến n (khoảng cách thực)
    - h(n): khoảng cách Euclid từ n đến target (heuristic admissible)

    Giảm không gian tìm kiếm so với Dijkstra.

    Args:
        graph:  Đồ thị giao thông
        source: Nút xuất phát
        target: Nút đích

    Returns:
        (path, cost): Đường đi tối ưu và chi phí, hoặc (None, inf)
    """
    # Priority queue: (f_score, counter, node)
    counter = 0
    open_set = [(0, counter, source)]
    came_from: Dict[str, str] = {}
    g_score: Dict[str, float] = {source: 0.0}

    while open_set:
        f, _, current = heapq.heappop(open_set)

        if current == target:
            # Reconstruct path
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            path.reverse()
            return path, g_score[target]

        for neighbor in graph.get_neighbors(current):
            # g = chi phí khoảng cách thực (static)
            edge_cost = graph.get_static_cost(current, neighbor)
            tentative_g = g_score[current] + edge_cost

            if tentative_g < g_score.get(neighbor, float('inf')):
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                # h = khoảng cách Euclid đến đích (admissible heuristic)
                h = graph.euclidean_distance(neighbor, target)
                f_score = tentative_g + h
                counter += 1
                heapq.heappush(open_set, (f_score, counter, neighbor))

    return None, float('inf')


# ═══════════════════════════════════════════════════════════════════
# INTERNAL: Dijkstra generic
# ═══════════════════════════════════════════════════════════════════

def _dijkstra(graph: TrafficGraph, source: str, target: str,
              cost_fn: str = "static") -> Tuple[Optional[List[str]], float]:
    """
    Dijkstra generic với nhiều loại cost function.

    Args:
        cost_fn: "static" (khoảng cách), "travel_time", hoặc "dynamic" (tổng hợp)
    """
    # Priority queue: (cost, counter, node)
    counter = 0
    pq = [(0, counter, source)]
    dist: Dict[str, float] = {source: 0.0}
    came_from: Dict[str, str] = {}

    while pq:
        d, _, current = heapq.heappop(pq)

        if current == target:
            # Reconstruct path
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            path.reverse()
            return path, dist[target]

        if d > dist.get(current, float('inf')):
            continue

        for neighbor in graph.get_neighbors(current):
            if cost_fn == "static":
                edge_cost = graph.get_static_cost(current, neighbor)
            elif cost_fn == "travel_time":
                edge_cost = graph.get_travel_time_cost(current, neighbor)
            elif cost_fn == "dynamic":
                edge_cost = graph.get_dynamic_cost(current, neighbor)
            else:
                edge_cost = graph.get_static_cost(current, neighbor)

            new_dist = dist[current] + edge_cost

            if new_dist < dist.get(neighbor, float('inf')):
                dist[neighbor] = new_dist
                came_from[neighbor] = current
                counter += 1
                heapq.heappush(pq, (new_dist, counter, neighbor))

    return None, float('inf')


# ═══════════════════════════════════════════════════════════════════
# WRAPPER: Chạy tất cả thuật toán
# ═══════════════════════════════════════════════════════════════════

def run_all_algorithms(graph: TrafficGraph, source: str, target: str,
                       aco_params: dict = None) -> List[Dict]:
    """
    Chạy tất cả thuật toán trên cùng một đồ thị và trả về kết quả so sánh.

    Args:
        graph:      Đồ thị giao thông (đã cập nhật dữ liệu động nếu có)
        source:     Nút xuất phát
        target:     Nút đích
        aco_params: Tham số cho ACO (n_ants, n_iterations, ...)

    Returns:
        List[Dict]: Kết quả của từng thuật toán
    """
    # Import ACO
    try:
        from .aco import AntColonyOptimizer
    except (ImportError, ValueError):
        try:
            from scripts.core.aco import AntColonyOptimizer
        except ImportError:
            try:
                from aco import AntColonyOptimizer
            except ImportError:
                _spec = importlib.util.spec_from_file_location("aco", Path(__file__).parent / "aco.py")
                _mod = importlib.util.module_from_spec(_spec)
                _spec.loader.exec_module(_mod)
                AntColonyOptimizer = _mod.AntColonyOptimizer

    if aco_params is None:
        aco_params = {}

    results = []

    # 1. Dijkstra Static
    t0 = time.time()
    path, cost = dijkstra_static(graph, source, target)
    elapsed = (time.time() - t0) * 1000
    results.append({
        "algorithm": "Dijkstra (static)",
        "path":      path,
        "path_str":  " → ".join(path) if path else "N/A",
        "edges":     graph.path_to_edges(path) if path else [],
        "cost":      round(cost, 6),
        "time_ms":   round(elapsed, 3),
    })

    # 2. Dijkstra Traffic-Aware
    t0 = time.time()
    path, cost = dijkstra_traffic(graph, source, target)
    elapsed = (time.time() - t0) * 1000
    results.append({
        "algorithm": "Dijkstra (traffic)",
        "path":      path,
        "path_str":  " → ".join(path) if path else "N/A",
        "edges":     graph.path_to_edges(path) if path else [],
        "cost":      round(cost, 6),
        "time_ms":   round(elapsed, 3),
    })

    # 3. Dijkstra Dynamic (cùng cost function với ACO traffic-aware)
    t0 = time.time()
    path, cost = dijkstra_dynamic(graph, source, target)
    elapsed = (time.time() - t0) * 1000
    results.append({
        "algorithm": "Dijkstra (dynamic)",
        "path":      path,
        "path_str":  " → ".join(path) if path else "N/A",
        "edges":     graph.path_to_edges(path) if path else [],
        "cost":      round(cost, 6),
        "time_ms":   round(elapsed, 3),
    })

    # 4. A*
    t0 = time.time()
    path, cost = astar(graph, source, target)
    elapsed = (time.time() - t0) * 1000
    results.append({
        "algorithm": "A*",
        "path":      path,
        "path_str":  " → ".join(path) if path else "N/A",
        "edges":     graph.path_to_edges(path) if path else [],
        "cost":      round(cost, 6),
        "time_ms":   round(elapsed, 3),
    })

    # 5. ACO Basic
    t0 = time.time()
    aco_basic = AntColonyOptimizer(graph, mode="basic", **aco_params)
    path, cost = aco_basic.solve(source, target)
    elapsed = (time.time() - t0) * 1000
    results.append({
        "algorithm": "ACO (basic)",
        "path":      path,
        "path_str":  " → ".join(path) if path else "N/A",
        "edges":     graph.path_to_edges(path) if path else [],
        "cost":      round(cost, 6),
        "time_ms":   round(elapsed, 3),
    })

    # 6. ACO Traffic-Aware
    t0 = time.time()
    aco_traffic = AntColonyOptimizer(graph, mode="traffic_aware", **aco_params)
    path, cost = aco_traffic.solve(source, target)
    elapsed = (time.time() - t0) * 1000
    results.append({
        "algorithm": "ACO (traffic-aware)",
        "path":      path,
        "path_str":  " → ".join(path) if path else "N/A",
        "edges":     graph.path_to_edges(path) if path else [],
        "cost":      round(cost, 6),
        "time_ms":   round(elapsed, 3),
    })

    return results


def print_comparison_table(results: List[Dict]):
    """In bảng so sánh kết quả các thuật toán."""
    print(f"\n{'═'*80}")
    print(f"  SO SÁNH CÁC THUẬT TOÁN TÌM ĐƯỜNG")
    print(f"{'═'*80}")
    print(f"  {'Thuật toán':<25} {'Đường đi':<25} {'Chi phí':>10} {'Thời gian':>10}")
    print(f"  {'─'*76}")
    for r in results:
        print(f"  {r['algorithm']:<25} {r['path_str']:<25} "
              f"{r['cost']:>10.4f} {r['time_ms']:>8.2f}ms")
    print(f"{'═'*80}")


# ═══════════════════════════════════════════════════════════════════
# SELF-TEST
# ═══════════════════════════════════════════════════════════════════

def run_self_test():
    """Kiểm tra tất cả thuật toán trên mạng 3×3 offline."""
    print("=" * 65)
    print("  SELF-TEST: Các thuật toán tìm đường trên mạng 3×3")
    print("=" * 65)

    graph = TrafficGraph()

    # ── Test 1: Dijkstra Static ──
    print(f"\n{'─'*65}")
    print("  TEST 1: Dijkstra Static (A → I)")
    print(f"{'─'*65}")
    path, cost = dijkstra_static(graph, "A", "I")
    print(f"  Đường: {' → '.join(path)}")
    print(f"  Chi phí: {cost:.2f}m")
    assert path is not None
    assert path[0] == "A" and path[-1] == "I"
    print(f"  ✓ OK")

    # ── Test 2: A* ──
    print(f"\n{'─'*65}")
    print("  TEST 2: A* (A → I)")
    print(f"{'─'*65}")
    path, cost = astar(graph, "A", "I")
    print(f"  Đường: {' → '.join(path)}")
    print(f"  Chi phí: {cost:.2f}m")
    assert path is not None
    print(f"  ✓ OK")

    # ── Test 3: Giả lập ùn tắc, so sánh tất cả ──
    print(f"\n{'─'*65}")
    print("  TEST 3: So sánh với ùn tắc giả lập trên B→C, C→F")
    print(f"{'─'*65}")

    # Giả lập ùn tắc
    graph.vehicles[("B", "C")] = 40
    graph.waiting[("B", "C")]  = 200.0
    graph.speed[("B", "C")]    = 2.0
    graph.travel_time[("B", "C")] = 100.0
    graph.vehicles[("C", "F")] = 35
    graph.waiting[("C", "F")]  = 180.0
    graph.speed[("C", "F")]    = 3.0
    graph.travel_time[("C", "F")] = 90.0

    results = run_all_algorithms(graph, "A", "I",
                                  aco_params={"n_ants": 20, "n_iterations": 30})
    print_comparison_table(results)

    print(f"\n  ✓ Tất cả test PASSED!")
    print(f"{'='*65}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Thuật toán tìm đường đối chứng")
    parser.add_argument("--test", action="store_true", help="Chạy self-test")
    args = parser.parse_args()

    if args.test:
        run_self_test()
    else:
        print("Sử dụng: python -m scripts.core.routing --test")
        print("Hoặc:    python scripts/core/routing.py --test")
