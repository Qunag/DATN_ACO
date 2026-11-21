# Hiệu quả phân luồng cho 10.000 xe trên bản đồ Hà Nội

Trên hai hạt giống kiểm chứng mới (61 và 62), thời gian trung bình là **78,2 phút/xe** với phân luồng mới, **105,5 phút/xe** khi giữ tuyến SUMO và **112,2 phút/xe** với cách phân luồng theo hàng đợi trước đây. Tổng thời gian của hai lượt giảm **25,92%** so với giữ tuyến và **30,33%** so với phương án hàng đợi. Số xe về đích bằng cách đi trọn tuyến tăng lần lượt **1.060** và **839** so với giữ tuyến.

## Thời gian cả mạng

Mỗi giá trị là số phút trung bình từ giờ xuất phát theo lịch đến lúc SUMO ghi nhận xe kết thúc ở cạnh đích, có tính thời gian chờ được vào mạng. Mỗi phương án phục vụ cùng 10.000 yêu cầu nên mức giảm phần trăm cũng là mức giảm tổng thời gian. Hai cột cuối tính theo từng hạt giống. Tỷ lệ ở đầu báo cáo tính trên tổng thời gian cộng lại của hai hạt giống mới.

| Hạt giống | Tuyến gốc | Theo hàng đợi | Phân luồng mới | Giảm so với gốc | Giảm so với hàng đợi |
|---|---:|---:|---:|---:|---:|
| 61 | 108,14 | 117,75 | 75,54 | 30,14% | 35,84% |
| 62 | 102,86 | 106,59 | 80,76 | 21,48% | 24,23% |
| 51 | 101,90 | 116,75 | 73,21 | 28,15% | 37,29% |
| 52 | 108,30 | 120,75 | 72,22 | 33,31% | 40,19% |

Các lượt 51 và 52 dùng để tìm nguyên nhân của kết quả cũ và kiểm tra lại. Với 61 và 62, nhóm giữ nguyên tham số đã chọn trước khi chạy. Có tám lượt mô phỏng mới và bốn lượt đối chứng 51, 52 đã lưu trước đó. [Đối chứng trước khi cải tiến](../map2/ket-qua.md)

## Số chuyến tự đi đến đích và thời gian của các chuyến chậm

