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
├── network/
│   ├── nodes.nod.xml          # 5 node: N, S, E, W, C
│   ├── edges.edg.xml          # 8 edges hai chiều
│   └── intersection.net.xml   # BUILD bằng build_network.py
│
├── routes/
│   ├── routes_TH1.rou.xml     # 200  xe/h/hướng
│   ├── routes_TH2.rou.xml     # 400  xe/h/hướng
│   ├── routes_TH3.rou.xml     # 600  xe/h/hướng
│   ├── routes_TH4.rou.xml     # 800  xe/h/hướng
│   ├── routes_TH5.rou.xml     # 1000 xe/h/hướng
│   └── routes_TH6.rou.xml     # 1200 xe/h/hướng
│
├── output/                    # Được tạo khi chạy
│   ├── traffic_TH1.csv        # Dữ liệu TraCI theo thời gian
│   ├── tripinfo_TH1.xml       # SUMO TripInfo output
│   ├── comparison.csv         # Bảng so sánh 6 kịch bản
│   └── analysis_results.csv   # Kết quả phân tích tổng hợp
│
├── scripts/
│   ├── build_network.py       # Build intersection.net.xml
│   ├── monitor.py             # TraCI data collector
│   ├── run_experiments.py     # Chạy batch 6 thí nghiệm
│   └── analyze.py             # Phân tích kết quả
│
└── intersection.sumocfg       # Cấu hình SUMO chính
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
cd d:\study\DATN\traffic-simulation
python scripts/build_network.py
```

### Bước 2: Chạy một kịch bản (có GUI)

```powershell
python scripts/monitor.py --scenario TH3
```

### Bước 3: Chạy một kịch bản (không GUI, nhanh hơn)

```powershell
python scripts/monitor.py --scenario TH3 --nogui
```

### Bước 4: Chạy tất cả 6 thí nghiệm

```powershell
python scripts/run_experiments.py
```

Chạy một số kịch bản nhất định:

```powershell
python scripts/run_experiments.py --scenarios TH3 TH4 TH5
```

### Bước 5: Phân tích kết quả

```powershell
python scripts/analyze.py

# Kèm biểu đồ (cần matplotlib):
pip install matplotlib
python scripts/analyze.py --plot
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

### Scripts mới

| Script | Vai trò |
|---|---|
| `scripts/aco.py` | ACO core: TrafficGraph + AntColonyOptimizer |
| `scripts/routing.py` | Dijkstra (3 modes) + A* + so sánh |
| `scripts/aco_runner.py` | Chạy ACO + SUMO, dynamic rerouting |
| `scripts/compare_algorithms.py` | So sánh tất cả thuật toán |

### Chạy nhanh

```powershell
# Self-test (không cần SUMO)
python scripts/aco.py --test
python scripts/routing.py --test

# Chạy ACO trên SUMO
python scripts/aco_runner.py --nogui --duration 600

# So sánh thuật toán
python scripts/compare_algorithms.py --nogui --duration 600
```

### Hàm chi phí cạnh động

$$C_{ij}(t) = w_d \cdot D_{norm} + w_t \cdot T_{norm} + w_q \cdot Q_{norm} + w_w \cdot W_{norm}$$

### Heuristic ACO

$$\eta_{ij}(t) = \frac{1}{C_{ij}(t) + \varepsilon}$$

### Xác suất chọn cạnh

$$P_{ij}^{k} = \frac{\tau_{ij}^{\alpha} \cdot \eta_{ij}^{\beta}}{\sum_{l \in N_i^k} \tau_{il}^{\alpha} \cdot \eta_{il}^{\beta}}$$

Chi tiết: xem [Báo cáo 3](../BÁO%20CÁO%203%20–%20TÍCH%20HỢP%20GIẢI%20THUẬT%20ĐÀN%20KIẾN%20VÀO%20MÔ%20HÌNH%20MÔ%20PHỎNG%20SUMO.md)
