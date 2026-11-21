# Kiểm chứng điều phối toàn bộ xe trên bản đồ OSM Hà Nội

Trên bản đồ `map2`, cả tám lượt đều xét đủ **10.000 xe** từ tệp nhu cầu. Giữ tuyến gốc cho thời gian toàn mạng thấp nhất ở cả hai hạt giống. Với phương án dùng hàng đợi và lưu lượng thoát qua đèn, tổng thời gian ghi nhận trong SUMO **tăng 13,04%** so với giữ tuyến gốc, **tăng 2,12%** so với cơ chế cộng 2 giây cho mỗi xe sắp tới và **giảm 6,97%** so với chia đều xác suất giữa hai tuyến. Các tỷ lệ là trung bình của hai chênh lệch ghép cặp theo hạt giống.

## Thời gian toàn mạng

Đơn vị là **phút/xe**, từ giờ xuất phát theo lịch đến lúc SUMO ghi nhận kết thúc ở cạnh đích. Mỗi phương án có cùng 10.000 chuyến nên phần trăm thay đổi của thời gian trung bình cũng là phần trăm thay đổi của tổng toàn mạng. Thời gian này có bao gồm các hành trình bị SUMO dịch chuyển.

| Phương án | Hạt giống 51 | Hạt giống 52 | So với giữ tuyến gốc |
|---|---:|---:|---:|
| Giữ tuyến SUMO | 101,90 | 108,30 | Mốc |
| Hai tuyến đồng xác suất | 127,90 | 127,40 | Tăng 21,58% |
| Xác suất và mức phạt cố định | 117,44 | 115,20 | Tăng 10,81% |
| Xác suất theo hàng đợi và lưu lượng thoát | 116,75 | 120,75 | Tăng 13,04% |

Ở hai lượt thăm dò giữ tuyến trước khi bổ sung nhật ký sự kiện, hạt giống 52 cho cùng tổng thời gian với lượt chính thức. Hạt giống 51 cho 106,81 phút/xe, so với 101,90 phút/xe ở lượt chính thức. Phần so sánh trên dùng cùng phiên bản bộ ghi cho cả tám lượt chính thức. Với hai hạt giống và độ chênh quan sát được khi chạy lại, cần thêm lần lặp để kết luận về tính ổn định. [Lượt thăm dò 51](../tham-do/giu-tuyen-seed51.xml.gz) · [Lượt thăm dò 52](../tham-do/giu-tuyen-seed52.xml.gz)

## Phạm vi điều phối và xe bị dịch chuyển

Tệp nhu cầu có 9.950 cặp cạnh xuất phát và đích. Cả 10.000 xe mang loại `passenger`, được lên lịch trong 1 giờ. Hệ thống xét từng xe một lần khi SUMO cho xe xuất phát. Với một xe có hai lựa chọn hợp lệ, ACO cung cấp tuyến thay thế và bộ điều phối lấy mẫu tuyến theo chi phí thời gian. Xe chỉ có một lựa chọn tiếp tục hành trình đã cấp. Ở đối chứng giữ tuyến, bộ điều phối chỉ ghi nhận xe.

| Phương án | Hạt giống | Xe có hai tuyến | Xe đổi tuyến | Đến đích không bị dịch chuyển | Xe bị dịch chuyển ít nhất một lần | Kết thúc bằng dịch chuyển |
|---|---:|---:|---:|---:|---:|---:|
| Giữ tuyến SUMO | 51 | 0 | 0 | 4.870 | 5.130 | 246 |
| Giữ tuyến SUMO | 52 | 0 | 0 | 4.798 | 5.202 | 253 |
| Hai tuyến đồng xác suất | 51 | 9.164 | 4.587 | 4.185 | 5.815 | 270 |
| Hai tuyến đồng xác suất | 52 | 9.164 | 4.585 | 4.150 | 5.850 | 284 |
| Xác suất và mức phạt cố định | 51 | 9.164 | 3.876 | 4.481 | 5.519 | 248 |
| Xác suất và mức phạt cố định | 52 | 9.164 | 3.806 | 4.475 | 5.525 | 231 |
| Xác suất theo hàng đợi và lưu lượng thoát | 51 | 9.164 | 3.909 | 4.402 | 5.598 | 238 |
| Xác suất theo hàng đợi và lưu lượng thoát | 52 | 9.164 | 3.929 | 4.448 | 5.552 | 259 |

