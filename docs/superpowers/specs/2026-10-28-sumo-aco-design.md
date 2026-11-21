# Thiết kế dự thảo: SUMO theo thời gian → dữ liệu → ACO

Ngày: 28/10/2026. Trạng thái: để người dùng xem trước khi triển khai; chưa được coi là code đã có.

## 1. Mục tiêu và phạm vi đã thống nhất

- Dùng toàn bộ mạng đường SUMO của bản đồ OSM đang chọn để mô phỏng giao thông theo thời gian.
- Lấy số liệu thực sự do SUMO tính, rồi dùng ACO tìm tuyến hiệu quả cho một xe.
- Có đúng một xe ACO, một xe đối chứng và các xe nền. Xe đối chứng giữ tuyến ngắn theo khoảng cách được chọn ban đầu.
- Luồng xe nền có thể thay đổi ngẫu nhiên theo từng giai đoạn; có giai đoạn tăng nhu cầu đi qua một đoạn đường dài.
- Mỗi lần công bố bộ dữ liệu giao thông đầy đủ mới cho thuật toán phải chạy ACO ngay sau khi cập nhật xong cả bộ dữ liệu đó, khi xe đang hoạt động. Lần đầu tính trước khi yêu cầu xuất phát; xe chưa vào được mạng/đã kết thúc hoặc bị teleport có trạng thái rõ ràng, không giải bài toán từ một vị trí không tồn tại.
- Chu kỳ T do người dùng đặt theo giây mô phỏng; 180 giây chỉ là ví dụ, không là giá trị cố định hay mặc định bắt buộc.
- Đo thời gian chuyến đi và thời gian chờ của hai xe để nhận xét ACO tốt hơn, tương đương hoặc kém hơn.
- Chưa làm dự đoán thời gian chờ đèn đỏ, điều khiển đèn, quản lý giao thông toàn mạng hay lấy dữ liệu giao thông ngoài đời.

"Toàn bộ bản đồ" trong bản dự thảo là toàn bộ mạng đường được nạp trong một phiên, không phải ghép nhiều mạng độc lập thành một bản đồ. Trước hết kiểm chứng trên osm/map2.net.xml hiện có; các mạng khác phải có cấu hình, nhu cầu xe và hình học tương ứng.

## 2. Hiện trạng đã kiểm tra

- Workspace sạch tại HEAD 72cbde2 sau revert; chưa có live_simulation.py hoặc cầu nối web–SUMO.
- osm_runner.py đã chạy SUMO, đọc TraCI, cập nhật đồ thị và gọi ACO trong cùng phiên. Hiện cập nhật mỗi bước, tìm lại mặc định mỗi 60 giây, sinh thêm xe ACO mỗi 30 giây.
- ACO hiện giải từ OD ban đầu và chỉ đổi xe còn nằm trên tuyến chung mới; chưa đáp ứng một xe đang đi trên bất kỳ đoạn hợp lệ nào.
- OSMTrafficGraph gộp dữ liệu theo cặp nút, có thể mất cạnh song song và chưa biểu diễn đầy đủ hạn chế rẽ.
- OSMAntColonyOptimizer mặc định nhận nghiệm Dijkstra làm tuyến tốt nhất ban đầu. Không được dùng kết quả đó để kết luận hiệu quả ACO độc lập.
- map2.rou.xml chứa 1.800 chuyến lập lịch trong một giờ, do randomTrips tạo; chưa có thay đổi nhu cầu cục bộ theo chu kỳ khi đang chạy.
- Web hiện dùng RealRoadEngine và chuyển động JavaScript; các số liệu đó chưa lấy trực tiếp từ SUMO.

## 3. Cách triển khai được đề xuất

Phương án đề xuất: hoàn thiện lõi Python/SUMO và kiểm chứng bằng lệnh trước; sau đó nối web hiện có với cùng lõi. Cách này cho phép xác minh số liệu, tuyến và kết quả mà không bị phụ thuộc giao diện.

Phương án khác đã cân nhắc: sửa web và vòng SUMO đồng thời. Tích hợp nhìn thấy sớm hơn, nhưng khó xác định lỗi thuộc mô phỏng hay giao diện. Bản kế hoạch chọn thứ tự lõi trước, web sau để giảm phần phải làm lại; đây là đề xuất kỹ thuật, chưa phải lựa chọn người dùng đã xác nhận.

Tái sử dụng Python, SUMO/TraCI/sumolib, OSMAntColonyOptimizer, Flask và Leaflet. Không thêm thư viện, cơ sở dữ liệu, dịch vụ ngoài hoặc sửa các runner thí nghiệm cũ để phục vụ luồng mới.

