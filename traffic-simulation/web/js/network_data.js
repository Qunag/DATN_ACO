/**
 * network_data.js – Định nghĩa mạng lưới giao thông dạng đồ thị G = (V, E)
 * Khu vực trung tâm Hà Nội (Đống Đa - Thanh Xuân - Hai Bà Trưng)
 * Khớp 100% tọa độ GPS thực tế (WGS84) của đề tài DATN ACO
 */

// ═══════════════════════════════════════════════════════════════════════════
// TẬP HỢP CÁC NÚT GIAO THÔNG (VERTICES - V)
// Gồm: Ngã ba, Ngã tư, Ngã năm, Nhà ga, Trung tâm trung chuyển
// ═══════════════════════════════════════════════════════════════════════════
const URBAN_NODES = {
    // ── 1. CÁC NÚT NGÃ NĂM PHỨC TẠP ──
    "N_O_CHO_DUA": {
        id: "N_O_CHO_DUA",
        name: "Ngã 5 Ô Chợ Dừa",
        desc: "Giao lộ 5 nhánh: Tôn Đức Thắng - Khâm Thiên - Xã Đàn - La Thành - Nguyễn Lương Bằng",
        lat: 21.018250,
        lng: 105.828550,
        type: "INTERSECTION_5",
        has_signals: true,
        cycle_time: 90, // chu kỳ đèn 90s
        signal_split: { NS: 40, EW: 40, Y: 5 } // tỉ lệ đèn
    },
    "N_KIM_LIEN": {
        id: "N_KIM_LIEN",
        name: "Ngã 5 Hầm chui Kim Liên",
        desc: "Giao cắt Giải Phóng - Lê Duẩn - Đại Cồ Việt - Xã Đàn - Hầm chui Kim Liên",
        lat: 21.011850,
        lng: 105.840750,
        type: "INTERSECTION_5",
        has_signals: true,
        cycle_time: 80,
        signal_split: { NS: 36, EW: 36, Y: 4 }
    },

    // ── 2. CÁC NÚT NGÃ TƯ TRỌNG ĐIỂM (ARTERIAL 4-WAY INTERSECTIONS) ──
    "N_NGA_TU_SO": {
        id: "N_NGA_TU_SO",
        name: "Ngã Tư Sở (Cầu vượt)",
        desc: "Cửa ngõ Tây Nam: Nguyễn Trãi - Tây Sơn - Trường Chinh - Đường Láng",
        lat: 21.002200,
        lng: 105.816400,
        type: "INTERSECTION_4",
        has_signals: true,
        cycle_time: 90,
        signal_split: { NS: 40, EW: 42, Y: 4 }
    },
    "N_NGA_TU_VONG": {
        id: "N_NGA_TU_VONG",
        name: "Ngã Tư Vọng (Cầu vượt)",
        desc: "Giao cắt Trục Giải Phóng - Vành đai 2 Trường Chinh - Đại La",
        lat: 20.999650,
        lng: 105.841100,
        type: "INTERSECTION_4",
        has_signals: true,
        cycle_time: 85,
        signal_split: { NS: 38, EW: 39, Y: 4 }
    },
    "N_CHUA_BOC_TAY_SON": {
        id: "N_CHUA_BOC_TAY_SON",
        name: "Ngã tư Chùa Bộc - Tây Sơn - Thái Hà",
        desc: "Giao lộ thương mại sầm uất Đống Đa",
        lat: 21.010150,
        lng: 105.823650,
        type: "INTERSECTION_4",
        has_signals: true,
        cycle_time: 75,
        signal_split: { NS: 34, EW: 33, Y: 4 }
    },
    "N_CHUA_BOC_PHAM_NGOC_THACH": {
        id: "N_CHUA_BOC_PHAM_NGOC_THACH",
        name: "Ngã tư Chùa Bộc - Phạm Ngọc Thạch",
        desc: "Cầu vượt Chùa Bộc - Tôn Thất Tùng - Đông Tác",
        lat: 21.006800,
        lng: 105.830500,
        type: "INTERSECTION_4",
        has_signals: true,
        cycle_time: 70,
        signal_split: { NS: 31, EW: 31, Y: 4 }
    },
    "N_TRUONG_CHINH_TON_THAT_TUNG": {
        id: "N_TRUONG_CHINH_TON_THAT_TUNG",
        name: "Ngã tư Trường Chinh - Tôn Thất Tùng",
        desc: "Giao cắt Trường Chinh - Lê Trọng Tấn - Tôn Thất Tùng",
        lat: 21.001500,
        lng: 105.830000,
        type: "INTERSECTION_4",
        has_signals: true,
        cycle_time: 75,
        signal_split: { NS: 34, EW: 33, Y: 4 }
    },
    "N_PHAM_NGOC_THACH_XA_DAN": {
        id: "N_PHAM_NGOC_THACH_XA_DAN",
        name: "Ngã tư Phạm Ngọc Thạch - Xã Đàn",
        desc: "Giao cắt Vành đai 1 Xã Đàn và phố Phạm Ngọc Thạch",
        lat: 21.012500,
        lng: 105.833500,
        type: "INTERSECTION_4",
        has_signals: true,
        cycle_time: 70,
        signal_split: { NS: 32, EW: 30, Y: 4 }
    },
    "N_THAI_HA_LANG_HA": {
        id: "N_THAI_HA_LANG_HA",
        name: "Ngã tư Thái Hà - Láng Hạ - Huỳnh Thúc Kháng",
        desc: "Cầu vượt Láng Hạ - Trục văn phòng và tài chính",
        lat: 21.017500,
        lng: 105.816800,
        type: "INTERSECTION_4",
        has_signals: true,
        cycle_time: 80,
        signal_split: { NS: 36, EW: 36, Y: 4 }
    },
    "N_DAI_CO_VIET_TRAN_DAI_NGHIA": {
        id: "N_DAI_CO_VIET_TRAN_DAI_NGHIA",
        name: "Ngã tư Đại Cồ Việt - Trần Đại Nghĩa",
        desc: "Khu vực Cổng Đại học Bách Khoa và Xây Dựng",
        lat: 21.009500,
        lng: 105.848000,
        type: "INTERSECTION_4",
        has_signals: true,
        cycle_time: 70,
        signal_split: { NS: 31, EW: 31, Y: 4 }
    },
    "N_DAI_CO_VIET_BACH_MAI": {
        id: "N_DAI_CO_VIET_BACH_MAI",
        name: "Ngã tư Đại Cồ Việt - Bạch Mai - Phố Huế",
        desc: "Cửa ngõ phố cổ phía Nam - Trần Khát Chân",
        lat: 21.011200,
        lng: 105.852500,
        type: "INTERSECTION_4",
        has_signals: true,
        cycle_time: 80,
        signal_split: { NS: 36, EW: 36, Y: 4 }
    },
    "N_BACH_MAI_LE_THANH_NGHI": {
        id: "N_BACH_MAI_LE_THANH_NGHI",
        name: "Ngã tư Bạch Mai - Lê Thanh Nghị - Thanh Nhàn",
        desc: "Giao lộ khu bệnh viện Thanh Nhàn và chợ Mơ",
        lat: 21.003500,
        lng: 105.850500,
        type: "INTERSECTION_4",
        has_signals: true,
        cycle_time: 70,
        signal_split: { NS: 32, EW: 30, Y: 4 }
    },
    "N_NGUYEN_TRAI_KHUAT_DUY_TIEN": {
        id: "N_NGUYEN_TRAI_KHUAT_DUY_TIEN",
        name: "Ngã tư Thanh Xuân (Vành đai 3)",
        desc: "Nút giao 4 tầng: Nguyễn Trãi - Khuất Duy Tiến - Đường trên cao",
        lat: 20.994500,
        lng: 105.802800,
        type: "INTERSECTION_4",
        has_signals: true,
        cycle_time: 90,
        signal_split: { NS: 40, EW: 42, Y: 4 }
    },

    // ── 3. CÁC NÚT NGÃ BA (3-WAY JUNCTIONS) ──
    "N_GIAI_PHONG_BACH_KHOA": {
        id: "N_GIAI_PHONG_BACH_KHOA",
        name: "Ngã 3 Giải Phóng - Lê Thanh Nghị",
        desc: "Cổng parabol Trường ĐH Bách Khoa Hà Nội",
        lat: 21.004800,
        lng: 105.841500,
        type: "INTERSECTION_3",
        has_signals: true,
        cycle_time: 60,
        signal_split: { NS: 38, EW: 18, Y: 4 }
    },
    "N_GIAI_PHONG_BENH_VIEN": {
        id: "N_GIAI_PHONG_BENH_VIEN",
        name: "Ngã 3 Giải Phóng - Phương Mai",
        desc: "Cổng Cụm Bệnh viện Bạch Mai - Việt Pháp - Tai Mũi Họng",
        lat: 21.002800,
        lng: 105.841400,
        type: "INTERSECTION_3",
        has_signals: true,
        cycle_time: 60,
        signal_split: { NS: 40, EW: 16, Y: 4 }
    },
    "N_GIAI_PHONG_DINH_CONG": {
        id: "N_GIAI_PHONG_DINH_CONG",
        name: "Ngã 3 Giải Phóng - Cầu Định Công",
        desc: "Điểm giao thông kết nối khu đô thị Định Công",
        lat: 20.988000,
        lng: 105.842500,
        type: "INTERSECTION_3",
        has_signals: true,
        cycle_time: 65,
        signal_split: { NS: 42, EW: 19, Y: 4 }
    },
    "N_LANG_YEN_LANG": {
        id: "N_LANG_YEN_LANG",
        name: "Ngã 3 Đường Láng - Yên Lãng",
        desc: "Giao cắt ga tàu điện trên cao Cát Linh - Hà Đông",
        lat: 21.008800,
        lng: 105.811500,
        type: "INTERSECTION_3",
        has_signals: true,
        cycle_time: 60,
        signal_split: { NS: 38, EW: 18, Y: 4 }
    },
    "N_KHAM_THIEN_LE_DUAN": {
        id: "N_KHAM_THIEN_LE_DUAN",
        name: "Ngã 3 Khâm Thiên - Lê Duẩn",
        desc: "Điểm giao đường sắt nội đô và công viên Thống Nhất",
        lat: 21.019500,
        lng: 105.841800,
        type: "INTERSECTION_3",
        has_signals: true,
        cycle_time: 60,
        signal_split: { NS: 36, EW: 20, Y: 4 }
    },
    "N_LE_TRONG_TAN_TRUONG_CHINH": {
        id: "N_LE_TRONG_TAN_TRUONG_CHINH",
        name: "Ngã 3 Trường Chinh - Lê Trọng Tấn",
        desc: "Lối vào khu vực sân bay Bạch Mai và viện Y học PKKQ",
        lat: 21.001800,
        lng: 105.827000,
        type: "INTERSECTION_3",
        has_signals: true,
        cycle_time: 60,
        signal_split: { NS: 38, EW: 18, Y: 4 }
    },

    // ── 4. CÁC NHÀ GA VÀ ĐẦU MỐI GIAO THÔNG (STATIONS & HUBS) ──
    "STA_GA_HA_NOI": {
        id: "STA_GA_HA_NOI",
        name: "Nhà Ga Hà Nội",
        desc: "Ga đường sắt trung tâm thủ đô - Đầu mối hành khách quốc gia",
        lat: 21.024500,
        lng: 105.841200,
        type: "STATION",
        has_signals: true,
        cycle_time: 60,
        signal_split: { NS: 36, EW: 20, Y: 4 }
    },
    "STA_GA_GIAP_BAT": {
        id: "STA_GA_GIAP_BAT",
        name: "Nhà Ga Giáp Bát & Bến xe",
        desc: "Đầu mối vận tải hành khách & hàng hóa phía Nam Hà Nội",
        lat: 20.982500,
        lng: 105.842000,
        type: "STATION",
        has_signals: true,
        cycle_time: 70,
        signal_split: { NS: 45, EW: 21, Y: 4 }
    },
    "HUB_BACH_KHOA": {
        id: "HUB_BACH_KHOA",
        name: "Trung tâm ĐH Bách Khoa - Xây Dựng",
        desc: "Cụm trường đại học lớn nhất Hà Nội với hơn 80.000 sinh viên",
        lat: 21.005500,
        lng: 105.844000,
        type: "HUB",
        has_signals: false,
        cycle_time: 0
    },
    "HUB_ROYAL_CITY": {
        id: "HUB_ROYAL_CITY",
        name: "Khu phức hợp Royal City",
        desc: "Trung tâm thương mại & khu dân cư lưu lượng phương tiện cực lớn",
        lat: 21.000500,
        lng: 105.814200,
        type: "HUB",
        has_signals: true,
        cycle_time: 60,
        signal_split: { NS: 40, EW: 16, Y: 4 }
    }
};

