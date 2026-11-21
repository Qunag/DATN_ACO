# SUMO trực tiếp và so sánh định tuyến — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Nối SUMO đang chạy với web và đánh giá công bằng ba chính sách: giữ tuyến ban đầu, Dijkstra thích nghi, ACO thích nghi, mỗi lượt đúng một xe đánh giá.

**Architecture:** Hoàn thiện lõi Python trước, web sau. Chuẩn bị một bundle nhu cầu cố định cho mỗi seed, chạy ba chính sách tuần tự trong các phiên SUMO sạch; một worker sở hữu TraCI và công bố dữ liệu cho CLI/web. So thuật toán trên cùng snapshot được thực hiện riêng sau mô phỏng, không ảnh hưởng chuyến đi.

**Tech Stack:** Python hiện có, SUMO/TraCI/sumolib, dijkstra_osm, OSMAntColonyOptimizer, Flask, Leaflet; unittest và Node built-in test. Không thêm dependency.

**Spec:** [2026-10-28-sumo-routing-comparison-design.md](../specs/2026-10-28-sumo-routing-comparison-design.md).

**Status:** Chỉ là kế hoạch để xem trước triển khai. Thay thế `2026-10-28-sumo-aco-implementation.md`; chưa chạy bất kỳ checkbox nào và chưa thay đổi ứng dụng.

## Global Constraints

- T do người dùng nhập, tính bằng giây mô phỏng; không mặc định bắt buộc 180 giây.
- Đề xuất: ba lượt riêng, mỗi lượt đúng một xe đánh giá và nhiều xe nền.
- Dijkstra thích nghi và ACO thích nghi dùng cùng đồ thị hợp lệ, hàm chi phí, bound, chu kỳ và quy tắc áp tuyến.
- ACO độc lập phải dùng seed_with_dijkstra=False, RNG riêng và không mang best_cost của snapshot cũ sang lần giải mới.
- Một worker duy nhất sở hữu kết nối TraCI; HTTP/polling chỉ đọc bản sao hoặc gửi lệnh đã kiểm tra.
- Không ghi đè output, route/network/dense đã có; giữ các runner cũ và caller cũ hoạt động.
- Không thêm dependency, không commit/push trong lượt lập kế hoạch; khi thực hiện phải kiểm tra lại yêu cầu tích hợp của người dùng.
- Chưa làm điều phối nhiều xe, dự đoán/điều khiển đèn, sự cố, API giao thông thật hoặc ép kết quả ACO phải thắng.

## Review Focus

1. Cạnh song song/cấm rẽ/OD không nối được: không trả tuyến SUMO từ chối; pin ở Task 1.
2. T/step không chia hết, snapshot lỗi lần đầu và lần sau: không dời requested_depart riêng từng chính sách hoặc giải lặp; pin ở Task 2–3.
3. RNG/flow chưa cụ thể/bundle bị đổi: không tuyên bố cùng nhu cầu khi lịch không khớp; pin ở Task 1–2 và 4.
4. Pending/junction/teleport/unfinished và ACO không có nghiệm: không tính thành chuyến thắng giả; pin ở Task 3–4.
5. Start trùng/polling muộn/đóng SUMO: không tạo worker trùng, trả trạng thái của run cũ hoặc ghi đè output; pin ở Task 3 và 5.

## File map và hợp đồng chung

Đường dẫn implementation bên dưới tính từ `D:/study/DATN/traffic-simulation/`. Tài liệu nằm ở `D:/study/DATN/docs/superpowers/`.

