# BÁO CÁO NGHIÊN CỨU GIẢI THUẬT ĐÀN KIẾN TRONG BÀI TOÁN ĐIỀU HƯỚNG GIAO THÔNG

## 1. Đặt vấn đề

Trong các hệ thống giao thông đô thị, bài toán tìm đường không chỉ phụ thuộc vào chiều dài của tuyến đường mà còn chịu ảnh hưởng của nhiều yếu tố như mật độ phương tiện, tốc độ trung bình, thời gian chờ tại nút giao, tình trạng ùn tắc và sự cố giao thông.

Các giải thuật tìm đường truyền thống như Dijkstra hoặc A* có khả năng tìm đường ngắn nhất hiệu quả trên đồ thị khi trọng số các cạnh đã được xác định. Tuy nhiên, khi trạng thái giao thông thay đổi theo thời gian, chi phí của một đoạn đường cũng thay đổi. Vì vậy, hướng nghiên cứu của đề tài là sử dụng **Ant Colony Optimization – ACO** như một phương pháp tối ưu thích nghi, trong đó kinh nghiệm của các lần tìm đường trước được lưu dưới dạng pheromone.

ACO thuộc nhóm phương pháp metaheuristic lấy cảm hứng từ hành vi tìm kiếm thức ăn của đàn kiến và đã được phát triển cho nhiều bài toán tối ưu tổ hợp như TSP và định tuyến.

---

## 2. Mục tiêu nghiên cứu

Đề tài hướng tới xây dựng một hệ thống điều hướng giao thông có khả năng:

- Tìm tuyến đường phù hợp giữa điểm xuất phát và điểm đích.
- Không chỉ xét khoảng cách mà còn xét trạng thái giao thông hiện tại.
- Hạn chế lựa chọn các tuyến đang ùn tắc.
- Có khả năng thay đổi tuyến khi điều kiện giao thông biến động.
- So sánh hiệu quả giữa ACO và các giải thuật tìm đường truyền thống.
- Làm nền tảng để nghiên cứu thêm điều khiển đèn giao thông thích nghi.

Mục tiêu cuối cùng không phải chỉ tìm **đường ngắn nhất về khoảng cách**, mà là tìm **đường có chi phí di chuyển thực tế thấp hơn trong từng trạng thái giao thông**.

---

## 3. Mô hình bài toán

Mạng lưới giao thông được biểu diễn bằng đồ thị:

\[
G=(V,E)
\]

Trong đó:

- \(V\): tập các nút giao.
- \(E\): tập các đoạn đường kết nối giữa các nút giao.
- Mỗi cạnh \((i,j)\) biểu diễn một đoạn đường từ nút \(i\) đến nút \(j\).

Thay vì chỉ sử dụng chiều dài đoạn đường làm trọng số, đề tài xây dựng trọng số động:

\[
C_{ij}(t)
=
w_dD_{ij}
+
w_tT_{ij}(t)
+
w_qQ_{ij}(t)
+
w_wW_{ij}(t)
\]

Trong đó:

- \(D_{ij}\): chiều dài đoạn đường.
- \(T_{ij}(t)\): thời gian di chuyển tại thời điểm \(t\).
- \(Q_{ij}(t)\): mức độ ùn tắc hoặc số phương tiện trên đoạn đường.
- \(W_{ij}(t)\): thời gian chờ.
- \(w_d,w_t,w_q,w_w\): trọng số của từng thành phần.

Các đại lượng cần được chuẩn hóa trước khi cộng vào cùng một hàm chi phí.

Heuristic của ACO được xác định:

\[
\eta_{ij}(t)
=
\frac{1}{C_{ij}(t)+\varepsilon}
\]

Với \(\varepsilon\) là một số rất nhỏ nhằm tránh phép chia cho 0.

Như vậy, một tuyến đường dài hơn về khoảng cách vẫn có thể được đánh giá tốt hơn nếu tốc độ di chuyển cao và mức độ ùn tắc thấp.

---

## 4. Nguyên lý hoạt động của ACO

Mỗi kiến nhân tạo bắt đầu từ nút xuất phát và xây dựng một đường đi đến nút đích.

Xác suất kiến \(k\) lựa chọn cạnh từ \(i\) đến \(j\):

\[
P_{ij}^{k}
=
\frac{
\tau_{ij}^{\alpha}
\eta_{ij}^{\beta}
}{
\sum_{l\in N_i^k}
\tau_{il}^{\alpha}
\eta_{il}^{\beta}
}
\]

Trong đó:

- \(\tau_{ij}\): lượng pheromone của cạnh.
- \(\eta_{ij}\): thông tin heuristic.
- \(\alpha\): mức độ ảnh hưởng của pheromone.
- \(\beta\): mức độ ảnh hưởng của thông tin giao thông.
- \(N_i^k\): tập các nút kiến có thể lựa chọn.

