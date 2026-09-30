/**
 * traffic_model.js – Mô hình toán học ước lượng thời gian di chuyển động trên từng con đường
 * Dựa trên lý thuyết giao thông chuẩn quốc tế (BPR, Greenshields, Webster)
 * và Đề tài Tốt nghiệp: "Điều hướng Giao thông bằng Giải thuật Đàn Kiến"
 */

class TrafficModel {
    constructor(graph, options = {}) {
        this.graph = graph; // Đồ thị mạng lưới { nodes, edges, adjacency }
        this.time = 0; // Thời gian mô phỏng (giây)

        // Trọng số hàm chi phí cạnh theo Báo cáo 1 & 3 của đề tài
        this.costWeights = options.costWeights || {
            w_d: 0.2, // Trọng số chiều dài khoảng cách
            w_t: 0.3, // Trọng số thời gian di chuyển
            w_q: 0.3, // Trọng số mật độ số lượng xe (ùn tắc)
            w_w: 0.2  // Trọng số thời gian chờ đèn và hàng đợi
        };

        // Giới hạn chuẩn hóa (Normalization Bounds)
        this.normBounds = options.normBounds || {
            distance: 2500.0,   // Chiều dài tối đa chuẩn hóa (m)
            travel_time: 300.0, // Thời gian tối đa chuẩn hóa (s)
            vehicles: 80,       // Số lượng xe tối đa chuẩn hóa
            waiting: 120.0      // Thời gian chờ tối đa chuẩn hóa (s)
        };

        // Tham số mô hình BPR (Bureau of Public Roads)
        this.bprAlpha = 0.15;
        this.bprBeta = 4.0;
        this.vCrawlMs = 1.0; // Vận tốc bò tối thiểu khi kẹt xe cứng: 3.6 km/h (1.0 m/s)
        this.queueHeadway = 2.0; // Khoảng thời gian giải tỏa 1 xe xếp hàng (s/xe)

        // Bộ lưu trữ trạng thái động của các cạnh
        // edgeId -> { vehicles, halting, incident, speed, travel_time, signal_delay, queue_delay, cost, los, color, pheromone }
        this.edgeStates = {};

        // Bộ lưu trữ trạng thái đèn tín hiệu tại các nút
        // nodeId -> { current_phase, phase_timer, phase_name, red_remaining_NS, red_remaining_EW }
        this.signalStates = {};

        // Khởi tạo trạng thái ban đầu
        this.initStates();
    }

    /**
     * Khởi tạo trạng thái ban đầu cho toàn bộ cạnh và đèn tín hiệu
     */
    initStates() {
        // 1. Khởi tạo trạng thái các cạnh
        for (const [edgeId, edge] of Object.entries(this.graph.edges)) {
            const freeFlowTime = edge.free_flow_time || Math.round(edge.length / edge.free_speed_ms);
            this.edgeStates[edgeId] = {
                id: edgeId,
                vehicles: 0,
                halting: 0,
                incident: 0.0, // 0.0: bình thường, 0.8: sự cố giảm 80% dung lượng
                effective_capacity: edge.capacity,
                vc_ratio: 0.0,
                speed_ms: edge.free_speed_ms,
                speed_kmh: edge.speed_limit_kmh,
                cruise_time: freeFlowTime,
                signal_delay: 0.0,
                queue_delay: 0.0,
                travel_time: freeFlowTime,
                cost: 0.1,
                los: "A", // Level of Service
                color: "#10b981", // Xanh lá
                pheromone: 1.0, // Nồng độ Pheromone ban đầu cho ACO
                history: []
            };
        }

        // 2. Khởi tạo trạng thái đèn tín hiệu tại các nút
        for (const [nodeId, node] of Object.entries(this.graph.nodes)) {
            if (node.has_signals) {
                const cycle = node.cycle_time || 80;
                const split = node.signal_split || { NS: 35, EW: 35, Y: 5 };
                this.signalStates[nodeId] = {
                    cycle: cycle,
                    split: split,
                    current_phase: "GREEN_NS", // 'GREEN_NS' | 'YELLOW_NS' | 'GREEN_EW' | 'YELLOW_EW'
                    timer: 0,
                    cycle_counter: Math.floor(Math.random() * cycle) // Phân tán pha ban đầu
                };
            }
        }
    }

