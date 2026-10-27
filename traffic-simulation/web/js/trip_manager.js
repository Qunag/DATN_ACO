/**
 * trip_manager.js – Quản lý việc sinh hành trình, theo dõi các phương tiện
 * và ước lượng tổng thời gian di chuyển trên mạng lưới giao thông.
 */

class TripManager {
    constructor(graph, trafficModel, routingEngine, options = {}) {
        this.graph = graph;
        this.model = trafficModel;
        this.routing = routingEngine;

        this.vehicles = new Map(); // id -> Vehicle
        this.completedVehicles = []; // Danh sách các xe đã hoàn thành
        this.vehicleCounter = 1;

        // Cấu hình sinh lưu lượng
        this.scenario = options.scenario || "TH3"; // 'TH1' .. 'TH5'
        this.scenarios = {
            "TH1": { name: "Giờ thấp điểm (Ban đêm / Trưa)", flow_vph: 250, desc: "Giao thông thông thoáng, ít xe" },
            "TH2": { name: "Bình thường (Giữa giờ)", flow_vph: 600, desc: "Mật độ vừa phải, lưu thông ổn định" },
            "TH3": { name: "Cao điểm sáng (7h30 - 8h30)", flow_vph: 1200, desc: "Lưu lượng lớn, xuất hiện ùn ứ tại các nút ngã 4, ngã 5" },
            "TH4": { name: "Cao điểm chiều (17h30 - 18h30)", flow_vph: 1800, desc: "Ùn tắc cục bộ diện rộng, nhiều nút vượt quá dung lượng" },
            "TH5": { name: "Sự cố giao thông trên trục chính", flow_vph: 1400, desc: "Tai nạn chặn 80% đường Trường Chinh, ACO tự động phân luồng" }
        };

        this.spawnAccumulator = 0; // Bộ tích lũy thời gian để sinh xe
        this.maxActiveVehicles = options.maxActiveVehicles || 80; // Giới hạn xe hiển thị mượt mà trên bản đồ

        // Tỷ lệ phân bổ thuật toán
        this.algoDistribution = {
            "ACO": 0.50,          // 50% xe dùng ACO
            "DIJKSTRA_DYN": 0.30, // 30% xe dùng Dijkstra Traffic
            "STATIC": 0.20        // 20% xe dùng Shortest Distance
        };

        // Trọng số xác suất chọn điểm xuất phát / điểm đến (nhà ga và nút lớn có nhu cầu cao hơn)
        this.nodeWeights = this.initNodeDemandWeights();
    }

    /**
     * Khởi tạo trọng số nhu cầu đi lại cho các nút giao thông
     */
    initNodeDemandWeights() {
        const weights = {};
        for (const [id, node] of Object.entries(this.graph.nodes)) {
            if (node.type === "STATION" || node.type === "HUB") {
                weights[id] = 5.0; // Nhà ga, trung tâm lớn nhu cầu gấp 5 lần
            } else if (node.type === "INTERSECTION_5") {
                weights[id] = 3.5;
            } else if (node.type === "INTERSECTION_4") {
                weights[id] = 2.0;
            } else {
                weights[id] = 1.0;
            }
        }
        return weights;
    }

    /**
     * Chọn ngẫu nhiên một nút theo phân phối xác suất
     */
    sampleNode(excludeNode = null) {
        const candidates = Object.keys(this.graph.nodes).filter(n => n !== excludeNode);
        let totalWeight = 0;
        for (const n of candidates) {
            totalWeight += (this.nodeWeights[n] || 1.0);
        }

        const rand = Math.random() * totalWeight;
        let accum = 0;
        for (const n of candidates) {
            accum += (this.nodeWeights[n] || 1.0);
            if (rand <= accum) return n;
        }
        return candidates[0];
    }

