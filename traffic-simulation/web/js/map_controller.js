/**
 * map_controller.js – Điều khiển bản đồ Google Maps tương tác tự do
 * Hỗ trợ hiển thị dải màu tình trạng giao thông thời gian thực như Google Maps:
 *   - Xanh lá (#10b981): Thông thoáng
 *   - Vàng (#f59e0b): Đông xe vừa phải
 *   - Đỏ (#ef4444): Tắc nghẽn
 *   - Đỏ thẫm (#991b1b): Kẹt cứng do sự cố tai nạn
 */

class MapController {
    constructor(containerId, options = {}) {
        this.containerId = containerId;
        this.map = null;

        this.originMarker = null;
        this.destMarker = null;
        this.accidentMarkers = [];
        this.accidentCircles = [];

        this.routeLayers = []; // Lưu trữ tất cả các lớp đường vẽ (đa sắc màu) để xóa sạch sẽ
        this.carMarkers = {};

        this.onMapClickCallback = null;

        // Vị trí trung tâm Hà Nội (Ngã Tư Sở / Đống Đa)
        this.center = options.center || [21.006, 105.828];
        this.zoom = options.zoom || 14;

        this.initMap();
    }

    initMap() {
        if (typeof L === "undefined") {
            console.error("Leaflet is not loaded!");
            return;
        }

        this.map = L.map(this.containerId, {
            center: this.center,
            zoom: this.zoom,
            zoomControl: false,
            attributionControl: false
        });

        L.control.zoom({ position: "bottomright" }).addTo(this.map);

        this.layers = {
            google_roadmap: L.tileLayer("https://mt{s}.google.com/vt/lyrs=m&x={x}&y={y}&z={z}", {
                subdomains: ["0", "1", "2", "3"],
                maxZoom: 20
            }),
            google_hybrid: L.tileLayer("https://mt{s}.google.com/vt/lyrs=y&x={x}&y={y}&z={z}", {
                subdomains: ["0", "1", "2", "3"],
                maxZoom: 20
            }),
            its_dark: L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
                subdomains: "abcd",
                maxZoom: 20
            })
        };

        this.layers.google_roadmap.addTo(this.map);
        this.currentLayer = "google_roadmap";

        this.map.on("click", (e) => {
            if (this.onMapClickCallback) {
                this.onMapClickCallback(e.latlng);
            }
        });
    }

    switchBaseLayer(layerKey) {
        if (!this.layers[layerKey] || layerKey === this.currentLayer) return;
        this.map.removeLayer(this.layers[this.currentLayer]);
        this.layers[layerKey].addTo(this.map);
        this.currentLayer = layerKey;
    }

    setOrigin(lat, lng, label = "Điểm Xuất Phát A") {
        this.clearOrigin();

        const iconHtml = `
            <div class="pin-marker pin-origin">
                <div class="pin-head">A</div>
                <div class="pin-pulse"></div>
            </div>
        `;
        const icon = L.divIcon({
            className: "custom-pin-icon",
            html: iconHtml,
            iconSize: [36, 48],
            iconAnchor: [18, 44]
        });

        this.originMarker = L.marker([lat, lng], { icon: icon, zIndexOffset: 2000 }).addTo(this.map);
        this.originMarker.bindTooltip(`<strong>🟢 ${label}</strong>`, { permanent: true, direction: "top", offset: [0, -42], className: "custom-map-tooltip" });
    }

    clearOrigin() {
        if (this.originMarker) {
            this.map.removeLayer(this.originMarker);
            this.originMarker = null;
        }
    }

    setDestination(lat, lng, label = "Điểm Đích Đến B") {
        this.clearDestination();

        const iconHtml = `
            <div class="pin-marker pin-dest">
                <div class="pin-head">B</div>
                <div class="pin-pulse"></div>
            </div>
        `;
        const icon = L.divIcon({
            className: "custom-pin-icon",
            html: iconHtml,
            iconSize: [36, 48],
            iconAnchor: [18, 44]
        });

        this.destMarker = L.marker([lat, lng], { icon: icon, zIndexOffset: 2000 }).addTo(this.map);
        this.destMarker.bindTooltip(`<strong>🔴 ${label}</strong>`, { permanent: true, direction: "top", offset: [0, -42], className: "custom-map-tooltip" });
    }

    clearDestination() {
        if (this.destMarker) {
            this.map.removeLayer(this.destMarker);
            this.destMarker = null;
        }
    }

    setSingleAccidentMarker(accident) {
        this.clearAccidents();

        const iconHtml = `
            <div class="accident-marker">
                <div class="accident-icon">💥</div>
                <div class="accident-label">TAI NẠN</div>
            </div>
        `;
        const icon = L.divIcon({
            className: "custom-accident-icon",
            html: iconHtml,
            iconSize: [40, 40],
            iconAnchor: [20, 20]
        });

        const marker = L.marker([accident.lat, accident.lng], { icon: icon, zIndexOffset: 3000 }).addTo(this.map);
        marker.bindTooltip(`<strong>⚠️ Sự Cố Giao Thông</strong><br>Ùn tắc 90% dung lượng đường`, { className: "custom-map-tooltip" });

        // Cho phép click xuyên qua hoặc chuyển tiếp sự kiện click khi cắm điểm mới
        marker.on("click", (e) => {
            if (this.onMapClickCallback) this.onMapClickCallback(e.latlng);
        });

        const circle = L.circle([accident.lat, accident.lng], {
            radius: accident.radius,
            color: "#dc2626",
            fillColor: "#ef4444",
            fillOpacity: 0.35,
            weight: 2,
            dashArray: "4, 4",
            interactive: false // Không chặn click bản đồ
        }).addTo(this.map);

        this.accidentMarkers.push(marker);
        this.accidentCircles.push(circle);
    }

    addAccidentMarker(accident) {
        return this.setSingleAccidentMarker(accident);
    }

    clearAccidents() {
        for (const m of this.accidentMarkers) this.map.removeLayer(m);
        for (const c of this.accidentCircles) this.map.removeLayer(c);
        this.accidentMarkers = [];
        this.accidentCircles = [];
    }

    setPickMode(isActive) {
        const container = document.getElementById(this.containerId);
        if (container) {
            if (isActive) {
                container.style.cursor = "crosshair";
            } else {
                container.style.cursor = "";
            }
        }
    }

    /**
     * VẼ CÁC TUYẾN ĐƯỜNG ĐA SẮC MÀU (XANH - VÀNG - ĐỎ NHƯ GOOGLE MAPS)
     * Kèm viền bao và phân biệt rõ ràng giữa Tuyến Tĩnh và Tuyến Đàn Kiến (ACO)
     */
    renderRoutes(staticRoute, acoRoute) {
        this.clearRoutes();

        // 1. Vẽ Tuyến Tĩnh (Static Route)
        if (staticRoute && staticRoute.segments && staticRoute.segments.length > 0) {
            // Lớp viền nền xám đen nhẹ
            const casing = L.polyline(staticRoute.points, {
                color: "#1e293b",
                weight: 8,
                opacity: 0.6,
                interactive: false
            }).addTo(this.map);
            this.routeLayers.push(casing);

            // Vẽ từng phân đoạn màu xanh / vàng / đỏ như Google Maps
            for (const seg of staticRoute.segments) {
                const segLine = L.polyline(seg.points, {
                    color: seg.color,
                    weight: 5,
                    opacity: 0.95,
                    lineJoin: "round",
                    lineCap: "round"
                }).addTo(this.map);

                segLine.bindTooltip(
                    `<strong>🟠 Lộ Trình Cố Định (Dijkstra)</strong><br>Tình trạng: <strong>${seg.desc}</strong><br>Tốc độ: ${seg.speed_kmh} km/h | Ùn tắc: ${Math.round(seg.congestion * 100)}%<br><small>TraCI: ${seg.traci.vehicles} xe | Chờ: ${seg.traci.waiting_s}s</small>`,
                    { sticky: true, className: "custom-map-tooltip" }
                );

                // Chuyển tiếp click nếu người dùng click trúng con đường
                segLine.on("click", (e) => {
                    if (this.onMapClickCallback) this.onMapClickCallback(e.latlng);
                });

                this.routeLayers.push(segLine);
            }
        }

        // 2. Vẽ Tuyến Thích Nghi ACO (Nếu có tuyến tránh khác tuyến tĩnh)
        if (acoRoute && acoRoute.segments && acoRoute.segments.length > 0) {
            // Lớp viền phát sáng tím dạ quang kép (Neon Violet Aura) làm nổi bật tuyến tránh ACO
            const acoGlowOuter = L.polyline(acoRoute.points, {
                color: "#c084fc",
                weight: 14,
                opacity: 0.55,
                interactive: false
            }).addTo(this.map);
            this.routeLayers.push(acoGlowOuter);

            const acoGlowInner = L.polyline(acoRoute.points, {
                color: "#9333ea",
                weight: 8,
                opacity: 0.7,
                interactive: false
            }).addTo(this.map);
            this.routeLayers.push(acoGlowInner);

            // Vẽ các phân đoạn màu của tuyến ACO (thường nhiều đoạn xanh và vàng hơn)
            for (const seg of acoRoute.segments) {
                const segLine = L.polyline(seg.points, {
                    color: seg.color,
                    weight: 5,
                    opacity: 1.0,
                    lineJoin: "round",
                    lineCap: "round"
                }).addTo(this.map);

                segLine.bindTooltip(
                    `<strong>🟣 Lộ Trình Thích Nghi (ACO)</strong><br>Tình trạng: <strong>${seg.desc}</strong><br>Tốc độ: ${seg.speed_kmh} km/h | Ùn tắc: ${Math.round(seg.congestion * 100)}%<br><small>TraCI: ${seg.traci.vehicles} xe | Chờ: ${seg.traci.waiting_s}s</small>`,
                    { sticky: true, className: "custom-map-tooltip" }
                );

                // Chuyển tiếp click nếu người dùng click trúng con đường
                segLine.on("click", (e) => {
                    if (this.onMapClickCallback) this.onMapClickCallback(e.latlng);
                });

                this.routeLayers.push(segLine);
            }
        }

        // Tự động căn chỉnh tầm nhìn bao trọn tuyến
        const allPoints = [
            ...(staticRoute ? staticRoute.points : []),
            ...(acoRoute ? acoRoute.points : [])
        ];
        if (allPoints.length > 0) {
            this.map.fitBounds(L.latLngBounds(allPoints), { padding: [50, 50] });
        }
    }

    clearRoutes() {
        for (const layer of this.routeLayers) {
            this.map.removeLayer(layer);
        }
        this.routeLayers = [];
    }

    clearCars() {
        for (const marker of Object.values(this.carMarkers)) {
            this.map.removeLayer(marker);
        }
        this.carMarkers = {};
    }

    updateCars(cars) {
        const activeIds = new Set();

        for (const car of cars) {
            activeIds.add(car.id);

            if (this.carMarkers[car.id]) {
                const marker = this.carMarkers[car.id];
                marker.setLatLng([car.lat, car.lng]);

                const elem = marker.getElement();
                if (elem) {
                    const arrow = elem.querySelector(".car-body");
                    if (arrow) {
                        arrow.style.transform = `rotate(${car.bearing}deg)`;
                    }
                    if (car.isBlocked) {
                        elem.classList.add("car-blocked");
                    } else {
                        elem.classList.remove("car-blocked");
                    }
                }
            } else {
                const isAco = car.type === "ACO";
                const carHtml = `
                    <div class="real-car-marker ${isAco ? 'car-aco' : 'car-static'}">
                        <div class="car-body" style="transform: rotate(${car.bearing}deg);">
                            <div class="car-sprite">${isAco ? '🏎️' : '🚗'}</div>
                            ${isAco ? '<span class="car-badge-aco">ACO</span>' : '<span class="car-badge-static">DIJKSTRA</span>'}
                        </div>
                    </div>
                `;

                const icon = L.divIcon({
                    className: "custom-car-icon",
                    html: carHtml,
                    iconSize: [36, 36],
                    iconAnchor: [18, 18]
                });

                const marker = L.marker([car.lat, car.lng], { icon: icon, zIndexOffset: 2500 }).addTo(this.map);
                this.carMarkers[car.id] = marker;
            }
        }

        for (const id of Object.keys(this.carMarkers)) {
            if (!activeIds.has(id)) {
                this.map.removeLayer(this.carMarkers[id]);
                delete this.carMarkers[id];
            }
        }
    }
}

// Xuất biến toàn cục
if (typeof window !== "undefined") {
    window.MapController = MapController;
}