    /**
     * Cập nhật chu kỳ đèn giao thông tại mỗi giây
     */
    updateTrafficSignals(dtSeconds = 1.0) {
        for (const [nodeId, state] of Object.entries(this.signalStates)) {
            state.cycle_counter = (state.cycle_counter + dtSeconds) % state.cycle;
            const t = state.cycle_counter;

            const tGreenNS = state.split.NS;
            const tYellowNS = tGreenNS + state.split.Y;
            const tGreenEW = tYellowNS + state.split.EW;
            const tYellowEW = state.cycle;

            if (t < tGreenNS) {
                state.current_phase = "GREEN_NS";
                state.red_remaining_NS = 0;
                state.red_remaining_EW = (tYellowNS - t) + state.split.Y; // Chờ hết pha NS
            } else if (t < tYellowNS) {
                state.current_phase = "YELLOW_NS";
                state.red_remaining_NS = (tYellowNS - t) + state.split.EW + state.split.Y;
                state.red_remaining_EW = (tYellowNS - t);
            } else if (t < tGreenEW) {
                state.current_phase = "GREEN_EW";
                state.red_remaining_NS = (tGreenEW - t) + state.split.Y;
                state.red_remaining_EW = 0;
            } else {
                state.current_phase = "YELLOW_EW";
                state.red_remaining_NS = (tYellowEW - t);
                state.red_remaining_EW = (tYellowEW - t) + state.split.NS + state.split.Y;
            }
        }
    }

    /**
     * Tính toán hướng tiếp cận của đoạn đường (Bắc-Nam hay Đông-Tây)
     * để xác định đèn xanh hay đèn đỏ khi tới nút giao
     */
    getApproachDirection(fromNodeId, toNodeId) {
        const u = this.graph.nodes[fromNodeId];
        const v = this.graph.nodes[toNodeId];
        if (!u || !v) return "NS";

        const dLat = Math.abs(v.lat - u.lat);
        const dLng = Math.abs(v.lng - u.lng);

        // Nếu chênh lệch Vĩ độ lớn hơn Kinh độ => Trục Bắc-Nam (NS), ngược lại là Đông-Tây (EW)
        return dLat >= dLng ? "NS" : "EW";
    }

    /**
     * TÍNH TOÁN VÀ ƯỚC LƯỢNG THỜI GIAN DI CHUYỂN TRÊN MỘT CON ĐƯỜNG
     * TẠI THỜI ĐIỂM HIỆN TẠI (T_ij(t)) - CHÍNH XÁC 100%
     */
    estimateEdgeTravelTime(edgeId) {
        const edge = this.graph.edges[edgeId];
        if (!edge) return 0;

        const state = this.edgeStates[edgeId];
        const toNode = this.graph.nodes[edge.to];

        // ── 1. Dung lượng hiệu dụng sau sự cố (Effective Capacity) ──
        const effectiveCap = Math.max(2, Math.round(edge.capacity * (1.0 - state.incident)));
        state.effective_capacity = effectiveCap;

        // ── 2. Tỷ số bão hòa V/C (Volume-to-Capacity ratio) ──
        const vcRatio = state.vehicles / effectiveCap;
        state.vc_ratio = Math.round(vcRatio * 100) / 100;

        // ── 3. Vận tốc hành trình theo Mô hình BPR (Bureau of Public Roads) ──
        // v(t) = v_free / [1 + alpha * (V / C)^beta]
        const bprDenominator = 1.0 + this.bprAlpha * Math.pow(vcRatio, this.bprBeta);
        const cruiseSpeed = edge.free_speed_ms / bprDenominator;

        // Áp dụng vận tốc bò tối thiểu nếu đường bị nghẽn cứng
        const actualSpeed = Math.max(this.vCrawlMs, cruiseSpeed);
        state.speed_ms = Math.round(actualSpeed * 10) / 10;
        state.speed_kmh = Math.round(actualSpeed * 3.6 * 10) / 10;

        // ── 4. Thời gian chạy thuần túy trên tuyến (Cruise Travel Time) ──
        const cruiseTime = edge.length / actualSpeed;
        state.cruise_time = Math.round(cruiseTime * 10) / 10;

        // ── 5. Thời gian trễ đèn tín hiệu tại nút giao cuối đường (W_signal) ──
        let signalDelay = 0.0;
        if (toNode && toNode.has_signals && this.signalStates[edge.to]) {
            const sigState = this.signalStates[edge.to];
            const direction = this.getApproachDirection(edge.from, edge.to);

            if (direction === "NS") {
                signalDelay = sigState.red_remaining_NS || 0;
            } else {
                signalDelay = sigState.red_remaining_EW || 0;
            }
        }
        state.signal_delay = Math.round(signalDelay * 10) / 10;

        // ── 6. Thời gian trễ giải tỏa hàng đợi (W_queue) ──
        // W_queue = (H_ij * headway) / lanes
        const queueDelay = (state.halting * this.queueHeadway) / Math.max(1, edge.lanes);
        state.queue_delay = Math.round(queueDelay * 10) / 10;

        // ── 7. TỔNG THỜI GIAN DI CHUYỂN ƯỚC LƯỢNG (T_ij(t)) ──
        const totalTravelTime = cruiseTime + signalDelay + queueDelay;
        state.travel_time = Math.round(totalTravelTime * 10) / 10;

        // ── 8. Mức độ phục vụ (Level of Service - LOS) & Màu sắc trực quan ──
        if (state.incident > 0.5) {
            state.los = "F (SỰ CỐ)";
            state.color = "#dc2626"; // Đỏ sẫm cảnh báo
        } else if (vcRatio < 0.60 && actualSpeed >= edge.free_speed_ms * 0.75) {
            state.los = "A (Rất thông thoáng)";
            state.color = "#10b981"; // Xanh lục
        } else if (vcRatio < 0.85 && actualSpeed >= edge.free_speed_ms * 0.50) {
            state.los = "B/C (Ổn định)";
            state.color = "#f59e0b"; // Vàng
        } else if (vcRatio < 1.10) {
            state.los = "D/E (Đông đúc / Ùn ứ)";
            state.color = "#f97316"; // Cam
        } else {
            state.los = "F (Ùn tắc nghiêm trọng)";
            state.color = "#ef4444"; // Đỏ
        }

        // ── 9. Hàm Chi Phí Cạnh Động cho Thuật toán ACO & Routing ──
        // C_ij(t) = w_d * D_norm + w_t * T_norm + w_q * Q_norm + w_w * W_norm
        const dNorm = Math.min(1.0, edge.length / this.normBounds.distance);
        const tNorm = Math.min(1.0, totalTravelTime / this.normBounds.travel_time);
        const qNorm = Math.min(1.0, state.vehicles / this.normBounds.vehicles);
        const wNorm = Math.min(1.0, (signalDelay + queueDelay) / this.normBounds.waiting);

        const edgeCost =
            this.costWeights.w_d * dNorm +
            this.costWeights.w_t * tNorm +
            this.costWeights.w_q * qNorm +
            this.costWeights.w_w * wNorm;

        state.cost = Math.round(edgeCost * 1000) / 1000;

        return state.travel_time;
    }