| File | Trách nhiệm |
|---|---|
| Tạo scripts/core/live_routing.py | Adapter edge_id/chuyển hướng, snapshot → chi phí → tuyến, benchmark cùng snapshot |
| Tạo scripts/core/live_demand.py | Kiểm tra options, đóng băng lịch nền + nhu cầu bổ sung, manifest/hash |
| Tạo scripts/core/live_simulation.py | Một worker, một xe/lượt, điều phối các lượt, số đo và kết quả ghép cặp |
| Tạo scripts/osm/live_runner.py | CLI mỏng: single/block/pilot và benchmark từ dữ liệu đã lưu |
| Sửa scripts/core/osm_graph.py | Chỉ bổ sung rng=None vào OSMAntColonyOptimizer, thay các random draw nội bộ |
| Sửa scripts/run_google_maps_sim.py | App factory, endpoint danh sách cạnh và start/state/stop dùng cùng LiveSimulation |
| Sửa web/js/app.js, map_controller.js, web/index.html | Nguồn dữ liệu SUMO, một xe, chọn chính sách và bảng kết quả ba lượt |
| Sửa README.md; CSS khi cần | Cách chạy mới, ý nghĩa chỉ số, giới hạn; bố cục vừa đủ |
| Tạo tests/test_live_*.py, tests/web_live.test.cjs | Kiểm chứng hành vi có rủi ro; không tính bytecode/cache cũ là test hiện có |

Không cần tạo framework, service mới hoặc module so sánh riêng: kết quả chuyến đi nằm cùng lifecycle; benchmark dùng adapter và hai hàm giải đã có. Giữ `real_road_engine.js` như file cũ không được nạp trong chế độ mới, không viết lại engine này.

Hợp đồng dữ liệu là dict JSON-compatible, dùng đơn vị m, m/s, s mô phỏng và ms tính toán:

- **options:** net_file, route_file, config_file, origin_edge, destination_edge, update_interval_s, extra_flow_vph, duration_s, environment_seed, aco_seed; các giá trị/điều kiện trong spec mục6. Thuộc tính xe mục tiêu và cấu hình kiến được cố định, ghi đầy đủ vào manifest.
- **bundle:** scenario_id, options, background_file, demand_events_file, initial_route, requested_depart, hashes. requested_depart là bước SUMO đầu tiên đạt T; bundle không phụ thuộc policy.
- **snapshot:** run_id, snapshot_id, nominal_time, traffic_time, complete, edges[edge_id]. Edge: length_m, max_speed_ms, vehicles, halting, waiting_s, mean_speed_ms, travel_time_s, observed, estimated, stale. Lỗi ghi traffic_attempt_time, giữ ID/thời gian bộ đầy đủ trước.
- **routing result:** policy, snapshot_id, source_edge, destination_edge, candidate_edges, score, solver_elapsed_ms, found, fallback_used, applied, reason. Không có nghiệm dùng null thay Infinity trong JSON.
- **trip result:** policy, requested_depart, actual_depart, arrival, departDelay, duration, elapsed_from_request_s, waitingTime, timeLoss, routeLength, reroute_count, ever_teleported, fallback_count, data_error_count, status. Chưa hoàn thành giữ các số đo đã có nhưng thời gian hoàn thành là null.
- **published state:** comparison_id, run_id, policy, progress, status, sim_time, telemetry_time, traffic_time, snapshot_id, data_status, network, target, route, routing_result, results. geometry lat/lng chỉ lấy từ mạng đang chạy, không gán offset cố định.

### Task 1: Định tuyến hợp lệ và hai bộ giải độc lập

**Files:** Create `scripts/core/live_routing.py`, `tests/test_live_routing.py`; modify `scripts/core/osm_graph.py`.

**Interfaces:** `LiveRoadGraph(net_file: str)` có nodes, coords, adjacency, distance và API graph mà hai bộ giải đang dùng; `apply_snapshot(snapshot: dict) -> None`; `is_valid_route(route: List[str]) -> bool`; `compute_path_cost(path: List[str], mode: str = "traffic_aware") -> float`. `solve_route(graph: LiveRoadGraph, policy: str, source: str, destination: str, snapshot_id: int, aco_seed: int) -> dict`; `benchmark_snapshot(graph: LiveRoadGraph, snapshot: dict, source: str, destination: str, aco_seed: int) -> dict`. Constructor ACO thêm `rng=None` ở cuối, caller bỏ qua vẫn dùng random như cũ.

