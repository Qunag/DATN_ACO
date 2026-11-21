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
    │   ├── fleet.py                 # Phân luồng các xe do SUMO sinh
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
| `scripts/osm/osm_runner.py` | Chạy so sánh, tái định tuyến hoặc điều phối toàn bộ xe trên bản đồ OSM |
| `scripts/osm/fleet.py` | Tìm tuyến hợp lệ, đo hàng đợi và phân luồng từng xe |
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

### Phân luồng toàn bộ xe trên bản đồ OSM

Chạy các lệnh sau trong thư mục `traffic-simulation`. Chế độ `fleet` xét từng xe do SUMO sinh ngay khi xuất phát. Mỗi xe giữ điểm đi, điểm đến và các điểm dừng bắt buộc của chuyến đó. Xe chạy theo tuyến dịch vụ cố định giữ nguyên hành trình.

```powershell
# Mở map2 bằng SUMO-GUI và điều phối toàn bộ nhu cầu
python -m scripts.osm.osm_runner --mode fleet

# Chạy năm phương án trên cùng nhu cầu và cùng hạt giống đến khi hết xe
python -m scripts.osm.osm_runner --mode fleet --nogui --policy compare --seed 51

# Tìm và phân bổ tuyến theo tình trạng hiện tại của toàn mạng
python -m scripts.osm.osm_runner --mode fleet --nogui --policy adaptive --seed 61

# Dùng mạng, các tuyến và luồng xe của một cấu hình SUMO khác
python -m scripts.osm.osm_runner --mode fleet --nogui --cfg duong-dan/ban-do.sumocfg

# Tai nạn ngẫu nhiên trên Bologna, đối chứng cùng vị trí cho cả năm chính sách
python -m scripts.osm.osm_runner --mode fleet --nogui --cfg scenarios/sumo-scenarios/bologna/acosta/run.sumocfg --policy compare --incident --seed 51 --output-dir output/bologna/incident

# Tai nạn nối tiếp, nhiều mức độ trong vùng trung tâm Bologna, nhu cầu xe tăng 1,5 lần
python -m scripts.osm.osm_runner --mode fleet --cfg scenarios/sumo-scenarios/bologna/acosta/run.sumocfg --policy adaptive --demand-scale 1.5 --incident-dynamic --incident-area 300 200 1500 1150 --incident-count 5 --seed 51 --gui-delay 5 --pause-at 3400 --output-dir output/bologna/regional-incident/gui

# Cùng lịch tai nạn trong vùng, giảm về 8.779 xe với hạt giống 51
python -B -m scripts.osm.osm_runner --mode fleet --cfg scenarios/sumo-scenarios/bologna/acosta/run.sumocfg --policy adaptive --demand-scale 1 --incident-dynamic --incident-area 300 200 1500 1150 --incident-count 5 --seed 51 --gui-delay 5 --pause-at 3400 --output-dir output/bologna/regional-incident-reduced/gui
```

ACO tìm một tuyến thay thế trên các đoạn và lượt rẽ hợp lệ cho loại xe. Hệ thống dùng Dijkstra để dựng các đường rẽ khác từ hành trình ban đầu và cho 4 kiến tìm đường trong 3 vòng trên tối đa 3 hành lang. Mỗi đường đề xuất có thời gian thông thoáng tối đa bằng 130% thời gian của tuyến gốc cộng 15 giây. Khi chỉ có một tuyến phù hợp, xe tiếp tục theo tuyến SUMO đã cấp. Mỗi xe nhận một quyết định lúc xuất phát. Số liệu giao thông tiếp tục cập nhật cho các xe đến sau.

| Phương án | Cách chọn khi có hai tuyến |
|---|---|
| `original` | Giữ tuyến gốc của từng xe trong SUMO. |
| `equal` | Mỗi tuyến có xác suất 50%. |
| `previous` | Ưu tiên tuyến có thời gian ước tính thấp hơn, cộng 2 giây cho mỗi xe sắp đến cùng lối vào đèn. |
| `queue` | Tính thời gian giải tỏa từ số xe đang chờ, số xe sắp đến và lượng xe thực tế qua lối vào trong từng chu kỳ đèn. |
| `adaptive` (mặc định) | Tìm lại đường vòng bằng chi phí từng lượt rẽ trên toàn mạng. Xác suất đổi tuyến tăng khi lợi ích dự kiến vượt cả 15 giây và 10% chi phí tuyến gốc. |

Các đoạn đường đều dùng tốc độ quan sát trong SUMO để ước tính thời gian. Ở lối vào có đèn, `queue` lấy giá trị lớn hơn giữa thời gian theo tốc độ và thời gian thông thoáng cộng thời gian giải tỏa, tránh tính trùng thời gian chờ. Khi xe chưa đến, hệ thống dự báo tải cho 120 giây tiếp theo, gộp các xe có giờ đến chênh tối đa 30 giây. Mức khởi đầu là 0,25 xe/giây cho mỗi làn được đèn điều khiển. Sau mỗi chu kỳ hoàn chỉnh có hàng đợi, hệ thống cập nhật mức này bằng trung bình của mức trước và lưu lượng thoát đo được.

