# SUMO theo thời gian và ACO — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mô phỏng toàn mạng OSM, dùng bộ số liệu SUMO theo chu kỳ do người dùng đặt để điều hướng đúng một xe ACO và đo kết quả với một xe đối chứng.

**Architecture:** Hoàn thiện lõi Python/SUMO trước, sau đó nối web với cùng session. Một worker sở hữu TraCI; mỗi snapshot giao thông đầy đủ tạo đúng một kết quả ACO có cùng snapshot_id khi đến thời điểm yêu cầu xuất phát lần đầu hoặc xe đang chạy; chờ chèn xe/đã kết thúc thì công bố lý do không solve. Dữ liệu chuyển động và kết quả đo được lưu riêng từng phiên.

**Tech Stack:** Python, SUMO/TraCI/sumolib, lõi OSMAntColonyOptimizer hiện có, Flask, Leaflet, pytest hoặc unittest và Node test có sẵn; không thêm dependency.

**Spec:** docs/superpowers/specs/2026-10-28-sumo-aco-design.md

**Status:** Dự thảo để duyệt trước triển khai. Chỉ tài liệu được tạo trong lượt này; không chạy các bước implementation phía dưới.

## Global Constraints

- Chu kỳ T do người dùng đặt theo giây mô phỏng; 180 giây chỉ là ví dụ, không là giá trị cố định hay mặc định bắt buộc.
- Đúng một xe ACO, một xe đối chứng và nhiều xe nền; không tự sinh thêm xe so sánh sau mỗi 30 giây.
- Thay đổi nhu cầu đầu vào, không đặt giả số xe/tốc độ/ùn tắc đầu ra; một snapshot không trộn trạng thái trước/sau bước SUMO.
- Lõi kiến sống không dùng Dijkstra để tạo nghiệm tốt nhất ban đầu; giữ các caller cũ tương thích.
- Tìm phần đường còn lại từ vị trí thực, theo chuyển hướng được phép; giữ tuyến hợp lệ nếu không có tuyến tốt hơn.
- Dùng cùng số liệu để so chi phí tuyến cũ/mới; kết quả đo chuyến đi phải tách khỏi ước tính.
- Một worker sở hữu TraCI; request HTTP chỉ đọc snapshot hoặc gửi lệnh đã kiểm tra.
- Không thêm dependency; không sửa các file mạng/luồng xe đã sinh hoặc runner thí nghiệm cũ; không commit/push khi chưa được yêu cầu.
- Không ghi đè output cũ; không làm điều khiển đèn, dự đoán đèn đỏ, sự cố hoặc API giao thông thực tế trong giai đoạn này.

## Review Focus

1. Giá trị T/nhu cầu không hợp lệ hoặc snapshot lỗi không được phát sinh quyết định định tuyến sai.
2. Cạnh song song, cấm rẽ, cạnh nội bộ và OD không nối được không được tạo tuyến SUMO từ chối.
3. Thêm xe phải tuân thủ khả năng chèn; chế độ mới không được làm biến mất hàng đợi cũ.
4. Reconnect/polling/start trùng không được nhân đôi worker, snapshot solve hoặc xe thử nghiệm.
5. Xe chưa xuất phát/chưa hoàn thành/teleport không được báo là đến đích hoặc được tính như một chiến thắng của ACO.

## File map và giao diện dùng chung

Tạo scripts/core/live_routing.py (đồ thị hợp lệ, snapshot → chi phí → tuyến), live_demand.py (lịch nhu cầu), live_simulation.py (session, lịch, số đo và kết quả), scripts/osm/live_runner.py (CLI mỏng). Chỉ sửa core/osm_graph.py để nhận RNG tùy chọn cho lõi kiến. Sau đó sửa scripts/run_google_maps_sim.py, web/js/app.js, map_controller.js, web/index.html và README; CSS chỉ sửa phần cần để hiển thị thông tin mới.

Các đường dẫn ở đây tính từ traffic-simulation/ trừ tài liệu thiết kế/kế hoạch.

Run options: origin_edge: str, destination_edge: str, update_interval_s: int > 0, extra_flow_vph: float > 0, duration_s: int > update_interval_s (đề xuất mặc định 3600, tính từ t=0 gồm warm-up), seed: int (đề xuất mặc định 42). Hai trường T/nhu cầu phải được nhập, không tự lấy 180 hay 600. SUMO và nhu cầu dùng seed; RNG ACO riêng dùng seed+1.