- [ ] **1. Viết test RED cho topology và điểm chi phí.** Fixture có hai cạnh cùng cặp giao lộ, một chuyển hướng cấm và hai đường hợp lệ tới đích. Assert giữ riêng hai edge_id; không dùng chuyển hướng cấm. Với D_norm=.5, TT_norm=.5, N_norm=.25, W_norm=.2, C=.365; đường `[s,a,t]` chỉ cộng C(a)+C(t), không cộng C(s).
- [ ] **2. Viết test RED cho so sánh độc lập.** Trên fixture hai đường có cost .8 và .6, Dijkstra trả .6. Khi ACO tìm được đường, assert score>=.6-1e-9. Patch dijkstra_osm chỉ trong nhánh adaptive_aco để ném lỗi nếu bị gọi; nhánh này phải không gọi Dijkstra. Seed giống nhau cho cùng chuỗi kết quả; RNG lịch xe không bị tiêu thụ. Kiểm tra source=destination, không nối được, invalid/sentinel/non-finite và snapshot chưa đầy đủ.
- [ ] **3. Chạy:** `python -m unittest discover -s tests -p test_live_routing.py -v`. Expected: FAIL do API/hành vi mới chưa có.
- [ ] **4. Triển khai adapter tối thiểu.** Dùng sumolib.net.readNet; adjacency lấy `edge.getAllowedOutgoing("passenger")`, giữ cạnh thường được phép. Chuyển `(e1,e2)` lấy độ dài/chi phí của e2; coords từ hình học mạng. Tái sử dụng dijkstra_osm(cost_fn="static" hoặc "dynamic") và OSMAntColonyOptimizer. Không dùng topology gộp cặp nút của OSMTrafficGraph.
- [ ] **5. Triển khai RNG và solve.** Mỗi solve kiến tạo optimizer mới, `seed_with_dijkstra=False`, `rng=random.Random(aco_seed+snapshot_id)`, cấu hình 30×80 và các giá trị spec mục5; max_steps=len(graph.nodes). Đo perf_counter quanh lời gọi bộ giải, gồm khởi tạo optimizer, không gồm nạp mạng/đọc TraCI. Benchmark chỉ gọi hai bộ giải trên cùng snapshot, tính gap theo spec mục8, không điều khiển SUMO.
- [ ] **6. Chạy lại tests Task1.** Expected: PASS; chạy các self-test core hiện có theo entrypoint của file sau khi kiểm tra nó, xác nhận caller không truyền rng còn hoạt động. Ghi số test/lệnh thực chạy, không dùng kết quả từ lần triển khai đã revert.

**Deliverable:** Hai thuật toán thực sự độc lập, tối ưu cùng mục tiêu và trả tuyến hợp lệ trên cùng graph.

### Task 2: Options và bundle nhu cầu dùng lại cho ba lượt

**Files:** Create `scripts/core/live_demand.py`, `tests/test_live_demand.py`.

**Interfaces:** `validate_options(options: dict) -> dict`; `prepare_scenario(options: dict, scenario_dir: Path) -> dict` trả bundle ở hợp đồng chung. Consumes LiveRoadGraph và static Dijkstra từ Task1; không gọi đàn kiến. Mọi ID/sort/serialization dùng thứ tự ổn định.

- [ ] **1. Viết test RED cho đầu vào.** Reject T thiếu/0/-1/True/NaN/infinity, T<step_length, duration<=T, nhu cầu thiếu/không dương, file/edge không hợp lệ và OD không nối được. T=37/90 hợp lệ; dt=.7,T=37 tạo requested_depart=37.1. Reject flow/trip/routeDistribution chưa explicit với thông báo cần tiền xử lý.
- [ ] **2. Viết test RED cho lịch cố định.** Cùng seed tạo cùng file/hash và demand_events. Chọn top25% theo độ dài, chỉ lấy route hợp lệ có đi qua cạnh. Fixture giai đoạn tăng [0,20),600xe/h có requested_depart=[0,6,12,18]. Không sinh ngoài duration, không xóa xe cũ, không làm thay đổi file đầu vào. Không có ứng viên phải báo lỗi. Chạy/đổi số kiến không thay hash bundle.
- [ ] **3. Chạy:** `python -m unittest discover -s tests -p test_live_demand.py -v`. Expected: FAIL.
- [ ] **4. Triển khai validate/prepare.** RNG riêng theo environment_seed; giữ cấu hình xe/lịch nền explicit, thêm ID không trùng, giới hạn lịch tới duration. Viết manifest, background.rou.xml, demand_events.csv trong thư mục mới; lấy cùng initial_route khoảng cách và requested_depart cho ba chính sách. Lưu hash nội dung net/route/config/bundle và thông số đèn/xe. Chưa thực thi SUMO.
- [ ] **5. Chạy lại tests Task2 và Task1.** Expected: PASS; xác nhận các file map2/dense/output hiện có không đổi.