    /**
     * Tạo một hành trình mới (Trip/Vehicle)
     */
    createTrip(origin, destination, algorithm = null) {
        if (!origin || !destination || origin === destination) return null;

        // Quyết định thuật toán nếu chưa chỉ định
        if (!algorithm) {
            const r = Math.random();
            if (r < this.algoDistribution.ACO) {
                algorithm = "ACO";
            } else if (r < this.algoDistribution.ACO + this.algoDistribution.DIJKSTRA_DYN) {
                algorithm = "DIJKSTRA_DYN";
            } else {
                algorithm = "STATIC";
            }
        }

        // Tìm đường phù hợp theo thuật toán
        let routeResult = null;
        if (algorithm === "ACO") {
            routeResult = this.routing.findRouteACO(origin, destination);
        } else if (algorithm === "DIJKSTRA_DYN") {
            routeResult = this.routing.findRouteDijkstra(origin, destination, "travel_time");
        } else {
            routeResult = this.routing.findRouteDijkstra(origin, destination, "distance");
        }

        if (!routeResult || !routeResult.path || routeResult.path.length < 2 || routeResult.edges.length === 0) {
            return null; // Không tìm được tuyến đường nối
        }

        // Quyết định loại phương tiện (xe máy, ô tô, xe buýt)
        const vTypes = ["car", "motorcycle", "motorcycle", "car", "bus"];
        const vType = vTypes[Math.floor(Math.random() * vTypes.length)];

        // Màu sắc phân biệt theo thuật toán
        let color = "#8b5cf6"; // Tím (ACO)
        if (algorithm === "DIJKSTRA_DYN") color = "#06b6d4"; // Xanh Cyan (Dijkstra Dynamic)
        if (algorithm === "STATIC") color = "#f97316";       // Cam (Static Shortest)

        const startNode = this.graph.nodes[origin];
        const vehId = `XE-${this.vehicleCounter++}`;

        const vehicle = {
            id: vehId,
            type: vType,
            algorithm: algorithm,
            color: color,
            origin: origin,
            destination: destination,
            origin_name: startNode ? startNode.name : origin,
            destination_name: this.graph.nodes[destination] ? this.graph.nodes[destination].name : destination,
            route_nodes: routeResult.path,
            route_edges: routeResult.edges,
            current_edge_idx: 0,
            distance_on_edge: 0.0,
            speed_ms: 10.0, // Vận tốc ban đầu
            lat: startNode.lat,
            lng: startNode.lng,
            bearing: 0,
            status: "RUNNING", // 'RUNNING' | 'QUEUED' | 'ARRIVED'
            start_time: this.model.time,
            estimated_travel_time: routeResult.travel_time,
            actual_travel_time: 0.0,
            delay_time: 0.0,
            total_distance_m: routeResult.distance
        };

        this.vehicles.set(vehId, vehicle);

        // Đếm tăng số xe trên cạnh đầu tiên
        const firstEdgeId = vehicle.route_edges[0];
        if (this.model.edgeStates[firstEdgeId]) {
            this.model.edgeStates[firstEdgeId].vehicles++;
        }

        return vehicle;
    }

    /**
     * Tự động sinh xe theo kịch bản thời gian thực (Poisson distribution)
     */
    updateSpawn(dtSeconds) {
        if (this.vehicles.size >= this.maxActiveVehicles) return;

        const currentCfg = this.scenarios[this.scenario] || this.scenarios["TH3"];
        const vehiclesPerSecond = currentCfg.flow_vph / 3600.0;

        this.spawnAccumulator += dtSeconds * vehiclesPerSecond;

        // Khi tích lũy đủ 1 hoặc nhiều xe, tiến hành sinh
        while (this.spawnAccumulator >= 1.0 && this.vehicles.size < this.maxActiveVehicles) {
            this.spawnAccumulator -= 1.0;
            const o = this.sampleNode();
            const d = this.sampleNode(o);
            this.createTrip(o, d);
        }
    }

