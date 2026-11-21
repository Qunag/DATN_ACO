# Tai nạn ngẫu nhiên nối tiếp trong một vùng Bologna

Đã bổ sung chế độ `--incident-dynamic`. Lượt kiểm tra dùng 13.169 xe, hạt giống 51, trong vùng chữ nhật `300 200 1500 1150` theo tọa độ SUMO địa phương, đơn vị mét. Vùng này chứa 65 đoạn đường hợp lệ. Mỗi đoạn được chọn có toàn bộ đường hình học nằm trong vùng.

Hệ thống thử tạo một tai nạn sau mỗi 120–300 giây, trong khoảng phút 15 đến trước phút 60, với tối đa 5 tai nạn đồng thời. Khi đạt giới hạn, lịch chờ lượt tạo tiếp theo. Đoạn đang có tai nạn được loại khỏi danh sách chọn. Mỗi tai nạn có mức độ và thời gian phục hồi riêng. Mức nhẹ giữ 70% tốc độ trong 5 phút, mức vừa giữ 40% trong 10 phút, mức nặng giữ 20% trong 20 phút và mức rất nặng giữ 10% trong 30 phút. Trọng số lấy mẫu tương ứng là 4, 3, 2, 1. Đây là các giả định do người triển khai chọn cho phép thử.

Với các tham số trên, lịch có 13 tai nạn gồm 6 nhẹ, 3 vừa, 3 nặng và 1 rất nặng. Sự cố cuối cùng phục hồi ở giây 4.740, tức phút 79. Chế độ cố định `--incident` tiếp tục dùng lịch chung cho các điểm như trước.

| Mã sự cố | Đoạn đường | Mức độ | Bắt đầu, phút | Phục hồi, phút | Tốc độ còn lại |
|---|---|---|---:|---:|---:|
| incident-0001 | 171 | Vừa | 15.0 | 25.0 | 40% |
| incident-0002 | 80 | Nhẹ | 19.77 | 24.77 | 70% |
| incident-0003 | 186 | Vừa | 24.2 | 34.2 | 40% |
| incident-0004 | 58[1] | Nhẹ | 28.02 | 33.02 | 70% |
| incident-0005 | 69 | Vừa | 31.4 | 41.4 | 40% |
| incident-0006 | 224[1] | Nhẹ | 34.78 | 39.78 | 70% |
| incident-0007 | 79 | Nhẹ | 36.9 | 41.9 | 70% |
| incident-0008 | 74 | Nặng | 41.8 | 61.8 | 20% |
| incident-0009 | 122 | Nặng | 45.35 | 65.35 | 20% |
| incident-0010 | 188 | Rất nặng | 47.73 | 77.73 | 10% |
| incident-0011 | 103 | Nhẹ | 52.13 | 57.13 | 70% |
| incident-0012 | 97 | Nhẹ | 56.43 | 61.43 | 70% |
| incident-0013 | 78[1][1] | Nặng | 59.0 | 79.0 | 20% |

Cả hai lượt đối chứng đều hoàn thành đủ 13.169 chuyến, có cùng danh sách xe, giờ xuất phát yêu cầu, điểm đi/đến, loại xe, hệ số tốc độ, lịch tai nạn và các lần áp dụng/phục hồi. Tổng thời gian và P95 được tính lại từ nhật ký chuyến đi.

| Phương án | Trung bình, phút/xe | P95, phút | Xe bị dịch chuyển | Lần dịch chuyển | Xe đổi tuyến |
|---|---:|---:|---:|---:|---:|
| Giữ tuyến gốc | 23.46 | 62.27 | 8 | 8 | 0 |
| Adaptive | 25.67 | 65.17 | 66 | 69 | 1298 |

Ở trường hợp này, tổng thời gian của `adaptive` cao hơn giữ tuyến gốc 9.41%. Hai lượt đều có chỉ số va chạm bằng 0. Nhật ký SUMO của `adaptive` có các xe buýt bị dịch chuyển và bỏ qua điểm dừng khi ùn tắc. Các chỉ số thời gian bao gồm những chuyến có dịch chuyển. Kết quả hiện chỉ bao phủ một vùng và một hạt giống.

Trong SUMO-GUI, vùng được vẽ bằng đường viền xanh. Ghim và đoạn đường có màu vàng, cam, đỏ, đỏ sẫm theo mức độ tai nạn. Dấu sự cố bị gỡ khi đoạn đường phục hồi. Xe đã được đổi tuyến có màu xanh ngọc. Lượt minh họa tạm dừng ở giây 3.400, khi có 5 tai nạn đang hoạt động. Nhấn nút chạy để tiếp tục đến các lần phục hồi.

```powershell
Set-Location "D:\study\DATN\traffic-simulation"
python -B -m scripts.osm.osm_runner --mode fleet --cfg scenarios/sumo-scenarios/bologna/acosta/run.sumocfg --policy adaptive --demand-scale 1.5 --incident-dynamic --incident-area 300 200 1500 1150 --incident-count 5 --seed 51 --gui-delay 5 --pause-at 3400 --output-dir output/bologna/regional-incident/gui
```