Sau khi các kiến hoàn thành hành trình, pheromone bay hơi:

\[
\tau_{ij}
\leftarrow
(1-\rho)\tau_{ij}
\]

Trong đó \(\rho\) là tỷ lệ bay hơi.

Các tuyến có chất lượng tốt được bổ sung pheromone:

\[
\Delta\tau_{ij}^{k}
=
\frac{Q}{L_k}
\]

với \(L_k\) là chi phí toàn bộ đường đi của kiến \(k\).

Qua nhiều vòng lặp, các cạnh thường xuyên thuộc các lời giải tốt sẽ có lượng pheromone cao hơn.

---

## 5. Ý tưởng cải tiến ACO

### 5.1. ACO nhận biết trạng thái giao thông

ACO thông thường có thể sử dụng:

\[
\eta_{ij}=\frac{1}{D_{ij}}
\]

Đề tài thay thế bằng:

\[
\eta_{ij}(t)
=
\frac{1}
{
w_dD_{ij}
+w_tT_{ij}(t)
+w_qQ_{ij}(t)
+w_wW_{ij}(t)
+\varepsilon
}
\]

Do đó heuristic thay đổi theo trạng thái giao thông.

Ví dụ:

**Tuyến 1**

- Khoảng cách: 800 m.
- Tốc độ thấp.
- Nhiều xe đang dừng.
- Thời gian chờ cao.

**Tuyến 2**

- Khoảng cách: 1.000 m.
- Ít xe.
- Tốc độ trung bình cao.
- Hầu như không phải chờ.

Hệ thống có thể lựa chọn tuyến 2 dù tuyến này dài hơn 200 m.

---

### 5.2. Pheromone thích nghi

Có thể nghiên cứu tỷ lệ bay hơi thay đổi theo thời gian:

\[
\rho(t)
=
\rho_{max}
-
\frac{t}{T}
(\rho_{max}-\rho_{min})
\]

Ở giai đoạn đầu, thuật toán ưu tiên khám phá nhiều tuyến.

Ở giai đoạn sau, thuật toán tăng mức độ khai thác những tuyến đã cho kết quả tốt.

---

### 5.3. Tái định tuyến khi giao thông thay đổi

Một trong những thành phần quan trọng nhất của đề tài là **dynamic rerouting**.

Quy trình:

```text
Phương tiện đang di chuyển
          ↓
Thu thập trạng thái giao thông
          ↓
Kiểm tra tuyến phía trước
          ↓
Có ùn tắc nghiêm trọng?
       /         \
     Không       Có
      ↓           ↓
Giữ tuyến      Chạy lại ACO
                  ↓
              Tuyến mới
                  ↓
         Cập nhật cho phương tiện
```

SUMO cho phép điều khiển phương tiện đang chạy thông qua TraCI, bao gồm thay đổi tuyến bằng `setRoute` hoặc thay đổi đích để hệ thống xây dựng lại tuyến.

---

## 6. Kiến trúc đề xuất

```text
                 MÔ PHỎNG SUMO
                       │
                       │ TraCI
                       ▼
             TRAFFIC DATA COLLECTOR
                       │
          ┌────────────┼────────────┐
          ↓            ↓            ↓
       Speed       Vehicle       Waiting
                    Count          Time
          └────────────┼────────────┘
                       ↓
               TRAFFIC GRAPH
                       │
                       ↓
               ROUTING ENGINE
          ┌────────────┼────────────┐
          │            │            │
      Dijkstra        A*           ACO
                                   │
                                   ↓
                          Improved ACO
                       Traffic-Aware ACO
                                   │
                                   ↓
                              Best Route
                                   │
                                   ↓
                                 TraCI
                                   │
                                   ↓
                           SUMO Vehicle
```

SUMO cung cấp qua TraCI các thông tin ở cấp edge như số phương tiện, tốc độ trung bình, occupancy, thời gian chờ, thời gian di chuyển và số phương tiện đang dừng.

---

## 7. Các giải thuật đối chứng

Để đánh giá khách quan, đề tài không chỉ chạy ACO mà cần xây dựng các phương pháp đối chứng.

### Dijkstra

Trọng số cạnh:

\[
C_{ij}=D_{ij}
\]

Dùng làm baseline cho bài toán đường ngắn nhất.

### Dijkstra với trọng số giao thông

\[
C_{ij}(t)=T_{ij}(t)
\]

Dùng để đánh giá việc chỉ cập nhật trọng số động đã mang lại hiệu quả đến đâu.

### A*

Sử dụng heuristic khoảng cách tới đích nhằm giảm không gian tìm kiếm.

### ACO cơ bản