Với `adaptive`, khi có xe xuất phát, hệ thống lấy tốc độ và số xe đứng chờ trên toàn mạng qua TraCI, tối đa một lần mỗi 30 giây. Nó làm trơn độ trễ với hằng số thời gian 60 giây và xét số làn phục vụ từng lượt rẽ. Sau mỗi quyết định, tuyến thực tế được ghi vào cửa sổ 120 giây để các xe tiếp theo tính đến tải mới. Khi lợi ích vượt ngưỡng, bộ điều phối tăng dần xác suất chuyển hướng nhưng giữ xác suất dưới 85%. Các ngưỡng và thời gian chờ tại lượt rẽ là giả thiết mô phỏng cần hiệu chỉnh khi dùng cho mạng khác.

Thêm `--incident` để mô phỏng tác động của một tai nạn bằng cách giảm giới hạn tốc độ trên toàn bộ các làn của một đoạn đường một chiều. Đoạn đường được chọn ngẫu nhiên trong các đoạn dài ít nhất 50 m, cho phép ô tô con và có đường vào/ra. Cùng mạng và `--seed` sẽ chọn cùng vị trí cho mọi chính sách. Mặc định sự cố xảy ra tại giây 900, kéo dài 900 giây và giới hạn tốc độ còn 20% ban đầu. Các tham số `--incident-start`, `--incident-duration`, `--incident-speed-factor` cho phép đổi ba giá trị này. Khi hết thời gian, mỗi làn được phục hồi đúng giới hạn tốc độ trước sự cố. Để xem cả quá trình bắt đầu và phục hồi trong lượt thử ngắn, dùng `--duration 2100`.

Các lượt có sự cố ghi thêm `incidents.csv` trong thư mục chính sách. Tệp ghi thời điểm thực tế, đoạn đường, làn và giới hạn tốc độ trước/sau mỗi lần áp dụng hoặc phục hồi, đơn vị m/s. `summary.csv` có thêm vị trí, lịch sự cố, tỷ lệ tốc độ và `incident_applied` cho biết sự cố đã thực sự được áp dụng. `adaptive` tiếp nhận ảnh hưởng thông qua tốc độ và hàng đợi quan sát được rồi gợi ý tuyến cho các xe xuất phát tiếp theo.

`--incident-count` đặt số đoạn tai nạn cố định, mặc định 1. `--demand-scale` nhân số xe trong cùng khoảng thời gian xuất phát, mặc định 1. Trong SUMO-GUI, các đoạn tai nạn có ghim màu và các xe thực sự đổi tuyến chuyển sang màu xanh ngọc. `--gui-delay` đặt độ trễ hiển thị theo mili giây giữa hai bước mô phỏng. `--pause-at` cho phép dừng tại một giây cụ thể để quan sát, nhấn nút chạy để tiếp tục.

`--incident-dynamic` phát sinh các tai nạn nối tiếp với mức độ riêng. Mặc định, hệ thống thử tạo sự cố cách nhau ngẫu nhiên 120–300 giây, từ giây 900 đến trước giây 3.600. Trong chế độ này, `--incident-duration` là khoảng thời gian phát sinh sự cố và `--incident-count` là số tai nạn tối đa đồng thời, mặc định 5. Mỗi sự cố tiếp tục tồn tại đến giờ phục hồi riêng, kể cả khi đã hết khoảng thời gian phát sinh. Khi đủ số lượng tối đa, hệ thống chờ lượt tạo tiếp theo. Đoạn đang có tai nạn được loại khỏi danh sách chọn cho đến khi phục hồi.

| Mức độ | Tốc độ giới hạn còn lại | Thời gian ảnh hưởng | Màu SUMO-GUI |
|---|---:|---:|---|
| Nhẹ | 70% | 5 phút | Vàng |
| Vừa | 40% | 10 phút | Cam |
| Nặng | 20% | 20 phút | Đỏ |
| Rất nặng | 10% | 30 phút | Đỏ sẫm |

Các mức độ được lấy mẫu với trọng số tương ứng 4, 3, 2, 1. Đây là giả định thí nghiệm. `--incident-speed-factor` dùng cho sự cố cố định. Trong chế độ động, tỷ lệ tốc độ và thời gian phục hồi lấy từ bảng mức độ.

`--incident-area XMIN YMIN XMAX YMAX` giới hạn vị trí trong vùng chữ nhật, dùng tọa độ SUMO địa phương tính bằng mét. Ví dụ Bologna `300 200 1500 1150` nằm trong mạng có giới hạn xấp xỉ `0 0 1817.58 1350.19`. Toàn bộ đường hình học của đoạn được chọn phải nằm trong vùng. Chế độ động hiển thị đường viền vùng màu xanh trên SUMO-GUI. Nếu bỏ tham số vùng, chế độ động dùng giới hạn toàn mạng.

