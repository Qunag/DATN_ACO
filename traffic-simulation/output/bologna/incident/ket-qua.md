# Tai nạn ngẫu nhiên và điều phối trên Bologna

Đã chạy thêm sáu lượt có tai nạn, mỗi lượt phục vụ đủ **8.779 xe**, ghép cặp giữ tuyến gốc và `adaptive` ở ba hạt giống 51, 52, 53. Trung bình cộng trên các chuyến của ba lượt, thời gian giảm từ **7,55 xuống 7,04 phút/xe**, tương đương **6,78%** khi có cùng tai nạn. Cả sáu lượt đều có `complete=True`. Tất cả xe tự về đích, chỉ số dịch chuyển và chỉ số va chạm đều bằng 0.

Sự cố được mô phỏng bằng cách hạ giới hạn tốc độ trên mọi làn của một đoạn đường một chiều, từ giây 900 đến trước giây 1.800. Tốc độ còn 20%, tương ứng khoảng 50 xuống 10 km/h ở cả ba đoạn được chọn. Sau đó, từng làn được phục hồi đúng giới hạn tốc độ ban đầu. Đây là các giả định do người triển khai chọn để kiểm tra yêu cầu tai nạn làm giảm tốc độ. [Điều khiển trạng thái làn bằng TraCI](https://sumo.dlr.de/docs/TraCI/Change_Lane_State.html)

Vị trí được lấy ngẫu nhiên, đồng đều từ các đoạn dài ít nhất 50 m, cho phép ô tô con và có đường vào/ra. Việc chọn dùng hạt giống riêng suy ra từ `--seed`. Với cùng mạng và hạt giống, mọi chính sách nhận cùng vị trí và cùng lịch sự cố. Ba mã đường được chọn là `200`, `38`, `44`. Trong nhu cầu gốc, lần lượt có 465, 544 và 30 chuyến đi qua các đoạn này. Mỗi hạt giống thay đổi cả yếu tố ngẫu nhiên của giao thông và vị trí tai nạn.

Đơn vị trong bốn cột thời gian là phút/xe, từ giờ xuất phát theo lịch đến lúc về đích, có tính thời gian chờ vào mạng. Sáu số liệu bình thường được lấy từ thử nghiệm đã lưu trước đó. Cột cuối so sánh hai chính sách có cùng tai nạn.

| Hạt giống | Mã đường | Giữ tuyến, bình thường | Adaptive, bình thường | Giữ tuyến, tai nạn | Adaptive, tai nạn | Giảm khi có tai nạn |
|---|---|---:|---:|---:|---:|---:|
| 51 | 200 | 7,33 | 7,12 | 7,58 | 6,95 | 8,33% |
| 52 | 38 | 7,42 | 7,02 | 7,60 | 7,10 | 6,52% |
| 53 | 44 | 7,41 | 6,86 | 7,47 | 7,06 | 5,46% |

Ở ba lượt bình thường, mức giảm gộp so với giữ tuyến là 5,24%. Trong ba lượt tai nạn, `adaptive` đổi tuyến cho tổng cộng 1535 lượt xe. Các tỷ lệ phản ánh hiệu quả chung của tìm tuyến và phân bổ xe theo xác suất. Nhật ký chuyến đi đã được đối chiếu theo mã xe, giờ xuất phát yêu cầu, điểm đầu/cuối, loại xe và hệ số tốc độ giữa các trường hợp cùng hạt giống. Tổng thời gian và P95 đã được tính lại từ `tripinfo.xml.gz`. Các bản ghi hạ và phục hồi tốc độ giống nhau giữa hai chính sách cùng hạt giống.

Trong bộ mã hiện tại, `adaptive` dùng Dijkstra và ACO để tìm tuyến theo chi phí thời gian có xét tốc độ, hàng đợi và lượng xe vừa được phân tuyến. Khi tai nạn làm đoạn đường chậm lại, dữ liệu TraCI cập nhật chi phí tìm tuyến và xác suất chuyển hướng cho xe xuất phát sau đó. Tốc độ được lấy tối đa một lần mỗi 30 giây khi có xe xuất phát, với độ trễ được làm trơn theo hằng số thời gian 60 giây. Xe được đổi tuyến khi lợi ích ước tính vượt cả 15 giây và 10% thời gian tuyến gốc. Mỗi xe nhận quyết định khi xuất phát.

Có thể định nghĩa T-ACO trong đồ án là Traffic-Aware Ant Colony Optimization, nghĩa là ACO có xét giao thông. Lõi ACO có thể tối ưu theo chi phí thời gian do mô hình cung cấp. Phương án `adaptive` hiện đã dùng cơ chế này. Đề xuất giữ lõi ACO và mô tả rõ dữ liệu giao thông, hàm chi phí cùng cách chia xác suất cho xe thật. Nếu chọn một biến thể T-ACO từ bài báo cụ thể, cần triển khai đúng các phương trình của bài đó để đối chiếu. [Tài liệu ACO của Dorigo, Di Caro và Gambardella](https://www.cs.yale.edu/homes/lans/readings/routing/dorigo-ants-1999.pdf)

Mô hình hiện biểu diễn vùng ảnh hưởng bằng cả một đoạn đường. Các tham số 900 giây, 900 giây và 20% cần được hiệu chỉnh khi có dữ liệu tai nạn thực tế. Đánh giá hiện bao phủ ba vị trí ngẫu nhiên trên một kịch bản nhu cầu Bologna. Các xe đã xuất phát chịu giới hạn tốc độ mới và tiếp tục theo tuyến đã được cấp.

Để mở lại mô phỏng trong SUMO-GUI, chạy lệnh sau từ thư mục `traffic-simulation`. Chương trình in mã đường được chọn ngay lúc bắt đầu.

```powershell
python -B -m scripts.osm.osm_runner --mode fleet --cfg scenarios/sumo-scenarios/bologna/acosta/run.sumocfg --policy adaptive --incident --seed 51 --output-dir output/bologna/incident
```

Thêm `--incident-start`, `--incident-duration`, `--incident-speed-factor` để điều chỉnh thời điểm, độ dài sự cố và tỷ lệ tốc độ còn lại. Ví dụ `--incident-start 600 --incident-duration 1200 --incident-speed-factor 0.3`. Mỗi lượt ghi `incidents.csv` cạnh các nhật ký chuyến đi, quyết định và dịch chuyển.

- Hạt giống 51. [Giữ tuyến, bình thường](../full/20261121-122557-982684-s51-compare/summary.csv) · [Adaptive, bình thường](../full/20261121-122557-982684-s51-compare/summary.csv) · [Giữ tuyến, tai nạn](20261121-133842-788774-s51-original-incident/summary.csv) · [Adaptive, tai nạn](20261121-133842-405067-s51-adaptive-incident/summary.csv).
- Hạt giống 52. [Giữ tuyến, bình thường](../full/20261121-123802-340304-s52-compare/summary.csv) · [Adaptive, bình thường](../full/20261121-123802-340304-s52-compare/summary.csv) · [Giữ tuyến, tai nạn](20261121-133846-043250-s52-original-incident/summary.csv) · [Adaptive, tai nạn](20261121-133842-214843-s52-adaptive-incident/summary.csv).
- Hạt giống 53. [Giữ tuyến, bình thường](../full/20261121-124315-124957-s53-compare/summary.csv) · [Adaptive, bình thường](../full/20261121-124315-124957-s53-compare/summary.csv) · [Giữ tuyến, tai nạn](20261121-133841-429768-s53-original-incident/summary.csv) · [Adaptive, tai nạn](20261121-133842-539272-s53-adaptive-incident/summary.csv).