Cột cuối là một phần của nhóm xe đã bị dịch chuyển. Xe cũng có thể bị dịch chuyển giữa đường, được đưa trở lại mạng rồi đến đích. Cấu hình `map2.sumocfg` đặt ngưỡng chờ dịch chuyển là 300 giây. Với tần suất dịch chuyển trong bảng, các số đo thời gian chỉ mô tả hành vi của cấu hình mô phỏng này. [Cơ chế dịch chuyển trong SUMO](https://sumo.dlr.de/docs/Simulation/Why_Vehicles_are_teleporting.html)

Khi chạy thêm đối chứng giữ tuyến với hạt giống 51, tắt dịch chuyển và dừng sau 4 giờ mô phỏng, **1.638 xe đã về đích, 6.619 xe còn trên mạng và 1.743 xe còn chờ xuất phát**. Để đánh giá hiệu quả ngoài thực địa, cần hiệu chỉnh nhu cầu theo giờ và kiểm tra các nút gây kẹt bằng số đếm quan sát tại chỗ. [Nhật ký 10.000 chuyến của lượt tắt dịch chuyển](../khong-dich-chuyen/seed51-tripinfo.xml.gz)

## Cách kiểm tra

Mỗi chính sách dùng đúng cùng mạng, nhu cầu, đèn và hạt giống tương ứng. Đã đối chiếu từng mã xe, điểm đi, điểm đến, giờ khởi hành theo lịch và hệ số tốc độ giữa các lượt ghép cặp. Tổng thời gian được tính lại trực tiếp từ nhật ký chuyến đi. Nhật ký đèn ghi nhận 60 đoạn vào thuộc 19 bộ điều khiển. Trên các đoạn còn lại, thời gian ước tính lấy từ tốc độ quan sát trong SUMO. Phép thử đo hiệu quả của chính sách phân luồng trên cùng cách tìm tuyến.

Chạy từ thư mục `traffic-simulation` để mở bản đồ cùng bộ điều phối hoặc chạy lại đối chứng.

```powershell
python -m scripts.osm.osm_runner --mode fleet
python -m scripts.osm.osm_runner --mode fleet --nogui --policy compare --seed 51
python -m scripts.osm.osm_runner --mode fleet --nogui --policy compare --seed 52
```

- Kết quả từng phương án với hạt giống 51. [Giữ tuyến SUMO](20261121-104607-739293-s51-original/summary.csv) · [Hai tuyến đồng xác suất](20261121-104656-736647-s51-equal/summary.csv) · [Xác suất và mức phạt cố định](20261121-104656-432738-s51-previous/summary.csv) · [Xác suất theo hàng đợi và lưu lượng thoát](20261121-104607-177272-s51-queue/summary.csv)
- Kết quả từng phương án với hạt giống 52. [Giữ tuyến SUMO](20261121-104605-347174-s52-original/summary.csv) · [Hai tuyến đồng xác suất](20261121-104655-941035-s52-equal/summary.csv) · [Xác suất và mức phạt cố định](20261121-104654-821500-s52-previous/summary.csv) · [Xác suất theo hàng đợi và lưu lượng thoát](20261121-104603-731762-s52-queue/summary.csv)
- Bên cạnh mỗi bảng là nhật ký `decisions.csv`, `cycles.csv`, `teleports.csv` và `tripinfo.xml.gz` trong thư mục mang tên phương án. [Hướng dẫn sử dụng](../../../README.md)

Mã SHA-256 của mạng là `90b50e155940fc73247298c5316f34867c1da1879f9f50c44187592bea36cd58`. Mã của tệp nhu cầu là `5ba2218d25d3860f4bb38b0a146f4224554c706d3ed1a84fa9cf262ef11080a5`.