Chỉ sử dụng khoảng cách.

### Traffic-Aware ACO

Sử dụng các thông số giao thông từ SUMO.

### Improved ACO

Có thể kết hợp:

- Pheromone thích nghi.
- Local search.
- Cơ chế chống hội tụ sớm.
- Cảnh báo và tái định tuyến.

---

## 8. Các chỉ số đánh giá

### Thời gian di chuyển trung bình

\[
ATT
=
\frac{1}{N}
\sum_{i=1}^{N}T_i
\]

### Thời gian chờ trung bình

\[
AWT
=
\frac{1}{N}
\sum_{i=1}^{N}W_i
\]

### Độ dài tuyến trung bình

\[
ARL
=
\frac{1}{N}
\sum_{i=1}^{N}L_i
\]

Ngoài ra đánh giá:

- `timeLoss`.
- Số lần phải thay đổi tuyến.
- Số phương tiện đang dừng.
- Tốc độ trung bình.
- Thời gian chạy thuật toán.
- Tỷ lệ phương tiện đến đích.
- Khả năng phục hồi khi xuất hiện sự cố.

SUMO `tripinfo` có thể xuất các đại lượng như `duration`, `routeLength`, `waitingTime`, `timeLoss` và số lần reroute để phục vụ đánh giá thực nghiệm.

---

## 9. Các kịch bản thực nghiệm

### Kịch bản 1 – Giao thông bình thường

Các tuyến có lưu lượng tương đối giống nhau.

Mục đích: kiểm tra ACO có tìm được tuyến hợp lý hay không.

### Kịch bản 2 – Một tuyến bị ùn tắc

Tăng số phương tiện trên một số cạnh.

Mục đích: kiểm tra khả năng tránh tuyến tắc.

### Kịch bản 3 – Ùn tắc xuất hiện đột ngột

Một phương tiện đang đi theo:

```text
A → B → C → F → I
```

Trong quá trình chạy:

```text
C → F
```

bị ùn tắc.

ACO phải tìm đường mới, ví dụ:

```text
C → B → E → H → I
```

### Kịch bản 4 – Đường bị đóng

Đặt một cạnh không còn khả dụng.

Kiểm tra khả năng tìm tuyến thay thế.

### Kịch bản 5 – Lưu lượng giao thông cao

Tăng dần số phương tiện nhằm kiểm tra khả năng của thuật toán trong môi trường ùn tắc nghiêm trọng.

---

## 10. Hướng mở rộng điều khiển đèn giao thông

Sau khi hoàn thành định tuyến, đề tài có thể mở rộng thêm điều khiển tín hiệu giao thông.

Ví dụ:

```text
Bắc → Nam : 12 xe
Nam → Bắc : 15 xe

Đông → Tây: 42 xe
Tây → Đông: 38 xe
```

Hệ thống có thể tăng thời gian đèn xanh cho hướng Đông–Tây.

SUMO cho phép thông qua TraCI thay đổi phase, thời gian còn lại của phase hoặc toàn bộ chương trình tín hiệu khi simulation đang chạy.

Tuy nhiên, điều khiển đèn nên được xem là giai đoạn mở rộng sau khi hệ thống định tuyến hoạt động ổn định.

---

## 11. Kết quả dự kiến

Đề tài dự kiến xây dựng được:

1. Mạng giao thông được mô phỏng bằng SUMO.
2. Module thu thập trạng thái giao thông bằng TraCI.
3. Mô hình đồ thị giao thông có trọng số động.
4. Dijkstra/A* làm thuật toán đối chứng.
5. ACO cơ bản.
6. Traffic-Aware ACO.
7. Cơ chế phát hiện ùn tắc.
8. Cơ chế tái định tuyến.
9. Hệ thống thực nghiệm và thống kê kết quả.
10. Khả năng mở rộng sang điều khiển đèn giao thông.

---

## 12. Kết luận

Trọng tâm nghiên cứu của đề tài không phải chứng minh ACO tốt hơn Dijkstra trong bài toán tìm đường tĩnh.

Đóng góp chính nằm ở việc xây dựng một **ACO thích nghi với trạng thái giao thông động**, trong đó chi phí cạnh được cập nhật từ dữ liệu mô phỏng thực tế.

Mô hình nghiên cứu tổng thể là:

```text
SUMO
  ↓
Dữ liệu giao thông
  ↓
Đồ thị động
  ↓
ACO
  ↓
Tuyến tối ưu
  ↓
SUMO
  ↓
Đánh giá
```

Nếu phát triển tốt, đề tài có thể mở rộng thành:

> **Hệ thống điều hướng và điều khiển giao thông thông minh sử dụng giải thuật đàn kiến thích nghi trên môi trường mô phỏng SUMO.**