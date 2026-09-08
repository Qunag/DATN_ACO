# BÁO CÁO TÍCH HỢP GIẢI THUẬT ĐÀN KIẾN VÀO MÔ HÌNH MÔ PHỎNG SUMO

## 1. Mục đích

Giai đoạn này tích hợp giải thuật Ant Colony Optimization (ACO) vào mô hình mô phỏng giao thông 3×3 đã xây dựng ở giai đoạn 2.

Mục tiêu cụ thể:

- Implement ACO core (basic và traffic-aware).
- Implement các thuật toán đối chứng: Dijkstra, A*.
- Kết nối ACO với SUMO qua TraCI.
- Xây dựng cơ chế tái định tuyến động (dynamic rerouting).
- So sánh hiệu quả các thuật toán trên cùng kịch bản.

---

## 2. Kiến trúc hệ thống

```text
                 MÔ PHỎNG SUMO (3×3 Grid)
                        │
                        │ TraCI
                        ▼
              TRAFFIC DATA COLLECTOR
                        │
           ┌────────────┼────────────┐
           ↓            ↓            ↓
        Speed       Vehicle       Waiting
                     Count          Time
           └────────────┼────────────┘
                        ↓
                 TRAFFIC GRAPH
            (TrafficGraph class)
                        │
       ┌────────────────┼────────────────┐
       ↓                ↓                ↓
  get_static_cost  get_dynamic_cost  get_travel_time
       │                │                │
       ↓                ↓                ↓
                ROUTING ENGINE
       ┌────────────────┼────────────────┐
       │                │                │
   Dijkstra            A*              ACO
   (3 modes)                      (basic + traffic)
                                        │
                                        ↓
                                   Best Route
                                        │
                                        ↓
                                      TraCI
                             setRoute / reroute
                                        │
                                        ↓
                                  SUMO Vehicle
```

---

## 3. Cấu trúc file

```text
traffic-simulation/
│
├── scripts/
│   ├── aco.py                  # [MỚI] ACO core module
│   │   ├── TrafficGraph        #   Đồ thị giao thông
│   │   └── AntColonyOptimizer  #   Thuật toán ACO
│   │
│   ├── routing.py              # [MỚI] Thuật toán đối chứng
│   │   ├── dijkstra_static()   #   Dijkstra (khoảng cách)
│   │   ├── dijkstra_traffic()  #   Dijkstra (travel time)
│   │   ├── dijkstra_dynamic()  #   Dijkstra (dynamic cost)
│   │   ├── astar()             #   A* (heuristic Euclid)
│   │   └── run_all_algorithms()#   So sánh tất cả
│   │
│   ├── aco_runner.py           # [MỚI] Tích hợp ACO + SUMO
│   │   └── run_aco_simulation()#   Chạy ACO trên SUMO
│   │
│   ├── compare_algorithms.py   # [MỚI] So sánh thuật toán
│   │   └── run_comparison()    #   Snapshot + so sánh
│   │
│   ├── monitor.py              # Thu thập dữ liệu (giai đoạn 2)
│   └── ...
│
├── network/
│   ├── grid_nodes.nod.xml      # 9 nút (A–I)
│   ├── grid_edges.edg.xml      # 24 cạnh
│   └── grid_net.xml            # Mạng đã build
│
├── routes/
│   └── grid_routes.rou.xml     # Luồng xe background
│
└── grid.sumocfg                # Config SUMO cho mạng 3×3
```

---

## 4. Module ACO (`aco.py`)

### 4.1. TrafficGraph

Biểu diễn mạng giao thông dạng đồ thị.

Mạng 3×3 gồm 9 nút và 24 cạnh (12 đoạn × 2 chiều):

```text
A ───── B ───── C
│       │       │
D ───── E ───── F
│       │       │
G ───── H ───── I
```

Mỗi cạnh lưu:

| Thuộc tính | Nguồn | Cập nhật |
|---|---|---|
| distance | Tọa độ nút | Cố định |
| travel_time | `traci.edge.getTraveltime()` | Mỗi bước |
| vehicles | `traci.edge.getLastStepVehicleNumber()` | Mỗi bước |
| waiting | `traci.edge.getWaitingTime()` | Mỗi bước |
| speed | `traci.edge.getLastStepMeanSpeed()` | Mỗi bước |
| halting | `traci.edge.getLastStepHaltingNumber()` | Mỗi bước |

### 4.2. Hàm chi phí cạnh động

Theo Báo cáo 1, Mục 3:

\[
C_{ij}(t) = w_d \cdot D_{norm} + w_t \cdot T_{norm} + w_q \cdot Q_{norm} + w_w \cdot W_{norm}
\]

Các thành phần được chuẩn hóa về [0, 1]:

| Thành phần | Giá trị chuẩn hóa | Trọng số mặc định |
|---|---:|---:|
| D (khoảng cách) | D / 500m | w_d = 0.2 |
| T (travel time) | T / 120s | w_t = 0.3 |
| Q (số xe) | Q / 50 | w_q = 0.3 |
| W (waiting time) | W / 300s | w_w = 0.2 |

### 4.3. AntColonyOptimizer

Tham số ACO:

| Tham số | Ký hiệu | Mặc định | Ý nghĩa |
|---|---|---:|---|
| n_ants | — | 20 | Số kiến mỗi vòng |
| n_iterations | — | 50 | Số vòng lặp |
| alpha | α | 1.0 | Ảnh hưởng pheromone |
| beta | β | 2.0 | Ảnh hưởng heuristic |
| rho | ρ | 0.1 | Tỷ lệ bay hơi |
| Q | Q | 100 | Hằng số cập nhật |

Hai chế độ:

- **basic**: \(\eta_{ij} = 1 / (D_{ij} + \varepsilon)\)
- **traffic_aware**: \(\eta_{ij}(t) = 1 / (C_{ij}(t) + \varepsilon)\)

Công thức xác suất chọn cạnh:

\[
P_{ij}^{k} = \frac{\tau_{ij}^{\alpha} \cdot \eta_{ij}^{\beta}}{\sum_{l \in N_i^k} \tau_{il}^{\alpha} \cdot \eta_{il}^{\beta}}
\]

Bay hơi pheromone:

\[
\tau_{ij} \leftarrow (1 - \rho) \cdot \tau_{ij}
\]

Cập nhật pheromone:

\[
\Delta\tau_{ij}^{k} = \frac{Q}{L_k}
\]

### 4.4. Pheromone thích nghi

Tùy chọn `adaptive_rho` (Báo cáo 1, Mục 5.2):

\[
\rho(t) = \rho_{max} - \frac{t}{T}(\rho_{max} - \rho_{min})
\]

Giai đoạn đầu ưu tiên khám phá, giai đoạn sau tăng khai thác.

---

## 5. Các thuật toán đối chứng (`routing.py`)

### 5.1. Dijkstra (static)

\[
C_{ij} = D_{ij}
\]

Baseline: đường ngắn nhất về khoảng cách.

### 5.2. Dijkstra (traffic-aware)

\[
C_{ij}(t) = T_{ij}(t)
\]

Chỉ dùng travel time thực tế.

### 5.3. Dijkstra (dynamic)

\[
C_{ij}(t) = w_d \cdot D_{norm} + w_t \cdot T_{norm} + w_q \cdot Q_{norm} + w_w \cdot W_{norm}
\]

Cùng hàm chi phí với ACO traffic-aware → so sánh trực tiếp.

### 5.4. A*

Heuristic admissible: khoảng cách Euclid đến đích.

\[
f(n) = g(n) + h(n)
\]

---

## 6. Tích hợp SUMO (`aco_runner.py`)

### 6.1. Quy trình Dynamic Rerouting

```text
Phương tiện đang di chuyển
          ↓
Mỗi REROUTE_INTERVAL bước
          ↓
Cập nhật đồ thị từ TraCI
          ↓
Chạy ACO tìm tuyến mới
          ↓
So sánh với Dijkstra
          ↓
Tuyến mới tốt hơn?
       /         \
     Không       Có
      ↓           ↓
Giữ tuyến   traci.vehicle.setRoute()
                  ↓
          Phương tiện đi tuyến mới
```

### 6.2. Luồng xử lý chính

```text
1. Khởi tạo SUMO + TraCI
2. Tạo TrafficGraph (mạng 3×3)
3. Chạy ACO ban đầu → tuyến khởi đầu
4. Vòng lặp simulation:
   a. traci.simulationStep()
   b. graph.update_from_traci(traci)
   c. Mỗi 60s: Chạy lại ACO
   d. So sánh với tuyến hiện tại
   e. Reroute nếu cần
   f. Sinh xe ACO mới (mỗi 30s)
5. Ghi log CSV
```

### 6.3. Xe ACO-controlled

Script sinh phương tiện riêng (prefix `aco_`) được gán tuyến từ ACO.

Khi reroute, chỉ các xe `aco_*` đang trên tuyến hợp lệ mới được cập nhật route mới.