Snapshot: run_id, snapshot_id, nominal_time, traffic_time, complete, edges keyed by edge_id. Edge record: length_m, vehicles, halting, waiting_s, mean_speed_ms, travel_time_s, observed, stale, points. Kết quả ACO: snapshot_id, source_edge, destination_edge, candidate_edges, applied, reason, elapsed_ms. Các lần đo lỗi chỉ cập nhật traffic_attempt_time/data_status, giữ snapshot_id/traffic_time cũ. Đơn vị trong lõi là m, m/s và giây mô phỏng.

### Task 1: Đồ thị định tuyến hợp lệ và cấu hình

**Files:** Create scripts/core/live_routing.py, tests/test_live_routing.py; modify scripts/core/osm_graph.py.

**Interfaces:** build_live_graph(net) trả adapter dùng edge_id làm nút và chỉ nối legal passenger turns. validate_options(options: dict) trả dict đã kiểm tra. plan_route(graph, snapshot, source_edge, destination_edge, current_route, rng) trả kết quả như schema trên. OSMAntColonyOptimizer nhận rng=None, giữ hành vi cũ khi bỏ qua.

- [ ] Viết test RED: các T=0,-1,True,NaN và nhu cầu thiếu/không dương bị từ chối; T=37 hợp lệ. Cạnh song song vẫn riêng; cấm rẽ bị loại; không tồn tại tuyến thì trả lý do rõ ràng, không ném tuyến giả.
- [ ] Chạy python -m pytest tests/test_live_routing.py -q và xác nhận thất bại vì hành vi chưa có.
- [ ] Tạo adapter bằng sumolib cùng net.xml; tái sử dụng công thức chi phí 0,2/0,3/0,3/0,2 và lõi kiến với seed_with_dijkstra=False. Chỉ thêm RNG riêng, không viết lại ACO.
- [ ] Test giá trị chi phí tính từ fixture độc lập; dữ liệu stale không tạo quyết định mới; tuyến mới phải từ source thật và tốt hơn current_route trên cùng snapshot.
- [ ] Test hai RNG có cùng seed cho cùng chuỗi kiến; các caller cũ không truyền rng vẫn dùng được. Chạy test routing và các self-test core hiện có; ghi lại kết quả.

### Task 2: Nhu cầu ngẫu nhiên theo giai đoạn

**Files:** Create scripts/core/live_demand.py, tests/test_live_demand.py.

**Interfaces:** DemandSchedule(net, route_pool, update_interval_s, extra_flow_vph, rng); choose_regime(begin_time) trả {begin_time,end_time,mode,target_edge,route_edges,extra_flow_vph}; due_departures(sim_time) trả các chuyến đã đến thời điểm yêu cầu sinh. Session là nơi gọi TraCI để thực hiện các chuyến đó.

- [ ] Viết RED với mạng nhỏ, pool tuyến được kiểm tra legal: chọn chế độ nền hoặc tăng nhu cầu theo RNG riêng; đoạn tăng nhu cầu nằm trong top 25% theo chiều dài và có tuyến hợp lệ đi qua.
- [ ] Kiểm tra cùng seed cho cùng lịch; thay số kiến không làm thay lịch; fixture extra_flow_vph=600 tạo khoảng cách yêu cầu sinh 6 giây, không có suy luận 600 xe hiện diện.
- [ ] Chạy test và xác nhận RED; triển khai lịch tối thiểu, giữ file xe nền hiện có. Các tuyến bổ sung phải tồn tại/được đăng ký trước khi vehicle.add.
- [ ] Khi hết giai đoạn, dừng yêu cầu sinh thêm từ chế độ cũ nhưng không remove xe đang chạy; không ghi speed/vehicle count của snapshot. Nếu không có đoạn đủ điều kiện, ghi chế độ nền và lý do.
- [ ] Chạy test GREEN. Không assert "đường chắc chắn tắc" từ số xe yêu cầu; chỉ assert lịch đầu vào và tính hợp lệ.

### Task 3: Session SUMO, một cặp xe và kết quả đo

**Files:** Create scripts/core/live_simulation.py, scripts/osm/live_runner.py, tests/test_live_simulation.py.

**Interfaces:** LiveSimulation.start(options), stop(), snapshot(). Lõi dùng adapter Task1 và DemandSchedule Task2; snapshot() chỉ trả bản sao trạng thái được publish. CLI nhận --origin-edge, --destination-edge, --update-interval, --extra-flow, --duration, --seed và gọi cùng session.