## 4. Các lựa chọn đề xuất cần người dùng xem

- Cùng một T điều khiển đổi chế độ nhu cầu và công bố dữ liệu cho ACO; chưa thêm hai chu kỳ độc lập.
- T và extra_flow_vph (nhu cầu thêm khi chọn chế độ đông) là đầu vào bắt buộc khi bắt đầu. Không tự gán T=180 hoặc gắn một lưu lượng cố định với một mức ùn tắc.
- Dùng nền map2.rou.xml hiện có. Mỗi giai đoạn chọn một trong hai chế độ: giữ nền (ít hơn tương đối) hoặc thêm luồng qua một đoạn dài. Hai chế độ có xác suất bằng nhau và có seed để chạy lại.
- "Đoạn dài" là 25% đoạn xe con dài nhất có ít nhất một tuyến sinh xe hợp lệ đi qua. Không coi chiều dài là bằng chứng sẽ tắc.
- Chạy xe nền trước một chu kỳ T, sau đó mới cho hai xe so sánh yêu cầu xuất phát. Đây là đề xuất để lần đầu ACO có dữ liệu đã quan sát; không cần đợi hết cả phiên.
- Chọn seed ban đầu 42 để có thể lặp lại. SUMO và RNG nhu cầu dùng seed, RNG ACO dùng seed+1; hai bộ sinh số Python độc lập. Việc kiến thử nhiều đường không được làm thay đổi lịch xe nền.
- Giữ các trọng số chi phí hiện tại: khoảng cách 0,2; thời gian đi 0,3; số xe 0,3; thời gian chờ 0,2. ACO sống dùng seed_with_dijkstra=False; Dijkstra chỉ tạo tuyến đối chứng/ban đầu hợp lệ.
- Chỉ đổi sang tuyến hợp lệ có chi phí mới thấp hơn tuyến còn lại hiện tại trên cùng bộ số liệu; không mang ngưỡng 5% của kế hoạch cũ vào yêu cầu mới.

Các tham số về nhu cầu có thể cần hiệu chỉnh qua thí nghiệm. Mức "tăng nhu cầu" là đầu vào, không tự động được gọi là "ùn tắc nặng" ở đầu ra.

## 5. Luồng chạy và thứ tự thời gian

1. Người dùng chọn A/B, T, extra_flow_vph, thời lượng phiên và seed; kiểm tra các giá trị và tuyến hợp lệ.
2. Nạp mạng đường, luồng nền và hình học cùng mã đoạn đường; chọn chế độ nhu cầu cho giai đoạn [0,T).
3. SUMO chạy theo từng bước. Lịch nhu cầu chỉ thêm các chuyến có đường đi hợp lệ; nếu không thể chèn xe thì để SUMO chờ, không ép chồng xe.
4. Tại bước SUMO đầu tiên đạt mốc danh nghĩa T: thử đọc đủ số liệu cho toàn mạng. Lần đầu đọc đủ, gắn snapshot_id=1, nominal_time bằng mốc kT của lần đọc thành công (có thể là 2T nếu lần trước lỗi) và traffic_time bằng thời gian đo thực; tạo đồ thị chi phí, tính ACO lần đầu và chuẩn bị hai xe. Hai xe cùng yêu cầu xuất phát ở thời điểm đo thực này, cùng loại xe và thiết lập. Nếu lần đọc đầu không đủ, chưa tạo cả hai xe và giữ warming; thử lại tại mốc danh nghĩa kế tiếp. Nếu hết phiên vẫn chưa có bộ dữ liệu đầy đủ thì báo hai chuyến chưa bắt đầu, không có kết quả so sánh.
5. Xe đối chứng giữ tuyến ngắn theo khoảng cách. Xe ACO dùng tuyến ACO tìm được; nếu chưa tìm được tuyến thì giữ tuyến ban đầu hợp lệ và ghi rõ lý do.
6. Sau khi xử lý mốc T, chọn nhu cầu cho giai đoạn tiếp theo [T,2T), kể cả khi lần đo tại mốc đó thất bại. Khi bước mô phỏng không trùng mốc, bắt đầu chế độ mới ở bước thực tế vừa đạt mốc; không chèn lại xe vào thời điểm quá khứ. Nhu cầu mới chưa được coi là tốc độ hay hàng đợi đã đo.
7. Tại t=2T,3T,...: đọc một bộ số liệu mới, cập nhật toàn bộ đồ thị, gọi ACO đúng một lần nếu xe còn đang hoạt động, kiểm tra và áp tuyến; sau đó chọn nhu cầu cho giai đoạn tiếp theo.
8. ACO luôn giải phần đường còn lại đến đích cố định. Khi xe trên cạnh thường, giải từ cạnh hiện tại. Khi xe đang trong giao lộ, xác định cạnh thường kế tiếp mà xe đã cam kết đi theo route/index, giải ngay từ cạnh đó và lưu pending_candidate kèm snapshot_id/source_edge. Chỉ hoãn áp tuyến đến khi xe thực sự ở cạnh source; không tính ACO thêm vì việc áp bị hoãn. Snapshot mới thay pending cũ; nếu xe đã đi qua source hoặc không xác định được cạnh kế tiếp thì ghi lý do và giữ tuyến. Trước khi áp, kiểm tra tuyến còn hợp lệ, bắt đầu bằng cạnh thực tế và còn cải thiện so với tuyến đang đi trên cùng snapshot.
9. Khi xe về đích hoặc bị loại/teleport, giữ trạng thái rõ ràng; không tự sinh thêm xe so sánh. Hết thời lượng thì lưu cả kết quả chưa hoàn thành.

