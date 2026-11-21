# Kiểm chứng phân luồng tại nút B bằng SUMO

Trên lưới 3×3, việc luôn gợi ý nhánh đang nhanh nhất làm tổng thời gian toàn mạng tăng **6,63%** khi nhu cầu qua B cao và đoạn C→F bị giảm tốc. Chọn tuyến theo xác suất có tính cả các xe sắp đến B thu hẹp mức tăng còn **1,11%**. Trong cùng sự cố ở tải gốc, hai cách này lần lượt **giảm 1,21% và 0,91%** tổng thời gian. Mốc so sánh là giữ nguyên lịch tuyến ban đầu, vốn chia đều hai nhánh.

## Kết quả của 80 lượt mô phỏng

Bảng ghi thời gian trung bình **giây/xe** của tất cả các chuyến, kể từ giờ khởi hành theo lịch đến khi về đích. Mỗi dòng lấy trung bình 5 lần chạy ghép cặp. Số xe bằng nhau giữa các cách chọn tuyến trong từng dòng nên cách có giá trị thấp nhất cũng có tổng thời gian toàn mạng thấp nhất.

| Nhu cầu và trạng thái C→F | Giữ tuyến 50/50 | Luôn chọn nhanh nhất | Chọn theo xác suất | Xác suất có tính xe sắp tới |
|---|---:|---:|---:|---:|
| Tải gốc, bình thường | 125,13 | **124,95** | 125,00 | 125,00 |
| Tải gốc, giảm tốc | 128,37 | **126,81** | 127,14 | 127,20 |
| Tải cao, bình thường | 145,07 | 151,17 | 145,11 | **144,93** |
| Tải cao, giảm tốc | **151,15** | 161,16 | 154,38 | 152,82 |

- **Khi C→F giảm tốc**, kết quả so với giữ tuyến cùng chiều ở cả 5 lần chạy của mỗi mức tải. Ở tải gốc, phương án xác suất có tính xe sắp tới tiết kiệm trung bình 42,8 phút cộng dồn cho 2.198 xe. Ở tải cao, phương án này tốn thêm 83,7 phút cho 2.996 xe.
- **Hiện tượng dồn xe xuất hiện ngay trong nhật ký gợi ý.** Ở tải cao, chia 20 phút giảm tốc thành từng khoảng một phút qua 5 lần chạy. Trong 77/100 khoảng, cách luôn chọn nhanh nhất gửi toàn bộ xe đủ điều kiện vào cùng một nhánh. Con số tương ứng là 9/100 với xác suất đơn thuần và 0/100 khi tính thêm xe sắp tới. Mỗi khoảng có từ 16 đến 18 quyết định ở ba phương án này.
- **Khi cả hai nhánh hoạt động bình thường**, lợi ích của xác suất có tính xe sắp tới so với giữ tuyến chỉ khoảng 0,1%. Phương án này nhanh hơn ở 3/5 lần tải gốc và 2/5 lần tải cao. Chưa đủ căn cứ để khẳng định cải thiện ổn định trong điều kiện này.

## Cách tổ chức đối chứng

- **Tuyến và vai trò của ACO.** Lõi ACO của dự án tìm hai đường khả thi từ B đến F, qua C hoặc E. Hai đường cùng có đoạn đầu A→B và đoạn cuối F→I. Khi tìm đường thứ hai, tăng chi phí các đoạn của đường thứ nhất để tạo lựa chọn khác. Mọi cách gợi ý dùng cùng hai tuyến. Phép thử này đo tác động của cách phân luồng. Giá trị riêng của ACO so với một thuật toán khác tạo cùng hai tuyến vẫn là câu hỏi mở.
- **Nhu cầu.** Phát xe trong 1 giờ. Ở tải gốc, có 266 xe được xét đổi tuyến tại B và 1.932 xe nền. Thử nghiệm tải cao tăng riêng hai luồng đủ điều kiện lên gấp bốn, thành 1.064 xe, giữ nguyên xe nền. Thử nghiệm tải cao được bổ sung sau khi xem kết quả tải gốc để kiểm tra giả thuyết dồn xe. Các tham số phân luồng giữ nguyên trong cả hai mức tải.
- **Sự cố và dữ liệu.** SUMO 1.27.1 chạy với bước 1 giây. Trong kịch bản giảm tốc, giới hạn trên C→F hạ từ khoảng 50 xuống 18 km/h từ phút 20 đến phút 40. Tín hiệu đèn cố định. Hệ thống ước tính thời gian đi từng đoạn từ chiều dài và tốc độ quan sát qua TraCI, làm trơn tốc độ với hằng số thời gian 30 giây.
- **Quyết định cho từng xe.** Khi xe đủ điều kiện vào A→B, hệ thống gợi ý nhánh một lần. Phương án xác suất ưu tiên tuyến có thời gian ước tính thấp hơn theo công thức logit với thang 30 giây. Biến thể có tính xe sắp tới cộng 2 giây vào chi phí của một nhánh cho mỗi xe đã được gợi ý nhánh đó, còn trên A→B và dự kiến đến nút trong cùng cửa sổ ±30 giây. Đây là tham số thử nghiệm. Tất cả xe được gợi ý đều làm theo.
- **Kiểm tra số liệu.** Mỗi cấu hình chạy với cùng 5 hạt giống ngẫu nhiên (41–45). Đã đối chiếu nhật ký từng xe về mã xe, điểm đi/đến, giờ khởi hành theo lịch và hệ số tốc độ giữa các phương án ghép cặp. Cả 80 lượt đều hoàn thành toàn bộ chuyến, không ghi nhận va chạm hoặc xe bị dịch chuyển tự động. Tổng thời gian gồm cả phần chờ được đưa vào mạng.

## Bước thử tiếp theo

Ưu tiên trường hợp **tải cao có giảm tốc**, nơi giữ tỷ lệ 50/50 đang tốt nhất. Đo số xe xếp hàng và số xe qua đèn mỗi chu kỳ ở hai nhánh, dùng các số đo đó để hiệu chỉnh mức phạt cho xe sắp tới. Sau đó giữ nguyên tham số và kiểm tra trên các hạt giống mới. Kết quả hiện tại chỉ áp dụng cho hai nhánh tại B trên lưới mô phỏng.

## Dữ liệu và cách chạy lại

Hai bảng CSV lưu tổng thời gian theo giây (`total_s`), số xe về đích, thời gian trung bình, phân vị 95% và số xe đi mỗi nhánh của từng lượt. Bên cạnh mỗi bảng có `decisions.csv` ghi từng quyết định và thư mục `raw` chứa nhật ký chuyến đi do SUMO xuất. [Bảng tải gốc](so-lieu/summary.csv) · [Bảng tải cao](so-lieu-tai-cao/summary.csv) · [Chương trình thí nghiệm](run.py)

Trên Windows có SUMO và biến môi trường `SUMO_HOME`, chạy từ thư mục gốc của dự án. Mỗi lệnh ghi kết quả vào một thư mục mới.

```powershell
python -B traffic-simulation/output/kiem-chung-sumo-20261121/run.py
python -B traffic-simulation/output/kiem-chung-sumo-20261121/run.py --high
```