- [ ] Viết RED cho timeline T=37: khi đọc đủ dữ liệu, ACO đầu tiên tại giây 37, tiếp theo 74 nếu xe đang chạy; đổi nhu cầu sau khi xử lý mốc, chỉ ảnh hưởng xe trong giai đoạn tới. Với dt=0,7, nominal_time vẫn là 37/74, traffic_time là 37,1/74,2; không tích lũy trễ mốc và không dựa step += 1. Không sinh chế độ ngoài duration_s; cắt giai đoạn cuối tại thời điểm kết thúc.
- [ ] Viết test rằng mỗi snapshot_id đầy đủ có một solve trước xuất phát lần đầu hoặc trong giai đoạn xe đang chạy; chờ chèn xe/đã đến/teleport/bị loại thì có reason và không solve. Test lỗi đọc tại37 giữ cả hai xe chưa tạo; đọc đủ tại74 tạo đúng hai xe cùng requested_depart_time=74 và solve một lần; hết phiên trước khi đọc đủ thì báo not_started.
- [ ] Viết test giữa hai mốc: telemetry_time/vị trí xe tăng sau bước, còn snapshot_id/traffic_time/edge measurements/solve identity giữ nguyên; HTTP reads và telemetry không phát sinh solve. Lỗi đo giữ trạng thái stale và không đổi tuyến.
- [ ] Chạy RED rồi triển khai một worker: khởi động SUMO, subscribe các số liệu, mô phỏng nền ít nhất một chu kỳ T, chờ bộ dữ liệu đầy đủ đầu tiên và chạy ACO lần đầu; tạo đúng cặp live_aco/live_control với cùng loại và điều kiện yêu cầu xuất phát ở thời điểm đó. Sau mỗi bước publish telemetry nhưng chỉ đổi số đo giao thông/solve theo các mốc T.
- [ ] Tại mỗi mốc, cập nhật đồ thị rồi tìm từ cạnh hiện tại; đảm bảo tuyến bắt đầu ở đó và đúng quyền rẽ. Xe trong giao lộ: giải ngay từ cạnh thường kế tiếp đã cam kết theo route/index, lưu pending_candidate {snapshot_id,source_edge,candidate_edges}; chỉ hoãn áp, không hoãn hay nhân đôi solve. Chỉ áp khi source trùng cạnh thực tế và ứng viên mới nhất còn hợp lệ/cải thiện trên cùng snapshot. Snapshot mới thay pending cũ; đã đi qua source thì bỏ ứng viên và ghi lý do. Viết test cho chờ áp, thay pending và bỏ ứng viên quá hạn.
- [ ] Test giữ nguyên tuyến khi ứng viên kém/không hợp lệ/không tìm thấy. Test xử lý internal lane, giữ vị trí sau arrival và không bỏ qua teleport/removal.
- [ ] Lưu run_id riêng và metadata/demand_events/edge_snapshots/routing_log/tripinfo/comparison theo spec. Bật ghi chuyến chưa hoàn tất; không kết thúc phiên chỉ vì hiện không còn xe nếu lịch nhu cầu tương lai còn hoạt động.
- [ ] Test duration/waiting/departDelay và trạng thái dở dang độc lập với chi phí ước tính; không ép kết quả ACO thắng. Kiểm tra start/stop/restart và cleanup tiến trình, không ghi đè file cũ.
- [ ] Chạy tích hợp SUMO thật: có xe nền, có số đo, có đúng hai xe đánh giá; một case có đường tránh và đổi tuyến thực, một case không đổi. Dùng route assertions theo hành vi hợp lệ, không cố định đường ngẫu nhiên duy nhất.

### Task 4: Nối web hiện có với lõi đã kiểm chứng

**Files:** Modify scripts/run_google_maps_sim.py, web/js/app.js, web/js/map_controller.js, web/index.html, web/css/style.css khi cần; create tests/test_live_api.py, tests/test_live_web.js.

**Interfaces:** create_app(simulation=None); GET /api/state; POST /api/start {origin,destination,update_interval_s,extra_flow_vph,duration_s,seed}; POST /api/stop. start chuyển tọa độ A/B thành cạnh xe con hợp lệ, kiểm tra trước khi thay phiên đang chạy. API có status, sim_time, telemetry_time, traffic_time, snapshot_id, data_status, cars, edges, routes, aco_result, demand_regime và kết quả đo. Status phiên/xe theo spec; polling chỉ làm mới hiển thị, không chạy giải thuật.