// ═══════════════════════════════════════════════════════════════════════════
// TẬP HỢP CÁC TUYẾN ĐƯỜNG KẾT NỐI (EDGES - E)
// Các con đường hai chiều và một chiều thực tế tại Hà Nội
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Hàm tính khoảng cách thực tế giữa 2 tọa độ GPS theo công thức Haversine (mét)
 */
function haversineDistance(lat1, lon1, lat2, lon2) {
    const R = 6371000.0; // Bán kính trái đất (m)
    const phi1 = (lat1 * Math.PI) / 180.0;
    const phi2 = (lat2 * Math.PI) / 180.0;
    const deltaPhi = ((lat2 - lat1) * Math.PI) / 180.0;
    const deltaLambda = ((lon2 - lon1) * Math.PI) / 180.0;

    const a =
        Math.sin(deltaPhi / 2.0) ** 2 +
        Math.cos(phi1) * Math.cos(phi2) * Math.sin(deltaLambda / 2.0) ** 2;
    const c = 2.0 * Math.atan2(Math.sqrt(a), Math.sqrt(1.0 - a));
    return Math.round(R * c);
}

// Danh sách các cặp kết nối đường bộ hai chiều chính
const ROAD_DEFINITIONS = [
    // ── Trục Giải Phóng (Bắc - Nam huyết mạch 6-8 làn, 60km/h) ──
    {
        name: "Đường Giải Phóng",
        from: "STA_GA_HA_NOI",
        to: "N_KHAM_THIEN_LE_DUAN",
        lanes: 3,
        speed_limit_kmh: 50
    },
    {
        name: "Đường Lê Duẩn",
        from: "N_KHAM_THIEN_LE_DUAN",
        to: "N_KIM_LIEN",
        lanes: 3,
        speed_limit_kmh: 50
    },
    {
        name: "Đường Giải Phóng",
        from: "N_KIM_LIEN",
        to: "N_GIAI_PHONG_BACH_KHOA",
        lanes: 4,
        speed_limit_kmh: 60
    },
    {
        name: "Đường Giải Phóng",
        from: "N_GIAI_PHONG_BACH_KHOA",
        to: "N_GIAI_PHONG_BENH_VIEN",
        lanes: 4,
        speed_limit_kmh: 60
    },
    {
        name: "Đường Giải Phóng",
        from: "N_GIAI_PHONG_BENH_VIEN",
        to: "N_NGA_TU_VONG",
        lanes: 4,
        speed_limit_kmh: 60
    },
    {
        name: "Đường Giải Phóng",
        from: "N_NGA_TU_VONG",
        to: "N_GIAI_PHONG_DINH_CONG",
        lanes: 4,
        speed_limit_kmh: 60
    },
    {
        name: "Đường Giải Phóng",
        from: "N_GIAI_PHONG_DINH_CONG",
        to: "STA_GA_GIAP_BAT",
        lanes: 4,
        speed_limit_kmh: 60
    },

    // ── Trục Trường Chinh - Vành đai 2 (Đông - Tây, 6 làn xe) ──
    {
        name: "Đường Trường Chinh (Vành đai 2)",
        from: "N_NGA_TU_VONG",
        to: "N_TRUONG_CHINH_TON_THAT_TUNG",
        lanes: 4,
        speed_limit_kmh: 60
    },
    {
        name: "Đường Trường Chinh",
        from: "N_TRUONG_CHINH_TON_THAT_TUNG",
        to: "N_LE_TRONG_TAN_TRUONG_CHINH",
        lanes: 4,
        speed_limit_kmh: 60
    },
    {
        name: "Đường Trường Chinh",
        from: "N_LE_TRONG_TAN_TRUONG_CHINH",
        to: "N_NGA_TU_SO",
        lanes: 4,
        speed_limit_kmh: 60
    },

    // ── Trục Nguyễn Trãi - Tây Sơn (Trục Tây Nam, 6 làn xe) ──
    {
        name: "Đường Nguyễn Trãi",
        from: "N_NGUYEN_TRAI_KHUAT_DUY_TIEN",
        to: "HUB_ROYAL_CITY",
        lanes: 4,
        speed_limit_kmh: 60
    },
    {
        name: "Đường Nguyễn Trãi",
        from: "HUB_ROYAL_CITY",
        to: "N_NGA_TU_SO",
        lanes: 4,
        speed_limit_kmh: 60
    },
    {
        name: "Phố Tây Sơn",
        from: "N_NGA_TU_SO",
        to: "N_CHUA_BOC_TAY_SON",
        lanes: 3,
        speed_limit_kmh: 50
    },
    {
        name: "Phố Tây Sơn",
        from: "N_CHUA_BOC_TAY_SON",
        to: "N_O_CHO_DUA",
        lanes: 3,
        speed_limit_kmh: 50
    },

    // ── Trục Xã Đàn - Đại Cồ Việt (Vành đai 1, 6 làn xe) ──
    {
        name: "Đường Xã Đàn (Vành đai 1)",
        from: "N_O_CHO_DUA",
        to: "N_PHAM_NGOC_THACH_XA_DAN",
        lanes: 3,
        speed_limit_kmh: 50
    },
    {
        name: "Đường Xã Đàn",
        from: "N_PHAM_NGOC_THACH_XA_DAN",
        to: "N_KIM_LIEN",
        lanes: 3,
        speed_limit_kmh: 50
    },
    {
        name: "Đường Đại Cồ Việt",
        from: "N_KIM_LIEN",
        to: "N_DAI_CO_VIET_TRAN_DAI_NGHIA",
        lanes: 4,
        speed_limit_kmh: 55
    },
    {
        name: "Đường Đại Cồ Việt",
        from: "N_DAI_CO_VIET_TRAN_DAI_NGHIA",
        to: "N_DAI_CO_VIET_BACH_MAI",
        lanes: 4,
        speed_limit_kmh: 55
    },

    // ── Trục Chùa Bộc - Phạm Ngọc Thạch - Tôn Thất Tùng (4 làn xe) ──
    {
        name: "Phố Chùa Bộc",
        from: "N_CHUA_BOC_TAY_SON",
        to: "N_CHUA_BOC_PHAM_NGOC_THACH",
        lanes: 2,
        speed_limit_kmh: 40
    },
    {
        name: "Phố Phạm Ngọc Thạch",
        from: "N_CHUA_BOC_PHAM_NGOC_THACH",
        to: "N_PHAM_NGOC_THACH_XA_DAN",
        lanes: 2,
        speed_limit_kmh: 40
    },
    {
        name: "Phố Tôn Thất Tùng",
        from: "N_CHUA_BOC_PHAM_NGOC_THACH",
        to: "N_TRUONG_CHINH_TON_THAT_TUNG",
        lanes: 2,
        speed_limit_kmh: 40
    },

    // ── Trục Thái Hà - Láng Hạ ──
    {
        name: "Phố Thái Hà",
        from: "N_CHUA_BOC_TAY_SON",
        to: "N_THAI_HA_LANG_HA",
        lanes: 2,
        speed_limit_kmh: 45
    },
    {
        name: "Đường Láng",
        from: "N_NGA_TU_SO",
        to: "N_LANG_YEN_LANG",
        lanes: 3,
        speed_limit_kmh: 50
    },

    // ── Trục Lê Thanh Nghị - Bạch Mai ──
    {
        name: "Phố Lê Thanh Nghị",
        from: "N_GIAI_PHONG_BACH_KHOA",
        to: "HUB_BACH_KHOA",
        lanes: 2,
        speed_limit_kmh: 40
    },
    {
        name: "Phố Lê Thanh Nghị",
        from: "HUB_BACH_KHOA",
        to: "N_DAI_CO_VIET_TRAN_DAI_NGHIA",
        lanes: 2,
        speed_limit_kmh: 40
    },
    {
        name: "Phố Lê Thanh Nghị",
        from: "HUB_BACH_KHOA",
        to: "N_BACH_MAI_LE_THANH_NGHI",
        lanes: 2,
        speed_limit_kmh: 40
    },
    {
        name: "Phố Bạch Mai",
        from: "N_DAI_CO_VIET_BACH_MAI",
        to: "N_BACH_MAI_LE_THANH_NGHI",
        lanes: 2,
        speed_limit_kmh: 40
    },
    {
        name: "Phố Bạch Mai - Trương Định",
        from: "N_BACH_MAI_LE_THANH_NGHI",
        to: "N_NGA_TU_VONG",
        lanes: 2,
        speed_limit_kmh: 40
    },

    // ── Trục Khâm Thiên - Ô Chợ Dừa ──
    {
        name: "Phố Khâm Thiên",
        from: "N_O_CHO_DUA",
        to: "N_KHAM_THIEN_LE_DUAN",
        lanes: 2,
        speed_limit_kmh: 40
    }
];

