# traffic-simulation

Dự án mô phỏng giao thông ban đầu bằng **SUMO** phục vụ nghiên cứu giải thuật ACO.  
Đây là **Giai đoạn 1** trong đề tài DATN: *Điều hướng Giao thông bằng Giải thuật Đàn Kiến*.

---

## Mô hình mô phỏng

```
               NORTH (N)
                 │  250m
                 │
WEST (W) ────── C ────── EAST (E)
          250m  │  250m
                │  250m
               SOUTH (S)
```

- **C**: Nút giao có đèn tín hiệu cố định (chu kỳ 66 giây)
- **8 edges**: N2C, C2N, S2C, C2S, E2C, C2E, W2C, C2W
- **2 làn**, tốc độ 50 km/h (13.89 m/s)

---

## Cấu trúc thư mục

```
traffic-simulation/
│
├── network/                         # Mạng đường
│   ├── nodes.nod.xml                # 5 node: N, S, E, W, C
│   ├── edges.edg.xml                # 8 edges hai chiều
│   ├── intersection.net.xml         # Mạng ngã tư
│   └── grid_net.xml                 # Mạng lưới 3×3
│
├── routes/                          # File sinh lưu lượng xe
│   ├── routes_TH1–TH6.rou.xml       # Kịch bản ngã tư (200-1200 xe/h)
│   └── grid_routes.rou.xml          # Kịch bản mạng 3×3
│
├── osm/                             # Bản đồ thực tế (OpenStreetMap)
│   ├── map2.osm                     # File bản đồ OSM thô
│   ├── map2.net.xml                 # Mạng SUMO (619 nodes, 1163 edges)
│   ├── map2.rou.xml                 # Lộ trình xe thực tế
│   └── map2.sumocfg                 # Cấu hình chạy SUMO trên map OSM
│
├── output/                          # Kết quả mô phỏng và log
│   ├── traffic_TH*.csv              # Dữ liệu TraCI theo thời gian
│   ├── tripinfo_*.xml               # Thống kê từng chuyến đi
│   └── comparison.csv               # Bảng so sánh
│
└── scripts/                         # Mã nguồn Python (tổ chức theo nhóm)
    ├── core/                        # ⭐ Module lõi (thuật toán dùng chung)
    │   ├── aco.py                   # TrafficGraph + AntColonyOptimizer
    │   ├── routing.py               # Dijkstra (3 modes) + A*
    │   └── osm_graph.py             # OSMTrafficGraph cho bản đồ OSM
    │
    ├── grid/                        # 🔲 Mạng 3×3 nhân tạo
    │   ├── build_network.py         # Build intersection.net.xml
    │   ├── build_grid.py            # Build grid 3×3
    │   ├── aco_runner.py            # ACO + SUMO trên grid
    │   └── compare_algorithms.py    # So sánh thuật toán trên grid
    │
    ├── osm/                         # 🗺️ Bản đồ thực tế
    │   ├── osm_setup.py             # Hỗ trợ tải/convert OSM
    │   └── osm_runner.py            # ACO + SUMO trên map OSM
    │
    ├── experiments/                 # 🧪 Thí nghiệm & phân tích
    │   ├── monitor.py               # TraCI data collector
    │   ├── run_experiments.py       # Batch 6 kịch bản TH1–TH6
    │   ├── incident_monitor.py      # Giả lập sự cố ùn tắc bất ngờ
    │   ├── adaptive_monitor.py      # Điều khiển đèn thích nghi
    │   └── analyze.py               # Phân tích & vẽ biểu đồ
    │
    └── utils/                       # 🔧 Tiện ích
        └── gui.py                   # Trình mở SUMO-GUI
```

---

## Yêu cầu

