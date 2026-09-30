/**
 * app.js – Trung tâm điều phối ứng dụng mô phỏng giao thông trên khung đường Google Maps
 * Xử lý click chọn điểm A - B tự do, cắm điểm tai nạn và thực thi so sánh thuật toán ACO.
 */

document.addEventListener("DOMContentLoaded", async () => {
    // ── 1. KHỞI TẠO CÁC ĐỘNG CƠ ──
    const realRoadEngine = new window.RealRoadEngine();
    const mapController = new window.MapController("map-container", {
        center: [21.012, 105.828], // Trung tâm Hà Nội
        zoom: 14
    });

    // Chế độ tương tác hiện tại ('IDLE', 'SET_ORIGIN', 'SET_DEST', 'SET_ACCIDENT')
    let currentInteractionMode = "IDLE";
    let isCarSimulationRunning = false;
    let lastTimestamp = performance.now();

    // ── 2. THIẾT LẬP MẶC ĐỊNH BAN ĐẦU ĐỂ USER THẤY NGAY ──
    // Điểm A: Ngã Tư Sở (21.0022, 105.8164)
    // Điểm B: Khu vực Bách Khoa - Giải Phóng (21.0055, 105.8440)
    let pointA = { lat: 21.0022, lng: 105.8164, name: "Ngã Tư Sở (Đường Nguyễn Trãi)" };
    let pointB = { lat: 21.0055, lng: 105.8440, name: "Đại học Bách Khoa (Đường Giải Phóng)" };

    mapController.setOrigin(pointA.lat, pointA.lng, pointA.name);
    mapController.setDestination(pointB.lat, pointB.lng, pointB.name);

    // Đặt sẵn 1 điểm tai nạn tại ngã tư Trường Chinh - Tôn Thất Tùng (21.0015, 105.8300)
    const initialAccident = realRoadEngine.setSingleAccident(21.0015, 105.8300, 220);
    mapController.setSingleAccidentMarker(initialAccident);

    // Tính toán lộ trình thực tế ban đầu (bảo vệ bằng try-catch)
    try {
        await updateAndRenderRoutes();
    } catch (err) {
        console.error("Lỗi khi tính toán ban đầu:", err);
    }

    // ── 3. VÒNG LẶP MÔ PHỎNG XE CHẠY (60 FPS) ──
    function animationLoop(timestamp) {
        const deltaSec = Math.min(0.1, (timestamp - lastTimestamp) / 1000.0);
        lastTimestamp = timestamp;

        if (isCarSimulationRunning) {
            realRoadEngine.updateVehicleKinematics(deltaSec);
            mapController.updateCars(realRoadEngine.cars);

            // Cập nhật trạng thái xe lên bảng điều khiển
            updateCarProgressInfo();
        }

        requestAnimationFrame(animationLoop);
    }
    requestAnimationFrame(animationLoop);

    // ── 4. HÀM TÍNH TOÁN VÀ VẼ LỘ TRÌNH THỰC TẾ TRÊN KHUNG ĐƯỜNG ──
    async function updateAndRenderRoutes() {
        showToast("Đang tính toán khung đường thực tế trên Google Maps...", "info");

        const result = await realRoadEngine.calculateRoutes(
            pointA.lat, pointA.lng,
            pointB.lat, pointB.lng
        );

        if (!result) {
            showToast("Không tìm được tuyến đường nối giữa 2 điểm này!", "error");
            return;
        }

        // Vẽ 2 tuyến đường uốn lượn trên Google Map
        mapController.renderRoutes(result.staticRoute, result.acoRoute);

        // Khởi động xe chạy thử nghiệm
        realRoadEngine.startVehicleSimulation();
        isCarSimulationRunning = true;

        // Cập nhật thông số so sánh lên bảng HUD
        updateComparisonDashboard(result);
    }

    // ── 5. CẬP NHẬT BẢNG SO SÁNH DASHBOARD ──
    function updateComparisonDashboard(result) {
        const staticR = result.staticRoute;
        const acoR = result.acoRoute;

        const staticKm = (staticR.length_m / 1000).toFixed(1);
        const staticMin = Math.round(staticR.travel_time_s / 60);

        const acoKm = (acoR.length_m / 1000).toFixed(1);
        const acoMin = Math.round(acoR.travel_time_s / 60);

        // Hiển thị thông số Tuyến Tĩnh
        document.getElementById("hud-static-dist").innerText = `${staticKm} km`;
        document.getElementById("hud-static-time").innerText = `${staticMin} phút`;
        document.getElementById("hud-static-status").innerHTML = staticR.has_accident ?
            `<span class="badge badge-danger">⚠️ Bị Kẹt Tai Nạn</span>` :
            `<span class="badge badge-neutral">Bình Thường</span>`;

        // Hiển thị thông số Tuyến ACO
        document.getElementById("hud-aco-dist").innerText = `${acoKm} km`;
        document.getElementById("hud-aco-time").innerText = `${acoMin} phút`;
        document.getElementById("hud-aco-status").innerHTML = acoR.has_accident ?
            `<span class="badge badge-danger">⚠️ Bị Kẹt Tai Nạn</span>` :
            `<span class="badge badge-success">✨ Thông Thoáng (Né Tai Nạn Nhanh Nhất)</span>`;

        // Tiết kiệm thời gian chính xác
        const savingsSec = Math.max(0, staticR.travel_time_s - acoR.travel_time_s);
        const savingsMin = Math.round(savingsSec / 60);
        const savingsPct = result.time_savings_pct;

        const badgeElem = document.getElementById("hud-savings-badge");
        if (badgeElem) {
            if (savingsMin >= 1) {
                badgeElem.innerText = `Tiết kiệm ${savingsMin} phút (Nhanh hơn ${savingsPct}%)`;
            } else if (savingsSec > 10) {
                badgeElem.innerText = `Tiết kiệm ${savingsSec}s (Nhanh hơn ${savingsPct}%)`;
            } else {
                badgeElem.innerText = `Thời gian tương đương`;
            }
        }
    }

    function updateCarProgressInfo() {
        const staticCar = realRoadEngine.cars.find(c => c.type === "STATIC");
        const acoCar = realRoadEngine.cars.find(c => c.type === "ACO");

        if (staticCar) {
            const spd = Math.round(staticCar.speedKmh);
            const color = staticCar.currentSegColor || "#f97316";
            document.getElementById("car-static-speed").innerHTML = `
                <span style="color: ${color}; font-weight: 800;">${spd} km/h</span>
            `;
            let stateText = staticCar.currentSegDesc || "Đang chạy";
            if (staticCar.status === "ARRIVED") {
                stateText = `🏁 Đã về đích (${Math.round(staticCar.timeElapsed)}s)`;
            }
            document.getElementById("car-static-state").innerHTML = `
                <span style="color: ${color}; font-size: 11px;">● ${stateText}</span>
            `;
        }

        if (acoCar) {
            const spd = Math.round(acoCar.speedKmh);
            const color = acoCar.currentSegColor || "#a855f7";
            document.getElementById("car-aco-speed").innerHTML = `
                <span style="color: ${color}; font-weight: 800;">${spd} km/h</span>
            `;
            let stateText = acoCar.currentSegDesc || "Lưu thông thông suốt";
            if (acoCar.status === "ARRIVED") {
                stateText = `🏁 Đã về đích (${Math.round(acoCar.timeElapsed)}s) ✓`;
            }
            document.getElementById("car-aco-state").innerHTML = `
                <span style="color: ${color}; font-size: 11px;">● ${stateText}</span>
            `;
        }
    }

    // ── 6. BẮT SỰ KIỆN CLICK TRÊN GOOGLE MAPS ──
    mapController.onMapClickCallback = async (latlng) => {
        const lat = latlng.lat;
        const lng = latlng.lng;

        if (currentInteractionMode === "IDLE") {
            showToast("💡 Mẹo: Nhấp vào nút 'Chọn Điểm Đi (A)', 'Chọn Điểm Đến (B)' hoặc 'Cắm Tai Nạn' bên trái trước khi click!", "info");
            return;
        }

        if (currentInteractionMode === "SET_ORIGIN") {
            // Khi chọn lại điểm A: Xóa sạch đoạn đường cũ, tai nạn cũ và xe cũ
            realRoadEngine.clearAccidents();
            mapController.clearAccidents();
            mapController.clearRoutes();
            mapController.clearCars();
            realRoadEngine.cars = [];

            pointA = { lat: lat, lng: lng, name: `Tọa độ (${lat.toFixed(4)}, ${lng.toFixed(4)})` };
            mapController.setOrigin(lat, lng, "Điểm Xuất Phát (A)");
            document.getElementById("btn-set-origin").classList.remove("active");
            mapController.setPickMode(false);
            currentInteractionMode = "IDLE";
            showToast("🟢 Đã chọn Điểm A mới! Đã xóa đoạn đường và sự cố cũ.", "success");

            if (pointB) {
                await updateAndRenderRoutes();
            }
        }
        else if (currentInteractionMode === "SET_DEST") {
            // Khi chọn lại điểm B: Xóa sạch đoạn đường cũ, tai nạn cũ và xe cũ
            realRoadEngine.clearAccidents();
            mapController.clearAccidents();
            mapController.clearRoutes();
            mapController.clearCars();
            realRoadEngine.cars = [];

            pointB = { lat: lat, lng: lng, name: `Tọa độ (${lat.toFixed(4)}, ${lng.toFixed(4)})` };
            mapController.setDestination(lat, lng, "Điểm Đích (B)");
            document.getElementById("btn-set-dest").classList.remove("active");
            mapController.setPickMode(false);
            currentInteractionMode = "IDLE";
            showToast("🔴 Đã chọn Điểm B mới! Đã xóa đoạn đường và sự cố cũ.", "success");

            if (pointA) {
                await updateAndRenderRoutes();
            }
        }
        else if (currentInteractionMode === "SET_ACCIDENT") {
            // Khi cắm tai nạn mới: Xóa sạch tai nạn cũ và đường cũ, cắm tai nạn duy nhất tại điểm click
            mapController.clearRoutes();
            mapController.clearCars();
            realRoadEngine.cars = [];

            const acc = realRoadEngine.setSingleAccident(lat, lng, 130);
            mapController.setSingleAccidentMarker(acc);

            document.getElementById("btn-set-accident").classList.remove("active");
            mapController.setPickMode(false);
            currentInteractionMode = "IDLE";
            showToast("💥 Đã xóa tai nạn cũ và cắm tai nạn mới! ACO đang vẽ lại đường né...", "error");

            await updateAndRenderRoutes();
        }
    };

    // ── 7. CÁC NÚT BẤM ĐIỀU KHIỂN CHẾ ĐỘ ──

    // Nút Chọn Điểm Xuất Phát A
    document.getElementById("btn-set-origin").addEventListener("click", () => {
        currentInteractionMode = "SET_ORIGIN";
        document.querySelectorAll(".mode-btn").forEach(b => b.classList.remove("active"));
        document.getElementById("btn-set-origin").classList.add("active");
        mapController.setPickMode(true);
        showToast("👉 Hãy nhấp chuột vào vị trí bất kỳ trên bản đồ để đặt Điểm A (Xuất phát)", "info");
    });

    // Nút Chọn Điểm Đích B
    document.getElementById("btn-set-dest").addEventListener("click", () => {
        currentInteractionMode = "SET_DEST";
        document.querySelectorAll(".mode-btn").forEach(b => b.classList.remove("active"));
        document.getElementById("btn-set-dest").classList.add("active");
        mapController.setPickMode(true);
        showToast("👉 Hãy nhấp chuột vào vị trí bất kỳ trên bản đồ để đặt Điểm B (Đích đến)", "info");
    });

    // Nút Cắm Điểm Tai Nạn
    document.getElementById("btn-set-accident").addEventListener("click", () => {
        currentInteractionMode = "SET_ACCIDENT";
        document.querySelectorAll(".mode-btn").forEach(b => b.classList.remove("active"));
        document.getElementById("btn-set-accident").classList.add("active");
        mapController.setPickMode(true);
        showToast("💥 Hãy nhấp chuột vào một con đường trên bản đồ để tạo điểm tai nạn / kẹt xe", "warning");
    });

    // Nút Xóa Toàn Bộ Tai Nạn
    document.getElementById("btn-clear-accidents").addEventListener("click", async () => {
        realRoadEngine.clearAccidents();
        mapController.clearAccidents();
        showToast("✅ Đã dọn dẹp các điểm tai nạn! Các tuyến đường trở lại bình thường.", "success");
        await updateAndRenderRoutes();
    });

    // Nút Khởi Hành Lại Xe Chạy
    document.getElementById("btn-restart-sim").addEventListener("click", () => {
        realRoadEngine.startVehicleSimulation();
        isCarSimulationRunning = true;
        showToast("🏎️ Các xe bắt đầu xuất phát chạy đua trên 2 tuyến!", "info");
    });

    // Nút Đổi Chế Độ Bản Đồ (Google Maps / Vệ tinh / Dark)
    document.querySelectorAll(".btn-map-layer").forEach(btn => {
        btn.addEventListener("click", (e) => {
            document.querySelectorAll(".btn-map-layer").forEach(b => b.classList.remove("active"));
            e.target.classList.add("active");
            const layerKey = e.target.getAttribute("data-layer");
            mapController.switchBaseLayer(layerKey);
        });
    });

    // Chọn Kịch Bản Lưu Lượng SUMO (TH1: 200 xe/h -> TH6: 1200 xe/h)
    const sumoScenarioSelect = document.getElementById("select-sumo-scenario");
    if (sumoScenarioSelect) {
        sumoScenarioSelect.addEventListener("change", async (e) => {
            const scId = e.target.value;
            realRoadEngine.currentScenario = scId;
            const sc = realRoadEngine.scenarios[scId];
            showToast(`🚦 Đã áp dụng kịch bản ${sc.name}! Màu sắc và tốc độ đang cập nhật theo SUMO...`, "info");
            await updateAndRenderRoutes();
        });
    }

    // Nút Chọn Tốc Độ Tua Mô Phỏng (4x, 8x, 15x, 25x)
    document.querySelectorAll(".btn-sim-speed").forEach(btn => {
        btn.addEventListener("click", (e) => {
            document.querySelectorAll(".btn-sim-speed").forEach(b => b.classList.remove("active"));
            e.target.classList.add("active");
            const spd = parseFloat(e.target.getAttribute("data-speed")) || 8.0;
            realRoadEngine.simSpeedMultiplier = spd;
            showToast(`⏩ Đã đổi tốc độ tua: ${spd}x`, "info");
        });
    });

    // Toast
    function showToast(message, type = "info") {
        const container = document.getElementById("toast-container");
        if (!container) return;
        const toast = document.createElement("div");
        toast.className = `toast toast-${type}`;
        toast.innerText = message;
        container.appendChild(toast);
        setTimeout(() => {
            toast.classList.add("fade-out");
            setTimeout(() => toast.remove(), 400);
        }, 3500);
    }
});