T luôn tính bằng simulation.getTime(), không dựa vào số lần vòng lặp hay đồng hồ máy. Nếu T không chia hết cho bước mô phỏng thì lấy bước đầu tiên đạt mốc, không phát lại nhiều lần ACO trên một trạng thái.

Thời lượng phiên tính từ t=0, bao gồm giai đoạn chạy nền; phải lớn hơn T. Không tạo chế độ nhu cầu mới sau thời điểm kết thúc, và cắt end_time của giai đoạn cuối tại duration_s.

Khi đổi chế độ, các xe đã xuất hiện tiếp tục chạy; chỉ thay lịch xe mới. Ảnh hưởng của luồng mới được quan sát ở những bước và snapshot tiếp theo. Không sửa trực tiếp số xe, tốc độ hoặc màu đường để giả làm kết quả SUMO.

## 6. Ràng buộc dữ liệu và thuật toán

- Đồ thị cho ACO dùng edge_id SUMO làm nút và chỉ nối các chuyển hướng hợp lệ cho xe con, để giữ cạnh song song và hạn chế rẽ.
- Tái sử dụng lõi kiến; bổ sung RNG tùy chọn, mặc định giữ hành vi cũ của các caller hiện có.
- Mỗi snapshot đầy đủ có run_id, snapshot_id tăng dần theo số bộ dữ liệu đầy đủ, nominal_time=kT, traffic_time là thời gian đo thực và bản ghi đầy đủ cho các đoạn thường được xe con phép đi. Các mốc kT không được dời theo thời điểm đo trễ của mốc trước.
- Số xe, xe dừng, tốc độ, thời gian chờ, thời gian đi phải đọc từ TraCI. Đoạn chưa có xe được ghi là chưa có quan sát/ước tính, không ghi như một số đo tốc độ thực tế.
- Không âm thầm giữ số liệu cũ như số liệu mới khi đọc lỗi: giữ last-known với cờ stale, giữ nguyên snapshot_id/traffic_time và ghi traffic_attempt_time cho lần thử lỗi; không thực hiện quyết định mới từ dữ liệu không đầy đủ.
- Lần đầu có bộ dữ liệu đầy đủ: solve đúng một lần từ origin rồi yêu cầu cả hai xe xuất phát. Sau đó mỗi snapshot đầy đủ khi xe ACO đang chạy: solve đúng một lần từ cạnh hiện tại/cạnh kế tiếp đã cam kết. Khi đang chờ SUMO chèn xe: aco_status=awaiting_departure, không solve thêm. Khi đến đích/teleport/bị loại/hết phiên: publish lý do, không solve và không tự tạo chuyến mới. Các ngoại lệ này là trạng thái của vòng đời, không phải một snapshot bị tính lặp.
- Một worker duy nhất sở hữu TraCI. Browser polling, tab reconnect và vẽ lại bản đồ không được làm chạy ACO thêm lần nữa.
- Trong giao lộ không lấy lanePosition của cạnh nội bộ trừ vào chiều dài cạnh thường; ước tính còn lại phải tách hoặc bỏ phần cạnh thường đã hoàn tất.

## 7. So sánh và lưu kết quả

Hai xe cùng OD, loại xe, tham số xe và thời điểm yêu cầu xuất phát trong cùng phiên. Khác biệt duy nhất về chính sách định tuyến: đối chứng giữ tuyến, ACO được điều chỉnh. Lưu thời điểm xuất phát thực, đến đích, duration, waitingTime, departDelay, timeLoss và trạng thái hoàn thành; thời gian ước tính tuyến phải tách khỏi kết quả đo.