**Deliverable:** Một bundle không phụ thuộc thuật toán, đủ để phát lại đầu vào ngoại sinh như nhau.

### Task 3: Một xe đang chạy, snapshot T và kết quả thật

**Files:** Create `scripts/core/live_simulation.py`, `tests/test_live_simulation.py`.

**Interfaces:** `LiveSimulation()`; `start(options: dict, policies: List[str]) -> str` trả comparison_id và khởi động đúng một worker; `stop() -> None`; `wait() -> dict` trả summary sau khi worker kết thúc; `snapshot() -> dict` trả bản sao. policies là một phần tử hoặc danh sách cố định `["fixed_initial","adaptive_dijkstra","adaptive_aco"]`. Worker gọi prepare_scenario một lần rồi khởi động SUMO sạch cho từng policy; đây cũng là lõi dùng chung với web/CLI.

- [ ] **1. Viết test RED cho lịch.** Fake TraCI dt=1,T=37: snapshot tại37/74, xe chỉ xuất hiện một lần; adaptive solve một lần ở mỗi snapshot hợp lệ khi xe hoạt động, fixed chỉ tìm tuyến ban đầu. dt=.7 cho nominal37/74, measured37.1/74.2. Snapshot đầu lỗi làm run error, requested_depart không dời; lỗi sau xuất phát giữ tuyến/ID cũ và bỏ solve. Poll snapshot() nhiều lần không chạy bước hoặc solve thêm.
- [ ] **2. Viết test RED cho route/lifecycle.** setRoute chỉ nhận tuyến bắt đầu current external edge. Junction có pending source/snapshot: áp sau khi tới source, không solve lại; bỏ pending quá hạn hoặc bị snapshot mới thay. Reject tuyến bằng/kém hơn trong tolerance1e-9, mất đích hoặc TraCI từ chối. Xe pending không có routeIndex hợp lệ không được giải từ vị trí giả. ACO no_solution dùng tuyến hợp lệ hiện tại/dự phòng và có cờ.
- [ ] **3. Viết test RED cho đầu ra.** requested=37,depart=42,arrival=100 cho departDelay=5,duration=58,elapsed=63. Pending/chưa về đích có elapsed hoàn thành=null. Teleport rồi quay lại/arrive vẫn ever_teleported=true và không clean. start trùng bị từ chối, stop/restart đóng đúng kết nối/process, mỗi run có thư mục mới và ba lượt chỉ có một target/run. Client sửa snapshot copy không đổi state nội bộ.
- [ ] **4. Chạy:** `python -m unittest discover -s tests -p test_live_simulation.py -v`. Expected: FAIL.
- [ ] **5. Triển khai worker và snapshot.** Tái dùng setup_sumo_path của osm_runner nếu import không có side-effect; chỉ worker truy cập kết nối TraCI riêng. Override route-file bằng bundle, begin/end/step/seed và mọi output path; ignore-route-errors=false,time-to-teleport=300,write-unfinished=true. Nạp toàn mạng, chuyển geometry bằng simulation.convertGeo khi có geo projection. Số đo có xe phải finite/hợp lệ; đoạn trống gắn estimated và dùng free-flow như spec.
- [ ] **6. Triển khai tính/áp tuyến và publish.** Khi đạt kT đọc đủ snapshot rồi solve policy từ source thật; không lấy lanePosition của internal edge trừ chiều dài external edge. Trước áp pending phải còn đúng source và cải thiện trên snapshot tạo nó. Publish telemetry mỗi bước, giữ nguyên số đo đường giữa hai mốc. Tại final flush ghi XML/log/result cả khi stop/error; đọc chỉ tripinfo của target bằng ElementTree, không lấy trung bình xe nền từ analyze.parse_tripinfo.
- [ ] **7. Chạy lại tests Task3 và Task1–2.** Expected: PASS. Xác minh thời gian solver tách khỏi thời gian mô phỏng, lỗi không bị nuốt, các output cũ không được mở ghi.