Ba cột đầu đếm số xe đi hết hành trình mà SUMO không phải dịch chuyển. Ba cột sau ghi thời gian ở phân vị 95 (P95), tính bằng phút. Có 95% chuyến hoàn thành trong thời gian bằng hoặc ngắn hơn mốc này. Thời gian trung bình và P95 đều bao gồm chuyến có dịch chuyển. Cấu hình cho phép SUMO giải phóng xe mắc kẹt sau ngưỡng 300 giây. [Cơ chế dịch chuyển của SUMO](https://sumo.dlr.de/docs/Simulation/Why_Vehicles_are_teleporting.html)

| Hạt giống | Tự đến đích · gốc | Hàng đợi | Mới | P95 · gốc | Hàng đợi | Mới |
|---|---:|---:|---:|---:|---:|---:|
| 61 | 4.829 | 4.414 | 5.889 | 228,9 | 285,7 | 172,9 |
| 62 | 4.875 | 4.838 | 5.714 | 219,2 | 248,7 | 198,7 |
| 51 | 4.870 | 4.402 | 6.007 | 213,1 | 278,3 | 169,9 |
| 52 | 4.798 | 4.448 | 6.095 | 227,9 | 305,3 | 165,8 |

Ở hạt giống 61, xe cuối cùng kết thúc sau 217,6 phút với cách mới và 272,9 phút với tuyến gốc. Ở hạt giống 62, xe cuối cùng của cách mới về muộn hơn 86,8 phút (366,6 so với 279,8 phút), dù thời gian trung bình và P95 đều giảm.

Tại giây 3.600, bảng dưới đếm số xe đã về đích mà không cần dịch chuyển. Hai cột cuối đếm quyết định trên **toàn bộ** lượt chạy của phương án mới.

| Hạt giống | Về trong 1 giờ · gốc | Hàng đợi | Mới | Xe có tuyến thay thế | Xe thực sự đổi tuyến |
|---|---:|---:|---:|---:|---:|
| 61 | 2.577 | 2.529 | 3.099 | 9.460 | 2.307 |
| 62 | 2.446 | 2.663 | 3.080 | 9.450 | 2.384 |
| 51 | 2.429 | 2.415 | 3.237 | 9.451 | 2.463 |
| 52 | 2.436 | 2.530 | 3.266 | 9.446 | 2.394 |

## Điều gì đã thay đổi

Ở thử nghiệm trước, 3.024 trong 7.838 lượt đổi tuyến dẫn xe sang phương án có thời gian dự kiến bằng hoặc dài hơn tuyến gốc.

1. Khi có xe xuất phát, hệ thống lấy tốc độ và số xe đứng chờ trên từng đoạn, tối đa một lần mỗi 30 giây mô phỏng. Dijkstra và đàn kiến tìm tuyến thay thế bằng chi phí thời gian của các lượt rẽ, có xét cả sự chậm trễ quan sát được. Mỗi xe giữ điểm đi, điểm đến và các điểm dừng bắt buộc. [Các đại lượng TraCI trên đoạn đường](https://sumo.dlr.de/docs/TraCI/Edge_Value_Retrieval.html)
2. Bộ điều phối ước lượng tải của từng lượt rẽ từ những xe được phân tuyến trong 120 giây gần nhất. Một xe chỉ có xác suất chuyển khi thời gian dự kiến tiết kiệm vượt cả 15 giây và 10% chi phí tuyến gốc. Xác suất tăng dần theo lợi ích và luôn dưới 85%. Nhật ký cả bốn hạt giống xác nhận mọi lần đổi tuyến thực tế đều vượt hai ngưỡng này. Mức giảm thời gian đo được phản ánh tác dụng chung của việc tìm tuyến và phân bổ xe.

## Phạm vi và cách chạy lại

SUMO 1.27.1 chạy trên mạng OSM `map2` với 10.000 ô tô con được `randomTrips.py` lên lịch trong một giờ. Các lượt dùng cùng mạng, nhu cầu, chương trình đèn và ngưỡng dịch chuyển. Mỗi lượt chạy đến khi hết xe. Đã đối chiếu mã xe, giờ khởi hành yêu cầu, điểm đầu/cuối và hệ số tốc độ theo từng hạt giống, đồng thời tính lại tổng thời gian và P95 từ nhật ký chuyến. Cả 12 lượt đều xét và ghi nhận kết thúc đủ 10.000 xe. SUMO chấp nhận mọi lệnh đổi tuyến của phương án mới.

Phương án mới ghi nhận 2 lượt xe liên quan va chạm ở hạt giống 51 và 2 ở hạt giống 61. Chỉ số này bằng 0 ở hai hạt giống còn lại và ở tất cả các lượt đối chứng. Chỉ số cộng số xe liên quan theo từng bước mô phỏng, một vụ có thể liên quan nhiều xe. [Định nghĩa chỉ số va chạm của TraCI](https://raw.githubusercontent.com/eclipse-sumo/sumo/v1_27_1/tools/traci/_simulation.py)

Ở hai hạt giống mới, vẫn có 4.111 và 4.286 xe bị dịch chuyển ít nhất một lần với phương án mới. Nhu cầu được sinh bằng mô phỏng. Để ước lượng hiệu quả trên đường thật hoặc trong giao thông hỗn hợp, cần hiệu chỉnh bằng lưu lượng đếm theo loại xe và thời gian hành trình quan sát tại nút. Các tham số về phục vụ lượt rẽ và mức sẵn sàng đổi tuyến hiện là giả thiết.

Từ thư mục `traffic-simulation`, chạy ba phương án ghép cặp như sau. Nhật ký `summary.csv` được tạo khi mỗi phương án hoàn thành.

```powershell
foreach ($seed in 61,62) {
    foreach ($policy in 'original','queue','adaptive') {
        python -m scripts.osm.osm_runner --mode fleet --nogui --policy $policy --seed $seed
    }
}
```

- Hạt giống 61. [Tuyến gốc](20261121-114052-924277-s61-original/summary.csv) · [Theo hàng đợi](20261121-114057-239385-s61-queue/summary.csv) · [Phân luồng mới](20261121-113723-969100-s61-adaptive/summary.csv).
- Hạt giống 62. [Tuyến gốc](20261121-114053-278566-s62-original/summary.csv) · [Theo hàng đợi](20261121-114053-440788-s62-queue/summary.csv) · [Phân luồng mới](20261121-113723-268600-s62-adaptive/summary.csv).
- Hạt giống 51. [Tuyến gốc](../map2/20261121-104607-739293-s51-original/summary.csv) · [Theo hàng đợi](../map2/20261121-104607-177272-s51-queue/summary.csv) · [Phân luồng mới](20261121-113945-845537-s51-adaptive/summary.csv).
- Hạt giống 52. [Tuyến gốc](../map2/20261121-104605-347174-s52-original/summary.csv) · [Theo hàng đợi](../map2/20261121-104603-731762-s52-queue/summary.csv) · [Phân luồng mới](20261121-113946-147015-s52-adaptive/summary.csv).

Bên cạnh mỗi bảng tổng hợp, thư mục phương án chứa `tripinfo.xml.gz`, `decisions.csv`, `teleports.csv` và `cycles.csv`. [Hướng dẫn chạy bản đồ](../../../README.md)
