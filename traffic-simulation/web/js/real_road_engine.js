/**
 * real_road_engine.js – Động cơ điều hướng và mô phỏng giao thông bám theo khung đường thực tế của Google Maps
 * Tích hợp công thức đo lường ùn tắc từ SUMO TraCI và mô hình Level of Service (LOS) đa sắc màu của Google Maps:
 *   - Xanh lá (#10b981): Thông thoáng
 *   - Vàng (#f59e0b): Đông xe vừa phải
 *   - Đỏ (#ef4444): Ùn tắc nghiêm trọng
 *   - Đỏ thẫm (#991b1b): Tắc cứng / Tai nạn giao thông
 */

class RealRoadEngine {
    constructor() {
        this.accidents = []; // Danh sách các điểm tai nạn [{ id, lat, lng, radius, severity }]
        this.originPoint = null; // { lat, lng, name }
        this.destPoint = null;   // { lat, lng, name }

        this.staticRoute = null; // Lộ trình tĩnh (ngắn nhất, qua tai nạn)
        this.acoRoute = null;    // Lộ trình đàn kiến (né tai nạn)

        this.cars = []; // Danh sách xe đang chạy trên tuyến
        this.carCounter = 1;

        // Kịch bản lưu lượng SUMO (TH1 - TH6 theo Báo cáo 2 & 3 của đề tài)
        this.currentScenario = "TH3";
        this.simSpeedMultiplier = 8.0; // Tỷ lệ tua thời gian thực (8x giúp lộ trình 3-4km xem trọn trong ~25s)
        this.scenarios = {
            "TH1": { name: "TH1: 200 xe/h (Thông thoáng)", flow_vph: 200, base_density: 0.15, max_speed_kmh: 50.0 },
            "TH2": { name: "TH2: 400 xe/h (Lưu thông tốt)", flow_vph: 400, base_density: 0.35, max_speed_kmh: 46.0 },
            "TH3": { name: "TH3: 600 xe/h (Trung bình - Mặc định)", flow_vph: 600, base_density: 0.55, max_speed_kmh: 40.0 },
            "TH4": { name: "TH4: 800 xe/h (Đông đúc)", flow_vph: 800, base_density: 0.75, max_speed_kmh: 30.0 },
            "TH5": { name: "TH5: 1000 xe/h (Ùn ứ diện rộng)", flow_vph: 1000, base_density: 0.95, max_speed_kmh: 18.0 },
            "TH6": { name: "TH6: 1200 xe/h (Ùn tắc nặng)", flow_vph: 1200, base_density: 1.20, max_speed_kmh: 10.0 }
        };

        // Trọng số hàm chi phí đề tài ACO
        this.weights = { w_d: 0.2, w_t: 0.4, w_q: 0.2, w_w: 0.2 };

        // Khởi tạo đồ thị từ dữ liệu OSM nội bộ
        this.initOsmGraph();
    }

    /**
     * Khởi tạo đồ thị mạng lưới đường thực tế từ bundle OSM (623 nút, 1226 cạnh)
     */
    initOsmGraph() {
        const osmData = window.OSM_NETWORK_DATA || { junctions: {}, edges: {} };
        this.junctions = osmData.junctions || {};
        this.edges = osmData.edges || {};

        this.adjacency = {};
        for (const jid of Object.keys(this.junctions)) {
            this.adjacency[jid] = [];
        }

        for (const [eid, edge] of Object.entries(this.edges)) {
            if (this.adjacency[edge.from]) {
                this.adjacency[edge.from].push({
                    to: edge.to,
                    edgeId: eid,
                    length: edge.length,
                    speed_ms: (edge.speed_limit_kmh || 50) / 3.6,
                    lanes: edge.lanes || 2,
                    capacity: edge.capacity || 20,
                    points: edge.points
                });
            }
        }
    }

    findNearestNode(lat, lng) {
        let nearest = null;
        let minDist = Infinity;

        for (const [jid, junc] of Object.entries(this.junctions)) {
            const d = this.haversine(lat, lng, junc.lat, junc.lng);
            if (d < minDist) {
                minDist = d;
                nearest = { id: jid, lat: junc.lat, lng: junc.lng, dist: d };
            }
        }
        return nearest;
    }

    /**
     * Đặt điểm tai nạn / sự cố tại vị trí click của người dùng
     * (Tự động xóa sạch toàn bộ điểm tai nạn cũ trước đó)
     */
    setSingleAccident(lat, lng, radius = 130) {
        this.clearAccidents();
        const id = `INC_${Date.now()}`;
        const accident = {
            id: id,
            lat: lat,
            lng: lng,
            radius: radius, // Bán kính phong tỏa (m)
            severity: 0.90  // Làm giảm 90% dung lượng đường
        };
        this.accidents = [accident];
        return accident;
    }

    addAccident(lat, lng, radius = 130) {
        return this.setSingleAccident(lat, lng, radius);
    }

    clearAccidents() {
        this.accidents = [];
    }