**Deliverable:** Một chính sách điều khiển thật một xe SUMO, với lịch, số liệu và kết quả có thể kiểm tra.

### Task 4: CLI, ba lượt ghép cặp và báo cáo đúng kết luận

**Files:** Create `scripts/osm/live_runner.py`, `tests/test_live_comparison.py`; extend kết quả trong `scripts/core/live_simulation.py`.

**Interfaces:** Trong live_simulation: `summarize_results(results: List[dict]) -> dict` dùng chung CLI/web. Trong live_runner: `run_experiment(options: dict, policies: List[str], environment_seeds: List[int]) -> dict`; `benchmark_saved_run(run_dir: Path) -> List[dict]`; `main(argv: Optional[List[str]] = None) -> int`. Consumes bundle/session/benchmark_snapshot đã định nghĩa.

- [ ] **1. Viết test RED cho báo cáo.** Ba run trong một block có cùng hash/input/requested_depart và policy riêng. Dữ liệu giả elapsed_Dijkstra=100,elapsed_ACO=120 trả saving=-20%, không clamp. arrived sạch/unfinished/teleport/error tách riêng; chỉ ghép thời gian khi cặp so sánh hợp lệ, ghi mẫu số và không xếp hạng block có lỗi kỹ thuật. ACO no_solution không bị giấu trong các lượt thành công.
- [ ] **2. Viết test RED cho benchmark.** Replay cùng snapshot/source/dest cho hai solver; không gọi TraCI hoặc thay route. Dijkstra=.6,ACO=.8 cho gap=100/3%; chuẩn0/ACO0 cho gap0; chuẩn0/ACO>0 cho gap=null; cost_ACO<cost_Dijkstra-1e-9 là lỗi cần kiểm tra. Metadata/log giữ bounds, snapshot_id, seed và thời gian solver. Hash thay đổi giữa ba lượt bị từ chối thay vì ghép nhầm.
- [ ] **3. Chạy:** `python -m unittest discover -s tests -p test_live_comparison.py -v`. Expected: FAIL.
- [ ] **4. Triển khai CLI và summary.** Hỗ trợ `--mode single|block|pilot|benchmark`, `--policy` cho single, `--environment-seeds` cho pilot, `--run-dir` cho benchmark; các input dùng tên kebab-case từ options và không có T mặc định. block theo đúng ba policy; pilot dùng danh sách seed tường minh. Benchmark chạy sau từng run/được gọi riêng, ngoài vòng TraCI. Xuất đúng cây thư mục spec mục9, summary nêu completion/error/teleport/unfinished, fallback/data errors và phân tán/chênh lệch ghép cặp. Không phát biểu ACO thắng vì cost thấp hơn tuyến giữ nguyên.
- [ ] **5. Chạy lại tests Task4.** Expected: PASS; `python -m scripts.osm.live_runner --help` có đủ mode/input và mô tả đơn vị.
- [ ] **6. Chạy tích hợp SUMO thật trên fixture mạng nhỏ có đường thay thế.** Thêm `tests/test_live_sumo_integration.py`, chỉ chạy khi `RUN_SUMO_INTEGRATION=1`; tạo mạng fixture bằng netconvert hiện có trong thư mục tạm. Case T=37 có nhu cầu làm đổi chi phí, assert adaptive_dijkstra đổi tuyến thực được chấp nhận; ACO route tìm được phải hợp lệ, không ép tìm đúng một đường ngẫu nhiên. Case không cải thiện giữ tuyến; case dừng giữa chừng ghi unfinished. Chạy một block map2 để kiểm tra toàn mạng/hash/log, không coi một block là kết luận thống kê.

**Deliverable:** Có thể trả lời riêng “tuyến nào tốt trên snapshot?” và “chính sách nào cho chuyến đi tốt trong thí nghiệm?”, với dữ liệu gốc đi kèm.