Trong mỗi thư mục chính sách, `incident-plan.csv` lưu toàn bộ lịch được tạo trước mô phỏng. `incidents.csv` lưu thời điểm thực sự áp dụng và phục hồi, mã sự cố, mức độ, tốc độ trước/sau. Việc gợi ý tuyến vẫn thực hiện khi xe xuất phát.

[Kết quả giữ tuyến](verification/20261121-153534-755842-s51-original-incident/summary.csv) · [Kết quả adaptive](verification/20261121-153532-188007-s51-adaptive-incident/summary.csv) · [Hướng dẫn tham số](../../../README.md)

## Trường hợp giảm số xe

Đã chạy thêm hai lượt ngày 21/11/2026 với `--demand-scale 1`, tương ứng 8.779 xe, giảm khoảng 33,3% so với 13.169 xe ở mức 1,5. Mạng đường, cấu hình SUMO, hạt giống 51, vùng `300 200 1500 1150`, khoảng phát sinh và giới hạn 5 tai nạn đồng thời được giữ nguyên. Cả bốn lượt có lịch 13 tai nạn và nhật ký áp dụng/phục hồi từng làn giống nhau.

| Số xe | Phương án | Trung bình, phút/xe | P95, phút | Xe bị dịch chuyển | Xe đổi tuyến |
|---:|---|---:|---:|---:|---:|
| 13.169 | Giữ tuyến gốc | 23,46 | 62,27 | 8 | 0 |
| 13.169 | Adaptive | 25,67 | 65,17 | 66 | 1.298 |
| 8.779 | Giữ tuyến gốc | 7,73 | 31,22 | 1 | 0 |
| 8.779 | Adaptive | 7,02 | 28,23 | 0 | 514 |

Ở mức 8.779 xe, `adaptive` giảm tổng thời gian từ 4.070.387 xuống 3.699.149 giây, tương đương **9,12%**, tiết kiệm trung bình 42,29 giây mỗi xe. Cả hai lượt hoàn thành đủ 8.779 chuyến, `complete=True`, không còn xe chưa kết thúc và chỉ số va chạm bằng 0. `adaptive` không có xe bị dịch chuyển. Giữ tuyến gốc có một xe bị SUMO dịch chuyển do chờ quá lâu, nên chỉ số thời gian của lượt này bao gồm chuyến đó.

Kết quả cho thấy hiệu quả điều phối phụ thuộc mức tải trong phép thử này. Ở 8.779 xe, `adaptive` cải thiện thời gian; ở 13.169 xe, phương án này chậm hơn 9,41%. Mức giảm thời gian giữa hai lượng xe phản ánh cả việc giảm tải, vì vậy cần so sánh hai chính sách trong cùng lượng xe để đánh giá lợi ích điều phối. Đây vẫn là một vùng và một hạt giống, chưa đủ kết luận cho mọi lưu lượng.

Đã tính lại tổng thời gian, trung bình và P95 từ `tripinfo.xml.gz`. Hai lượt mới có cùng mã xe, điểm đi/đến, giờ xuất phát theo lịch, loại xe và hệ số tốc độ. Nhật ký xác nhận tất cả tai nạn bắt đầu và phục hồi đúng lịch, từng làn trở về giới hạn tốc độ trước sự cố. Thuật toán giữ nguyên, quyết định gợi ý tuyến vẫn được đưa ra khi xe xuất phát.

Chạy lại hai phương án đến khi hết xe trong PowerShell

```powershell
Set-Location "D:\study\DATN\traffic-simulation"
foreach ($policy in @("original", "adaptive")) {
    python -B -m scripts.osm.osm_runner --mode fleet --nogui --cfg scenarios/sumo-scenarios/bologna/acosta/run.sumocfg --policy $policy --demand-scale 1 --incident-dynamic --incident-area 300 200 1500 1150 --incident-count 5 --seed 51 --output-dir output/bologna/regional-incident-reduced/verification
}
```

Để xem trường hợp giảm xe bằng SUMO-GUI và tạm dừng ở giây 3.400

```powershell
python -B -m scripts.osm.osm_runner --mode fleet --cfg scenarios/sumo-scenarios/bologna/acosta/run.sumocfg --policy adaptive --demand-scale 1 --incident-dynamic --incident-area 300 200 1500 1150 --incident-count 5 --seed 51 --gui-delay 5 --pause-at 3400 --output-dir output/bologna/regional-incident-reduced/gui
```

[Kết quả giữ tuyến, 8.779 xe](../regional-incident-reduced/verification/20261121-155937-585646-s51-original-incident/summary.csv) · [Kết quả adaptive, 8.779 xe](../regional-incident-reduced/verification/20261121-155937-195375-s51-adaptive-incident/summary.csv)