Lịch `incident-plan.csv` được tạo trước mô phỏng, gồm mã sự cố, đoạn đường, thời điểm bắt đầu/kết thúc, mức độ và tỷ lệ tốc độ. Cùng mạng, vùng, tham số và hạt giống tạo cùng lịch cho mọi chính sách, độc lập với quyết định phân luồng. Với chế độ động, `incidents.csv` ghi thêm các thông tin kế hoạch bên cạnh thời điểm thực sự áp dụng/phục hồi. `incident_count` trong bảng tổng hợp là tổng số sự cố đã lên lịch, `incident_applied_count` là số đã bắt đầu và `incident_max_active` là giới hạn đồng thời.

Mỗi lượt tạo thư mục riêng trong `output/fleet`. Trong `summary.csv`, `loaded` và `considered` lần lượt đếm xe SUMO nạp và xe được xét. `finished_in_sumo` đếm chuyến kết thúc tại cạnh đích, gồm xe tới bình thường (`arrived`) và xe kết thúc bằng dịch chuyển (`ended_by_teleport`). `arrived_without_teleport` đếm các xe về đích mà suốt hành trình không bị dịch chuyển. `total_s` tính từ giờ xuất phát theo lịch đến lúc mô phỏng ghi nhận kết thúc, kể cả chờ vào mạng. Chỉ số này được ghi khi `complete=True`. Với các lượt có dịch chuyển, cần đọc nó cùng số chuyến bị ảnh hưởng.

Trong từng thư mục phương án, `decisions.csv` ghi quyết định cho từng xe, `cycles.csv` ghi hàng đợi và số xe qua đèn, `teleports.csv` ghi mã xe và thời điểm bắt đầu dịch chuyển, `tripinfo.xml.gz` chứa số liệu chuyến đi gốc của SUMO. Các tệp xuất khác mà bản đồ đã cấu hình có tiền tố riêng cho từng lượt. Để kiểm tra nhanh có thể đặt `--duration 120`. Khi dừng sớm, `requested` đếm các bản ghi chuyến SUMO đã xuất tại thời điểm dừng và `loaded` có thể lớn hơn. Các lượt đối chứng dùng cùng nhu cầu, cùng hạt giống và cùng thiết lập dịch chuyển của cấu hình bản đồ.

Trong thử nghiệm ban đầu với 10.000 xe trên `map2`, giữ tuyến gốc nhanh nhất trong bốn phương án `original`, `equal`, `previous` và `queue` ở cả hai hạt giống 51 và 52. [Báo cáo thử nghiệm ban đầu](output/fleet/map2/ket-qua.md)

Ở hai hạt giống mới 61 và 62, `adaptive` giảm thời gian trung bình từ **105,5 xuống 78,2 phút/xe** so với giữ tuyến SUMO, tương đương **25,9%** tổng thời gian. Mỗi lượt có thêm 839 đến 1.060 xe tới đích mà SUMO không phải dịch chuyển. Dữ liệu thử gồm 10.000 ô tô con và mỗi lượt chạy đến khi hết xe. [Kết quả từng hạt giống và nhật ký đối chứng](output/fleet/map2-performance/ket-qua.md)

Đã chạy thêm sáu lượt có tai nạn trên Bologna, mỗi lượt đủ 8.779 xe. Với ba vị trí ngẫu nhiên ở hạt giống 51, 52, 53, `adaptive` giảm **6,78%** tổng thời gian so với giữ tuyến gốc dưới cùng sự cố. Tất cả xe trong sáu lượt đều tự về đích, chỉ số dịch chuyển và va chạm bằng 0. [Báo cáo tai nạn và cách chạy lại](output/bologna/incident/ket-qua.md)

Với chế độ động trong vùng trung tâm và nhu cầu 1,5 lần, hạt giống 51 tạo 13 tai nạn nhiều mức độ, tối đa 5 đồng thời. Hai lượt đều hoàn thành đủ 13.169 xe. Trong phép thử này, `adaptive` có tổng thời gian cao hơn giữ tuyến **9,41%**, với 66 so với 8 xe bị dịch chuyển. [Lịch sự cố, kết quả đối chứng và lệnh mở SUMO-GUI](output/bologna/regional-incident/ket-qua.md)

Giảm về nhu cầu gốc 8.779 xe và giữ nguyên lịch tai nạn trên, `adaptive` giảm thời gian trung bình từ **7,73 xuống 7,02 phút/xe**, tương đương **9,12%** tổng thời gian. Hai lượt đều hoàn thành đủ xe; giữ tuyến gốc có 1 xe bị dịch chuyển, `adaptive` có 0. Kết quả phản ánh một hạt giống và một vùng. [So sánh hai mức nhu cầu và lệnh chạy lại](output/bologna/regional-incident/ket-qua.md#trường-hợp-giảm-số-xe)