    /**
     * Cập nhật vị trí và động học cho tất cả các phương tiện (60 FPS kinematic update)
     */
    updateVehicles(dtSeconds) {
        // Reset bộ đếm số xe và số xe dừng trên các cạnh để tính toán lại chính xác
        for (const state of Object.values(this.model.edgeStates)) {
            state.vehicles = 0;
            state.halting = 0;
        }

        const arrivedVehicles = [];

        for (const [id, veh] of this.vehicles.entries()) {
            if (veh.status === "ARRIVED") continue;

            const edgeId = veh.route_edges[veh.current_edge_idx];
            const edgeData = this.graph.edges[edgeId];
            const edgeState = this.model.edgeStates[edgeId];

            if (!edgeData || !edgeState) {
                arrivedVehicles.push(id);
                continue;
            }

            // Ghi nhận sự hiện diện của xe trên cạnh
            edgeState.vehicles++;
            veh.actual_travel_time += dtSeconds;

            // Kiểm tra trạng thái đèn giao thông và hàng đợi ở cuối đường
            const toNode = this.graph.nodes[edgeData.to];
            const distanceToEnd = edgeData.length - veh.distance_on_edge;
            let isBlockedBySignal = false;

            if (distanceToEnd <= 30.0 && toNode && toNode.has_signals) {
                const sigState = this.model.signalStates[edgeData.to];
                if (sigState) {
                    const direction = this.model.getApproachDirection(edgeData.from, edgeData.to);
                    const isRed = (direction === "NS" && sigState.red_remaining_NS > 0) ||
                                  (direction === "EW" && sigState.red_remaining_EW > 0);
                    if (isRed) {
                        isBlockedBySignal = true;
                    }
                }
            }

            if (isBlockedBySignal) {
                // Xe dừng chờ đèn đỏ trước vạch dừng
                veh.status = "QUEUED";
                veh.speed_ms = 0.0;
                edgeState.halting++;
                veh.delay_time += dtSeconds;
            } else {
                // Xe di chuyển theo vận tốc động của đoạn đường
                veh.status = "RUNNING";
                const targetSpeed = Math.max(1.5, edgeState.speed_ms);
                // Làm mượt vận tốc (acceleration / deceleration)
                veh.speed_ms += (targetSpeed - veh.speed_ms) * Math.min(1.0, dtSeconds * 2.0);

                // Cập nhật quãng đường đi
                veh.distance_on_edge += veh.speed_ms * dtSeconds;
            }

            // ── Kiểm tra xe đã đi hết đoạn đường hiện tại ──
            if (veh.distance_on_edge >= edgeData.length) {
                veh.distance_on_edge = 0.0;
                veh.current_edge_idx++;

                // Kiểm tra xem đã đến đích cuối cùng hay chưa
                if (veh.current_edge_idx >= veh.route_edges.length) {
                    veh.status = "ARRIVED";
                    const destNode = this.graph.nodes[veh.destination];
                    veh.lat = destNode.lat;
                    veh.lng = destNode.lng;
                    arrivedVehicles.push(id);
                    continue;
                }
            }

            // ── Nội suy tọa độ GPS (lat, lng) dọc theo polyline của đường ──
            this.interpolateVehiclePosition(veh, edgeData);
        }

        // Xóa các xe đã hoàn thành khỏi danh sách active và lưu vào lịch sử
        for (const id of arrivedVehicles) {
            const v = this.vehicles.get(id);
            if (v) {
                this.completedVehicles.push({
                    id: v.id,
                    algorithm: v.algorithm,
                    origin: v.origin_name,
                    destination: v.destination_name,
                    estimated_time: Math.round(v.estimated_travel_time),
                    actual_time: Math.round(v.actual_travel_time),
                    delay_time: Math.round(v.delay_time),
                    distance: v.total_distance_m
                });
                this.vehicles.delete(id);
            }
        }
    }

    /**
     * Nội suy chính xác tọa độ GPS và góc xoay (bearing) dọc theo polyline của cạnh
     */
    interpolateVehiclePosition(vehicle, edgeData) {
        const points = edgeData.points;
        if (!points || points.length === 0) return;

        if (points.length === 2) {
            const fraction = Math.min(1.0, Math.max(0.0, vehicle.distance_on_edge / Math.max(1.0, edgeData.length)));
            const p1 = points[0];
            const p2 = points[1];

            vehicle.lat = p1[0] + fraction * (p2[0] - p1[0]);
            vehicle.lng = p1[1] + fraction * (p2[1] - p1[1]);

            // Tính góc xoay hướng di chuyển (Bearing: 0° Bắc, 90° Đông)
            const dLat = p2[0] - p1[0];
            const dLng = p2[1] - p1[1];
            vehicle.bearing = (Math.atan2(dLng, dLat) * 180.0 / Math.PI + 360) % 360;
            return;
        }

        // Với polyline nhiều điểm uốn lượn (từ OSM)
        const totalDist = edgeData.length;
        const targetDist = vehicle.distance_on_edge;
        const segmentDist = totalDist / (points.length - 1);

        const segIdx = Math.min(points.length - 2, Math.floor(targetDist / segmentDist));
        const segFrac = Math.min(1.0, Math.max(0.0, (targetDist - segIdx * segmentDist) / segmentDist));

        const pA = points[segIdx];
        const pB = points[segIdx + 1];

        vehicle.lat = pA[0] + segFrac * (pB[0] - pA[0]);
        vehicle.lng = pA[1] + segFrac * (pB[1] - pA[1]);

        const dLat = pB[0] - pA[0];
        const dLng = pB[1] - pA[1];
        vehicle.bearing = (Math.atan2(dLng, dLat) * 180.0 / Math.PI + 360) % 360;
    }

