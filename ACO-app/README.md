# ACO-app: Ứng Dụng Điều Hướng Giao Thông Thông Minh (ITS) – Thuật Toán T-ACO & Google Maps

> **Đề tài Đồ án Tốt nghiệp:** Nghiên cứu và ứng dụng giải thuật Tối ưu hóa Đàn kiến (T-ACO) trong điều hướng giao thông đô thị thích nghi, tích hợp mô phỏng vi mô SUMO và nền tảng di động Flutter.

Ứng dụng di động **ACO-app** (hỗ trợ Android, iOS, Web, Windows Desktop) cung cấp trải nghiệm điều hướng thời gian thực theo phong cách Google Maps, trực quan hóa khả năng tự thích ứng và phân luồng xác suất của thuật toán **T-ACO (Traffic Ant Colony Optimization)** khi xảy ra ùn tắc hoặc tai nạn đột xuất trên mạng lưới giao thông thực tế tại Hà Nội (hành lang: **Ngã Tư Sở ↔ Đại học Bách Khoa**).

---

## 🌟 1. CÁC TÍNH NĂNG CHÍNH

### 🗺️ Giao diện Bản đồ Google Maps & Đa lộ trình Thực tế
- Sử dụng trực tiếp nền bản đồ Google Maps sắc nét, hỗ trợ đầy đủ các thao tác vuốt, xoay, zoom và định vị.
- **Top-3 Tuyến đường song song (Stochastic Multi-path):** Hiển thị đồng thời 3 phương án di chuyển (Tuyến chính xanh đậm, 2 tuyến phụ xám) kèm theo bóng thời gian (Floating Badge) và tỷ lệ phần trăm phân luồng theo phân phối Boltzmann nhằm tránh *Nghịch lý Braess*.

### 💥 Cắm / Đổi Điểm Tai Nạn & Ùn Tắc Trực Quan (Interactive Accident Injection)
- **Chạm tự do trên bản đồ:** Bấm `Cắm Tai Nạn` (hoặc nút nổi `💥` góc phải) và chạm vào bất kỳ tuyến phố nào trên bản đồ để tạo điểm tai nạn kèm vòng tròn đỏ phát sáng 180m.
- **Menu điểm ùn tắc trọng điểm Hà Nội:** Chọn nhanh các nút giao kinh điển:
  - *Ngã tư Trường Chinh – Tôn Thất Tùng* (Điểm nghẽn trọng yếu).
  - *Nút giao Ngã Tư Sở – Nguyễn Trãi* (Cửa ngõ Tây Nam).
  - *Nút giao Đại La – Giải Phóng* (Khu vực tiếp cận ĐH Bách Khoa).
  - *Tuyến phố Chùa Bộc – Phạm Ngọc Thạch* (Nhánh phân luồng phía Bắc).
- Chạm trực tiếp vào biểu tượng `💥 TAI NẠN` trên bản đồ để di chuyển, đổi vị trí hoặc bấm `Xóa Tai Nạn` để khôi phục thông thoáng.

### 🏎️ Mô Phỏng Xe Chạy Thực Tế (Dijkstra vs T-ACO)
- Bấm nút **`🏎️ Mô Phỏng Xe`** để xem 2 ô tô đua thực nghiệm trực tiếp trên bản đồ:
  - 🚗 **Xe Dijkstra (Thuật toán truyền thống):** Cố chấp đi theo lộ trình ngắn nhất cố định. Khi gặp khu vực tai nạn, xe bị kẹt cứng (vận tốc tụt xuống 2 km/h, trễ kéo dài).
  - 🏎️ **Xe T-ACO (Thuật toán đề xuất):** Nhờ cơ chế bốc hơi và cập nhật pheromone động, xe tự động rẽ sang lộ trình nhánh thông thoáng (duy trì 38–40 km/h) và về đích nhanh hơn rõ rệt.

### 📊 Bảng So Sánh Hiệu Quả Thuật Toán (HUD Comparison)
- Hiển thị song song các chỉ số định lượng: Thời gian di chuyển (phút), cự ly (km), trạng thái lưu thông, thời gian tiết kiệm được và % cải thiện hiệu năng của T-ACO so với Dijkstra.

### 🚦 Tích Hợp Kịch Bản Lưu Lượng SUMO & Chế Độ Phương Tiện
- Hỗ trợ 6 kịch bản mật độ giao thông vi mô SUMO: từ **TH1 (200 xe/h - Đêm vắng)** đến **TH6 (1200 xe/h - Kẹt cứng toàn diện)**.
- Chế độ di chuyển linh hoạt: **Ô tô**, **Xe máy**, **Đi bộ**.

---

## 🛠️ 2. KIẾN TRÚC HỆ THỐNG

```
┌────────────────────────────────────────────────────────┐
│             ACO-app (Flutter Mobile Client)            │
│  - Google Maps & OpenStreetMap Tile Rendering          │
│  - Top-3 Multi-path Polylines & Time Floating Badges   │
│  - Interactive Accident Markers & Animated Sim Cars    │
└───────────────────────────▲────────────────────────────┘
                            │ REST API (JSON)
                            │ Port: 8050
┌───────────────────────────▼────────────────────────────┐
│      ITS Backend Server (Python Flask & OSRM Engine)   │
│  - Point-to-Segment Geometric Accident Detection       │
│  - BPR (Bureau of Public Roads) Delay Function        │
│  - T-ACO Boltzmann Stochastic Distribution Routing     │
│  - Real-time Performance Metrics (Dijkstra vs T-ACO)   │
└────────────────────────────────────────────────────────┘
```

