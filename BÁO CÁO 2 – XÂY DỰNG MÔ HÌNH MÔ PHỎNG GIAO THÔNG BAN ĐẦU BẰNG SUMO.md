# BÁO CÁO XÂY DỰNG MÔ HÌNH MÔ PHỎNG GIAO THÔNG BAN ĐẦU BẰNG SUMO

## 1. Mục đích

Trước khi xây dựng giải thuật ACO, cần có một môi trường có khả năng mô phỏng phương tiện và tạo ra dữ liệu giao thông.

Đề tài lựa chọn **SUMO – Simulation of Urban MObility** làm môi trường thực nghiệm.

SUMO là trình mô phỏng giao thông vi mô, mô phỏng phương tiện riêng lẻ trên mạng đường và cung cấp giao diện TraCI để chương trình bên ngoài đọc trạng thái cũng như tác động vào simulation.

Giai đoạn đầu chưa tập trung vào tìm đường bằng ACO mà nhằm trả lời các câu hỏi:

- Một nút giao được biểu diễn trong SUMO như thế nào?
- Phương tiện được sinh ra như thế nào?
- Đèn tín hiệu ảnh hưởng đến dòng xe như thế nào?
- Làm thế nào xác định một đoạn đường đang đông hoặc ùn tắc?
- Những dữ liệu nào cần cung cấp cho ACO?

---

## 2. Phạm vi mô phỏng ban đầu

Không sử dụng ngay bản đồ thực tế lớn.

Mô hình đầu tiên sử dụng **một nút giao bốn hướng có đèn tín hiệu**.

```text
                   NORTH
                     │
                     │
                     ↓
                     │
                     │
WEST ───────────── JUNCTION ──────────── EAST
                     │
                     │
                     ↑
                     │
                   SOUTH
```

Các hướng lưu thông:

```text
North → South

South → North

East → West

West → East
```

Mô hình này đủ đơn giản để kiểm soát toàn bộ tham số nhưng vẫn tạo được:

- Hàng đợi.
- Thời gian chờ.
- Xung đột dòng xe.
- Ảnh hưởng của chu kỳ đèn.
- Trạng thái ùn tắc.

---

## 3. Thành phần của mô hình

### 3.1. Node

Các node:

```text
N
S
E
W
C
```

Trong đó `C` là nút giao có traffic light.

---

### 3.2. Edge

Mỗi hướng cần hai cạnh.

Ví dụ:

```text
N2C
C2N

S2C
C2S

E2C
C2E

W2C
C2W
```

Tổng cộng:

```text
8 edges
```

Các cạnh có thể chứa thông tin:

- Chiều dài.
- Số làn.
- Tốc độ tối đa.
- Loại phương tiện được phép đi.

---

## 4. Sinh phương tiện

Trong giai đoạn đầu có thể sử dụng cùng một loại xe:

```text
Passenger Car
```

Tốc độ tối đa ví dụ:

```text
13.89 m/s ≈ 50 km/h
```

Các luồng xe được tạo theo bốn hướng.

Ví dụ:

```text
North → South = 600 xe/h

South → North = 600 xe/h

East → West = 600 xe/h

West → East = 600 xe/h
```

Sau khi mô hình chạy ổn định, lưu lượng được thay đổi để tạo các trường hợp ùn tắc.

---

## 5. Thiết kế thí nghiệm lưu lượng

Thử lần lượt:

| Thí nghiệm | Lưu lượng mỗi hướng |
|---|---:|
| TH1 | 200 xe/h |
| TH2 | 400 xe/h |
| TH3 | 600 xe/h |
| TH4 | 800 xe/h |
| TH5 | 1000 xe/h |
| TH6 | 1200 xe/h |

Không đặt trước một ngưỡng nào là “chắc chắn tắc”; mục tiêu của thí nghiệm là quan sát tại cấu hình mạng và chu kỳ đèn cụ thể khi nào các chỉ số suy giảm rõ rệt.

---

## 6. Điều khiển đèn giao thông

Trong bước đầu sử dụng đèn cố định.

Ví dụ:

```text
Phase 1

Bắc – Nam : GREEN
Đông – Tây: RED

30 giây
```

Sau đó:

```text
Phase 2

Bắc – Nam : YELLOW

3 giây
```

Tiếp theo:

```text
Phase 3

Đông – Tây: GREEN
Bắc – Nam : RED

30 giây
```

Và:

```text
Phase 4

Đông – Tây: YELLOW

3 giây
```

SUMO hỗ trợ các chương trình traffic light theo phase và cho phép một controller quản lý một hoặc nhiều nút giao.

Ở giai đoạn này:

> Thời gian đèn chưa được tối ưu.

