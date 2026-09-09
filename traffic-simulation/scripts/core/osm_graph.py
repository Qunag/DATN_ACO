#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
osm_graph.py – Xây dựng TrafficGraph từ bản đồ OSM/SUMO net.xml
=================================================================

Module này tự động đọc topology mạng đường từ file SUMO net.xml
(được convert từ OpenStreetMap) và xây dựng đồ thị giao thông
tương thích với ACO engine.

Khác biệt so với TrafficGraph gốc (mạng 3×3 hardcode):
  - Topology được tự động parse từ net.xml
  - Edge IDs giữ nguyên định dạng SUMO (ví dụ: "123456#0")
  - Hỗ trợ hàng trăm/nghìn nút và cạnh
  - Tự chọn cặp OD phù hợp (cách xa, có đường đi)

Sử dụng:
    python scripts/osm_graph.py --test
    python scripts/osm_graph.py --net osm/map2.net.xml --info
"""

import sys
import io
import os
import math
import random
import heapq
import time
import argparse
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set
from collections import defaultdict

# Fix Unicode output trên Windows console
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


# ═══════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════

# Trọng số hàm chi phí cạnh động (giống aco.py)
DEFAULT_COST_WEIGHTS = {
    "w_d": 0.2,   # trọng số khoảng cách
    "w_t": 0.3,   # trọng số thời gian di chuyển
    "w_q": 0.3,   # trọng số số phương tiện (mức ùn tắc)
    "w_w": 0.2,   # trọng số thời gian chờ
}

# Giá trị chuẩn hóa – tăng bounds cho mạng lớn
NORM_BOUNDS = {
    "distance":     1000.0,   # chiều dài tối đa một cạnh (m) – OSM edges dài hơn
    "travel_time":  200.0,    # travel time tối đa (s)
    "vehicles":     80,       # số xe tối đa trên một cạnh
    "waiting":      500.0,    # waiting time tối đa (s)
}

EPSILON = 1e-6

# Tốc độ mặc định nếu không có thông tin (50 km/h)
DEFAULT_SPEED = 13.89  # m/s

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_NET_FILE = PROJECT_DIR / "osm" / "map2.net.xml"


# ═══════════════════════════════════════════════════════════════════
# HELPER: Parse SUMO net.xml
# ═══════════════════════════════════════════════════════════════════

def parse_net_xml(net_file: str) -> dict:
    """
    Parse file SUMO net.xml để lấy topology mạng đường.

    Returns:
        dict với các key:
          - junctions: {junction_id: {"x": float, "y": float, "type": str}}
          - edges: {edge_id: {"from": str, "to": str, "length": float, "speed": float}}
          - adjacency: {junction_id: [(neighbor_junction_id, edge_id), ...]}
    """
    print(f"  Đang parse net.xml: {net_file}")
    tree = ET.parse(net_file)
    root = tree.getroot()

    # ── Parse junctions ──
    junctions = {}
    for j in root.findall('.//junction'):
        jid = j.get('id')
        jtype = j.get('type', '')

        # Bỏ qua internal junctions
        if jtype == 'internal':
            continue

        x = float(j.get('x', 0))
        y = float(j.get('y', 0))
        junctions[jid] = {"x": x, "y": y, "type": jtype}

    # ── Parse edges ──
    edges = {}
    for e in root.findall('.//edge'):
        eid = e.get('id', '')

        # Bỏ qua internal edges (bắt đầu bằng ':')
        if eid.startswith(':'):
            continue

        from_j = e.get('from')
        to_j = e.get('to')

        # Bỏ qua nếu junction không tồn tại
        if from_j not in junctions or to_j not in junctions:
            continue

        # Lấy chiều dài và tốc độ từ lane con
        total_length = 0.0
        max_speed = DEFAULT_SPEED
        lane_count = 0

        for lane in e.findall('lane'):
            length = float(lane.get('length', 0))
            speed = float(lane.get('speed', DEFAULT_SPEED))
            total_length += length
            max_speed = max(max_speed, speed)
            lane_count += 1

        # Nếu không có lane, tính khoảng cách Euclid
        if lane_count == 0:
            x1, y1 = junctions[from_j]["x"], junctions[from_j]["y"]
            x2, y2 = junctions[to_j]["x"], junctions[to_j]["y"]
            total_length = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
        else:
            total_length /= lane_count  # Lấy trung bình

        # Bỏ qua edge quá ngắn
        if total_length < 1.0:
            continue

        edges[eid] = {
            "from": from_j,
            "to": to_j,
            "length": total_length,
            "speed": max_speed,
            "lanes": lane_count,
        }

    # ── Build adjacency list ──
    adjacency = defaultdict(list)
    for eid, edata in edges.items():
        adjacency[edata["from"]].append((edata["to"], eid))

    # Chỉ giữ lại junctions có kết nối
    connected_junctions = set()
    for from_j, neighbors in adjacency.items():
        connected_junctions.add(from_j)
        for to_j, _ in neighbors:
            connected_junctions.add(to_j)

    junctions = {jid: jdata for jid, jdata in junctions.items()
                 if jid in connected_junctions}

    print(f"  → {len(junctions)} junctions, {len(edges)} edges")

    return {
        "junctions": junctions,
        "edges": edges,
        "adjacency": dict(adjacency),
    }


# ═══════════════════════════════════════════════════════════════════
# CLASS: OSMTrafficGraph
# ═══════════════════════════════════════════════════════════════════

class OSMTrafficGraph:
    """
    Đồ thị giao thông xây dựng từ bản đồ SUMO/OSM.

    Tương thích API với TrafficGraph (aco.py) nhưng:
    - Topology tự động từ net.xml
    - Edge IDs giữ nguyên định dạng SUMO
    - Hỗ trợ mạng lớn (hàng trăm/nghìn nút)
    """

    def __init__(self, net_file: str = None,
                 cost_weights: Dict[str, float] = None,
                 norm_bounds: Dict[str, float] = None):
        """
        Args:
            net_file:     Đường dẫn đến file SUMO net.xml
            cost_weights: Trọng số hàm chi phí {w_d, w_t, w_q, w_w}
            norm_bounds:  Giá trị chuẩn hóa tùy chỉnh
        """
        self.cost_weights = cost_weights or DEFAULT_COST_WEIGHTS.copy()
        self.norm_bounds = norm_bounds or NORM_BOUNDS.copy()

        # Dữ liệu topology
        self.nodes: List[str] = []
        self.adjacency: Dict[str, List[str]] = {}  # junction_id -> [neighbor_ids]
        self.coords: Dict[str, Tuple[float, float]] = {}  # junction_id -> (x, y)

        # Mapping edge ↔ (from, to)
        self._edge_to_pair: Dict[str, Tuple[str, str]] = {}  # edge_id -> (from, to)
        self._pair_to_edge: Dict[Tuple[str, str], str] = {}  # (from, to) -> edge_id

        # Dữ liệu tĩnh
        self.distance: Dict[Tuple[str, str], float] = {}
        self.max_speed: Dict[Tuple[str, str], float] = {}

        # Dữ liệu động (cập nhật từ SUMO)
        self.travel_time: Dict[Tuple[str, str], float] = {}
        self.vehicles:    Dict[Tuple[str, str], int]   = {}
        self.waiting:     Dict[Tuple[str, str], float] = {}
        self.speed:       Dict[Tuple[str, str], float] = {}
        self.halting:     Dict[Tuple[str, str], int]   = {}

        if net_file:
            self.load_from_net_xml(net_file)

    def load_from_net_xml(self, net_file: str):
        """Tải topology từ SUMO net.xml."""
        data = parse_net_xml(net_file)

        # Build nodes & coords
        self.nodes = list(data["junctions"].keys())
        self.coords = {
            jid: (jdata["x"], jdata["y"])
            for jid, jdata in data["junctions"].items()
        }

        # Build adjacency (junction -> [neighbor junctions])
        adj_nodes = defaultdict(list)
        for from_j, neighbors in data["adjacency"].items():
            for to_j, edge_id in neighbors:
                adj_nodes[from_j].append(to_j)
                self._edge_to_pair[edge_id] = (from_j, to_j)
                self._pair_to_edge[(from_j, to_j)] = edge_id

        self.adjacency = dict(adj_nodes)

        # Đảm bảo tất cả node có entry trong adjacency
        for node in self.nodes:
            if node not in self.adjacency:
                self.adjacency[node] = []

        # Build distance & khởi tạo dữ liệu động
        for eid, edata in data["edges"].items():
            pair = (edata["from"], edata["to"])
            self.distance[pair] = edata["length"]
            self.max_speed[pair] = edata["speed"]

            # Khởi tạo dữ liệu động với giá trị mặc định
            self.travel_time[pair] = edata["length"] / edata["speed"]
            self.vehicles[pair]    = 0
            self.waiting[pair]     = 0.0
            self.speed[pair]       = edata["speed"]
            self.halting[pair]     = 0

        # Cập nhật norm_bounds dựa trên mạng thực
        max_dist = max(self.distance.values()) if self.distance else 1000.0
        self.norm_bounds["distance"] = max(max_dist * 1.2, 500.0)

        print(f"  → Graph loaded: {len(self.nodes)} nodes, "
              f"{len(self.distance)} edges, "
              f"max edge length: {max_dist:.0f}m")

    # ─────────────────────────────────────────────────────────────
    # API tương thích với TrafficGraph
    # ─────────────────────────────────────────────────────────────

    def get_neighbors(self, node: str) -> List[str]:
        """Trả về danh sách nút láng giềng."""
        return self.adjacency.get(node, [])

    def sumo_edge_id(self, from_node: str, to_node: str) -> str:
        """Trả về SUMO edge ID cho cặp (from, to)."""
        return self._pair_to_edge.get((from_node, to_node), "")

    def euclidean_distance(self, node1: str, node2: str) -> float:
        """Khoảng cách Euclid giữa hai nút."""
        if node1 not in self.coords or node2 not in self.coords:
            return float('inf')
        x1, y1 = self.coords[node1]
        x2, y2 = self.coords[node2]
        return math.sqrt((x2 - x1)**2 + (y2 - y1)**2)

    # ─────────────────────────────────────────────────────────────
    # Cập nhật từ TraCI
    # ─────────────────────────────────────────────────────────────

    def update_from_traci(self, traci):
        """Cập nhật tất cả trọng số động từ SUMO qua TraCI."""
        for edge_id, (from_j, to_j) in self._edge_to_pair.items():
            pair = (from_j, to_j)
            try:
                self.travel_time[pair] = traci.edge.getTraveltime(edge_id)
                self.vehicles[pair]    = traci.edge.getLastStepVehicleNumber(edge_id)
                self.waiting[pair]     = traci.edge.getWaitingTime(edge_id)
                self.speed[pair]       = traci.edge.getLastStepMeanSpeed(edge_id)
                self.halting[pair]     = traci.edge.getLastStepHaltingNumber(edge_id)
            except Exception:
                pass

    # ─────────────────────────────────────────────────────────────
    # Hàm chi phí cạnh
    # ─────────────────────────────────────────────────────────────

    def get_static_cost(self, from_node: str, to_node: str) -> float:
        """Chi phí tĩnh: chỉ khoảng cách."""
        return self.distance.get((from_node, to_node), float('inf'))

    def get_dynamic_cost(self, from_node: str, to_node: str) -> float:
        """
        Chi phí động (giống TrafficGraph):
        C_ij(t) = w_d·D_norm + w_t·T_norm + w_q·Q_norm + w_w·W_norm
        """
        w = self.cost_weights
        nb = self.norm_bounds
        key = (from_node, to_node)

        d_norm = min(self.distance.get(key, 0) / nb["distance"], 1.0)
        t_norm = min(self.travel_time.get(key, 0) / nb["travel_time"], 1.0)
        q_norm = min(self.vehicles.get(key, 0) / nb["vehicles"], 1.0)
        w_norm = min(self.waiting.get(key, 0) / nb["waiting"], 1.0)

        cost = (
            w["w_d"] * d_norm +
            w["w_t"] * t_norm +
            w["w_q"] * q_norm +
            w["w_w"] * w_norm
        )
        return cost

    def get_cost(self, from_node: str, to_node: str,
                 mode: str = "traffic_aware") -> float:
        """Trả về chi phí cạnh theo mode."""
        if mode == "static":
            return self.get_static_cost(from_node, to_node)
        else:
            return self.get_dynamic_cost(from_node, to_node)

    def get_travel_time_cost(self, from_node: str, to_node: str) -> float:
        """Chi phí = travel time thực tế."""
        return self.travel_time.get((from_node, to_node), float('inf'))

    # ─────────────────────────────────────────────────────────────
    # Chuyển đổi path ↔ edges
    # ─────────────────────────────────────────────────────────────

    def path_to_edges(self, path: List[str]) -> List[str]:
        """Chuyển danh sách junction IDs thành danh sách SUMO edge IDs."""
        edges = []
        for i in range(len(path) - 1):
            edge_id = self._pair_to_edge.get((path[i], path[i + 1]), "")
            if edge_id:
                edges.append(edge_id)
        return edges

    def edges_to_path(self, edges: List[str]) -> List[str]:
        """Chuyển danh sách SUMO edge IDs thành danh sách junction IDs."""
        if not edges:
            return []
        path = []
        for eid in edges:
            pair = self._edge_to_pair.get(eid)
            if pair:
                if not path:
                    path.append(pair[0])
                path.append(pair[1])
        return path

    def compute_path_cost(self, path: List[str],
                          mode: str = "traffic_aware") -> float:
        """Tính tổng chi phí của một đường đi."""
        total = 0.0
        for i in range(len(path) - 1):
            total += self.get_cost(path[i], path[i + 1], mode)
        return total

    # ─────────────────────────────────────────────────────────────
    # Chọn cặp OD phù hợp
    # ─────────────────────────────────────────────────────────────

    def find_od_pairs(self, n_pairs: int = 3,
                      min_distance: float = 1000.0,
                      seed: int = 42) -> List[Tuple[str, str]]:
        """
        Tự động chọn n cặp Origin-Destination hợp lý.

        Tiêu chí:
        - Cách nhau ít nhất min_distance (m)
        - Có đường đi hợp lệ (kiểm tra bằng BFS)
        - Ưu tiên các nút có nhiều kết nối (nút giao lớn)

        Args:
            n_pairs:      Số cặp OD cần tìm
            min_distance: Khoảng cách Euclid tối thiểu (m)
            seed:         Random seed cho reproducibility

        Returns:
            List[(origin, destination)]
        """
        rng = random.Random(seed)

        # Ưu tiên nút có nhiều kết nối (nút giao lớn)
        node_degree = {
            n: len(self.adjacency.get(n, []))
            for n in self.nodes
        }

        # Lọc các nút có ít nhất 2 kết nối (tránh dead-end)
        candidates = [n for n in self.nodes if node_degree[n] >= 2]

        if len(candidates) < 2:
            candidates = [n for n in self.nodes if node_degree[n] >= 1]

        # Sắp xếp theo degree giảm dần, lấy top 30% làm ứng viên tốt
        candidates.sort(key=lambda n: node_degree[n], reverse=True)
        top_candidates = candidates[:max(len(candidates) // 3, 10)]

        od_pairs = []
        attempts = 0
        max_attempts = n_pairs * 50

        while len(od_pairs) < n_pairs and attempts < max_attempts:
            attempts += 1

            origin = rng.choice(top_candidates)
            dest = rng.choice(candidates)

            if origin == dest:
                continue

            # Kiểm tra khoảng cách
            dist = self.euclidean_distance(origin, dest)
            if dist < min_distance:
                continue

            # Kiểm tra đường đi bằng BFS
            if not self._bfs_reachable(origin, dest):
                continue

            # Kiểm tra không trùng
            if (origin, dest) not in od_pairs:
                od_pairs.append((origin, dest))

        if len(od_pairs) < n_pairs:
            print(f"  [!] Chỉ tìm được {len(od_pairs)}/{n_pairs} cặp OD "
                  f"(min_distance={min_distance}m)")

        return od_pairs

    def _bfs_reachable(self, source: str, target: str,
                       max_depth: int = 100) -> bool:
        """Kiểm tra có đường đi từ source đến target bằng BFS."""
        if source == target:
            return True

        visited = {source}
        queue = [source]
        depth = 0

        while queue and depth < max_depth:
            next_queue = []
            for node in queue:
                for nb in self.adjacency.get(node, []):
                    if nb == target:
                        return True
                    if nb not in visited:
                        visited.add(nb)
                        next_queue.append(nb)
            queue = next_queue
            depth += 1

        return False

    def get_od_info(self, origin: str, dest: str) -> str:
        """Trả về thông tin ngắn gọn về cặp OD."""
        dist = self.euclidean_distance(origin, dest)
        o_deg = len(self.adjacency.get(origin, []))
        d_deg = len(self.adjacency.get(dest, []))
        return (f"{origin[:12]:>12} → {dest[:12]:<12} "
                f"(dist={dist:.0f}m, deg={o_deg}→{d_deg})")

    def __repr__(self):
        return (f"OSMTrafficGraph(nodes={len(self.nodes)}, "
                f"edges={len(self.distance)})")


# ═══════════════════════════════════════════════════════════════════
# ACO cho OSM Graph
# ═══════════════════════════════════════════════════════════════════

class OSMAntColonyOptimizer:
    """
    Giải thuật Đàn Kiến (ACO) tối ưu cho mạng đường OSM lớn.

    Cải tiến so với ACO cơ bản (aco.py) để xử lý mạng thực tế:

    1. **Directional heuristic (γ)**: Thêm thành phần hướng đích vào
       xác suất chọn cạnh, giúp kiến không đi lạc trong mạng lớn.

       P_ij^k = (τ_ij^α · η_ij^β · δ_ij^γ) / Σ(...)

       Trong đó δ_ij = 1 / (dist(j, dest) + ε) — hấp dẫn hướng đích

    2. **Dijkstra seed**: Khởi tạo pheromone cao hơn trên đường đi
       Dijkstra, giúp kiến có "bản đồ sơ bộ" để bắt đầu khám phá.

    3. **Dead-end avoidance**: Ưu tiên nút có nhiều kết nối,
       tránh các ngõ cụt trong mạng thực.
    """

    def __init__(
        self,
        graph: OSMTrafficGraph,
        n_ants:       int   = 30,
        n_iterations: int   = 80,
        alpha:        float = 1.0,
        beta:         float = 3.0,
        gamma:        float = 2.0,
        rho:          float = 0.1,
        Q:            float = 100.0,
        mode:         str   = "traffic_aware",
        adaptive_rho: bool  = False,
        rho_min:      float = 0.05,
        rho_max:      float = 0.3,
        seed_with_dijkstra: bool = True,
    ):
        """
        Args:
            graph:        OSMTrafficGraph
            n_ants:       Số kiến mỗi vòng lặp
            n_iterations: Số vòng lặp
            alpha:        Mức độ ảnh hưởng pheromone
            beta:         Mức độ ảnh hưởng heuristic chi phí
            gamma:        Mức độ ảnh hưởng heuristic hướng đích (MỚI)
            rho:          Tỷ lệ bay hơi pheromone
            Q:            Hằng số cập nhật pheromone
            mode:         "static" hoặc "traffic_aware"
            adaptive_rho: Bật pheromone thích nghi
            seed_with_dijkstra: Khởi tạo pheromone từ Dijkstra
        """
        self.graph = graph
        self.n_ants = n_ants
        self.n_iterations = n_iterations
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma
        self.rho = rho
        self.Q = Q
        self.mode = mode
        self.adaptive_rho = adaptive_rho
        self.rho_min = rho_min
        self.rho_max = rho_max
        self.seed_with_dijkstra = seed_with_dijkstra

        # Pheromone
        self.pheromone: Dict[Tuple[str, str], float] = {}
        self._init_pheromone()

        # Best solution
        self.best_path: Optional[List[str]] = None
        self.best_cost: float = float('inf')
        self.iteration_history: List[Dict] = []

        # Cache cho destination distance (tính 1 lần mỗi solve)
        self._dest_dist_cache: Dict[str, float] = {}

    def _init_pheromone(self, tau_0: float = 1.0):
        """Khởi tạo pheromone cho tất cả cạnh."""
        for pair in self.graph.distance:
            self.pheromone[pair] = tau_0

    def _seed_pheromone_from_dijkstra(self, source: str, destination: str,
                                       seed_factor: float = 5.0):
        """
        Khởi tạo pheromone cao hơn trên đường đi Dijkstra.

        Giúp kiến có "bản đồ sơ bộ" trong mạng lớn, sau đó
        tự khám phá các tuyến thay thế tốt hơn.

        Args:
            seed_factor: Hệ số nhân pheromone trên đường Dijkstra
        """
        path, cost = dijkstra_osm(self.graph, source, destination, "dynamic")
        if path:
            for i in range(len(path) - 1):
                edge = (path[i], path[i + 1])
                if edge in self.pheromone:
                    self.pheromone[edge] *= seed_factor
            # Lưu đường Dijkstra làm best ban đầu
            self.best_path = path[:]
            self.best_cost = self.graph.compute_path_cost(path, self.mode)

    def _precompute_dest_distances(self, destination: str):
        """
        Tính trước khoảng cách Euclid từ mỗi nút đến đích.
        Dùng cho directional heuristic.
        """
        self._dest_dist_cache = {}
        dx, dy = self.graph.coords.get(destination, (0, 0))
        for node in self.graph.nodes:
            if node in self.graph.coords:
                nx, ny = self.graph.coords[node]
                dist = math.sqrt((dx - nx)**2 + (dy - ny)**2)
                self._dest_dist_cache[node] = dist
            else:
                self._dest_dist_cache[node] = float('inf')

    def reset(self):
        """Reset pheromone và lịch sử."""
        self._init_pheromone()
        self.best_path = None
        self.best_cost = float('inf')
        self.iteration_history = []
        self._dest_dist_cache = {}

    def _heuristic(self, from_node: str, to_node: str) -> float:
        """η_ij = 1 / (C_ij(t) + ε) — heuristic chi phí cạnh"""
        cost = self.graph.get_cost(from_node, to_node, self.mode)
        return 1.0 / (cost + EPSILON)

    def _directional_heuristic(self, to_node: str) -> float:
        """δ_ij = 1 / (dist(j, dest) + ε) — heuristic hướng đích"""
        dist = self._dest_dist_cache.get(to_node, float('inf'))
        return 1.0 / (dist + 1.0)  # +1m tránh chia 0

    def _select_next_node(self, current: str, visited: Set[str],
                          destination: str) -> Optional[str]:
        """
        Chọn nút tiếp theo cho kiến.

        Công thức mở rộng cho mạng lớn:
        P_ij^k = (τ_ij^α · η_ij^β · δ_ij^γ) / Σ(...)

        Trong đó:
        - τ_ij: pheromone
        - η_ij: heuristic chi phí (1/cost)
        - δ_ij: heuristic hướng đích (1/dist_to_dest)
        """
        neighbors = self.graph.get_neighbors(current)
        candidates = [n for n in neighbors if n not in visited]

        # Ưu tiên đích nếu là neighbor
        if destination in candidates:
            return destination

        if not candidates:
            return None

        # Tính xác suất với directional heuristic
        probabilities = []
        for nb in candidates:
            tau = self.pheromone.get((current, nb), EPSILON)
            eta = self._heuristic(current, nb)
            delta = self._directional_heuristic(nb)

            # P = τ^α · η^β · δ^γ
            prob = (tau ** self.alpha) * (eta ** self.beta) * (delta ** self.gamma)

            # Bonus nhỏ cho nút có nhiều kết nối (tránh dead-end)
            degree = len(self.graph.adjacency.get(nb, []))
            if degree > 1:
                prob *= (1.0 + 0.1 * min(degree, 5))

            probabilities.append(prob)

        total = sum(probabilities)
        if total == 0:
            return random.choice(candidates)

        probabilities = [p / total for p in probabilities]

        # Roulette wheel selection
        r = random.random()
        cumulative = 0.0
        for i, prob in enumerate(probabilities):
            cumulative += prob
            if r <= cumulative:
                return candidates[i]

        return candidates[-1]

    def _construct_path(self, source: str, destination: str,
                        max_steps: int = 200) -> Optional[List[str]]:
        """Một kiến xây dựng đường đi."""
        path = [source]
        visited = {source}
        current = source

        for _ in range(max_steps):
            if current == destination:
                return path

            next_node = self._select_next_node(current, visited, destination)
            if next_node is None:
                return None

            path.append(next_node)
            visited.add(next_node)
            current = next_node

        return None

    def _evaporate_pheromone(self, iteration: int = 0):
        """Bay hơi pheromone."""
        if self.adaptive_rho:
            rho = self.rho_max - (iteration / max(self.n_iterations, 1)) * \
                  (self.rho_max - self.rho_min)
        else:
            rho = self.rho

        for key in self.pheromone:
            self.pheromone[key] *= (1.0 - rho)
            if self.pheromone[key] < EPSILON:
                self.pheromone[key] = EPSILON

    def _update_pheromone(self, paths: List[Tuple[List[str], float]]):
        """Cập nhật pheromone từ các kiến thành công."""
        for path, cost in paths:
            if cost <= 0:
                continue
            delta = self.Q / cost
            for i in range(len(path) - 1):
                edge = (path[i], path[i + 1])
                self.pheromone[edge] = self.pheromone.get(edge, 0) + delta

    def solve(self, source: str, destination: str,
              verbose: bool = False,
              max_steps: int = 200) -> Tuple[Optional[List[str]], float]:
        """
        Chạy ACO tìm đường tối ưu.

        Args:
            source:      Junction ID xuất phát
            destination: Junction ID đích
            verbose:     In thông tin
            max_steps:   Số bước tối đa cho mỗi kiến

        Returns:
            (best_path, best_cost)
        """
        start_time = time.time()

        # Pre-compute distances to destination
        self._precompute_dest_distances(destination)

        # Seed pheromone từ Dijkstra
        if self.seed_with_dijkstra:
            self._seed_pheromone_from_dijkstra(source, destination)

        for iteration in range(self.n_iterations):
            ant_paths = []

            for ant in range(self.n_ants):
                path = self._construct_path(source, destination, max_steps)
                if path is not None:
                    cost = self.graph.compute_path_cost(path, self.mode)
                    ant_paths.append((path, cost))

                    if cost < self.best_cost:
                        self.best_cost = cost
                        self.best_path = path[:]

            self._evaporate_pheromone(iteration)
            self._update_pheromone(ant_paths)

            iter_best_cost = min((c for _, c in ant_paths),
                                 default=float('inf'))
            success_rate = len(ant_paths) / self.n_ants * 100

            self.iteration_history.append({
                "iteration":    iteration + 1,
                "best_cost":    round(self.best_cost, 6),
                "iter_cost":    round(iter_best_cost, 6),
                "success_rate": round(success_rate, 1),
                "n_paths":      len(ant_paths),
            })

            if verbose and (iteration + 1) % 20 == 0:
                print(f"    Vòng {iteration+1:3d}/{self.n_iterations}: "
                      f"best={self.best_cost:.4f}, "
                      f"iter_best={iter_best_cost:.4f}, "
                      f"success={success_rate:.0f}%")

        elapsed = time.time() - start_time

        if verbose:
            print(f"    ACO hoàn thành trong {elapsed*1000:.1f}ms")
            if self.best_path:
                print(f"    Path length: {len(self.best_path)} nodes")
                print(f"    Chi phí: {self.best_cost:.6f}")

        return self.best_path, self.best_cost


# ═══════════════════════════════════════════════════════════════════
# Dijkstra cho OSM Graph
# ═══════════════════════════════════════════════════════════════════

def dijkstra_osm(graph: OSMTrafficGraph, source: str, target: str,
                 cost_fn: str = "dynamic") -> Tuple[Optional[List[str]], float]:
    """
    Dijkstra trên OSMTrafficGraph.

    Args:
        cost_fn: "static", "travel_time", hoặc "dynamic"
    """
    counter = 0
    pq = [(0, counter, source)]
    dist: Dict[str, float] = {source: 0.0}
    came_from: Dict[str, str] = {}

    while pq:
        d, _, current = heapq.heappop(pq)

        if current == target:
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


def astar_osm(graph: OSMTrafficGraph, source: str,
              target: str) -> Tuple[Optional[List[str]], float]:
    """A* trên OSMTrafficGraph với heuristic Euclid."""
    counter = 0
    open_set = [(0, counter, source)]
    came_from: Dict[str, str] = {}
    g_score: Dict[str, float] = {source: 0.0}

    while open_set:
        f, _, current = heapq.heappop(open_set)

        if current == target:
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            path.reverse()
            return path, g_score[target]

        for neighbor in graph.get_neighbors(current):
            edge_cost = graph.get_static_cost(current, neighbor)
            tentative_g = g_score[current] + edge_cost

            if tentative_g < g_score.get(neighbor, float('inf')):
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                h = graph.euclidean_distance(neighbor, target)
                f_score = tentative_g + h
                counter += 1
                heapq.heappush(open_set, (f_score, counter, neighbor))

    return None, float('inf')


def run_all_osm_algorithms(graph: OSMTrafficGraph, source: str, target: str,
                           aco_params: dict = None) -> List[Dict]:
    """
    Chạy tất cả thuật toán trên OSMTrafficGraph.

    Returns:
        List[Dict]: Kết quả từng thuật toán
    """
    if aco_params is None:
        aco_params = {}

    results = []

    # 1. Dijkstra Static
    t0 = time.time()
    path, cost = dijkstra_osm(graph, source, target, "static")
    elapsed = (time.time() - t0) * 1000
    results.append({
        "algorithm": "Dijkstra (static)",
        "path":      path,
        "path_len":  len(path) if path else 0,
        "edges":     graph.path_to_edges(path) if path else [],
        "cost":      round(cost, 6),
        "time_ms":   round(elapsed, 3),
    })

    # 2. Dijkstra Traffic
    t0 = time.time()
    path, cost = dijkstra_osm(graph, source, target, "travel_time")
    elapsed = (time.time() - t0) * 1000
    results.append({
        "algorithm": "Dijkstra (traffic)",
        "path":      path,
        "path_len":  len(path) if path else 0,
        "edges":     graph.path_to_edges(path) if path else [],
        "cost":      round(cost, 6),
        "time_ms":   round(elapsed, 3),
    })

    # 3. Dijkstra Dynamic
    t0 = time.time()
    path, cost = dijkstra_osm(graph, source, target, "dynamic")
    elapsed = (time.time() - t0) * 1000
    results.append({
        "algorithm": "Dijkstra (dynamic)",
        "path":      path,
        "path_len":  len(path) if path else 0,
        "edges":     graph.path_to_edges(path) if path else [],
        "cost":      round(cost, 6),
        "time_ms":   round(elapsed, 3),
    })

    # 4. A*
    t0 = time.time()
    path, cost = astar_osm(graph, source, target)
    elapsed = (time.time() - t0) * 1000
    results.append({
        "algorithm": "A*",
        "path":      path,
        "path_len":  len(path) if path else 0,
        "edges":     graph.path_to_edges(path) if path else [],
        "cost":      round(cost, 6),
        "time_ms":   round(elapsed, 3),
    })

    # 5. ACO Traffic-Aware
    t0 = time.time()
    aco = OSMAntColonyOptimizer(graph, mode="traffic_aware", **aco_params)
    path, cost = aco.solve(source, target)
    elapsed = (time.time() - t0) * 1000
    results.append({
        "algorithm": "ACO (traffic-aware)",
        "path":      path,
        "path_len":  len(path) if path else 0,
        "edges":     graph.path_to_edges(path) if path else [],
        "cost":      round(cost, 6),
        "time_ms":   round(elapsed, 3),
    })

    return results


def print_osm_comparison_table(results: List[Dict], od_label: str = ""):
    """In bảng so sánh kết quả."""
    header = f"  SO SÁNH THUẬT TOÁN – {od_label}" if od_label else "  SO SÁNH THUẬT TOÁN"
    print(f"\n{'═'*80}")
    print(header)
    print(f"{'═'*80}")
    print(f"  {'Thuật toán':<22} {'Nodes':>6} {'Chi phí':>12} {'Thời gian':>12}")
    print(f"  {'─'*56}")
    for r in results:
        print(f"  {r['algorithm']:<22} {r['path_len']:>6} "
              f"{r['cost']:>12.4f} {r['time_ms']:>10.2f}ms")
    print(f"{'═'*80}")


# ═══════════════════════════════════════════════════════════════════
# SELF-TEST
# ═══════════════════════════════════════════════════════════════════

def run_self_test(net_file: str = None):
    """Test offline trên map OSM (không cần SUMO)."""
    if net_file is None:
        net_file = str(DEFAULT_NET_FILE)

    print("=" * 70)
    print("  SELF-TEST: OSMTrafficGraph")
    print("=" * 70)

    if not Path(net_file).exists():
        print(f"\n  [!] File không tồn tại: {net_file}")
        print("  Cần có file map2.net.xml trong thư mục osm/")
        return False

    # ── Load graph ──
    print(f"\n  [1/4] Loading graph từ {Path(net_file).name}...")
    graph = OSMTrafficGraph(net_file)
    print(f"  → {graph}")

    # ── Tìm cặp OD ──
    print(f"\n  [2/4] Tìm cặp OD phù hợp...")
    od_pairs = graph.find_od_pairs(n_pairs=3, min_distance=1000.0)

    if not od_pairs:
        print("  [!] Không tìm được cặp OD. Thử giảm min_distance...")
        od_pairs = graph.find_od_pairs(n_pairs=3, min_distance=500.0)

    if not od_pairs:
        print("  [!] Vẫn không tìm được cặp OD hợp lệ!")
        return False

    for i, (o, d) in enumerate(od_pairs):
        print(f"  Cặp {i+1}: {graph.get_od_info(o, d)}")

    # ── Test Dijkstra ──
    print(f"\n  [3/4] Test Dijkstra trên cặp OD đầu tiên...")
    origin, dest = od_pairs[0]

    t0 = time.time()
    path_s, cost_s = dijkstra_osm(graph, origin, dest, "static")
    t_static = (time.time() - t0) * 1000

    t0 = time.time()
    path_d, cost_d = dijkstra_osm(graph, origin, dest, "dynamic")
    t_dynamic = (time.time() - t0) * 1000

    if path_s:
        print(f"  Dijkstra static:  cost={cost_s:.4f}, "
              f"{len(path_s)} nodes, {t_static:.2f}ms")
    else:
        print(f"  Dijkstra static:  KHÔNG TÌM ĐƯỢC ĐƯỜNG")

    if path_d:
        print(f"  Dijkstra dynamic: cost={cost_d:.4f}, "
              f"{len(path_d)} nodes, {t_dynamic:.2f}ms")
    else:
        print(f"  Dijkstra dynamic: KHÔNG TÌM ĐƯỢC ĐƯỜNG")

    # ── Test ACO ──
    print(f"\n  [4/4] Test ACO trên cặp OD đầu tiên...")
    aco = OSMAntColonyOptimizer(
        graph, n_ants=30, n_iterations=80,
        mode="traffic_aware", beta=3.0
    )
    t0 = time.time()
    path_aco, cost_aco = aco.solve(origin, dest, verbose=True, max_steps=200)
    t_aco = (time.time() - t0) * 1000

    if path_aco:
        print(f"  ACO traffic-aware: cost={cost_aco:.4f}, "
              f"{len(path_aco)} nodes, {t_aco:.2f}ms")

        # So sánh với Dijkstra
        if path_d and cost_d > 0:
            ratio = cost_aco / cost_d
            print(f"  ACO/Dijkstra ratio: {ratio:.4f} "
                  f"({'tối ưu!' if ratio <= 1.05 else f'sai lệch {(ratio-1)*100:.1f}%'})")
    else:
        print(f"  ACO traffic-aware: KHÔNG TÌM ĐƯỢC ĐƯỜNG")

    # ── Tóm tắt ──
    print(f"\n{'='*70}")
    print(f"  TÓM TẮT SELF-TEST")
    print(f"{'='*70}")
    print(f"  Graph: {len(graph.nodes)} nodes, {len(graph.distance)} edges")
    print(f"  Cặp OD: {len(od_pairs)} cặp tìm được")
    print(f"  Dijkstra: {'✓ OK' if path_d else '✗ FAIL'}")
    print(f"  ACO:      {'✓ OK' if path_aco else '✗ FAIL'}")

    if path_d and path_aco:
        print(f"\n  THỜI GIAN TÍNH TOÁN:")
        print(f"    Dijkstra static:  {t_static:.2f}ms")
        print(f"    Dijkstra dynamic: {t_dynamic:.2f}ms")
        print(f"    ACO (30×80):      {t_aco:.2f}ms")

    print(f"{'='*70}")
    return True


def print_net_info(net_file: str):
    """In thông tin mạng đường."""
    graph = OSMTrafficGraph(net_file)

    print(f"\n{'='*60}")
    print(f"  THÔNG TIN MẠNG ĐƯỜNG")
    print(f"{'='*60}")
    print(f"  File: {net_file}")
    print(f"  Nodes: {len(graph.nodes)}")
    print(f"  Edges: {len(graph.distance)}")

    if graph.distance:
        lengths = list(graph.distance.values())
        print(f"  Edge length: min={min(lengths):.1f}m, "
              f"max={max(lengths):.1f}m, "
              f"avg={sum(lengths)/len(lengths):.1f}m")

    # Thống kê degree
    degrees = [len(graph.adjacency.get(n, [])) for n in graph.nodes]
    if degrees:
        print(f"  Node degree: min={min(degrees)}, "
              f"max={max(degrees)}, "
              f"avg={sum(degrees)/len(degrees):.1f}")

    # Tìm cặp OD
    od_pairs = graph.find_od_pairs(n_pairs=5, min_distance=1000.0)
    if od_pairs:
        print(f"\n  Cặp OD gợi ý:")
        for i, (o, d) in enumerate(od_pairs):
            print(f"    {i+1}. {graph.get_od_info(o, d)}")

    print(f"{'='*60}")


# ═══════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="OSM TrafficGraph – Đồ thị giao thông từ bản đồ thực"
    )
    parser.add_argument("--test", action="store_true",
                        help="Chạy self-test (không cần SUMO)")
    parser.add_argument("--info", action="store_true",
                        help="In thông tin mạng đường")
    parser.add_argument("--net", type=str, default=None,
                        help="Đường dẫn file net.xml (mặc định: osm/map2.net.xml)")
    args = parser.parse_args()

    if args.test:
        run_self_test(args.net)
    elif args.info:
        net_file = args.net or str(DEFAULT_NET_FILE)
        print_net_info(net_file)
    else:
        print("Sử dụng:")
        print("  python -m scripts.core.osm_graph --test")
        print("  python -m scripts.core.osm_graph --info")
        print("  python -m scripts.core.osm_graph --net osm/map2.net.xml --info")