- [ ] Viết RED cho JSON không hợp lệ, T/nhu cầu thiếu, điểm ngoài mạng hoặc OD không nối; một lệnh start sai không được làm hỏng phiên đang chạy.
- [ ] Nối Flask vào cùng session, bind loopback và đóng worker khi máy chủ dừng. Không gọi TraCI từ request thread, không cho polling kích hoạt lại thuật toán.
- [ ] Node test RED: hai lần poll cùng snapshot không chạy thuật toán; khi sim_time tăng mà traffic_time chưa đổi, giao diện vẫn ghi đúng thời điểm dữ liệu cũ. Mất kết nối không tự di chuyển xe hoặc tạo số đo giả.
- [ ] Thay nguồn RealRoadEngine/OSRM bằng snapshot SUMO; giữ thành phần bản đồ. Hiển thị toàn mạng theo mã đoạn, vị trí thực, A/B, T, luồng bổ sung, seed, trạng thái chạy nền/đang chạy/hoàn thành/lỗi. Ẩn chức năng sự cố/đèn và nút tua tốc độ chưa nối API trong chế độ này.
- [ ] Hiển thị số liệu chưa có quan sát/stale rõ ràng. Số đo chuyến đi, ước tính tuyến và thời gian chờ trước xuất phát phải có nhãn riêng; chưa đủ hai kết quả hoàn thành thì không tính phần trăm tiết kiệm.
- [ ] Browser-check chọn A/B, nhập T tùy ý, chạy/dừng/chạy lại, thời điểm traffic_time/snapshot_id/ACO tương ứng, màu số đo và kết quả cả trường hợp ACO chậm hơn.
- [ ] Chạy python -m pytest tests/test_live_api.py -q; node --test tests/test_live_web.js; node --check các JS đã đổi. Kiểm tra request trùng không tạo worker/xe trùng.

### Task 5: Kiểm chứng tổng thể và tài liệu sử dụng

**Files:** Modify traffic-simulation/README.md, cập nhật tiến độ trong kế hoạch này; giữ báo cáo kiểm thử bên ngoài code ứng dụng hoặc dưới output/runs/.

- [ ] Chạy toàn bộ Python tests, Node tests, các core self-test và kiểm tra syntax; báo rõ mọi test đỏ, không chỉ test vừa viết.
- [ ] Chạy ít nhất hai T khác 180 (37 và 90), kiểm tra số lần solve ứng với snapshot_id và việc kết thúc chuyến; đọc số liệu trên toàn mạng hiện có.
- [ ] Chạy hai lượt cùng seed/đầu vào và so lịch nhu cầu đã lưu; dùng cùng luồng nền và điều kiện cho đối chứng/ACO. Ghi nhận thời gian đọc snapshot và tính ACO, chưa cam kết chạy ngang tốc độ đồng hồ thật.
- [ ] Kiểm tra một tình huống tăng nhu cầu tạo hàng đợi đo được; nếu không tạo được thì báo kết quả và hiệu chỉnh đầu vào, không đổi màu/giá trị để làm giả kết quả.
- [ ] Review độc lập toàn bộ diff, giải quyết lỗi ảnh hưởng chức năng và chạy lại đúng các kiểm tra bị tác động.
- [ ] Cập nhật lệnh chạy CLI/web, ý nghĩa T và warm-up T, ý nghĩa extra_flow_vph, trạng thái dữ liệu và file đầu ra. Giải thích giới hạn một cặp xe, mô phỏng chưa hiệu chỉnh ngoài đời, và phần đèn đỏ để sau.

## Tự rà soát và quyết định còn cần xác nhận

- Các ràng buộc về thời gian, nguồn số liệu, số xe so sánh, đường hợp lệ, tính ngẫu nhiên và kết quả đo đều có task/test sở hữu.
- Cùng schema và tên trường được dùng từ Task1 đến Task4; code legacy không bị đổi hành vi trừ tham số RNG tùy chọn.
- Cần người dùng xem các đề xuất trong mục4 của spec: dùng chung T, warm-up một chu kỳ T, xác định đoạn dài bằng top25%, nhập mức tăng nhu cầu, đối chứng giữ tuyến và phạm vi bản đồ mỗi phiên.
- Kế hoạch chỉ mô tả triển khai giai đoạn đầu. Chưa có bước dự đoán thời gian đèn đỏ hoặc quản lý đèn; không tự thêm chúng trong khi thực hiện.
- Đã rà soát độc lập bản dự thảo và sửa các mâu thuẫn về nguồn giải khi xe ở giao lộ, dữ liệu đầu tiên không đầy đủ, telemetry giữa các mốc T, mốc danh nghĩa so với thời gian đo thực, và trạng thái chuyến chưa bắt đầu/đã kết thúc. Đây là rà soát tài liệu, chưa phải kiểm chứng code chạy.