- **SUMO** ≥ 1.15.0 — [Tải tại đây](https://sumo.dlr.de/docs/Downloads.php)
- **Python** ≥ 3.8
- Biến môi trường `SUMO_HOME` được set đúng

### Kiểm tra cài đặt

```powershell
# Kiểm tra SUMO
sumo --version

# Kiểm tra SUMO_HOME
echo $env:SUMO_HOME

# Nếu chưa set (PowerShell):
$env:SUMO_HOME = "C:\Program Files (x86)\Eclipse\Sumo"
```

---

## Hướng dẫn chạy

### Bước 1: Build mạng đường

Chạy **một lần duy nhất** để tạo `network/intersection.net.xml`:

```powershell
python -m scripts.grid.build_network
```

### Bước 2: Chạy một kịch bản (có GUI)

```powershell
python -m scripts.experiments.monitor --scenario TH3
```

### Bước 3: Chạy một kịch bản (không GUI, nhanh hơn)

```powershell
python -m scripts.experiments.monitor --scenario TH3 --nogui
```

### Bước 4: Chạy tất cả 6 thí nghiệm

```powershell
python -m scripts.experiments.run_experiments
```

Chạy một số kịch bản nhất định:

```powershell
python -m scripts.experiments.run_experiments --scenarios TH3 TH4 TH5
```

### Bước 5: Phân tích kết quả

```powershell
python -m scripts.experiments.analyze

# Kèm biểu đồ (cần matplotlib):
pip install matplotlib
python -m scripts.experiments.analyze --plot
```

---

## Dữ liệu thu thập (TraCI)

Theo Báo cáo 2, Mục 8:

| TraCI API | Ký hiệu | Ý nghĩa |
|---|---|---|
| `getLastStepVehicleNumber()` | N_ij(t) | Số phương tiện trên cạnh |
| `getLastStepMeanSpeed()` | V_ij(t) | Tốc độ trung bình (m/s) |
| `getLastStepHaltingNumber()` | H_ij(t) | Số xe đang dừng (speed < 0.1 m/s) |
| `getWaitingTime()` | W_ij(t) | Tổng thời gian chờ (s) |
| `getTraveltime()` | T_ij(t) | Thời gian di chuyển (s) |

### Format CSV output

```
time,edge,vehicles,speed,waiting,halting,traveltime,congestion
100,N2C,8,11.42,2.00,1,22.34,0.1250
100,S2C,9,10.85,5.00,2,23.10,0.1680
100,E2C,26,3.15,92.00,18,79.36,0.6821
100,W2C,29,2.80,105.00,21,89.28,0.7430
```

---

## Chỉ số ùn tắc tổng hợp

Theo Báo cáo 2, Mục 10:

$$Congestion_{ij} = a \cdot N_{norm} + b \cdot H_{norm} + c \cdot W_{norm} + d \cdot \left(1 - \frac{V_{ij}}{V_{max}}\right)$$

Trọng số mặc định:

| Thành phần | Trọng số |
|---|---:|
| a (số xe) | 0.30 |
| b (xe dừng) | 0.30 |
| c (waiting time) | 0.20 |
| d (tốc độ) | 0.20 |

---

## Thiết kế thí nghiệm

| Kịch bản | Lưu lượng | Dự kiến trạng thái |
|---|---:|---|
| TH1 | 200 xe/h | Thông thoáng |
| TH2 | 400 xe/h | Tốt |
| TH3 | 600 xe/h | Trung bình |
| TH4 | 800 xe/h | Đông đúc |
| TH5 | 1000 xe/h | Ùn tắc |
| TH6 | 1200 xe/h | Ùn tắc nặng |

---

## Chu kỳ đèn tín hiệu

```
Phase 1: Bắc–Nam GREEN, Đông–Tây RED  → 30s
Phase 2: Bắc–Nam YELLOW               → 3s
Phase 3: Đông–Tây GREEN, Bắc–Nam RED → 30s
Phase 4: Đông–Tây YELLOW              → 3s
─────────────────────────────────────────────
Tổng chu kỳ: 66 giây
```

---

## ACO Routing Engine (Giai đoạn 3)

### Kiến trúc

```
SUMO → TraCI → TrafficGraph → ACO / Dijkstra / A* → Best Route → TraCI → SUMO Vehicle
```

### Scripts

| Script | Vai trò |
|---|---|
| `scripts/core/aco.py` | ACO core: TrafficGraph + AntColonyOptimizer |
| `scripts/core/routing.py` | Dijkstra (3 modes) + A* + so sánh |
| `scripts/grid/aco_runner.py` | Chạy ACO + SUMO, dynamic rerouting |
| `scripts/grid/compare_algorithms.py` | So sánh tất cả thuật toán trên mạng 3×3 |

### Chạy nhanh

```powershell
# Self-test (không cần SUMO)
python -m scripts.core.aco --test
python -m scripts.core.routing --test

# Chạy ACO trên SUMO
python -m scripts.grid.aco_runner --nogui --duration 600

# So sánh thuật toán
python -m scripts.grid.compare_algorithms --nogui --duration 600
```

### Hàm chi phí cạnh động

$$C_{ij}(t) = w_d \cdot D_{norm} + w_t \cdot T_{norm} + w_q \cdot Q_{norm} + w_w \cdot W_{norm}$$

### Heuristic ACO

$$\eta_{ij}(t) = \frac{1}{C_{ij}(t) + \varepsilon}$$

### Xác suất chọn cạnh

$$P_{ij}^{k} = \frac{\tau_{ij}^{\alpha} \cdot \eta_{ij}^{\beta}}{\sum_{l \in N_i^k} \tau_{il}^{\alpha} \cdot \eta_{il}^{\beta}}$$

Chi tiết: xem [Báo cáo 3](../BÁO%20CÁO%203%20–%20TÍCH%20HỢP%20GIẢI%20THUẬT%20ĐÀN%20KIẾN%20VÀO%20MÔ%20HÌNH%20MÔ%20PHỎNG%20SUMO.md)

---

## ACO trên bản đồ thực tế – OSM (Giai đoạn 4)

### Mục tiêu

Chạy ACO trên bản đồ thực (OpenStreetMap) với hàng trăm nút giao,
thay vì mạng 3×3 nhân tạo, để đánh giá scalability.

### Mạng đường map2

- **Nguồn**: OpenStreetMap (Hà Nội)
- **Quy mô**: ~619 nút giao, ~1163 cạnh (gấp ~69× so với mạng 3×3)
- **20 nút giao** có đèn tín hiệu
- Bounding box: `105.80°–105.85°E, 20.96°–21.05°N`

### Scripts

| Script | Vai trò |
|---|---|
| `scripts/core/osm_graph.py` | OSMTrafficGraph: parse net.xml, ACO + Dijkstra cho mạng OSM |
| `scripts/osm/osm_runner.py` | Chạy so sánh + dynamic rerouting trên bản đồ OSM |
| `scripts/osm/osm_setup.py` | Tiện ích tải và cấu hình OSM |

### ACO cải tiến cho mạng lớn

Trên mạng thực (600+ nút), ACO cơ bản không hoạt động vì kiến bị lạc.
Các cải tiến:

1. **Directional heuristic (γ)** – Thêm thành phần hướng đích:

$$P_{ij}^{k} = \frac{\tau_{ij}^{\alpha} \cdot \eta_{ij}^{\beta} \cdot \delta_{ij}^{\gamma}}{\sum_{l \in N_i^k} \tau_{il}^{\alpha} \cdot \eta_{il}^{\beta} \cdot \delta_{il}^{\gamma}}$$

Trong đó $\delta_{ij} = \frac{1}{dist(j, dest) + \varepsilon}$

2. **Dijkstra seed** – Khởi tạo pheromone từ đường Dijkstra, kiến có "bản đồ sơ bộ"

3. **Dead-end avoidance** – Ưu tiên nút có nhiều kết nối, tránh ngõ cụt

### Chạy nhanh

```powershell
# Self-test (không cần SUMO)
python -m scripts.core.osm_graph --test

# Xem thông tin mạng
python -m scripts.core.osm_graph --info

# So sánh thuật toán trên map OSM
python -m scripts.osm.osm_runner --nogui --mode compare --duration 600

# Dynamic rerouting ACO trên map OSM
python -m scripts.osm.osm_runner --nogui --mode reroute --duration 600

# Tùy chỉnh ACO
python -m scripts.osm.osm_runner --nogui --mode compare --n-ants 50 --iterations 100
```