### Task 5: Web hiển thị phiên thật và bảng ba chính sách

**Files:** Modify `scripts/run_google_maps_sim.py`, `web/js/app.js`, `web/js/map_controller.js`, `web/index.html`; CSS chỉ khi bố cục cần. Create `tests/test_live_api.py`, `tests/web_live.test.cjs`.

**Interfaces:** `create_app(simulation=None)` trả Flask app để test; giữ `run_flask_server(port)` và cách gọi cũ. `GET /api/network?net_file=...` trả `{net_file, hash, edges:[{edge_id,name,length_m}]}` bằng cách đọc topology, không khởi động SUMO hoặc truy cập TraCI. `POST /api/start {mode:"single"|"block", options:{...}}`; `GET /api/state`; `POST /api/stop`. App dùng LiveSimulation từ Task3, không có worker/solver riêng. MapController thêm `renderLiveState(state)` để vẽ network/route/target theo policy, dùng clearRoutes/updateCars sau khi bỏ nhãn hai xe cố định; giữ các hàm nền bản đồ hiện có.

- [ ] **1. Viết test RED API với Flask test_client.** network trả danh sách A/B trước khi start, giữ cạnh song song và không gọi TraCI/khởi động process. Đầu vào sai trả400 trước tạo worker; khi đang chạy trả409, không dừng phiên; start hợp lệ trả202 và comparison_id; state/stop không truy cập TraCI từ request. Start lỗi dọn worker, state có error rõ; stop giữa block không tự chạy các policy còn lại. API chỉ nhận đường dẫn mạng/config hợp lệ trong project, thư mục output do server tạo.
- [ ] **2. Viết test RED client dùng node:test + vm + stub DOM/fetch.** HTTP lỗi không hiển thị số liệu cũ như mới; response run cũ không ghi đè run mới; polling không chồng request/start. Có trạng thái chưa có kết quả, stale và ACO chậm hơn; không có clamp lợi ích âm. Không gọi RealRoadEngine/OSRM hoặc kinematics JavaScript. Không cần thêm module product chỉ để test.
- [ ] **3. Chạy:** `python -m unittest discover -s tests -p test_live_api.py -v` và `node --test tests/web_live.test.cjs`. Expected: FAIL.
- [ ] **4. Triển khai API và nguồn hiển thị.** create_app dùng dependency injection của session; endpoint network chỉ đọc topology từ đường dẫn đã kiểm tra, các endpoint còn lại validate/start/read/stop. app.js lấy danh sách A/B trước start, theo dõi comparison_id/run_id và telemetry_time/traffic_time; polling một giây đồng hồ không đổi T. index không nạp real_road_engine.js; bỏ auto accident/TH presets/tua tốc độ chưa nối. Thêm trường edge_id A/B có tìm mã, policy/T/nhu cầu/duration/seed, chế độ một lượt/ba lượt và progress.
- [ ] **5. Triển khai MapController/UI tối thiểu.** Một marker xe mục tiêu của run hiện tại, một tuyến đang đi; tên policy đúng. Màu đường dựa tốc độ đo với ngưỡng spec mục9; chưa quan sát/lỗi màu xám. Không fitBounds mỗi polling. Kết quả bảng phân biệt ước tính, elapsed sau yêu cầu xuất phát, duration sau chèn, waitingTime và solver_ms. Hiện số âm/kết quả chưa hoàn thành, không tự gọi hai tuyến là “Dijkstra vs ACO” khi không có kết quả tương ứng.
- [ ] **6. Chạy lại tests API/client và browser-check.** Expected: PASS; kiểm tra chọn chính sách, T=37/90, chạy/dừng/chạy lại, block1/3–3/3, mất kết nối, geo projection thiếu và stale. Kiểm tra marker từ SUMO, không phải animation JS. Mở tab không được tự tạo thí nghiệm nếu người dùng chưa bấm chạy.

**Deliverable:** Web quan sát và điều khiển cùng phiên đã được CLI kiểm chứng, hiển thị trung thực dữ liệu và kết quả.

### Task 6: Hướng dẫn, pilot và nghiệm thu