---

## 🚀 3. HƯỚNG DẪN CÀI ĐẶT & CHẠY ỨNG DỤNG

### Yêu Cầu Môi Trường (Prerequisites)
1. **Flutter SDK:** Phiên bản `>= 3.0.0` ([Hướng dẫn cài đặt Flutter](https://docs.flutter.dev/get-started/install)).
2. **Python:** Phiên bản `>= 3.8` ([Tải Python](https://www.python.org/downloads/)).
3. Điện thoại Android / iOS thật (hoặc Máy ảo Android Emulator / Chrome Browser).

---

### BƯỚC 1: Khởi Động Máy Chủ Backend (Python)

Mở cửa sổ Terminal thứ nhất tại thư mục dự án và chạy:

```bash
cd traffic-simulation
pip install flask flask-cors requests numpy
python scripts/run_its_backend_server.py --port 8050
```

> **Ghi chú:** Khi khởi động thành công, Backend sẽ báo:
> `* Running on all addresses (0.0.0.0)`
> `* Running on http://127.0.0.1:8050`
> Giữ cửa sổ này mở để phục vụ tính toán định tuyến cho ứng dụng.

---

### BƯỚC 2: Cài Đặt Thư Viện Cho App

Mở cửa sổ Terminal thứ hai, di chuyển vào thư mục `ACO-app`:

```bash
cd ACO-app
flutter pub get
```

---

### BƯỚC 3: Khởi Chạy Ứng Dụng Flutter

Bạn có thể chạy ứng dụng theo 1 trong các cách sau:

#### Cách 1: Chạy trên Điện Thoại Android Thật (Khuyên Dùng Nhất)
1. Bật chế độ **Gỡ lỗi USB (USB Debugging)** trên điện thoại và cắm cáp kết nối với máy tính.
2. Kiểm tra thiết bị đã nhận:
   ```bash
   flutter devices
   ```
3. Chạy lệnh:
   ```bash
   flutter run
   ```
4. **Cấu hình IP máy chủ:**
   - Đảm bảo điện thoại và máy tính kết nối **chung một mạng Wi-Fi**.
   - Mở app trên điện thoại, bấm vào biểu tượng **⚙️ Cài đặt** ở góc trên màn hình.
   - Nhập địa chỉ IP Wi-Fi của máy tính (ví dụ: `http://192.168.1.15:8050`) và nhấn **Lưu cấu hình**.

#### Cách 2: Chạy trên Trình Duyệt Web (Demo Nhanh Không Cần Điện Thoại)
```bash
flutter run -d chrome
```

#### Cách 3: Chạy Ứng Dụng Windows Desktop
```bash
flutter run -d windows
```

---

## 📁 4. CẤU TRÚC THƯ MỤC NGUỒN (`ACO-app`)

```
ACO-app/
├── lib/
│   ├── main.dart                      # Điểm khởi chạy ứng dụng (Entry point)
│   ├── models/
│   │   └── traffic_model.dart         # Data models (RouteOption, OptimizationComparison,...)
│   ├── services/
│   │   └── api_service.dart           # Giao tiếp HTTP REST API với Backend Python
│   ├── views/
│   │   └── map_screen.dart            # Màn hình chính Google Maps, cắm tai nạn, đua xe mô phỏng
│   └── widgets/
│       ├── transport_selector.dart    # Bộ chọn Ô tô / Xe máy / Đi bộ
│       ├── route_card_widget.dart     # Thẻ hiển thị lộ trình
│       └── ops_control_panel.dart     # Bảng điều khiển kịch bản
├── assets/                            # Hình ảnh, icons
├── pubspec.yaml                       # Khai báo thư viện phụ thuộc Flutter
└── README.md                          # Tài liệu hướng dẫn sử dụng
```

---

## 💡 5. HƯỚNG DẪN DEMO BẢO VỆ ĐỒ ÁN (SCENARIO WALKTHROUGH)

Khi trình bày với Hội đồng hoặc Thầy/Cô hướng dẫn:

1. **Khảo sát trạng thái bình thường:**
   - Mở app, hệ thống hiển thị 3 phương án đường từ *Ngã Tư Sở* đi *Bách Khoa*. Tuyến chính Trường Chinh chiếm tỷ lệ phân luồng cao nhất (~58%).
2. **Kích hoạt sự cố tai nạn:**
   - Nhấn nút **`💥 Cắm Tai Nạn`** (hoặc nút tròn `💥` góc phải) và chọn *Ngã tư Trường Chinh – Tôn Thất Tùng*.
   - Tuyến đường qua Trường Chinh lập tức đổi sang màu đỏ sẫm báo kẹt xe/tai nạn kèm nhãn `⚠️`.
   - Thuật toán T-ACO lập tức thích nghi: Phân luồng ưu tiên tự động chuyển sang tuyến đường vòng Chùa Bộc – Phạm Ngọc Thạch hoặc Định Công.
3. **Thực thi mô phỏng 2 xe chạy:**
   - Nhấn **`🏎️ Mô Phỏng Xe`**: Xe Dijkstra đi vào đường Trường Chinh bị khựng lại ở điểm tai nạn với vận tốc 2 km/h; Xe T-ACO rẽ đường khác với tốc độ 40 km/h và cán đích sớm hơn đáng kể.
   - Bảng HUD đáy màn hình hiển thị trực quan số phút và tỷ lệ % tối ưu của giải thuật T-ACO.