Lưu riêng output/runs/<run_id>/ gồm metadata.json, demand_events.csv, edge_snapshots.csv, routing_log.csv, tripinfo.xml và comparison.csv. Metadata lưu đường dẫn/dấu nhận diện mạng, cấu hình, OD, T, extra_flow_vph, thời lượng, trọng số, tham số ACO và các seed. Không ghi đè output thí nghiệm cũ.

Không tuyên bố ACO luôn tốt hơn, không dùng chi phí tuyến tại một snapshot thay cho thời gian chuyến đi, và không biến xe chưa đến đích/teleport thành một chuyến hoàn thành bình thường. Kết quả của một cặp xe là minh họa ban đầu; đánh giá tổng quát cần các lượt chạy lặp sau đó.

## 8. Web sau khi lõi đã đúng

Giữ bản đồ Leaflet và cách hiển thị hiện có. Python/Flask cung cấp trạng thái đo và nhận lệnh chọn A/B, T, nhu cầu, chạy/dừng/chạy lại; web không gọi RealRoadEngine để tự tạo số liệu hay tự tính tuyến OSRM cho thí nghiệm này.

GET /api/state trả sim_time/telemetry_time hiện tại, traffic_time của bộ số liệu gần nhất, snapshot_id, trạng thái xe, kết quả ACO, dữ liệu đoạn đường và trạng thái phiên. telemetry_time đổi khi có vị trí/trạng thái xe mới, còn traffic_time/snapshot_id chỉ đổi khi lấy bộ số liệu giao thông theo T. status phiên là idle/warming/running/completed/stopped/error; trạng thái xe là not_started/pending/running/arrived/teleporting/removed/unfinished. not_started là bản ghi chuyến dự kiến chưa được tạo trong SUMO, phân biệt với pending đã yêu cầu sinh nhưng chưa chèn được. Web có thể đọc mỗi giây đồng hồ để xem vị trí xe; việc này không đổi chu kỳ T và không kích hoạt thuật toán. Phải hiển thị thời điểm dữ liệu giao thông để người xem không nhầm số liệu cũ là vừa cập nhật.

Worker publish telemetry sau mỗi bước SUMO. Giữa hai mốc T, telemetry chỉ đổi sim_time/telemetry_time, vị trí, trạng thái, kết quả chuyến đi và kết quả áp pending; giữ nguyên traffic_time, snapshot_id, số đo đoạn đường và danh tính kết quả solve. Một pending được áp có thể cập nhật applied/reason/route đang chạy mà không biến thành kết quả solve mới. HTTP polling chỉ sao chép trạng thái đã publish.

Không có tính năng cắm sự cố hoặc thay đèn trong phạm vi giai đoạn đầu. Các nút cũ tương ứng, cũng như nút tua tốc độ chưa được nối API, cần ẩn trong chế độ SUMO trực tiếp. Chưa đặt yêu cầu nhịp mô phỏng phải bằng nhịp đồng hồ thực.

## 9. Tiêu chí kiểm chứng trước khi hoàn thành giai đoạn đầu

- Toàn mạng được đọc đúng mã đoạn và số đo, không dùng số liệu JavaScript tự sinh.
- T khác nhau như 37 và 90 giây cho đúng lịch, không có hằng 180 bắt buộc.
- Mỗi snapshot đầy đủ kích hoạt đúng một ACO trước xuất phát lần đầu hoặc khi xe đang chạy; chờ chèn xe/đã kết thúc/teleport ghi lý do mà không solve theo vòng đời ở mục6. Refresh web không kích hoạt thêm.
- Đúng một xe ACO và một xe đối chứng; tuyến mới thực sự được SUMO chấp nhận từ vị trí hiện tại.
- Đổi nhu cầu chỉ sinh các chuyến tương lai hợp lệ, không xóa xe đang đi hoặc sửa trực tiếp số đo.
- Cùng seed cho cùng lịch nhu cầu; đổi số kiến không làm đổi lịch đó.
- Đo và lưu kết quả thật, bao gồm chuyến chưa hoàn thành và thời gian chờ trước xuất phát.
- Đã chạy thử một tình huống có đường tránh hợp lệ và ghi nhận đổi tuyến thực; thử cả trường hợp giữ tuyến vì không cải thiện.
- Dừng/chạy lại không để sót tiến trình SUMO, không ghi đè dữ liệu cũ.
- Chưa đặt cam kết hiệu năng toàn bản đồ trước khi đo thời gian lấy dữ liệu và thời gian tính ACO.