**Files:** Modify `README.md`; các báo cáo sinh mới chỉ vào `output/comparisons/<comparison_id>/`.

- [ ] **1. Viết hướng dẫn chạy đúng code vừa hoàn tất.** Nêu SUMO_HOME, lệnh help/single/block/pilot/benchmark, cách tìm edge_id, đầu vào T không bắt buộc180, phương thức chạy web, output và định nghĩa chỉ số. Ví dụ seed/T chỉ ghi là ví dụ. Nêu mạng thực địa + lưu lượng tổng hợp chưa phải dữ liệu giao thông ngoài đường.
- [ ] **2. Chạy bộ kiểm chứng một lần sau thay đổi cuối.** `python -m unittest discover -s tests -p "test_live_*.py" -v`; `node --test tests/web_live.test.cjs`. Với PowerShell, bật `$env:RUN_SUMO_INTEGRATION='1'`, chạy `python -m unittest discover -s tests -p test_live_sumo_integration.py -v`, rồi gỡ biến bằng `Remove-Item Env:RUN_SUMO_INTEGRATION`. Expected: toàn bộ unit/client pass, integration pass hoặc báo rõ lý do chưa chạy; không lấy SKIP làm bằng chứng tích hợp thành công. Không chạy lặp vô ích khi không có thay đổi/lỗi mới.
- [ ] **3. Chạy pilot năm environment_seed đã ghi trước với cùng OD/T/nhu cầu, 15 lượt.** Đề xuất seeds42,43,44,45,46; aco_seed cố định được khai báo riêng trong manifest. Không thay seed vì kết quả xấu. Lưu summary, số block hợp lệ, completion/teleport/unfinished/error và thời gian đọc/tính toàn mạng. Đây là kiểm chứng bước đầu, không tuyên bố đủ sức kết luận tổng quát.
- [ ] **4. Rà kết luận theo số liệu.** So adaptive_aco với adaptive_dijkstra cùng mục tiêu; fixed_initial là mốc phụ. Báo cả khi ACO hòa/thua/chậm tính; nếu cost snapshot và thời gian chuyến đi khác xu hướng, giải thích chúng đo hai việc khác nhau. Kiểm tra source/destination/hash/bounds trước khi quy kết nguyên nhân cho thuật toán.
- [ ] **5. Rà diff và bàn giao.** Chỉ liệt kê file đã đổi, lệnh/test/pilot thực chạy và giới hạn chưa kiểm chứng. Không đụng output cũ/route dense; không gộp các thay đổi riêng của người dùng. Chỉ tạo commit hoặc PR khi bước thực hiện được người dùng cho phép theo yêu cầu tích hợp lúc đó.

**Deliverable:** Người mới chạy được luồng và đọc đúng ý nghĩa phép so sánh; không cần dựa vào lời khẳng định ACO tốt hơn để đánh giá dự án.

## Tự rà kế hoạch

- Spec mục1–5 → Task1,4; mục6 → Task2; mục7 → Task3; mục8 → Task4,6; mục9 → Task3–5; mục10 → Task1–6.
- Năm Review Focus đều có test chủ sở hữu; topology/bundle/session/CLI/API dùng cùng tên và schema ở hợp đồng chung.
- Không có nhiệm vụ tạo đa xe phối hợp, tối ưu đèn, database, engine mới hoặc thay SUMO bằng số liệu JavaScript.
- Các lựa chọn cần người dùng xem: ba lượt riêng thay vì chạy cạnh nhau; A/B theo mã đoạn ở bản đầu; chạy nền một T; chung T cho nhu cầu/định tuyến; chi phí trọng số hiện có; pilot năm seed. Chúng là đề xuất, không ghi thành quyết định đã được duyệt.

## Bàn giao trước triển khai

Đọc spec và kế hoạch mới cùng nhau. Trong lượt hiện tại chỉ tạo tài liệu, không chạy implementation. Khi người dùng yêu cầu thực hiện, xác nhận phạm vi/đề xuất còn thay đổi rồi dùng cùng workflow đã chọn; không tự chuyển sang điều phối nhiều xe để tạo lợi thế cho ACO.
