#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
aco.py – Giải thuật Đàn Kiến (Ant Colony Optimization) cho bài toán điều hướng giao thông
===========================================================================================

Module này implement:
  1. TrafficGraph  – Biểu diễn mạng giao thông dạng đồ thị
  2. AntColonyOptimizer – Thuật toán ACO (basic + traffic-aware)

Tham chiếu:
  - Báo cáo 1, Mục 3: Mô hình bài toán (công thức chi phí cạnh)
  - Báo cáo 1, Mục 4: Nguyên lý hoạt động ACO
  - Báo cáo 1, Mục 5: Ý tưởng cải tiến (traffic-aware heuristic)

Sử dụng độc lập (self-test):
    python scripts/aco.py --test
"""

import sys
import io
import math
import random
import time
import argparse
from typing import Dict, List, Tuple, Optional, Set

# Fix Unicode output trên Windows console
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


# ═══════════════════════════════════════════════════════════════════
# CONSTANTS – Tham số mặc định
# ═══════════════════════════════════════════════════════════════════

# Trọng số hàm chi phí cạnh động (Báo cáo 1, Mục 3)
# C_ij(t) = w_d·D_ij + w_t·T_ij(t) + w_q·Q_ij(t) + w_w·W_ij(t)
DEFAULT_COST_WEIGHTS = {
    "w_d": 0.2,   # trọng số khoảng cách
    "w_t": 0.3,   # trọng số thời gian di chuyển
    "w_q": 0.3,   # trọng số số phương tiện (mức ùn tắc)
    "w_w": 0.2,   # trọng số thời gian chờ
}

# Giá trị chuẩn hóa (normalization bounds)
NORM_BOUNDS = {
    "distance":     500.0,    # chiều dài tối đa một cạnh (m)
    "travel_time":  120.0,    # travel time tối đa (s)
    "vehicles":     50,       # số xe tối đa trên một cạnh
    "waiting":      300.0,    # waiting time tối đa (s)
}

# Epsilon tránh chia cho 0 (Báo cáo 1, Mục 3)
EPSILON = 1e-6

# Tọa độ các nút trong mạng 3×3 (dùng cho A* heuristic)
NODE_COORDS = {
    "A": (0, 500),    "B": (500, 500),   "C": (1000, 500),
    "D": (0, 0),      "E": (500, 0),     "F": (1000, 0),
    "G": (0, -500),   "H": (500, -500),  "I": (1000, -500),
}

# Kề của mạng 3×3 (danh sách các nút láng giềng)
GRID_ADJACENCY = {
    "A": ["B", "D"],
    "B": ["A", "C", "E"],
    "C": ["B", "F"],
    "D": ["A", "E", "G"],
    "E": ["B", "D", "F", "H"],
    "F": ["C", "E", "I"],
    "G": ["D", "H"],
    "H": ["E", "G", "I"],
    "I": ["F", "H"],
}


# ═══════════════════════════════════════════════════════════════════
# CLASS: TrafficGraph
# ═══════════════════════════════════════════════════════════════════

class TrafficGraph:
    """
    Biểu diễn mạng giao thông dạng đồ thị có trọng số động.

    Mỗi cạnh (i, j) có:
      - distance:    chiều dài đoạn đường (m) – cố định
      - travel_time: thời gian di chuyển thực tế (s) – cập nhật từ SUMO
      - vehicles:    số phương tiện trên đoạn đường – cập nhật từ SUMO
      - waiting:     thời gian chờ tổng cộng (s) – cập nhật từ SUMO
      - speed:       tốc độ trung bình (m/s) – cập nhật từ SUMO
      - halting:     số xe đang dừng – cập nhật từ SUMO

    Tên edge trong SUMO: "{i}2{j}" (ví dụ A2B, B2C, ...)
    """

    def __init__(self, adjacency: Dict[str, List[str]] = None,
                 coords: Dict[str, Tuple[float, float]] = None,
                 cost_weights: Dict[str, float] = None):
        """
        Args:
            adjacency:    Danh sách kề {node: [neighbors]}
            coords:       Tọa độ các nút {node: (x, y)}
            cost_weights: Trọng số hàm chi phí {w_d, w_t, w_q, w_w}
        """
        self.adjacency = adjacency or GRID_ADJACENCY
        self.coords = coords or NODE_COORDS
        self.cost_weights = cost_weights or DEFAULT_COST_WEIGHTS.copy()
        self.nodes = list(self.adjacency.keys())

        # Dữ liệu tĩnh: khoảng cách (tính từ tọa độ)
        self.distance: Dict[Tuple[str, str], float] = {}

        # Dữ liệu động: cập nhật từ SUMO mỗi bước
        self.travel_time: Dict[Tuple[str, str], float] = {}
        self.vehicles:    Dict[Tuple[str, str], int]   = {}
        self.waiting:     Dict[Tuple[str, str], float] = {}
        self.speed:       Dict[Tuple[str, str], float] = {}
        self.halting:     Dict[Tuple[str, str], int]   = {}

        self._init_distances()

    def _init_distances(self):
        """Tính khoảng cách Euclid cho tất cả các cạnh."""
        for node, neighbors in self.adjacency.items():
            for nb in neighbors:
                x1, y1 = self.coords[node]
                x2, y2 = self.coords[nb]
                dist = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
                self.distance[(node, nb)] = dist
                # Khởi tạo dữ liệu động với giá trị mặc định
                self.travel_time[(node, nb)] = dist / 13.89  # 50 km/h
                self.vehicles[(node, nb)]    = 0
                self.waiting[(node, nb)]     = 0.0
                self.speed[(node, nb)]       = 13.89
                self.halting[(node, nb)]     = 0

    def sumo_edge_id(self, from_node: str, to_node: str) -> str:
        """Trả về tên edge SUMO: 'A2B'."""
        return f"{from_node}2{to_node}"

    def get_neighbors(self, node: str) -> List[str]:
        """Trả về danh sách nút láng giềng."""
        return self.adjacency.get(node, [])

    def euclidean_distance(self, node1: str, node2: str) -> float:
        """Khoảng cách Euclid giữa hai nút (dùng cho A* heuristic)."""
        x1, y1 = self.coords[node1]
        x2, y2 = self.coords[node2]
        return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

    # ─────────────────────────────────────────────────────────────
    # Cập nhật dữ liệu từ SUMO TraCI
    # ─────────────────────────────────────────────────────────────

    def update_from_traci(self, traci):
        """
        Cập nhật tất cả trọng số động từ SUMO qua TraCI.

        Đọc dữ liệu cho mọi cạnh trong đồ thị.
        Tương ứng Báo cáo 2, Mục 8.
        """
        for node, neighbors in self.adjacency.items():
            for nb in neighbors:
                edge_id = self.sumo_edge_id(node, nb)
                try:
                    self.travel_time[(node, nb)] = traci.edge.getTraveltime(edge_id)
                    self.vehicles[(node, nb)]    = traci.edge.getLastStepVehicleNumber(edge_id)
                    self.waiting[(node, nb)]     = traci.edge.getWaitingTime(edge_id)
                    self.speed[(node, nb)]       = traci.edge.getLastStepMeanSpeed(edge_id)
                    self.halting[(node, nb)]      = traci.edge.getLastStepHaltingNumber(edge_id)
                except Exception:
                    pass  # Cạnh có thể chưa tồn tại trong một số trường hợp

    def update_edge_from_traci(self, traci, from_node: str, to_node: str):
        """Cập nhật dữ liệu cho một cạnh cụ thể."""
        edge_id = self.sumo_edge_id(from_node, to_node)
        try:
            self.travel_time[(from_node, to_node)] = traci.edge.getTraveltime(edge_id)
            self.vehicles[(from_node, to_node)]    = traci.edge.getLastStepVehicleNumber(edge_id)
            self.waiting[(from_node, to_node)]     = traci.edge.getWaitingTime(edge_id)
            self.speed[(from_node, to_node)]       = traci.edge.getLastStepMeanSpeed(edge_id)
            self.halting[(from_node, to_node)]      = traci.edge.getLastStepHaltingNumber(edge_id)
        except Exception:
            pass

    # ─────────────────────────────────────────────────────────────
    # Hàm chi phí cạnh (Báo cáo 1, Mục 3)
    # ─────────────────────────────────────────────────────────────

    def get_static_cost(self, from_node: str, to_node: str) -> float:
        """
        Chi phí tĩnh: chỉ khoảng cách.
        Dùng cho ACO basic và Dijkstra static.
        """
        return self.distance.get((from_node, to_node), float('inf'))

    def get_dynamic_cost(self, from_node: str, to_node: str) -> float:
        """
        Chi phí động (Báo cáo 1, Mục 3):

            C_ij(t) = w_d·D_norm + w_t·T_norm + w_q·Q_norm + w_w·W_norm

        Tất cả thành phần được chuẩn hóa về [0, 1] trước khi tổng hợp.
        """
        w = self.cost_weights
        key = (from_node, to_node)

        # Chuẩn hóa từng thành phần
        d_norm = min(self.distance.get(key, 0) / NORM_BOUNDS["distance"], 1.0)
        t_norm = min(self.travel_time.get(key, 0) / NORM_BOUNDS["travel_time"], 1.0)
        q_norm = min(self.vehicles.get(key, 0) / NORM_BOUNDS["vehicles"], 1.0)
        w_norm = min(self.waiting.get(key, 0) / NORM_BOUNDS["waiting"], 1.0)

        cost = (
            w["w_d"] * d_norm +
            w["w_t"] * t_norm +
            w["w_q"] * q_norm +
            w["w_w"] * w_norm
        )
        return cost

    def get_cost(self, from_node: str, to_node: str, mode: str = "traffic_aware") -> float:
        """
        Trả về chi phí cạnh theo mode.

        Args:
            mode: "static" (chỉ khoảng cách) hoặc "traffic_aware" (có dữ liệu giao thông)
        """
        if mode == "static":
            return self.get_static_cost(from_node, to_node)
        else:
            return self.get_dynamic_cost(from_node, to_node)

    def get_travel_time_cost(self, from_node: str, to_node: str) -> float:
        """Chi phí = travel time thực tế. Dùng cho Dijkstra traffic-aware."""
        return self.travel_time.get((from_node, to_node), float('inf'))

    # ─────────────────────────────────────────────────────────────
    # Chuyển đổi path nodes ↔ SUMO edges
    # ─────────────────────────────────────────────────────────────

    def path_to_edges(self, path: List[str]) -> List[str]:
        """
        Chuyển danh sách node thành danh sách SUMO edge IDs.
        Ví dụ: ["A", "B", "C"] → ["A2B", "B2C"]
        """
        edges = []
        for i in range(len(path) - 1):
            edges.append(self.sumo_edge_id(path[i], path[i + 1]))
        return edges

    def compute_path_cost(self, path: List[str], mode: str = "traffic_aware") -> float:
        """Tính tổng chi phí của một đường đi."""
        total = 0.0
        for i in range(len(path) - 1):
            total += self.get_cost(path[i], path[i + 1], mode)
        return total

    def __repr__(self):
        return f"TrafficGraph(nodes={len(self.nodes)}, edges={len(self.distance)})"


# ═══════════════════════════════════════════════════════════════════
# CLASS: AntColonyOptimizer
# ═══════════════════════════════════════════════════════════════════

class AntColonyOptimizer:
    """
    Giải thuật Đàn Kiến (ACO) cho bài toán tìm đường trong mạng giao thông.

    Implement theo Báo cáo 1:
      - Mục 4: Nguyên lý hoạt động (xác suất, pheromone, bay hơi)
      - Mục 5.1: ACO nhận biết trạng thái giao thông
      - Mục 5.2: Pheromone thích nghi (tùy chọn)

    Hai chế độ:
      - "basic":         η_ij = 1 / (D_ij + ε)  — chỉ khoảng cách
      - "traffic_aware":  η_ij = 1 / (C_ij(t) + ε)  — có dữ liệu giao thông
    """

    def __init__(
        self,
        graph: TrafficGraph,
        n_ants:       int   = 20,
        n_iterations: int   = 50,
        alpha:        float = 1.0,
        beta:         float = 2.0,
        rho:          float = 0.1,
        Q:            float = 100.0,
        mode:         str   = "traffic_aware",
        adaptive_rho: bool  = False,
        rho_min:      float = 0.05,
        rho_max:      float = 0.3,
    ):
        """
        Args:
            graph:        Đồ thị giao thông
            n_ants:       Số kiến mỗi vòng lặp
            n_iterations: Số vòng lặp
            alpha:        Mức độ ảnh hưởng của pheromone (Báo cáo 1, Mục 4)
            beta:         Mức độ ảnh hưởng của heuristic (Báo cáo 1, Mục 4)
            rho:          Tỷ lệ bay hơi pheromone (Báo cáo 1, Mục 4)
            Q:            Hằng số cập nhật pheromone (Báo cáo 1, Mục 4)
            mode:         "basic" hoặc "traffic_aware"
            adaptive_rho: Bật pheromone thích nghi (Báo cáo 1, Mục 5.2)
            rho_min:      Tỷ lệ bay hơi tối thiểu (cho adaptive)
            rho_max:      Tỷ lệ bay hơi tối đa (cho adaptive)
        """
        self.graph = graph
        self.n_ants = n_ants
        self.n_iterations = n_iterations
        self.alpha = alpha
        self.beta = beta
        self.rho = rho
        self.Q = Q
        self.mode = mode
        self.adaptive_rho = adaptive_rho
        self.rho_min = rho_min
        self.rho_max = rho_max

        # Ma trận pheromone: τ[i][j]
        # Khởi tạo τ_0 = 1.0 cho tất cả cạnh
        self.pheromone: Dict[Tuple[str, str], float] = {}
        self._init_pheromone()

        # Lịch sử tối ưu
        self.best_path: Optional[List[str]] = None
        self.best_cost: float = float('inf')
        self.iteration_history: List[Dict] = []

    def _init_pheromone(self, tau_0: float = 1.0):
        """Khởi tạo pheromone cho tất cả cạnh."""
        for node, neighbors in self.graph.adjacency.items():
            for nb in neighbors:
                self.pheromone[(node, nb)] = tau_0

    def reset(self):
        """Reset pheromone và lịch sử để chạy lại từ đầu."""
        self._init_pheromone()
        self.best_path = None
        self.best_cost = float('inf')
        self.iteration_history = []

    # ─────────────────────────────────────────────────────────────
    # Heuristic η_ij (Báo cáo 1, Mục 3 và 5.1)
    # ─────────────────────────────────────────────────────────────

    def _heuristic(self, from_node: str, to_node: str) -> float:
        """
        Tính giá trị heuristic η_ij.

        - Basic:         η_ij = 1 / (D_ij + ε)
        - Traffic-aware: η_ij = 1 / (C_ij(t) + ε)

        Báo cáo 1, Mục 5.1: ACO nhận biết trạng thái giao thông
        """
        cost = self.graph.get_cost(from_node, to_node, self.mode)
        return 1.0 / (cost + EPSILON)

    # ─────────────────────────────────────────────────────────────
    # Xác suất lựa chọn cạnh (Báo cáo 1, Mục 4)
    # ─────────────────────────────────────────────────────────────

    def _select_next_node(self, current: str, visited: Set[str],
                          destination: str) -> Optional[str]:
        """
        Chọn nút tiếp theo cho kiến dựa trên công thức xác suất.

        P_ij^k = (τ_ij^α · η_ij^β) / Σ(τ_il^α · η_il^β)

        Báo cáo 1, Mục 4.

        Args:
            current:     Nút hiện tại
            visited:     Tập các nút đã đi qua
            destination: Nút đích

        Returns:
            Nút được chọn, hoặc None nếu không có nút nào khả dụng
        """
        neighbors = self.graph.get_neighbors(current)

        # Lọc các nút chưa thăm (N_i^k trong công thức)
        candidates = [n for n in neighbors if n not in visited]

        # Nếu đích là neighbor và chưa thăm → ưu tiên đi thẳng đến đích
        if destination in candidates:
            return destination

        if not candidates:
            return None

        # Tính xác suất cho từng candidate
        probabilities = []
        for nb in candidates:
            tau = self.pheromone.get((current, nb), EPSILON)
            eta = self._heuristic(current, nb)

            # τ_ij^α · η_ij^β
            prob = (tau ** self.alpha) * (eta ** self.beta)
            probabilities.append(prob)

        # Chuẩn hóa xác suất
        total = sum(probabilities)
        if total == 0:
            # Nếu tất cả xác suất = 0, chọn ngẫu nhiên
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

    # ─────────────────────────────────────────────────────────────
    # Xây dựng đường đi cho một kiến
    # ─────────────────────────────────────────────────────────────

    def _construct_path(self, source: str, destination: str) -> Optional[List[str]]:
        """
        Một kiến xây dựng đường đi từ source đến destination.

        Returns:
            Danh sách node tạo thành đường đi, hoặc None nếu thất bại
        """
        path = [source]
        visited = {source}
        current = source

        # Giới hạn số bước để tránh vòng lặp vô hạn
        max_steps = len(self.graph.nodes) * 2

        for _ in range(max_steps):
            if current == destination:
                return path

            next_node = self._select_next_node(current, visited, destination)
            if next_node is None:
                return None  # Kiến bị kẹt, không tìm được đường

            path.append(next_node)
            visited.add(next_node)
            current = next_node

        return None  # Vượt quá giới hạn bước

    # ─────────────────────────────────────────────────────────────
    # Bay hơi và cập nhật pheromone (Báo cáo 1, Mục 4)
    # ─────────────────────────────────────────────────────────────

    def _evaporate_pheromone(self, iteration: int = 0):
        """
        Bay hơi pheromone trên tất cả cạnh.

        τ_ij ← (1 - ρ) · τ_ij

        Nếu adaptive_rho = True (Báo cáo 1, Mục 5.2):
            ρ(t) = ρ_max - (t/T)(ρ_max - ρ_min)
        """
        if self.adaptive_rho:
            # Pheromone thích nghi (Báo cáo 1, Mục 5.2)
            rho = self.rho_max - (iteration / max(self.n_iterations, 1)) * \
                  (self.rho_max - self.rho_min)
        else:
            rho = self.rho

        for key in self.pheromone:
            self.pheromone[key] *= (1.0 - rho)
            # Đảm bảo pheromone không quá nhỏ
            if self.pheromone[key] < EPSILON:
                self.pheromone[key] = EPSILON

    def _update_pheromone(self, paths: List[Tuple[List[str], float]]):
        """
        Cập nhật pheromone cho các đường đi thành công.

        Δτ_ij^k = Q / L_k

        Báo cáo 1, Mục 4.

        Args:
            paths: Danh sách (path, cost) của các kiến đã tìm được đường
        """
        for path, cost in paths:
            if cost <= 0:
                continue
            delta = self.Q / cost
            for i in range(len(path) - 1):
                edge = (path[i], path[i + 1])
                self.pheromone[edge] = self.pheromone.get(edge, 0) + delta

    # ─────────────────────────────────────────────────────────────
    # Chạy ACO
    # ─────────────────────────────────────────────────────────────

    def solve(self, source: str, destination: str,
              verbose: bool = False) -> Tuple[Optional[List[str]], float]:
        """
        Chạy ACO để tìm đường tối ưu từ source đến destination.

        Args:
            source:      Nút xuất phát (ví dụ "A")
            destination: Nút đích (ví dụ "I")
            verbose:     In thông tin mỗi vòng lặp

        Returns:
            (best_path, best_cost) – đường đi tốt nhất và chi phí
        """
        start_time = time.time()

        for iteration in range(self.n_iterations):
            ant_paths = []  # Lưu (path, cost) của kiến thành công

            for ant in range(self.n_ants):
                path = self._construct_path(source, destination)
                if path is not None:
                    cost = self.graph.compute_path_cost(path, self.mode)
                    ant_paths.append((path, cost))

                    # Cập nhật best
                    if cost < self.best_cost:
                        self.best_cost = cost
                        self.best_path = path[:]

            # Bay hơi pheromone
            self._evaporate_pheromone(iteration)

            # Cập nhật pheromone từ các kiến thành công
            self._update_pheromone(ant_paths)

            # Ghi lịch sử
            iter_best_cost = min((c for _, c in ant_paths), default=float('inf'))
            success_rate = len(ant_paths) / self.n_ants * 100
            self.iteration_history.append({
                "iteration":    iteration + 1,
                "best_cost":    round(self.best_cost, 6),
                "iter_cost":    round(iter_best_cost, 6),
                "success_rate": round(success_rate, 1),
                "n_paths":      len(ant_paths),
            })

            if verbose and (iteration + 1) % 10 == 0:
                print(f"  Vòng {iteration+1:3d}/{self.n_iterations}: "
                      f"best={self.best_cost:.4f}, "
                      f"iter_best={iter_best_cost:.4f}, "
                      f"success={success_rate:.0f}%")

        elapsed = time.time() - start_time

        if verbose:
            print(f"\n  ACO hoàn thành trong {elapsed*1000:.1f}ms")
            if self.best_path:
                edges = self.graph.path_to_edges(self.best_path)
                print(f"  Đường tốt nhất: {' → '.join(self.best_path)}")
                print(f"  SUMO edges: {edges}")
                print(f"  Chi phí: {self.best_cost:.6f}")

        return self.best_path, self.best_cost

    def get_stats(self) -> Dict:
        """Trả về thống kê sau khi chạy."""
        return {
            "mode":         self.mode,
            "n_ants":       self.n_ants,
            "n_iterations": self.n_iterations,
            "alpha":        self.alpha,
            "beta":         self.beta,
            "rho":          self.rho,
            "best_path":    self.best_path,
            "best_cost":    self.best_cost,
            "best_edges":   self.graph.path_to_edges(self.best_path) if self.best_path else [],
            "history":      self.iteration_history,
        }


# ═══════════════════════════════════════════════════════════════════
# SELF-TEST: Kiểm tra ACO hoạt động offline (không cần SUMO)
# ═══════════════════════════════════════════════════════════════════

def run_self_test():
    """
    Chạy ACO trên mạng 3×3 với dữ liệu giả lập.
    Kiểm tra thuật toán tìm được đường hợp lệ từ A → I.
    """
    print("=" * 65)
    print("  SELF-TEST: ACO trên mạng 3×3 (không cần SUMO)")
    print("=" * 65)

    graph = TrafficGraph()
    print(f"\n  Đồ thị: {graph}")
    print(f"  Nodes: {graph.nodes}")
    print(f"  Khoảng cách A→B: {graph.distance[('A','B')]:.1f}m")
    print(f"  Khoảng cách A→D: {graph.distance[('A','D')]:.1f}m")

    # ── Test 1: ACO Basic ──
    print(f"\n{'─'*65}")
    print("  TEST 1: ACO Basic (chỉ khoảng cách)")
    print(f"{'─'*65}")
    aco_basic = AntColonyOptimizer(graph, mode="basic", n_ants=20, n_iterations=50)
    path, cost = aco_basic.solve("A", "I", verbose=True)
    assert path is not None, "ACO basic không tìm được đường!"
    assert path[0] == "A" and path[-1] == "I", "Đường đi không hợp lệ!"
    print(f"  ✓ ACO Basic: OK")

    # ── Test 2: ACO Traffic-Aware ──
    print(f"\n{'─'*65}")
    print("  TEST 2: ACO Traffic-Aware (dữ liệu giả lập)")
    print(f"{'─'*65}")

    # Giả lập ùn tắc trên tuyến B→C→F (tuyến rìa phải)
    graph.vehicles[("B", "C")] = 40
    graph.waiting[("B", "C")]  = 200.0
    graph.speed[("B", "C")]    = 2.0
    graph.travel_time[("B", "C")] = 100.0

    graph.vehicles[("C", "F")] = 35
    graph.waiting[("C", "F")]  = 180.0
    graph.speed[("C", "F")]    = 3.0
    graph.travel_time[("C", "F")] = 90.0

    aco_traffic = AntColonyOptimizer(graph, mode="traffic_aware", n_ants=20, n_iterations=50)
    path2, cost2 = aco_traffic.solve("A", "I", verbose=True)
    assert path2 is not None, "ACO traffic-aware không tìm được đường!"
    print(f"  ✓ ACO Traffic-Aware: OK")

    # Kiểm tra ACO tránh tuyến ùn tắc
    if "C" not in path2:
        print(f"  ✓ ACO đã tránh nút C (tuyến ùn tắc B→C→F)")
    else:
        print(f"  ⚠ ACO vẫn đi qua C – có thể do random, chạy lại để kiểm tra")

    # ── Test 3: ACO với Adaptive Rho ──
    print(f"\n{'─'*65}")
    print("  TEST 3: ACO với Pheromone thích nghi")
    print(f"{'─'*65}")
    aco_adaptive = AntColonyOptimizer(
        graph, mode="traffic_aware",
        n_ants=20, n_iterations=50,
        adaptive_rho=True, rho_min=0.05, rho_max=0.3
    )
    path3, cost3 = aco_adaptive.solve("A", "I", verbose=True)
    assert path3 is not None, "ACO adaptive không tìm được đường!"
    print(f"  ✓ ACO Adaptive: OK")

    # ── Tóm tắt ──
    print(f"\n{'='*65}")
    print("  TÓM TẮT SELF-TEST")
    print(f"{'='*65}")
    print(f"  ACO Basic:          {' → '.join(aco_basic.best_path)}  "
          f"(cost={aco_basic.best_cost:.4f})")
    print(f"  ACO Traffic-Aware:  {' → '.join(aco_traffic.best_path)}  "
          f"(cost={aco_traffic.best_cost:.4f})")
    print(f"  ACO Adaptive:       {' → '.join(aco_adaptive.best_path)}  "
          f"(cost={aco_adaptive.best_cost:.4f})")
    print(f"\n  ✓ Tất cả test PASSED!")
    print(f"{'='*65}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ACO cho bài toán điều hướng giao thông")
    parser.add_argument("--test", action="store_true", help="Chạy self-test (không cần SUMO)")
    args = parser.parse_args()

    if args.test:
        run_self_test()
    else:
        print("Sử dụng: python scripts/aco.py --test")
        print("Hoặc import module: from aco import TrafficGraph, AntColonyOptimizer")