---

## 7. Kết quả self-test

### 7.1. ACO tìm đường offline

Test trên mạng 3×3, **không cần SUMO**:

| Test | Đường đi | Chi phí | Thời gian |
|---|---|---:|---:|
| ACO Basic | A → D → G → H → I | 1.1600 | 12.7ms |
| ACO Traffic-Aware | A → B → E → F → I | 1.1600 | 12.5ms |
| ACO Adaptive | A → D → G → H → I | 1.1600 | 13.3ms |

### 7.2. So sánh với ùn tắc giả lập

Giả lập ùn tắc trên B→C và C→F:

| Thuật toán | Đường đi | Chi phí | Thời gian |
|---|---|---:|---:|
| Dijkstra (static) | A → B → C → F → I | 2000.0000 | 0.01ms |
| Dijkstra (traffic) | A → B → E → F → I | 143.9885 | 0.02ms |
| Dijkstra (dynamic) | A → B → E → F → I | 1.1600 | 0.03ms |
| A* | A → B → E → F → I | 2000.0000 | 0.02ms |
| ACO (basic) | A → B → E → F → I | 1.1600 | 7.94ms |
| ACO (traffic-aware) | A → B → E → F → I | 1.1600 | 7.37ms |

Nhận xét:

- Dijkstra (static) **không tránh được ùn tắc** vì chỉ xét khoảng cách.
- Tất cả các thuật toán traffic-aware đều chọn tuyến tránh ùn tắc.
- ACO chậm hơn Dijkstra (~7ms vs 0.02ms) nhưng vẫn nhanh ở quy mô nhỏ.
- Ưu điểm chính của ACO sẽ thể hiện rõ khi mạng lớn hơn và có nhiều thay đổi liên tục.

---

## 8. Hướng dẫn chạy

### 8.1. Self-test (không cần SUMO)

```powershell
python scripts/aco.py --test
python scripts/routing.py --test
```

### 8.2. Chạy ACO trên SUMO

```powershell
# Có GUI
python scripts/aco_runner.py

# Không GUI, 600 giây
python scripts/aco_runner.py --nogui --duration 600

# ACO basic (chỉ khoảng cách)
python scripts/aco_runner.py --aco-mode basic

# Tùy chỉnh tham số
python scripts/aco_runner.py --n-ants 30 --iterations 100 --reroute 30
```

### 8.3. So sánh thuật toán

```powershell
# Chạy với snapshots mặc định
python scripts/compare_algorithms.py --nogui --duration 600

# Tùy chọn thời điểm snapshot
python scripts/compare_algorithms.py --nogui --snapshot-at 100 200 300 500

# Cặp OD khác
python scripts/compare_algorithms.py --origin C --dest G
```

---

## 9. Mapping công thức → Code

| Công thức (Báo cáo 1) | Hàm trong code | File |
|---|---|---|
| \(C_{ij}(t) = w_d D + w_t T + w_q Q + w_w W\) | `TrafficGraph.get_dynamic_cost()` | `aco.py` |
| \(\eta_{ij} = 1 / (C_{ij} + \varepsilon)\) | `AntColonyOptimizer._heuristic()` | `aco.py` |
| \(P_{ij}^k = \tau^{\alpha} \eta^{\beta} / \Sigma\) | `AntColonyOptimizer._select_next_node()` | `aco.py` |
| \(\tau \leftarrow (1-\rho)\tau\) | `AntColonyOptimizer._evaporate_pheromone()` | `aco.py` |
| \(\Delta\tau = Q / L_k\) | `AntColonyOptimizer._update_pheromone()` | `aco.py` |
| \(\rho(t) = \rho_{max} - ...\) | `_evaporate_pheromone()` (adaptive) | `aco.py` |
| Dijkstra: \(C_{ij} = D_{ij}\) | `dijkstra_static()` | `routing.py` |
| Dijkstra: \(C_{ij} = T_{ij}(t)\) | `dijkstra_traffic()` | `routing.py` |
| A*: \(f = g + h\) | `astar()` | `routing.py` |

---

## 10. Giai đoạn tiếp theo

Sau khi hệ thống routing hoạt động ổn định:

1. Chạy thực nghiệm trên các kịch bản ùn tắc (Báo cáo 1, Mục 9).
2. Thu thập và phân tích kết quả so sánh.
3. Mở rộng sang bản đồ thực tế (OpenStreetMap).
4. Nghiên cứu điều khiển đèn giao thông thích nghi.