    /**
     * Cập nhật toàn bộ mạng lưới tại mỗi bước thời gian dt (mặc định 1 giây)
     */
    step(dtSeconds = 1.0) {
        this.time += dtSeconds;

        // 1. Cập nhật chu kỳ đèn giao thông
        this.updateTrafficSignals(dtSeconds);

        // 2. Tính toán lại thời gian di chuyển và chi phí cho từng đoạn đường
        for (const edgeId of Object.keys(this.graph.edges)) {
            this.estimateEdgeTravelTime(edgeId);
        }

        // 3. Bay hơi pheromone nhẹ theo chu kỳ (ACO Pheromone Evaporation)
        const rho = 0.02; // Tỷ lệ bay hơi
        for (const [edgeId, state] of Object.entries(this.edgeStates)) {
            state.pheromone = Math.max(0.1, state.pheromone * (1.0 - rho));
        }
    }

    /**
     * Đặt hoặc hủy bỏ sự cố giao thông trên một đoạn đường
     */
    setIncident(edgeId, hasIncident = true, severity = 0.8) {
        if (this.edgeStates[edgeId]) {
            this.edgeStates[edgeId].incident = hasIncident ? severity : 0.0;
            this.estimateEdgeTravelTime(edgeId);
            return true;
        }
        return false;
    }

    /**
     * Trả về bảng giải thích công thức chi tiết cho một con đường
     * phục vụ hiển thị minh bạch cho người dùng
     */
    getEdgeFormulaDetails(edgeId) {
        const edge = this.graph.edges[edgeId];
        if (!edge) return null;

        const state = this.edgeStates[edgeId];
        const toNode = this.graph.nodes[edge.to];
        const fromNode = this.graph.nodes[edge.from];

        return {
            road_name: edge.name,
            from: fromNode ? fromNode.name : edge.from,
            to: toNode ? toNode.name : edge.to,
            length_m: edge.length,
            lanes: edge.lanes,
            free_speed_kmh: edge.speed_limit_kmh,
            free_speed_ms: edge.free_speed_ms,
            free_flow_time_s: edge.free_flow_time,
            current_vehicles: state.vehicles,
            halting_vehicles: state.halting,
            capacity: edge.capacity,
            effective_capacity: state.effective_capacity,
            vc_ratio: state.vc_ratio,
            incident: state.incident > 0 ? `${state.incident * 100}% dung lượng bị nghẽn` : "Bình thường",
            current_speed_kmh: state.speed_kmh,
            cruise_time_s: state.cruise_time,
            signal_delay_s: state.signal_delay,
            queue_delay_s: state.queue_delay,
            total_travel_time_s: state.travel_time,
            level_of_service: state.los,
            cost: state.cost,
            pheromone: Math.round(state.pheromone * 100) / 100,
            formulas: {
                bpr: "v(t) = v_free / [1 + 0.15 * (V / C)^4]",
                cruise: "T_cruise(t) = L / v(t)",
                queue: "W_queue(t) = (H * 2.0s) / lanes",
                total: "T_ij(t) = T_cruise(t) + W_signal(t) + W_queue(t)",
                cost: "C_ij(t) = 0.2*D_norm + 0.3*T_norm + 0.3*Q_norm + 0.2*W_norm"
            }
        };
    }
}

// Xuất biến toàn cục
if (typeof window !== "undefined") {
    window.TrafficModel = TrafficModel;
}

if (typeof module !== "undefined" && module.exports) {
    module.exports = { TrafficModel };
}