/**
 * Xây dựng đồ thị 2 chiều hoàn chỉnh và chuẩn hóa các thông số kỹ thuật
 */
function buildUrbanGraph() {
    const nodes = { ...URBAN_NODES };
    const edges = {};
    const adjacency = {};

    // Khởi tạo danh sách kề cho mỗi nút
    for (const nodeId of Object.keys(nodes)) {
        adjacency[nodeId] = [];
    }

    // Xây dựng các cạnh 2 chiều
    let edgeIndex = 1;
    for (const def of ROAD_DEFINITIONS) {
        const u = def.from;
        const v = def.to;

        if (!nodes[u] || !nodes[v]) {
            console.warn(`[!] Bỏ qua cạnh không hợp lệ: ${u} <-> ${v}`);
            continue;
        }

        const dist_m = haversineDistance(
            nodes[u].lat,
            nodes[u].lng,
            nodes[v].lat,
            nodes[v].lng
        );
        const free_speed_ms = def.speed_limit_kmh / 3.6;
        const free_flow_time = Math.round((dist_m / free_speed_ms) * 10) / 10;

        // Dung lượng tối đa: xe chiếm ~25m khi lưu thông tự do, k_crit ~ 0.04 xe/m/làn
        const capacity = Math.max(
            8,
            Math.round(dist_m * def.lanes * 0.04)
        );

        // Chiều đi: u -> v
        const edgeIdForward = `${u}__TO__${v}`;
        edges[edgeIdForward] = {
            id: edgeIdForward,
            name: `${def.name} (${nodes[u].name} → ${nodes[v].name})`,
            road_name: def.name,
            from: u,
            to: v,
            length: dist_m,
            lanes: def.lanes,
            speed_limit_kmh: def.speed_limit_kmh,
            free_speed_ms: free_speed_ms,
            free_flow_time: free_flow_time,
            capacity: capacity,
            points: [
                [nodes[u].lat, nodes[u].lng],
                [nodes[v].lat, nodes[v].lng]
            ]
        };
        adjacency[u].push(v);

        // Chiều về: v -> u
        const edgeIdBackward = `${v}__TO__${u}`;
        edges[edgeIdBackward] = {
            id: edgeIdBackward,
            name: `${def.name} (${nodes[v].name} → ${nodes[u].name})`,
            road_name: def.name,
            from: v,
            to: u,
            length: dist_m,
            lanes: def.lanes,
            speed_limit_kmh: def.speed_limit_kmh,
            free_speed_ms: free_speed_ms,
            free_flow_time: free_flow_time,
            capacity: capacity,
            points: [
                [nodes[v].lat, nodes[v].lng],
                [nodes[u].lat, nodes[u].lng]
            ]
        };
        adjacency[v].push(u);

        edgeIndex++;
    }

    return {
        type: "URBAN_ARTERIAL",
        name: "Mạng Lưới Giao Thông Trục Chính Hà Nội",
        center: { lat: 21.008, lng: 105.832 },
        zoom: 14,
        nodes: nodes,
        edges: edges,
        adjacency: adjacency
    };
}

// Xuất biến toàn cục
if (typeof window !== "undefined") {
    window.URBAN_GRAPH = buildUrbanGraph();
    window.URBAN_NODES = URBAN_NODES;
    window.haversineDistance = haversineDistance;
}

if (typeof module !== "undefined" && module.exports) {
    module.exports = {
        URBAN_NODES,
        ROAD_DEFINITIONS,
        buildUrbanGraph,
        haversineDistance
    };
}