Mục tiêu chỉ là tạo ra môi trường để quan sát dòng xe.

---

## 7. Giao tiếp giữa chương trình và SUMO

Sử dụng:

# TraCI – Traffic Control Interface

Kiến trúc:

```text
Python
   │
   │ TraCI
   ▼
SUMO
```

TraCI hoạt động theo mô hình client/server, cho phép một chương trình bên ngoài điều khiển simulation đang chạy.

Trong mỗi bước mô phỏng:

```text
Python
   ↓

simulationStep()

   ↓

SUMO chạy thêm một bước

   ↓

Python đọc trạng thái
```

---

## 8. Dữ liệu cần thu thập

Đây là mục quan trọng nhất của giai đoạn SUMO.

### 8.1. Số phương tiện trên đoạn đường

```python
traci.edge.getLastStepVehicleNumber(edge)
```

Ký hiệu:

\[
N_{ij}(t)
\]

---

### 8.2. Tốc độ trung bình

```python
traci.edge.getLastStepMeanSpeed(edge)
```

Ký hiệu:

\[
V_{ij}(t)
\]

---

### 8.3. Số phương tiện đang dừng

```python
traci.edge.getLastStepHaltingNumber(edge)
```

Ký hiệu:

\[
H_{ij}(t)
\]

SUMO coi phương tiện có tốc độ dưới `0.1 m/s` là phương tiện đang halt đối với chỉ số này.

---

### 8.4. Waiting time

```python
traci.edge.getWaitingTime(edge)
```

Ký hiệu:

\[
W_{ij}(t)
\]

---

### 8.5. Travel time

```python
traci.edge.getTraveltime(edge)
```

Ký hiệu:

\[
T_{ij}(t)
\]

TraCI Edge API cung cấp trực tiếp các đại lượng trên trong quá trình mô phỏng.

---

## 9. Dữ liệu thu được

Ví dụ chương trình có thể ghi:

```text
TIME = 100 s

N2C
Vehicle count = 8
Mean speed    = 11.42 m/s
Waiting       = 2 s
Halting       = 1

S2C
Vehicle count = 9
Mean speed    = 10.85 m/s
Waiting       = 5 s
Halting       = 2

E2C
Vehicle count = 26
Mean speed    = 3.15 m/s
Waiting       = 92 s
Halting       = 18

W2C
Vehicle count = 29
Mean speed    = 2.80 m/s
Waiting       = 105 s
Halting       = 21
```

Từ dữ liệu giả định trên có thể nhận thấy hướng Đông–Tây đang có trạng thái xấu hơn Bắc–Nam.

Giai đoạn tiếp theo sẽ xây dựng công thức định lượng mức độ ùn tắc thay vì chỉ nhận xét bằng mắt.

---

## 10. Xây dựng chỉ số ùn tắc sơ bộ

Có thể nghiên cứu một chỉ số:

\[
Congestion_{ij}
=
aN_{ij}
+
bH_{ij}
+
cW_{ij}
+
d\left(1-\frac{V_{ij}}{V_{max}}\right)
\]

Trong đó:

- \(N\): số xe.
- \(H\): số xe đang dừng.
- \(W\): waiting time.
- \(V\): tốc độ trung bình.
- \(V_{max}\): tốc độ thiết kế của đường.

Các giá trị cần được chuẩn hóa trước khi kết hợp.

Ở giai đoạn đầu, công thức này chỉ dùng để thử nghiệm. Các trọng số sẽ được hiệu chỉnh sau dựa trên kết quả mô phỏng.

---

## 11. Kết quả đánh giá cuối simulation

SUMO có thể xuất:

```text
tripinfo.xml
```

Trong đó có các chỉ số như:

- `duration`.
- `routeLength`.
- `waitingTime`.
- `waitingCount`.
- `timeLoss`.
- `rerouteNo`.

Các trường này được SUMO định nghĩa trong TripInfo output và phù hợp để tổng hợp kết quả sau từng lần thực nghiệm.

---

## 12. Quy trình thực nghiệm

```text
START
  │
  ▼
Khởi tạo SUMO
  │
  ▼
Tạo phương tiện
  │
  ▼
Chạy simulation
  │
  ▼
Đọc dữ liệu bằng TraCI
  │
  ├── Vehicle Count
  ├── Mean Speed
  ├── Halting Number
  ├── Waiting Time
  └── Travel Time
  │
  ▼
Lưu CSV / Database
  │
  ▼
Simulation kết thúc
  │
  ▼
Đọc tripinfo.xml
  │
  ▼
Phân tích kết quả
  │
  ▼
END
```

---

## 13. File của project bước đầu