    /**
     * BƯỚC MÔ PHỎNG HÀNH TRÌNH TẠI MỖI TICK (step)
     */
    step(dtSeconds = 1.0) {
        // 1. Tự động sinh chuyến đi
        this.updateSpawn(dtSeconds);

        // 2. Di chuyển các xe
        this.updateVehicles(dtSeconds);
    }

    /**
     * THỐNG KÊ TỔNG THỂ TOÀN BỘ MẠNG LƯỚI GIAO THÔNG (AGGREGATED METRICS)
     * Ước lượng tổng thời gian di chuyển, vận tốc trung bình, so sánh thuật toán
     */
    getNetworkMetrics() {
        let activeEstimatedTimeSum = 0;
        let activeActualTimeSum = 0;
        let activeDelaySum = 0;
        let totalSpeedSum = 0;

        const algoStats = {
            "ACO": { active: 0, completed: 0, actual_time_sum: 0, est_time_sum: 0 },
            "DIJKSTRA_DYN": { active: 0, completed: 0, actual_time_sum: 0, est_time_sum: 0 },
            "STATIC": { active: 0, completed: 0, actual_time_sum: 0, est_time_sum: 0 }
        };

        for (const v of this.vehicles.values()) {
            activeEstimatedTimeSum += v.estimated_travel_time;
            activeActualTimeSum += v.actual_travel_time;
            activeDelaySum += v.delay_time;
            totalSpeedSum += (v.speed_ms * 3.6);

            if (algoStats[v.algorithm]) {
                algoStats[v.algorithm].active++;
            }
        }

        for (const v of this.completedVehicles) {
            if (algoStats[v.algorithm]) {
                algoStats[v.algorithm].completed++;
                algoStats[v.algorithm].actual_time_sum += v.actual_time;
                algoStats[v.algorithm].est_time_sum += v.estimated_time;
            }
        }

        const activeCount = this.vehicles.size;
        const completedCount = this.completedVehicles.length;

        // Vận tốc trung bình toàn mạng (km/h)
        const avgSpeed = activeCount > 0 ? Math.round((totalSpeedSum / activeCount) * 10) / 10 : 40.0;

        // Thời gian hoàn thành trung bình theo từng thuật toán
        const calcAvg = (stat) => (stat.completed > 0 ? Math.round(stat.actual_time_sum / stat.completed) : 0);

        const acoAvg = calcAvg(algoStats["ACO"]);
        const dynAvg = calcAvg(algoStats["DIJKSTRA_DYN"]);
        const staticAvg = calcAvg(algoStats["STATIC"]);

        // Mức độ tiết kiệm thời gian của ACO so với Static
        let savingsPct = 0;
        if (staticAvg > 0 && acoAvg > 0) {
            savingsPct = Math.round(((staticAvg - acoAvg) / staticAvg) * 100);
        }

        return {
            scenario: this.scenario,
            scenario_name: this.scenarios[this.scenario].name,
            active_vehicles: activeCount,
            completed_vehicles: completedCount,
            total_trips_created: this.vehicleCounter - 1,
            // ── ƯỚC LƯỢNG TỔNG THỜI GIAN DI CHUYỂN TOÀN MẠNG LƯỚI ──
            total_estimated_travel_time_s: Math.round(activeEstimatedTimeSum),
            total_actual_travel_time_s: Math.round(activeActualTimeSum),
            total_delay_time_s: Math.round(activeDelaySum),
            average_speed_kmh: avgSpeed,
            algorithm_comparison: {
                aco_avg_time_s: acoAvg,
                dijkstra_dynamic_avg_time_s: dynAvg,
                dijkstra_static_avg_time_s: staticAvg,
                aco_time_savings_pct: savingsPct
            },
            algo_counts: {
                aco_active: algoStats["ACO"].active,
                dijkstra_dyn_active: algoStats["DIJKSTRA_DYN"].active,
                static_active: algoStats["STATIC"].active
            }
        };
    }
}

// Xuất biến toàn cục
if (typeof window !== "undefined") {
    window.TripManager = TripManager;
}

if (typeof module !== "undefined" && module.exports) {
    module.exports = { TripManager };
}