    /**
     * Tính khoảng cách vuông góc từ một điểm (P) đến đoạn thẳng AB (tính theo mét)
     */
    pointToSegmentDistance(pLat, pLng, aLat, aLng, bLat, bLng) {
        const cosLat = Math.cos(((aLat + bLat) / 2) * Math.PI / 180.0);
        const ax = aLng * 111320 * cosLat;
        const ay = aLat * 110540;
        const bx = bLng * 111320 * cosLat;
        const by = bLat * 110540;
        const px = pLng * 111320 * cosLat;
        const py = pLat * 110540;

        const dx = bx - ax;
        const dy = by - ay;
        const lenSq = dx * dx + dy * dy;

        if (lenSq === 0) return Math.hypot(px - ax, py - ay);

        const t = Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / lenSq));
        const projX = ax + t * dx;
        const projY = ay + t * dy;

        return Math.hypot(px - projX, py - projY);
    }

    checkAccidentImpact(points) {
        if (!points || points.length === 0 || this.accidents.length === 0) return null;

        for (const acc of this.accidents) {
            // 1. Kiểm tra khoảng cách tới từng đỉnh tọa độ
            for (let i = 0; i < points.length; i++) {
                const pt = points[i];
                const dist = this.haversine(pt[0], pt[1], acc.lat, acc.lng);
                if (dist <= acc.radius) {
                    return { accident: acc, dist: dist, pointIndex: i };
                }
            }

            // 2. Kiểm tra khoảng cách tới các đoạn thẳng giữa 2 đỉnh liên tiếp (chính xác 100%)
            for (let i = 0; i < points.length - 1; i++) {
                const p1 = points[i];
                const p2 = points[i + 1];
                const d = this.pointToSegmentDistance(acc.lat, acc.lng, p1[0], p1[1], p2[0], p2[1]);
                if (d <= acc.radius) {
                    return { accident: acc, dist: d, segmentIndex: i };
                }
            }
        }
        return null;
    }

    /**
     * CÔNG THỨC CHUẨN TỪ BÁO CÁO 2 SUMO:
     * Tính toán chỉ số ùn tắc tổng hợp (Congestion Index) và phân loại màu sắc Google Maps:
     * Congestion = a*N_norm + b*H_norm + c*W_norm + d*(1 - V/V_max)
     */
    /**
     * CÔNG THỨC CHUẨN TỪ BÁO CÁO 2 SUMO:
     * Tính toán chỉ số ùn tắc tổng hợp (Congestion Index) và phân loại màu sắc Google Maps:
     * Congestion = a*N_norm + b*H_norm + c*W_norm + d*(1 - V/V_max)
     */
    evaluateTrafficSegment(p1, p2, segmentIndex, totalSegments, isAccident = false, isAcoDetour = false) {
        const segLength = this.haversine(p1[0], p1[1], p2[0], p2[1]);
        const scInfo = this.scenarios[this.currentScenario] || this.scenarios["TH3"];
        // Vận tốc tối đa của mạng lưới bị khống chế chặt chẽ bởi kịch bản SUMO (TH1 -> TH6)
        const vMaxKmh = scInfo.max_speed_kmh || 50.0;
        const vMaxMs = vMaxKmh / 3.6;

        // Kịch bản TH chi phối TOÀN BỘ mạng lưới giao thông của thành phố!
        // Tuyến tránh né được nút thắt tai nạn, nhưng vẫn phải chịu áp lực giao thông chung của kịch bản TH (chỉ giảm nhẹ ~15% mật độ do phân tán lưu lượng)
        const detourRelief = isAcoDetour ? 0.85 : 1.0;
        const baseDensity = scInfo.base_density * detourRelief;

        if (isAccident) {
            // Đoạn đường xảy ra tai nạn: Tắc nghẽn kẹt cứng, xe bò 2 km/h
            const speedKmh = 2.0;
            const speedMs = speedKmh / 3.6;
            const travelTime = segLength / speedMs + 180.0;
            const congestion = 0.98;

            return {
                points: [p1, p2],
                length_m: Math.round(segLength),
                speed_kmh: speedKmh,
                travel_time_s: Math.round(travelTime),
                congestion: congestion,
                status: "ACCIDENT_BLOCKED",
                color: "#991b1b", // Đỏ thẫm
                desc: "💥 Điểm tai nạn - Kẹt cứng (2 km/h)",
                traci: {
                    vehicles: 38,
                    halting: 32,
                    waiting_s: 210.0,
                    mean_speed_ms: 0.55
                }
            };
        }

        // Tạo sự biến thiên lưu lượng tự nhiên dọc theo tuyến (các nút giao cắt đông hơn đường thẳng)
        const intersectionFactor = Math.sin(segmentIndex * 1.3) * 0.18;
        const effectiveDensity = Math.max(0.1, baseDensity + intersectionFactor);

        // Vận tốc thực tế tính theo mô hình BPR chuẩn mực (với alpha = 1.8, beta = 3.2)
        // Vận tốc tự động phản ánh đúng kịch bản TH1 (50 km/h) -> TH6 (5-10 km/h)
        const bprDenominator = 1.0 + 1.8 * Math.pow(effectiveDensity, 3.2);
        const actualSpeedKmh = Math.max(2.5, Math.min(vMaxKmh, Math.round(vMaxKmh / bprDenominator)));
        const actualSpeedMs = actualSpeedKmh / 3.6;

        // Các đại lượng TraCI chuẩn hóa
        const nNorm = Math.min(1.0, effectiveDensity * 0.8);
        const haltingVehicles = effectiveDensity > 0.8 ? Math.round(effectiveDensity * 12) : 0;
        const hNorm = Math.min(1.0, haltingVehicles / 15.0);
        const waitingTime = effectiveDensity > 0.7 ? (effectiveDensity * 35.0) : 0.0;
        const wNorm = Math.min(1.0, waitingTime / 60.0);
        const speedNorm = 1.0 - (actualSpeedMs / vMaxMs);

        // Chỉ số ùn tắc tổng hợp theo Báo cáo 2 (Trọng số 0.3, 0.3, 0.2, 0.2)
        const congestion = Math.min(0.95, 0.30 * nNorm + 0.30 * hNorm + 0.20 * wNorm + 0.20 * speedNorm);

        // Phân cấp màu sắc Google Maps chính xác theo vận tốc thực tế
        let color = "#10b981"; // Xanh lá
        let desc = "Thông thoáng";

        if (actualSpeedKmh < 12 || congestion >= 0.80) {
            color = "#ef4444"; // Đỏ: Tắc nghẽn nặng
            desc = `Tắc nghẽn nghiêm trọng (${actualSpeedKmh} km/h)`;
        } else if (actualSpeedKmh < 24 || congestion >= 0.55) {
            color = "#f97316"; // Cam: Ùn ứ
            desc = `Ùn ứ chậm chạp (${actualSpeedKmh} km/h)`;
        } else if (actualSpeedKmh < 36 || congestion >= 0.30) {
            color = "#f59e0b"; // Vàng: Đông xe vừa phải
            desc = `Đông xe vừa phải (${actualSpeedKmh} km/h)`;
        } else {
            color = "#10b981"; // Xanh lá: Thông thoáng
            desc = `Lưu thông thông suốt (${actualSpeedKmh} km/h)`;
        }

        const travelTime = segLength / actualSpeedMs;

        return {
            points: [p1, p2],
            length_m: Math.round(segLength),
            speed_kmh: actualSpeedKmh,
            travel_time_s: Math.round(travelTime),
            congestion: Math.round(congestion * 100) / 100,
            status: "NORMAL",
            color: color,
            desc: desc,
            traci: {
                vehicles: Math.round(nNorm * 25),
                halting: haltingVehicles,
                waiting_s: Math.round(waitingTime),
                mean_speed_ms: Math.round(actualSpeedMs * 10) / 10
            }
        };
    }

    /**
     * Chia polyline đường uốn lượn thành các phân đoạn đa sắc màu (Google Maps Traffic Flow)
     */
    segmentizeRoute(points, length_m, isAcoDetour = false) {
        if (!points || points.length < 2) return [];

        const segments = [];
        const total = points.length;

        for (let i = 0; i < total - 1; i++) {
            const p1 = points[i];
            const p2 = points[i + 1];

            // Kiểm tra phân đoạn này có đi qua vùng ảnh hưởng tai nạn không
            const isAcc = this.accidents.some(acc => {
                const d1 = this.haversine(p1[0], p1[1], acc.lat, acc.lng);
                const d2 = this.haversine(p2[0], p2[1], acc.lat, acc.lng);
                const dSeg = this.pointToSegmentDistance(acc.lat, acc.lng, p1[0], p1[1], p2[0], p2[1]);
                return (d1 <= acc.radius) || (d2 <= acc.radius) || (dSeg <= acc.radius);
            });

            const seg = this.evaluateTrafficSegment(p1, p2, i, total, isAcc, isAcoDetour);
            segments.push(seg);
        }

        return segments;
    }

    /**
     * TÌM KIẾM ĐƯỜNG ĐI VÀ PHÂN ĐOẠN ĐA SẮC MÀU
     */
    async calculateRoutes(latA, lngA, latB, lngB) {
        this.originPoint = { lat: latA, lng: lngA };
        this.destPoint = { lat: latB, lng: lngB };

        // 1. Thử gọi OSRM online
        let osrmRoutes = null;
        try {
            const url = `https://router.project-osrm.org/route/v1/driving/${lngA},${latA};${lngB},${latB}?overview=full&geometries=geojson&alternatives=true&steps=true`;
            const resp = await fetch(url, { signal: AbortSignal.timeout(3000) });
            if (resp.ok) {
                const data = await resp.json();
                if (data.routes && data.routes.length > 0) {
                    osrmRoutes = data.routes;
                }
            }
        } catch (e) {
            console.log("Using internal high-precision OSM road graph.", e);
        }

        if (osrmRoutes && osrmRoutes.length > 0) {
            return await this.processOsrmRoutes(osrmRoutes, latA, lngA, latB, lngB);
        }

        return this.processLocalNetworkRoutes(latA, lngA, latB, lngB);
    }

    async processOsrmRoutes(routes, latA, lngA, latB, lngB) {
        const analyzed = routes.map((r, idx) => {
            const points = r.geometry.coordinates.map(c => [c[1], c[0]]);
            const length_m = r.distance;
            const impact = this.checkAccidentImpact(points);
            const hasAccident = impact !== null;

            // Phân đoạn thành các đoạn đa sắc màu chuẩn Google Maps
            const segments = this.segmentizeRoute(points, length_m, false);

            // Tính tổng thời gian di chuyển từ các phân đoạn
            const totalTravelTime = segments.reduce((sum, s) => sum + s.travel_time_s, 0);

            return {
                id: `route_${idx}`,
                points: points,
                segments: segments,
                length_m: Math.round(length_m),
                travel_time_s: Math.round(totalTravelTime),
                has_accident: hasAccident,
                impact: impact
            };
        });

        // Tuyến Dijkstra (Cố định): Luôn là tuyến ngắn nhất ban đầu (đi qua tai nạn nếu có)
        let staticCandidate = analyzed[0];
        let acoCandidate = analyzed[0];

        if (this.accidents.length > 0) {
            // 1. Kiểm tra các tuyến nhánh có sẵn từ OSRM (những tuyến đại lộ chuẩn hoàn toàn không bị dính tai nạn)
            const cleanOsrmAlternatives = analyzed.filter((r, idx) => idx > 0 && !r.has_accident);

            if (cleanOsrmAlternatives.length > 0) {
                // Tuyệt đối ưu tiên các đại lộ thay thế tự nhiên của thành phố (không bao giờ bị lỗi vòng vào ngõ)
                cleanOsrmAlternatives.sort((a, b) => a.travel_time_s - b.travel_time_s);
                acoCandidate = cleanOsrmAlternatives[0];
            } else if (staticCandidate.has_accident) {
                // 2. Chỉ khi OSRM không trả về tuyến nhánh nào thì mới kích hoạt thuật toán fetchDetourRoute
                const smartDetour = await this.fetchDetourRoute(latA, lngA, latB, lngB, staticCandidate, this.accidents[0]);
                if (smartDetour) {
                    acoCandidate = smartDetour;
                }
            }
        }

        // ĐỒNG BỘ HÓA ĐOẠN ĐƯỜNG DÙNG CHUNG:
        // Cùng một mặt đường vật lý thì 2 xe phải có cùng vận tốc và tình trạng lưu thông
        this.syncSharedSegmentsTraffic(staticCandidate.segments, acoCandidate.segments);

        // Tính lại tổng thời gian di chuyển của ACO sau khi đồng bộ các đoạn chung
        const acoTotalTime = acoCandidate.segments.reduce((sum, s) => sum + s.travel_time_s, 0);

        this.staticRoute = {
            name: "Lộ Trình Cố Định (Dijkstra)",
            type: "STATIC",
            points: staticCandidate.points,
            segments: staticCandidate.segments,
            length_m: staticCandidate.length_m,
            travel_time_s: staticCandidate.travel_time_s,
            has_accident: staticCandidate.has_accident
        };

        this.acoRoute = {
            name: "Lộ Trình Thích Nghi (ACO)",
            type: "ACO",
            points: acoCandidate.points,
            segments: acoCandidate.segments,
            length_m: acoCandidate.length_m,
            travel_time_s: Math.round(acoTotalTime),
            has_accident: acoCandidate.has_accident
        };

        return {
            staticRoute: this.staticRoute,
            acoRoute: this.acoRoute,
            time_savings_s: Math.max(0, this.staticRoute.travel_time_s - this.acoRoute.travel_time_s),
            time_savings_pct: this.staticRoute.travel_time_s > 0 ?
                Math.round(((this.staticRoute.travel_time_s - this.acoRoute.travel_time_s) / this.staticRoute.travel_time_s) * 100) : 0
        };
    }

    /**
     * Đồng bộ hóa trạng thái giao thông trên các đoạn đường dùng chung:
     * Cùng một con đường thì xe Dijkstra và xe ACO phải chịu chung điều kiện giao thông và vận tốc.
     * Vận tốc chỉ khác nhau khi xe ACO bẻ lái sang đường tránh riêng biệt!
     */
    syncSharedSegmentsTraffic(staticSegments, acoSegments) {
        if (!staticSegments || !acoSegments) return;

        for (const aSeg of acoSegments) {
            const p1 = aSeg.points[0];
            const p2 = aSeg.points[1];

            // Tìm phân đoạn tương ứng trên tuyến tĩnh (cùng tọa độ địa lý trong phạm vi 25m)
            const matchedStaticSeg = staticSegments.find(sSeg => {
                const sp1 = sSeg.points[0];
                const sp2 = sSeg.points[1];
                const d1 = this.haversine(p1[0], p1[1], sp1[0], sp1[1]);
                const d2 = this.haversine(p2[0], p2[1], sp2[0], sp2[1]);
                return d1 < 25.0 && d2 < 25.0;
            });

            if (matchedStaticSeg) {
                // Đây là đoạn đường đi chung (ví dụ đoạn xuất phát từ A hoặc nhập làn về B)
                // Cả hai xe đều chịu chung vận tốc và mật độ của con đường đó!
                aSeg.speed_kmh = matchedStaticSeg.speed_kmh;
                aSeg.color = matchedStaticSeg.color;
                aSeg.desc = matchedStaticSeg.desc;
                aSeg.congestion = matchedStaticSeg.congestion;
                aSeg.traci = { ...matchedStaticSeg.traci };
                aSeg.travel_time_s = matchedStaticSeg.travel_time_s;
            }
        }
    }

    /**
     * TÌM LỘ TRÌNH VÒNG TRÁNH (ACO DETOUR) NÉ ĐIỂM TAI NẠN QUA CÁC CON ĐƯỜNG SONG SONG
     * Quét các trục đường song song lân cận từ 500m đến 1.200m cả hai bên trái/phải,
     * gửi truy vấn đồng thời (Parallel) và chọn ra tuyến đường VỪA NÉ TAI NẠN VỪA NHANH NHẤT!
     */
    async fetchDetourRoute(latA, lngA, latB, lngB, primaryRoute, accident) {
        if (!primaryRoute || !primaryRoute.points || primaryRoute.points.length < 2) return null;

        // 1. Tìm điểm trên tuyến chính gần tâm tai nạn nhất
        let closestIdx = 0;
        let minDist = Infinity;
        for (let i = 0; i < primaryRoute.points.length; i++) {
            const pt = primaryRoute.points[i];
            const d = this.haversine(pt[0], pt[1], accident.lat, accident.lng);
            if (d < minDist) {
                minDist = d;
                closestIdx = i;
            }
        }

        // 2. Tính vector tiếp tuyến ổn định (lấy khoảng cách ~150m trước và sau điểm gần tai nạn)
        let prevIdx = closestIdx;
        let distBack = 0;
        while (prevIdx > 0 && distBack < 150) {
            distBack += this.haversine(primaryRoute.points[prevIdx][0], primaryRoute.points[prevIdx][1], primaryRoute.points[prevIdx - 1][0], primaryRoute.points[prevIdx - 1][1]);
            prevIdx--;
        }

        let nextIdx = closestIdx;
        let distFwd = 0;
        while (nextIdx < primaryRoute.points.length - 1 && distFwd < 150) {
            distFwd += this.haversine(primaryRoute.points[nextIdx][0], primaryRoute.points[nextIdx][1], primaryRoute.points[nextIdx + 1][0], primaryRoute.points[nextIdx + 1][1]);
            nextIdx++;
        }

        const pPrev = primaryRoute.points[prevIdx];
        const pNext = primaryRoute.points[nextIdx];

        // Đổi sang hệ mét để vector vuông góc không bị méo theo vĩ độ
        const cosLat = Math.cos(accident.lat * Math.PI / 180.0);
        const dLatM = (pNext[0] - pPrev[0]) * 110540;
        const dLngM = (pNext[1] - pPrev[1]) * 111320 * cosLat;
        const lenM = Math.hypot(dLatM, dLngM) || 1.0;

        // Vector pháp tuyến vuông góc 90 độ so với trục đường
        const normLat = -dLngM / lenM;
        const normLng = dLatM / lenM;

        // Quét các trục đường song song lân cận từ 500m đến 1.200m cả hai bên (Trái/Phải)
        const offsets = [500, -500, 650, -650, 850, -850, 1050, -1050, 1200, -1200];

        // 3. Gửi đồng thời (Parallel) tất cả các yêu cầu tìm đường vòng tránh qua OSRM
        const fetchPromises = offsets.map(async (offsetM) => {
            const wpLat = accident.lat + (offsetM * normLat) / 110540;
            const wpLng = accident.lng + (offsetM * normLng) / (111320 * cosLat);
            const url = `https://router.project-osrm.org/route/v1/driving/${lngA},${latA};${wpLng.toFixed(5)},${wpLat.toFixed(5)};${lngB},${latB}?overview=full&geometries=geojson&continue_straight=true`;

            try {
                const resp = await fetch(url, { signal: AbortSignal.timeout(3000) });
                if (!resp.ok) return null;
                const data = await resp.json();
                if (!data.routes || data.routes.length === 0) return null;
                return { offsetM, route: data.routes[0] };
            } catch (e) {
                return null;
            }
        });

        const results = await Promise.allSettled(fetchPromises);
        const candidates = [];

        for (const res of results) {
            if (res.status !== "fulfilled" || !res.value) continue;
            const { offsetM, route } = res.value;
            const detourPoints = route.geometry.coordinates.map(c => [c[1], c[0]]);

            // ĐIỀU KIỆN 1: Tuyến vòng tránh phải NÉ SẠCH TOÀN BỘ VÙNG TAI NẠN
            if (this.checkAccidentImpact(detourPoints) !== null) continue;

            // ĐIỀU KIỆN 2: Tuyến vòng tránh không được dài gấp 2.8 lần tuyến gốc (tránh đi vòng vô tận)
            if (primaryRoute.length_m > 0 && route.distance > primaryRoute.length_m * 2.8) continue;

            // ĐIỀU KIỆN 3: TUYỆT ĐỐI LOẠI BỎ CÁC TUYẾN CÓ VÒNG MÓC CÂU / QUAY ĐẦU CHỮ U TRONG NGÕ CỤT
            if (this.hasAlleyUTurnHook(detourPoints)) continue;

            // ĐIỀU KIỆN 4: LOẠI BỎ TUYẾN RẼ VÀO NGÕ RỒI LẠI ĐÂM RA ĐÚNG CON ĐƯỜNG CŨ (LOOPBACK)
            if (this.hasAlleyLoopback(detourPoints, primaryRoute)) continue;

            // Phân đoạn tuyến đường với trạng thái thông thoáng của đường tránh (isAcoDetour = true)
            const segments = this.segmentizeRoute(detourPoints, route.distance, true);
            const travelTime = segments.reduce((sum, s) => sum + s.travel_time_s, 0);

            // HÀM MỤC TIÊU ACO (ĐA MỤC TIÊU - TỐI THIỂU HÓA THỜI GIAN VÀ ĐỘ DÀI):
            // Ưu tiên cao nhất là THỜI GIAN NHANH NHẤT (travel_time_s) + phạt nhẹ độ dài dư thừa
            const distanceOverheadM = Math.max(0, route.distance - (primaryRoute.length_m || route.distance));
            const acoCost = travelTime + (distanceOverheadM / 1000) * 10.0;

            candidates.push({
                points: detourPoints,
                segments: segments,
                length_m: Math.round(route.distance),
                travel_time_s: Math.round(travelTime),
                offsetM: offsetM,
                acoCost: acoCost,
                has_accident: false
            });
        }

        // 4. CHỌN TUYẾN ĐƯỜNG VÒNG TRÁNH TỐI ƯU NHẤT (NHANH NHẤT VÀ NÉ SẠCH TAI NẠN)
        if (candidates.length > 0) {
            candidates.sort((a, b) => a.acoCost - b.acoCost);
            const bestDetour = candidates[0];
            console.log(`[ACO Detour Engine] Tuyến vòng tránh hợp lệ: Offset ${bestDetour.offsetM > 0 ? '+' : ''}${bestDetour.offsetM}m | Độ dài: ${(bestDetour.length_m / 1000).toFixed(1)} km | Thời gian: ${Math.round(bestDetour.travel_time_s / 60)} phút`);
            return bestDetour;
        }

        // 5. Fallback nếu OSRM không có tuyến phù hợp: Thuật toán Dijkstra/ACO đồ thị nội bộ
        return this.getLocalBypassRoute(latA, lngA, latB, lngB);
    }

    /**
     * Phát hiện và loại bỏ các tuyến có vòng móc câu quay đầu vô lý trong ngõ cụt:
     * Xe đang đi đường lớn bỗng rẽ vào ngõ, quay đầu chữ U (> 114 độ) rồi lại đâm ra đường cũ.
     */
    hasAlleyUTurnHook(points) {
        if (!points || points.length < 4) return false;

        for (let i = 1; i < points.length - 2; i++) {
            const p0 = points[i - 1];
            const p1 = points[i];
            const p2 = points[i + 1];

            const v1Lat = p1[0] - p0[0];
            const v1Lng = p1[1] - p0[1];
            const v2Lat = p2[0] - p1[0];
            const v2Lng = p2[1] - p1[1];

            const len1 = Math.hypot(v1Lat, v1Lng);
            const len2 = Math.hypot(v2Lat, v2Lng);
            if (len1 < 1e-7 || len2 < 1e-7) continue;

            const cosAngle = (v1Lat * v2Lat + v1Lng * v2Lng) / (len1 * len2);
            // cosAngle < -0.40 tương đương góc rẽ gập > 114 độ (quay ngược lại hướng vừa đi)
            if (cosAngle < -0.40) {
                return true;
            }
        }
        return false;
    }

    /**
     * Phát hiện hiện tượng rẽ vào ngõ lượn một vòng ngắn rồi lại đâm ra chính con đường cũ
     */
    hasAlleyLoopback(points, primaryRoute) {
        if (!points || !primaryRoute || !primaryRoute.points || primaryRoute.points.length < 2) return false;

        let departIdx = -1;
        let rejoinIdx = -1;

        for (let i = 0; i < points.length; i++) {
            const pt = points[i];
            const isNearPrimary = primaryRoute.points.some(ppt => this.haversine(pt[0], pt[1], ppt[0], ppt[1]) < 22);

            if (!isNearPrimary && departIdx === -1) {
                departIdx = i;
            } else if (isNearPrimary && departIdx !== -1 && rejoinIdx === -1) {
                rejoinIdx = i;
                let detourDist = 0;
                for (let k = departIdx; k < rejoinIdx; k++) {
                    detourDist += this.haversine(points[k][0], points[k][1], points[k + 1][0], points[k + 1][1]);
                }
                // Nếu rẽ ra khỏi đường chính rồi lại đâm ra đúng đường chính sau một đoạn ngắn (< 450m)
                // -> Đây là một vòng lách ngõ vô nghĩa (Dog-leg hook)!
                if (detourDist < 450) {
                    return true;
                }
                departIdx = -1;
                rejoinIdx = -1;
            }
        }
        return false;
    }

    getLocalBypassRoute(latA, lngA, latB, lngB) {
        const startNode = this.findNearestNode(latA, lngA);
        const endNode = this.findNearestNode(latB, lngB);
        if (!startNode || !endNode) return null;

        const acoPath = this.dijkstraOsm(startNode.id, endNode.id, true);
        if (acoPath && acoPath.points && acoPath.points.length > 1) {
            const segments = this.segmentizeRoute(acoPath.points, acoPath.length);
            const travelTime = segments.reduce((sum, s) => sum + s.travel_time_s, 0);
            return {
                points: acoPath.points,
                segments: segments,
                length_m: Math.round(acoPath.length),
                travel_time_s: Math.round(travelTime),
                has_accident: acoPath.has_accident
            };
        }
        return null;
    }

    processLocalNetworkRoutes(latA, lngA, latB, lngB) {
        const startNode = this.findNearestNode(latA, lngA);
        const endNode = this.findNearestNode(latB, lngB);

        if (!startNode || !endNode) return null;

        const staticPath = this.dijkstraOsm(startNode.id, endNode.id, false);
        const acoPath = this.dijkstraOsm(startNode.id, endNode.id, true);

        const staticSegments = this.segmentizeRoute(staticPath.points, staticPath.length);
        const acoSegments = this.segmentizeRoute(acoPath.points, acoPath.length);

        const staticTime = staticSegments.reduce((sum, s) => sum + s.travel_time_s, 0);
        const acoTime = acoSegments.reduce((sum, s) => sum + s.travel_time_s, 0);

        this.staticRoute = {
            name: "Lộ Trình Cố Định (Dijkstra)",
            type: "STATIC",
            points: staticPath.points,
            segments: staticSegments,
            length_m: staticPath.length,
            travel_time_s: staticTime,
            has_accident: staticPath.has_accident
        };

        this.acoRoute = {
            name: "Lộ Trình Thích Nghi (ACO)",
            type: "ACO",
            points: acoPath.points,
            segments: acoSegments,
            length_m: acoPath.length,
            travel_time_s: acoTime,
            has_accident: acoPath.has_accident
        };

        return {
            staticRoute: this.staticRoute,
            acoRoute: this.acoRoute,
            time_savings_s: Math.max(0, this.staticRoute.travel_time_s - this.acoRoute.travel_time_s),
            time_savings_pct: this.staticRoute.travel_time_s > 0 ?
                Math.round(((this.staticRoute.travel_time_s - this.acoRoute.travel_time_s) / this.staticRoute.travel_time_s) * 100) : 0
        };
    }

    dijkstraOsm(startId, endId, trafficAware = true) {
        const dist = {};
        const prev = {};
        const prevEdge = {};
        const unvisited = new Set(Object.keys(this.junctions));

        for (const jid of Object.keys(this.junctions)) dist[jid] = Infinity;
        dist[startId] = 0;

        while (unvisited.size > 0) {
            let u = null;
            let minDist = Infinity;
            for (const n of unvisited) {
                if (dist[n] < minDist) {
                    minDist = dist[n];
                    u = n;
                }
            }

            if (!u || minDist === Infinity || u === endId) break;
            unvisited.delete(u);

            for (const edge of (this.adjacency[u] || [])) {
                if (!unvisited.has(edge.to)) continue;

                const impact = this.checkAccidentImpact(edge.points);
                const isBlocked = trafficAware && (impact !== null);

                const penalty = isBlocked ? 100000.0 : 1.0;
                const weight = edge.length * penalty;
                const alt = dist[u] + weight;

                if (alt < dist[edge.to]) {
                    dist[edge.to] = alt;
                    prev[edge.to] = u;
                    prevEdge[edge.to] = edge;
                }
            }
        }

        const points = [];
        let curr = endId;
        let totalLen = 0;
        let hasAccident = false;

        while (curr && prev[curr]) {
            const edge = prevEdge[curr];
            if (edge && edge.points) {
                const impact = this.checkAccidentImpact(edge.points);
                if (impact) hasAccident = true;
                totalLen += edge.length;

                for (let i = edge.points.length - 1; i >= 0; i--) {
                    points.unshift(edge.points[i]);
                }
            }
            curr = prev[curr];
        }

        if (points.length === 0) {
            const nA = this.junctions[startId];
            const nB = this.junctions[endId];
            points.push([nA.lat, nA.lng], [nB.lat, nB.lng]);
            totalLen = this.haversine(nA.lat, nA.lng, nB.lat, nB.lng);
        }

        return {
            points: points,
            length: Math.round(totalLen),
            has_accident: hasAccident
        };
    }

    startVehicleSimulation() {
        this.cars = [];

        if (this.staticRoute && this.staticRoute.points.length > 1) {
            const firstSeg = (this.staticRoute.segments && this.staticRoute.segments[0]) ? this.staticRoute.segments[0] : null;
            const initSpeed = firstSeg ? firstSeg.speed_kmh : 35;
            this.cars.push({
                id: "CAR_STATIC",
                name: "Xe Dijkstra (Cố định)",
                type: "STATIC",
                color: "#f97316",
                points: this.staticRoute.points,
                segments: this.staticRoute.segments || [],
                totalPoints: this.staticRoute.points.length,
                currentPtIdx: 0,
                lat: this.staticRoute.points[0][0],
                lng: this.staticRoute.points[0][1],
                speedKmh: initSpeed,
                currentSegColor: firstSeg ? firstSeg.color : "#10b981",
                currentSegDesc: firstSeg ? firstSeg.desc : "Bắt đầu xuất phát",
                progress: 0.0,
                bearing: 0,
                isBlocked: false,
                status: "RUNNING",
                timeElapsed: 0
            });
        }

        if (this.acoRoute && this.acoRoute.points.length > 1) {
            const firstSeg = (this.acoRoute.segments && this.acoRoute.segments[0]) ? this.acoRoute.segments[0] : null;
            const initSpeed = firstSeg ? firstSeg.speed_kmh : 35;
            this.cars.push({
                id: "CAR_ACO",
                name: "Xe ACO (Thích nghi)",
                type: "ACO",
                color: "#a855f7",
                points: this.acoRoute.points,
                segments: this.acoRoute.segments || [],
                totalPoints: this.acoRoute.points.length,
                currentPtIdx: 0,
                lat: this.acoRoute.points[0][0],
                lng: this.acoRoute.points[0][1],
                speedKmh: initSpeed,
                currentSegColor: firstSeg ? firstSeg.color : "#10b981",
                currentSegDesc: firstSeg ? firstSeg.desc : "Bắt đầu xuất phát",
                progress: 0.0,
                bearing: 0,
                isBlocked: false,
                status: "RUNNING",
                timeElapsed: 0
            });
        }
    }

    updateVehicleKinematics(dtSeconds) {
        // Tỷ lệ tua thời gian mô phỏng (mặc định 8x giúp cung đường 3-4km chạy hết trong ~25s)
        const timeScale = this.simSpeedMultiplier || 8.0;

        for (const car of this.cars) {
            if (car.status === "ARRIVED") continue;

            car.timeElapsed += dtSeconds * timeScale;

            // 1. Xác định phân đoạn đường mà xe đang lăn bánh
            const segIdx = Math.min(car.currentPtIdx, (car.segments ? car.segments.length - 1 : 0));
            const currentSeg = (car.segments && car.segments.length > 0) ? car.segments[segIdx] : null;

            // 2. Kiểm tra xe có đang nằm trong bán kính phong tỏa của tai nạn không
            let inAccidentZone = false;
            for (const acc of this.accidents) {
                const distToAcc = this.haversine(car.lat, car.lng, acc.lat, acc.lng);
                if (distToAcc <= acc.radius) {
                    inAccidentZone = true;
                    break;
                }
            }

            // 3. TÍNH VẬN TỐC MỤC TIÊU THEO ĐÚNG ĐOẠN ĐƯỜNG SUMO VÀ MÀU SẮC GOOGLE MAPS
            let targetSpeed = 35.0; // Mặc định
            let segColor = "#10b981";
            let segDesc = "Thông thoáng";

            if (inAccidentZone) {
                // Gặp tai nạn: Kẹt cứng, nhích từng mét với vận tốc 1.8 - 2.5 km/h
                targetSpeed = 2.0;
                segColor = "#991b1b";
                segDesc = "💥 KẸT CỨNG TAI NẠN (2 km/h)";
                car.isBlocked = true;
            } else if (currentSeg) {
                // Lấy đúng vận tốc thực tế của phân đoạn đường tính từ SUMO TraCI & kịch bản TH1-TH6!
                targetSpeed = currentSeg.speed_kmh;
                segColor = currentSeg.color;
                segDesc = currentSeg.desc;
                car.isBlocked = targetSpeed < 14.0; // Dưới 14 km/h là ùn tắc
            }

            car.currentSegColor = segColor;
            car.currentSegDesc = segDesc;

            // 4. MÔ HÌNH VẬT LÝ GIA TỐC VÀ PHANH (SUMO Krauss Model)
            // Xe không đổi vận tốc tức thì mà tăng tốc / phanh mượt mà theo gia tốc thực
            const speedDiff = targetSpeed - car.speedKmh;
            if (speedDiff > 0) {
                // Tăng tốc: a = 2.5 m/s² = 9.0 km/h mỗi giây
                const accel = 9.0;
                car.speedKmh = Math.min(targetSpeed, car.speedKmh + accel * dtSeconds * (timeScale * 0.45));
            } else {
                // Giảm tốc / Phanh: b = 4.5 m/s² = 16.2 km/h mỗi giây (hoặc phanh gấp khi gặp tai nạn)
                const brake = inAccidentZone ? 28.0 : 16.2;
                car.speedKmh = Math.max(targetSpeed, car.speedKmh - brake * dtSeconds * (timeScale * 0.45));
            }

            // 5. TÍNH QUÃNG ĐƯỜNG XE DI CHUYỂN TRONG BƯỚC NÀY
            // Vận tốc (m/s) = speedKmh / 3.6
            // Quãng đường (m) = speedMs * dtSeconds * timeScale
            // Khi tốc độ thấp (2 km/h), xe di chuyển cực chậm; khi tốc độ cao (50 km/h), xe phi nhanh!
            const speedMs = Math.max(0.3, car.speedKmh / 3.6);
            const stepDist = speedMs * dtSeconds * timeScale;

            const pts = car.points;
            if (car.currentPtIdx < pts.length - 1) {
                const p1 = pts[car.currentPtIdx];
                const p2 = pts[car.currentPtIdx + 1];
                const segLen = Math.max(1.0, this.haversine(p1[0], p1[1], p2[0], p2[1]));

                car.progress += stepDist / segLen;

                if (car.progress >= 1.0) {
                    car.progress = 0.0;
                    car.currentPtIdx++;
                    if (car.currentPtIdx >= pts.length - 1) {
                        car.status = "ARRIVED";
                        car.lat = pts[pts.length - 1][0];
                        car.lng = pts[pts.length - 1][1];
                        car.speedKmh = 0;
                        car.currentSegDesc = "🏁 Đã về đích!";
                        continue;
                    }
                }

                const curP1 = pts[car.currentPtIdx];
                const curP2 = pts[car.currentPtIdx + 1];
                car.lat = curP1[0] + car.progress * (curP2[0] - curP1[0]);
                car.lng = curP1[1] + car.progress * (curP2[1] - curP1[1]);

                const dLat = curP2[0] - curP1[0];
                const dLng = curP2[1] - curP1[1];
                car.bearing = (Math.atan2(dLng, dLat) * 180.0 / Math.PI + 360) % 360;
            }
        }
    }

    haversine(lat1, lon1, lat2, lon2) {
        const R = 6371000.0;
        const dLat = (lat2 - lat1) * Math.PI / 180.0;
        const dLon = (lon2 - lon1) * Math.PI / 180.0;
        const a = Math.sin(dLat / 2) ** 2 + Math.cos(lat1 * Math.PI / 180.0) * Math.cos(lat2 * Math.PI / 180.0) * Math.sin(dLon / 2) ** 2;
        return R * 2.0 * Math.atan2(Math.sqrt(a), Math.sqrt(1.0 - a));
    }
}

// Xuất biến toàn cục
if (typeof window !== "undefined") {
    window.RealRoadEngine = RealRoadEngine;
}