```text
traffic-simulation/
│
├── network/
│   ├── nodes.nod.xml
│   ├── edges.edg.xml
│   └── intersection.net.xml
│
├── routes/
│   └── routes.rou.xml
│
├── output/
│   ├── traffic.csv
│   └── tripinfo.xml
│
├── scripts/
│   └── monitor.py
│
└── intersection.sumocfg
```

---

## 14. Tiêu chí hoàn thành giai đoạn 1

Giai đoạn đầu được xem là hoàn thành khi đáp ứng được:

### Tiêu chí 1

SUMO GUI mô phỏng được ngã tư bốn hướng.

### Tiêu chí 2

Xe có thể:

```text
N → S
S → N
E → W
W → E
```

### Tiêu chí 3

Đèn tín hiệu hoạt động đúng, các luồng xung đột không được phép cùng đi khi chúng có tín hiệu đối nghịch.

### Tiêu chí 4

Python kết nối được SUMO bằng TraCI.

### Tiêu chí 5

Đọc được:

```text
vehicleCount
meanSpeed
waitingTime
haltingNumber
travelTime
```

### Tiêu chí 6

Lưu dữ liệu theo thời gian:

```text
time,edge,vehicles,speed,waiting,halting
```

Ví dụ:

```text
100,N2C,8,11.42,2,1
100,S2C,9,10.85,5,2
100,E2C,26,3.15,92,18
100,W2C,29,2.80,105,21
```

### Tiêu chí 7

Chứng minh được khi tăng traffic demand thì các chỉ số như waiting time, halting hoặc timeLoss có thể được theo dõi và so sánh giữa các kịch bản.

---

## 15. Giai đoạn tiếp theo

Sau khi hoàn thành một ngã tư, chuyển sang mạng:

```text
A ───── B ───── C
│       │       │
│       │       │
D ───── E ───── F
│       │       │
│       │       │
G ───── H ───── I
```

Mạng gồm 9 nút giao tạo ra nhiều tuyến từ A đến I.

Ví dụ:

```text
A → B → C → F → I

A → B → E → F → I

A → D → E → H → I

A → D → G → H → I
```

Đây là thời điểm phù hợp để đưa các giải thuật:

```text
Dijkstra

A*

ACO

Traffic-Aware ACO
```

vào cùng một môi trường và bắt đầu so sánh.

---

## 16. Giai đoạn bản đồ thực tế

Sau khi mô hình nhân tạo hoạt động ổn định, có thể chuyển sang OpenStreetMap.

SUMO cung cấp **OSM Web Wizard**, cho phép chọn một vùng trên bản đồ, xây dựng mạng SUMO từ dữ liệu OSM và có tùy chọn sinh nhu cầu giao thông để nhanh chóng tạo scenario.

Có thể lựa chọn một khu vực nhỏ như:

```text
một phần Hà Đông
```

thay vì sử dụng toàn thành phố ngay từ đầu.

---

## 17. Quan hệ giữa bước mô phỏng và ACO

Giai đoạn SUMO không tách rời thuật toán.

Những dữ liệu thu được:

```text
distance
vehicleCount
speed
waitingTime
travelTime
haltingNumber
```

sẽ được chuyển thành:

\[
C_{ij}(t)
\]

Sau đó ACO sử dụng:

\[
\eta_{ij}(t)
=
\frac{1}{C_{ij}(t)+\varepsilon}
\]

Chuỗi xử lý cuối cùng:

```text
SUMO
   ↓
TraCI
   ↓
Traffic Data
   ↓
Edge Cost
   ↓
ACO
   ↓
Best Route
   ↓
TraCI
   ↓
SUMO Vehicle
```

TraCI cho phép gán danh sách edge mới cho phương tiện bằng `setRoute`, tạo nền tảng cho cơ chế rerouting trong các giai đoạn tiếp theo.

---

## 18. Kết luận

Giai đoạn SUMO đầu tiên chưa nhằm giải quyết toàn bộ bài toán điều hướng.

Mục tiêu của giai đoạn này là xây dựng được một **môi trường thực nghiệm có thể kiểm soát và đo lường được**.

Kết quả quan trọng nhất không phải giao diện mô phỏng mà là luồng dữ liệu:

```text
Road
 ↓
Vehicle
 ↓
Traffic condition
 ↓
TraCI
 ↓
Data
```

Khi dữ liệu này được thu thập ổn định, bước tiếp theo mới là:

```text
Data
 ↓
Dynamic Graph
 ↓
Dijkstra / A* / ACO
 ↓
Routing
```

Do đó, mô hình một ngã tư bốn hướng chính là bước nền tảng trước khi nghiên cứu ACO trong mạng giao thông lớn hơn.