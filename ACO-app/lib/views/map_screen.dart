import 'dart:async';
import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'package:provider/provider.dart';

import '../models/traffic_model.dart';
import '../services/api_service.dart';
import '../widgets/transport_selector.dart';

class MapScreen extends StatefulWidget {
  const MapScreen({super.key});

  @override
  State<MapScreen> createState() => _MapScreenState();
}

class _MapScreenState extends State<MapScreen> {
  final MapController _mapController = MapController();

  // Điểm đi và Điểm đến mặc định (Hành lang nghiên cứu ĐATN: Ngã Tư Sở -> ĐH Bách Khoa)
  String _originName = 'Ngã Tư Sở (Đường Nguyễn Trãi)';
  String _destName = 'Đại học Bách Khoa (Đường Giải Phóng)';
  LatLng _originPoint = const LatLng(21.0022, 105.8164);
  LatLng _destPoint = const LatLng(21.0055, 105.8440);

  // Điểm sự cố tai nạn do người dùng cắm trực tiếp trên bản đồ
  LatLng? _accidentPoint = const LatLng(21.0015, 105.8300); // Mặc định: Ngã tư Trường Chinh - Tôn Thất Tùng
  final double _accidentRadius = 180.0;

  // Chế độ tương tác hiện tại: 0 = IDLE, 1 = SET_ORIGIN, 2 = SET_DEST, 3 = SET_ACCIDENT
  int _interactionMode = 0;
  TransportMode _transportMode = TransportMode.driving;
  String _sumoScenario = 'TH3'; // Kịch bản SUMO mặc định

  List<EdgeCongestion> _edges = [];
  List<RouteOption> _routes = [];
  RouteOption? _selectedRoute;
  OptimizationComparison? _comparison;
  bool _isLoadingRoutes = false;
  bool _showTrafficLayer = false;

  // ── TRẠNG THÁI MÔ PHỎNG 2 XE CHẠY THỬ NGHIỆM (DIJKSTRA vs ACO) ──
  bool _isCarSimulationRunning = false;
  Timer? _carSimTimer;
  int _dijkstraCarIdx = 0;
  int _tacoCarIdx = 0;
  LatLng? _dijkstraCarPos;
  LatLng? _tacoCarPos;
  double _dijkstraSpeedKmh = 35.0;
  double _tacoSpeedKmh = 38.0;
  String _dijkstraCarState = 'Khởi hành';
  String _tacoCarState = 'Khởi hành';

  Timer? _trafficPollingTimer;

  final Map<String, String> _scenariosList = {
    'TH1': 'TH1: 200 xe/h (Thông thoáng)',
    'TH2': 'TH2: 400 xe/h (Lưu thông tốt)',
    'TH3': 'TH3: 600 xe/h (Bình thường - Xanh/Vàng)',
    'TH4': 'TH4: 800 xe/h (Đông đúc - Vàng/Đỏ)',
    'TH5': 'TH5: 1000 xe/h (Ùn ứ diện rộng)',
    'TH6': 'TH6: 1200 xe/h (Ùn tắc nặng - Đỏ rực)',
  };

  @override
  void initState() {
    super.initState();
    _loadInitialData();
    _trafficPollingTimer = Timer.periodic(const Duration(milliseconds: 2500), (_) {
      _pollTrafficUpdate();
    });
  }

  @override
  void dispose() {
    _trafficPollingTimer?.cancel();
    _carSimTimer?.cancel();
    super.dispose();
  }

  Future<void> _loadInitialData() async {
    await Future.wait([
      _pollTrafficUpdate(),
      _fetchRoutes(),
    ]);
  }

  Future<void> _pollTrafficUpdate() async {
    if (!mounted) return;
    final apiService = context.read<ApiService>();
    final trafficData = await apiService.fetchLiveTraffic();

    if (mounted) {
      setState(() {
        _edges = trafficData['edges'] as List<EdgeCongestion>;
      });
    }
  }

  Future<void> _fetchRoutes() async {
    setState(() => _isLoadingRoutes = true);
    final apiService = context.read<ApiService>();

    final res = await apiService.fetchStochasticRoutes(
      origin: _originName,
      destination: _destName,
      originLat: _originPoint.latitude,
      originLng: _originPoint.longitude,
      destLat: _destPoint.latitude,
      destLng: _destPoint.longitude,
      accidentLat: _accidentPoint?.latitude,
      accidentLng: _accidentPoint?.longitude,
      accidentRadius: _accidentRadius,
      transportMode: _transportMode.value,
      scenario: _sumoScenario,
      topK: 3,
    );

    if (mounted) {
      final List<RouteOption> routes = res['routes'] as List<RouteOption>? ?? [];
      final OptimizationComparison? comp = res['comparison'] as OptimizationComparison?;

      setState(() {
        _routes = routes;
        _comparison = comp;
        _isLoadingRoutes = false;
        if (routes.isNotEmpty) {
          // Ưu tiên chọn tuyến né tai nạn có xác suất cao nhất
          _selectedRoute = routes.firstWhere((r) => !r.hasAccident, orElse: () => routes.first);
        }
      });

      if (routes.isNotEmpty && routes.first.coordinates.isNotEmpty) {
        _fitRoutesBounds(routes);
      }
    }
  }

  void _fitRoutesBounds(List<RouteOption> routes) {
    double minLat = 90.0, maxLat = -90.0, minLng = 180.0, maxLng = -180.0;
    bool hasCoords = false;

    for (final r in routes) {
      for (final pt in r.coordinates) {
        hasCoords = true;
        if (pt.latitude < minLat) minLat = pt.latitude;
        if (pt.latitude > maxLat) maxLat = pt.latitude;
        if (pt.longitude < minLng) minLng = pt.longitude;
        if (pt.longitude > maxLng) maxLng = pt.longitude;
      }
    }

    if (!hasCoords) return;

    final bounds = LatLngBounds(LatLng(minLat, minLng), LatLng(maxLat, maxLng));
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      _mapController.fitCamera(
        CameraFit.bounds(
          bounds: bounds,
          padding: const EdgeInsets.only(top: 185, bottom: 275, left: 35, right: 35),
        ),
      );
    });
  }

  LatLng _getDivergenceBadgePoint(RouteOption route, int routeIndex, List<RouteOption> allRoutes) {
    if (route.coordinates.isEmpty) return const LatLng(0, 0);
    if (routeIndex == 0 || allRoutes.isEmpty || allRoutes.first.coordinates.isEmpty) {
      final idx = (route.coordinates.length * 0.45).toInt().clamp(0, route.coordinates.length - 1);
      return route.coordinates[idx];
    }

    final mainCoords = allRoutes.first.coordinates;
    double maxMinDist = -1;
    LatLng bestPt = route.coordinates[route.coordinates.length ~/ 2];

    final startIdx = (route.coordinates.length * 0.15).toInt();
    final endIdx = (route.coordinates.length * 0.85).toInt();
    final step = math.max(1, (endIdx - startIdx) ~/ 12);

    for (int i = startIdx; i < endIdx; i += step) {
      final pt = route.coordinates[i];
      double minDist = double.infinity;
      for (int j = 0; j < mainCoords.length; j += math.max(1, mainCoords.length ~/ 15)) {
        final mpt = mainCoords[j];
        final dLat = pt.latitude - mpt.latitude;
        final dLng = pt.longitude - mpt.longitude;
        final d = math.sqrt(dLat * dLat + dLng * dLng);
        if (d < minDist) minDist = d;
      }
      if (minDist > maxMinDist) {
        maxMinDist = minDist;
        bestPt = pt;
      }
    }
    return bestPt;
  }

  void _handleMapTap(LatLng point) {
    setState(() {
      if (_interactionMode == 1) {
        // Chế độ chọn Điểm A
        _originPoint = point;
        _originName = 'Điểm A (${point.latitude.toStringAsFixed(3)}, ${point.longitude.toStringAsFixed(3)})';
        _interactionMode = 0;
        _stopCarSimulation();
        _fetchRoutes();
      } else if (_interactionMode == 2) {
        // Chế độ chọn Điểm B
        _destPoint = point;
        _destName = 'Điểm B (${point.latitude.toStringAsFixed(3)}, ${point.longitude.toStringAsFixed(3)})';
        _interactionMode = 0;
        _stopCarSimulation();
        _fetchRoutes();
      } else if (_interactionMode == 3) {
        // Chế độ Cắm Tai Nạn Trên Đường
        _accidentPoint = point;
        _interactionMode = 0;
        _stopCarSimulation();
        _fetchRoutes();
      }
    });
  }

  void _clearAccident() {
    setState(() {
      _accidentPoint = null;
      _stopCarSimulation();
    });
    _fetchRoutes();
  }

  void _resetToHanoiDefault() {
    setState(() {
      _originPoint = const LatLng(21.0022, 105.8164);
      _destPoint = const LatLng(21.0055, 105.8440);
      _originName = 'Ngã Tư Sở (Đường Nguyễn Trãi)';
      _destName = 'Đại học Bách Khoa (Đường Giải Phóng)';
      _accidentPoint = const LatLng(21.0015, 105.8300);
      _interactionMode = 0;
      _stopCarSimulation();
    });
    _fetchRoutes();
  }

  // ── KHỞI CHẠY MÔ PHỎNG 2 XE CHẠY THỰC TẾ (DIJKSTRA vs ACO) ──
  void _startCarSimulation() {
    if (_routes.isEmpty) return;
    _carSimTimer?.cancel();

    final staticRoute = _routes.first;
    final acoRoute = _routes.firstWhere(
      (r) => !r.hasAccident && r.routeId != staticRoute.routeId,
      orElse: () => _routes.length > 1 ? _routes[1] : _routes.first,
    );

    setState(() {
      _isCarSimulationRunning = true;
      _dijkstraCarIdx = 0;
      _tacoCarIdx = 0;
      _dijkstraCarPos = staticRoute.coordinates.isNotEmpty ? staticRoute.coordinates.first : null;
      _tacoCarPos = acoRoute.coordinates.isNotEmpty ? acoRoute.coordinates.first : null;
      _dijkstraSpeedKmh = 35.0;
      _tacoSpeedKmh = 38.0;
      _dijkstraCarState = 'Khởi hành';
      _tacoCarState = 'Khởi hành';
    });

    _carSimTimer = Timer.periodic(const Duration(milliseconds: 140), (timer) {
      if (!mounted) {
        timer.cancel();
        return;
      }

      setState(() {
        // 1. Xe Dijkstra (Tuyến ngắn nhất - đi qua tai nạn)
        if (_dijkstraCarIdx < staticRoute.coordinates.length - 1) {
          final curPos = staticRoute.coordinates[_dijkstraCarIdx];
          bool inAccident = false;
          if (_accidentPoint != null) {
            final dist = const Distance().as(LengthUnit.Meter, curPos, _accidentPoint!);
            if (dist <= _accidentRadius) inAccident = true;
          }

          if (inAccident) {
            _dijkstraSpeedKmh = 2.0; // Xe kẹt cứng
            _dijkstraCarState = '💥 Kẹt tai nạn (2 km/h)';
            if (timer.tick % 5 == 0) _dijkstraCarIdx++;
          } else {
            _dijkstraSpeedKmh = 32.0;
            _dijkstraCarState = 'Đang chạy (32 km/h)';
            _dijkstraCarIdx++;
          }
          _dijkstraCarPos = staticRoute.coordinates[_dijkstraCarIdx];
        } else {
          _dijkstraCarState = '🏁 Đã về đích';
        }

        // 2. Xe T-ACO (Tuyến thích nghi - né tai nạn)
        if (_tacoCarIdx < acoRoute.coordinates.length - 1) {
          _tacoCarIdx++;
          _tacoCarPos = acoRoute.coordinates[_tacoCarIdx];
          _tacoSpeedKmh = 40.0;
          _tacoCarState = '✨ Né tai nạn thông suốt (40 km/h)';
        } else {
          _tacoCarState = '🏁 Đã về đích trước! ✓';
        }

        if (_dijkstraCarIdx >= staticRoute.coordinates.length - 1 &&
            _tacoCarIdx >= acoRoute.coordinates.length - 1) {
          timer.cancel();
          _isCarSimulationRunning = false;
        }
      });
    });
  }

  void _stopCarSimulation() {
    _carSimTimer?.cancel();
    setState(() {
      _isCarSimulationRunning = false;
      _dijkstraCarPos = null;
      _tacoCarPos = null;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Stack(
        children: [
          // ═════════════════════════════════════════════════════════════════
          // 1. BẢN ĐỒ GOOGLE MAPS VỚI TUYẾN ĐƯỜNG, ĐIỂM TAI NẠN & 2 XE MÔ PHỎNG
          // ═════════════════════════════════════════════════════════════════
          FlutterMap(
            mapController: _mapController,
            options: MapOptions(
              initialCenter: const LatLng(21.0040, 105.8300),
              initialZoom: 14.5,
              minZoom: 10.0,
              maxZoom: 18.0,
              onTap: (tapPosition, point) => _handleMapTap(point),
            ),
            children: [
              TileLayer(
                urlTemplate: 'https://mt{s}.google.com/vt/lyrs=m&x={x}&y={y}&z={z}',
                subdomains: const ['0', '1', '2', '3'],
                userAgentPackageName: 'com.google.maps',
              ),

              // Lớp mật độ giao thông SUMO (Xanh - Vàng - Đỏ, bật/tắt bằng nút 🚦)
              if (_showTrafficLayer)
                PolylineLayer(
                  polylines: _edges
                      .where((e) => e.points.length >= 2)
                      .map((e) => Polyline(
                            points: e.points,
                            strokeWidth: 3.5,
                            color: e.color.withValues(alpha: 0.65),
                          ))
                      .toList(),
                ),

              // VÙNG TAI NẠN GIAO THÔNG (Vòng tròn đỏ phát sáng bán kính 180m)
              if (_accidentPoint != null)
                CircleLayer(
                  circles: [
                    CircleMarker(
                      point: _accidentPoint!,
                      radius: _accidentRadius,
                      useRadiusInMeter: true,
                      color: const Color(0xFFEF4444).withValues(alpha: 0.22),
                      borderColor: const Color(0xFFDC2626),
                      borderStrokeWidth: 2.5,
                    ),
                  ],
                ),

              // VẼ CÁC TUYẾN ĐƯỜNG THAY THẾ (Màu xám #80868B)
              if (_routes.isNotEmpty)
                PolylineLayer(
                  polylines: _routes
                      .where((r) => r.routeId != _selectedRoute?.routeId && r.coordinates.isNotEmpty)
                      .expand((r) => [
                            Polyline(
                              points: r.coordinates,
                              strokeWidth: 6.5,
                              color: r.hasAccident ? const Color(0xFF991B1B).withValues(alpha: 0.5) : const Color(0xFF5F6368).withValues(alpha: 0.5),
                            ),
                            Polyline(
                              points: r.coordinates,
                              strokeWidth: 4.8,
                              color: r.hasAccident ? const Color(0xFFDC2626) : const Color(0xFF80868B),
                            ),
                          ])
                      .toList(),
                ),

              // VẼ TUYẾN ĐƯỢC CHỌN (Xanh dương Google Maps #1A73E8 hoặc Đỏ nếu dính tai nạn)
              if (_selectedRoute != null && _selectedRoute!.coordinates.isNotEmpty)
                PolylineLayer(
                  polylines: [
                    Polyline(
                      points: _selectedRoute!.coordinates,
                      strokeWidth: 9.0,
                      color: _selectedRoute!.hasAccident
                          ? const Color(0xFF991B1B).withValues(alpha: 0.45)
                          : const Color(0xFF1557B0).withValues(alpha: 0.4),
                    ),
                    Polyline(
                      points: _selectedRoute!.coordinates,
                      strokeWidth: 6.0,
                      color: _selectedRoute!.hasAccident ? const Color(0xFFDC2626) : const Color(0xFF1A73E8),
                    ),
                  ],
                ),

              // LỚP CÁC MARKER: ĐIỂM A, ĐIỂM B, TAI NẠN, BONG BÓNG THỜI GIAN VÀ 2 XE CHẠY
              MarkerLayer(
                markers: [
                  // Marker Điểm A
                  Marker(
                    point: _originPoint,
                    width: 48,
                    height: 48,
                    alignment: Alignment.center,
                    child: Container(
                      decoration: BoxDecoration(
                        color: const Color(0xFF1A73E8).withValues(alpha: 0.22),
                        shape: BoxShape.circle,
                      ),
                      child: Center(
                        child: Container(
                          width: 22,
                          height: 22,
                          decoration: BoxDecoration(
                            color: const Color(0xFF1A73E8),
                            shape: BoxShape.circle,
                            border: Border.all(color: Colors.white, width: 3.5),
                            boxShadow: const [BoxShadow(color: Colors.black26, blurRadius: 4)],
                          ),
                        ),
                      ),
                    ),
                  ),

                  // Marker Điểm B
                  Marker(
                    point: _destPoint,
                    width: 44,
                    height: 44,
                    alignment: Alignment.topCenter,
                    child: const Icon(Icons.location_on, color: Color(0xFFEA4335), size: 40),
                  ),

                  // Marker Điểm Tai Nạn (Biểu tượng 💥)
                  if (_accidentPoint != null)
                    Marker(
                      point: _accidentPoint!,
                      width: 100,
                      height: 56,
                      alignment: Alignment.center,
                      child: GestureDetector(
                        onTap: _showAccidentPickerBottomSheet,
                        child: Column(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2.5),
                              decoration: BoxDecoration(
                                color: const Color(0xFF991B1B),
                                borderRadius: BorderRadius.circular(10),
                                boxShadow: const [BoxShadow(color: Colors.black38, blurRadius: 4)],
                              ),
                              child: const Text(
                                '💥 TAI NẠN (Chạm)',
                                style: TextStyle(color: Colors.white, fontSize: 9.5, fontWeight: FontWeight.bold),
                              ),
                            ),
                            const Icon(Icons.warning, color: Color(0xFFDC2626), size: 28),
                          ],
                        ),
                      ),
                    ),

                  // ── BONG BÓNG THỜI GIAN NHỎ GỌN NỔI PHÍA TRÊN ĐƯỜNG (KHÔNG TRÀN PIXEL) ──
                  ..._routes.asMap().entries.map((entry) {
                    final int idx = entry.key;
                    final RouteOption r = entry.value;
                    if (r.coordinates.length < 2) return null;

                    final bool isSel = r.routeId == _selectedRoute?.routeId;
                    final LatLng badgePos = _getDivergenceBadgePoint(r, idx, _routes);

                    return Marker(
                      point: badgePos,
                      width: 96,
                      height: 46,
                      alignment: Alignment.bottomCenter,
                      child: GestureDetector(
                        onTap: () {
                          setState(() => _selectedRoute = r);
                        },
                        child: FittedBox(
                          fit: BoxFit.scaleDown,
                          child: Column(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2.5),
                                decoration: BoxDecoration(
                                  color: r.hasAccident
                                      ? const Color(0xFFDC2626)
                                      : (isSel ? const Color(0xFF1A73E8) : Colors.white),
                                  borderRadius: BorderRadius.circular(12),
                                  border: Border.all(
                                    color: isSel ? const Color(0xFF1557B0) : const Color(0xFFBDC1C6),
                                    width: isSel ? 1.4 : 1.0,
                                  ),
                                  boxShadow: [
                                    BoxShadow(
                                      color: Colors.black.withValues(alpha: isSel ? 0.22 : 0.12),
                                      blurRadius: 4,
                                      offset: const Offset(0, 2),
                                    ),
                                  ],
                                ),
                                child: Row(
                                  mainAxisSize: MainAxisSize.min,
                                  mainAxisAlignment: MainAxisAlignment.center,
                                  children: [
                                    Text(
                                      '${r.minutes.toStringAsFixed(0)} ph',
                                      style: TextStyle(
                                        color: (r.hasAccident || isSel) ? Colors.white : const Color(0xFF202124),
                                        fontWeight: FontWeight.bold,
                                        fontSize: 11,
                                      ),
                                    ),
                                    if (r.hasAccident) ...[
                                      const SizedBox(width: 3),
                                      const Text('⚠️', style: TextStyle(fontSize: 10)),
                                    ] else if (isSel) ...[
                                      const SizedBox(width: 3),
                                      const Icon(Icons.eco, color: Color(0xFF81C995), size: 12),
                                    ] else ...[
                                      const SizedBox(width: 3),
                                      Text(
                                        '${r.probabilityPct.toStringAsFixed(0)}%',
                                        style: const TextStyle(
                                          color: Color(0xFF70757A),
                                          fontSize: 9.5,
                                          fontWeight: FontWeight.w600,
                                        ),
                                      ),
                                    ],
                                  ],
                                ),
                              ),
                              Transform.translate(
                                offset: const Offset(0, -4),
                                child: Icon(
                                  Icons.arrow_drop_down,
                                  color: r.hasAccident
                                      ? const Color(0xFFDC2626)
                                      : (isSel ? const Color(0xFF1A73E8) : Colors.white),
                                  size: 16,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                    );
                  }).whereType<Marker>(),

                  // ── 2 XE CHẠY MÔ PHỎNG THỜI GIAN THỰC (DIJKSTRA vs ACO) ──
                  if (_dijkstraCarPos != null)
                    Marker(
                      point: _dijkstraCarPos!,
                      width: 110,
                      height: 54,
                      child: FittedBox(
                        fit: BoxFit.scaleDown,
                        child: Column(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 2),
                              decoration: BoxDecoration(
                                color: const Color(0xFFEA580C),
                                borderRadius: BorderRadius.circular(6),
                                boxShadow: const [BoxShadow(color: Colors.black26, blurRadius: 3)],
                              ),
                              child: Text(
                                'Dijkstra: ${_dijkstraSpeedKmh.toStringAsFixed(0)}km/h\n$_dijkstraCarState',
                                textAlign: TextAlign.center,
                                style: const TextStyle(color: Colors.white, fontSize: 8.5, fontWeight: FontWeight.bold),
                              ),
                            ),
                            const Icon(Icons.directions_car, color: Color(0xFFEA580C), size: 24),
                          ],
                        ),
                      ),
                    ),

                  if (_tacoCarPos != null)
                    Marker(
                      point: _tacoCarPos!,
                      width: 110,
                      height: 54,
                      child: FittedBox(
                        fit: BoxFit.scaleDown,
                        child: Column(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 2),
                              decoration: BoxDecoration(
                                color: const Color(0xFF2563EB),
                                borderRadius: BorderRadius.circular(6),
                                boxShadow: const [BoxShadow(color: Colors.black26, blurRadius: 3)],
                              ),
                              child: Text(
                                'T-ACO: ${_tacoSpeedKmh.toStringAsFixed(0)}km/h\n$_tacoCarState',
                                textAlign: TextAlign.center,
                                style: const TextStyle(color: Colors.white, fontSize: 8.5, fontWeight: FontWeight.bold),
                              ),
                            ),
                            const Icon(Icons.directions_car, color: Color(0xFF2563EB), size: 24),
                          ],
                        ),
                      ),
                    ),
                ],
              ),
            ],
          ),

          // ═════════════════════════════════════════════════════════════════
          // 2. KHUNG TÌM KIẾM & BẢNG ĐIỀU KHIỂN TƯƠNG TÁC (CHỌN A, B, TAI NẠN)
          // ═════════════════════════════════════════════════════════════════
          Positioned(
            top: 48,
            left: 14,
            right: 14,
            child: Column(
              children: [
                // Khung tìm kiếm 2 dòng
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(16),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black.withValues(alpha: 0.12),
                        blurRadius: 12,
                        offset: const Offset(0, 3),
                      ),
                    ],
                  ),
                  child: Row(
                    children: [
                      Column(
                        children: [
                          Container(
                            width: 12,
                            height: 12,
                            decoration: BoxDecoration(
                              color: const Color(0xFF1A73E8),
                              shape: BoxShape.circle,
                              border: Border.all(color: Colors.white, width: 2),
                            ),
                          ),
                          Container(width: 2, height: 24, color: const Color(0xFFBDC1C6)),
                          const Icon(Icons.location_on, color: Color(0xFFEA4335), size: 16),
                        ],
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              _originName,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: Color(0xFF202124)),
                            ),
                            const Divider(height: 14, thickness: 0.7, color: Color(0xFFE8EAED)),
                            Text(
                              _destName,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: Color(0xFF202124)),
                            ),
                          ],
                        ),
                      ),
                      if (_isLoadingRoutes)
                        const Padding(
                          padding: EdgeInsets.all(8.0),
                          child: SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(strokeWidth: 2, color: Color(0xFF1A73E8)),
                          ),
                        )
                      else
                        IconButton(
                          icon: const Icon(Icons.swap_vert, color: Color(0xFF5F6368)),
                          tooltip: 'Đổi chiều điểm đi / điểm đến',
                          onPressed: () {
                            setState(() {
                              final tp = _originPoint;
                              _originPoint = _destPoint;
                              _destPoint = tp;
                              final tn = _originName;
                              _originName = _destName;
                              _destName = tn;
                            });
                            _stopCarSimulation();
                            _fetchRoutes();
                          },
                        ),
                    ],
                  ),
                ),

                const SizedBox(height: 8),

                // THANH CÔNG CỤ TƯƠNG TÁC (CHỌN A, CHỌN B, CẮM TAI NẠN, XÓA TAI NẠN)
                SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: Row(
                    children: [
                      _buildInteractiveModeBtn(
                        label: '🟢 Điểm A',
                        mode: 1,
                        color: const Color(0xFF10B981),
                      ),
                      const SizedBox(width: 6),
                      _buildInteractiveModeBtn(
                        label: '🔴 Điểm B',
                        mode: 2,
                        color: const Color(0xFFEF4444),
                      ),
                      const SizedBox(width: 6),
                      InkWell(
                        onTap: _showAccidentPickerBottomSheet,
                        borderRadius: BorderRadius.circular(16),
                        child: Container(
                          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                          decoration: BoxDecoration(
                            color: _accidentPoint != null ? const Color(0xFFEA580C) : Colors.white,
                            borderRadius: BorderRadius.circular(16),
                            border: Border.all(color: const Color(0xFFEA580C), width: 1.2),
                            boxShadow: const [
                              BoxShadow(color: Colors.black12, blurRadius: 4, offset: Offset(0, 1)),
                            ],
                          ),
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              const Text('💥', style: TextStyle(fontSize: 12)),
                              const SizedBox(width: 4),
                              Text(
                                _accidentPoint != null ? 'Đổi Tai Nạn' : 'Cắm Tai Nạn',
                                style: TextStyle(
                                  fontSize: 11,
                                  fontWeight: FontWeight.bold,
                                  color: _accidentPoint != null ? Colors.white : const Color(0xFFEA580C),
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                      if (_accidentPoint != null) ...[
                        const SizedBox(width: 6),
                        ElevatedButton.icon(
                          onPressed: _clearAccident,
                          icon: const Icon(Icons.delete_outline, size: 14, color: Colors.white),
                          label: const Text('Xóa', style: TextStyle(color: Colors.white, fontSize: 11)),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: const Color(0xFFDC2626),
                            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                            elevation: 1,
                          ),
                        ),
                      ],
                      const SizedBox(width: 6),
                      _buildPresetChip('🔄 Mặc định', _resetToHanoiDefault),
                    ],
                  ),
                ),

                // Thông báo nhắc nhở khi đang ở chế độ chạm
                if (_interactionMode > 0)
                  Container(
                    margin: const EdgeInsets.only(top: 6),
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                    decoration: BoxDecoration(
                      color: _interactionMode == 3 ? const Color(0xFFEA580C) : const Color(0xFF1E293B),
                      borderRadius: BorderRadius.circular(12),
                      boxShadow: const [BoxShadow(color: Colors.black26, blurRadius: 4, offset: Offset(0, 2))],
                    ),
                    child: Row(
                      children: [
                        Expanded(
                          child: Text(
                            _interactionMode == 1
                                ? '👉 Chạm vào bản đồ để chọn Điểm Đi (A)'
                                : (_interactionMode == 2
                                    ? '👉 Chạm vào bản đồ để chọn Điểm Đến (B)'
                                    : '💥 Chạm vào con đường bất kỳ để cắm Điểm Tai Nạn'),
                            style: const TextStyle(color: Colors.white, fontSize: 11.5, fontWeight: FontWeight.bold),
                          ),
                        ),
                        InkWell(
                          onTap: () => setState(() => _interactionMode = 0),
                          child: const Padding(
                            padding: EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                            child: Text(
                              'ĐÓNG',
                              style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 11),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
              ],
            ),
          ),

          // NÚT BẬT/TẮT LỚP MẬT ĐỘ GIAO THÔNG VÀ CĂN LẠI CAMERA Ở GÓC PHẢI
          Positioned(
            right: 16,
            bottom: 270,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                FloatingActionButton.small(
                  heroTag: 'accident_btn',
                  backgroundColor: _accidentPoint != null ? const Color(0xFFDC2626) : Colors.white,
                  foregroundColor: _accidentPoint != null ? Colors.white : const Color(0xFFDC2626),
                  tooltip: 'Tùy chọn Điểm Tai Nạn (💥)',
                  onPressed: _showAccidentPickerBottomSheet,
                  child: const Text('💥', style: TextStyle(fontSize: 16)),
                ),
                const SizedBox(height: 10),
                FloatingActionButton.small(
                  heroTag: 'traffic_layer_btn',
                  backgroundColor: _showTrafficLayer ? const Color(0xFF1A73E8) : Colors.white,
                  foregroundColor: _showTrafficLayer ? Colors.white : const Color(0xFF5F6368),
                  tooltip: 'Bật/Tắt lớp lưu lượng giao thông',
                  onPressed: () {
                    setState(() => _showTrafficLayer = !_showTrafficLayer);
                  },
                  child: const Icon(Icons.traffic, size: 20),
                ),
                const SizedBox(height: 10),
                FloatingActionButton.small(
                  heroTag: 'recenter_btn',
                  backgroundColor: Colors.white,
                  foregroundColor: const Color(0xFF1A73E8),
                  onPressed: () {
                    if (_routes.isNotEmpty) _fitRoutesBounds(_routes);
                  },
                  child: const Icon(Icons.my_location),
                ),
              ],
            ),
          ),

          // ═════════════════════════════════════════════════════════════════
          // 3. BẢNG ĐIỀU HƯỚNG & SO SÁNH TỐI ƯU HÓA THUẬT TOÁN Ở ĐÁY MÀN HÌNH
          // ═════════════════════════════════════════════════════════════════
          Positioned(
            bottom: 0,
            left: 0,
            right: 0,
            child: Container(
              padding: const EdgeInsets.fromLTRB(16, 10, 16, 20),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.15),
                    blurRadius: 18,
                    offset: const Offset(0, -4),
                  ),
                ],
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Center(
                    child: Container(
                      width: 36,
                      height: 4,
                      decoration: BoxDecoration(
                        color: const Color(0xFFDADCE0),
                        borderRadius: BorderRadius.circular(2),
                      ),
                    ),
                  ),
                  const SizedBox(height: 8),

                  // Hàng 1: Bộ chọn phương tiện (Ô tô / Xe máy / Đi bộ) + Thời gian lộ trình đang chọn
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Flexible(
                        child: FittedBox(
                          fit: BoxFit.scaleDown,
                          alignment: Alignment.centerLeft,
                          child: TransportSelector(
                            selected: _transportMode,
                            onSelect: (mode) {
                              setState(() => _transportMode = mode);
                              _fetchRoutes();
                            },
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      if (_selectedRoute != null)
                        FittedBox(
                          fit: BoxFit.scaleDown,
                          child: Text(
                            '${_selectedRoute!.minutes.toStringAsFixed(0)} phút (${(_selectedRoute!.lengthM / 1000).toStringAsFixed(1)}km)',
                            style: TextStyle(
                              fontSize: 13,
                              fontWeight: FontWeight.bold,
                              color: _selectedRoute!.hasAccident ? const Color(0xFFDC2626) : const Color(0xFF1A73E8),
                            ),
                          ),
                        ),
                    ],
                  ),
                  const SizedBox(height: 8),

                  // Hàng 2: Dropdown Kịch bản Mật độ SUMO (TH1 - TH6) chiếm trọn chiều rộng có nhãn rõ ràng
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 2),
                    decoration: BoxDecoration(
                      color: const Color(0xFFF1F5F9),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: const Color(0xFFCBD5E1)),
                    ),
                    child: Row(
                      children: [
                        const Icon(Icons.traffic, size: 16, color: Color(0xFF475569)),
                        const SizedBox(width: 6),
                        const Text(
                          'Mật độ SUMO:',
                          style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.bold, color: Color(0xFF475569)),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: DropdownButtonHideUnderline(
                            child: DropdownButton<String>(
                              value: _sumoScenario,
                              isDense: true,
                              isExpanded: true,
                              style: const TextStyle(fontSize: 11.5, fontWeight: FontWeight.bold, color: Color(0xFF1E293B)),
                              items: _scenariosList.entries.map((e) {
                                return DropdownMenuItem(
                                  value: e.key,
                                  child: Text(e.value, maxLines: 1, overflow: TextOverflow.ellipsis),
                                );
                              }).toList(),
                              onChanged: (val) {
                                if (val != null) {
                                  setState(() => _sumoScenario = val);
                                  _fetchRoutes();
                                }
                              },
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 10),

                  // BẢNG SO SÁNH HIỆU QUẢ TỐI ƯU HÓA: DIJKSTRA vs T-ACO
                  if (_comparison != null)
                    Container(
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(
                        color: const Color(0xFFF8FAFC),
                        borderRadius: BorderRadius.circular(14),
                        border: Border.all(color: const Color(0xFFE2E8F0)),
                      ),
                      child: Column(
                        children: [
                          Row(
                            children: [
                              // Cột Dijkstra (Cố định)
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    const Text('LỘ TRÌNH CỐ ĐỊNH (DIJKSTRA)',
                                        style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: Color(0xFF64748B))),
                                    const SizedBox(height: 2),
                                    Text(
                                      '${_comparison!.dijkstraMinutes.toStringAsFixed(0)} phút · ${_comparison!.dijkstraLengthKm.toStringAsFixed(1)} km',
                                      style: TextStyle(
                                        fontSize: 13,
                                        fontWeight: FontWeight.bold,
                                        color: _comparison!.dijkstraHasAccident ? const Color(0xFFDC2626) : const Color(0xFF1E293B),
                                      ),
                                    ),
                                    Text(
                                      _comparison!.dijkstraStatus,
                                      style: TextStyle(
                                        fontSize: 10,
                                        fontWeight: FontWeight.bold,
                                        color: _comparison!.dijkstraHasAccident ? const Color(0xFFDC2626) : const Color(0xFF64748B),
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                              Container(width: 1, height: 35, color: const Color(0xFFCBD5E1)),
                              const SizedBox(width: 10),
                              // Cột T-ACO (Thích nghi)
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    const Text('LỘ TRÌNH TỐI ƯU (T-ACO)',
                                        style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: Color(0xFF2563EB))),
                                    const SizedBox(height: 2),
                                    Text(
                                      '${_comparison!.tacoMinutes.toStringAsFixed(0)} phút · ${_comparison!.tacoLengthKm.toStringAsFixed(1)} km',
                                      style: const TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: Color(0xFF16A34A)),
                                    ),
                                    Text(
                                      _comparison!.tacoStatus,
                                      style: const TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: Color(0xFF16A34A)),
                                    ),
                                  ],
                                ),
                              ),
                            ],
                          ),
                          if (_comparison!.timeSavedMinutes > 0) ...[
                            const Divider(height: 12, thickness: 0.8),
                            Row(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                const Icon(Icons.bolt, color: Color(0xFFF59E0B), size: 16),
                                const SizedBox(width: 4),
                                Text(
                                  'T-ACO tối ưu: ${_comparison!.summary}',
                                  style: const TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: Color(0xFF0F766E)),
                                ),
                              ],
                            ),
                          ],
                        ],
                      ),
                    ),

                  const SizedBox(height: 12),

                  // HÀNG NÚT BẮT ĐẦU VÀ NÚT CHẠY XE MÔ PHỎNG (DIJKSTRA vs ACO)
                  Row(
                    children: [
                      // Nút Đưa Xe Mô Phỏng
                      Expanded(
                        flex: 6,
                        child: ElevatedButton.icon(
                          onPressed: _isCarSimulationRunning ? _stopCarSimulation : _startCarSimulation,
                          icon: Icon(
                            _isCarSimulationRunning ? Icons.stop : Icons.directions_car,
                            color: Colors.white,
                            size: 18,
                          ),
                          label: FittedBox(
                            fit: BoxFit.scaleDown,
                            child: Text(
                              _isCarSimulationRunning ? 'Dừng Mô Phỏng' : '🏎️ Mô Phỏng Xe',
                              style: const TextStyle(color: Colors.white, fontSize: 13, fontWeight: FontWeight.bold),
                            ),
                          ),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: _isCarSimulationRunning ? const Color(0xFFDC2626) : const Color(0xFF7C3AED), // Tím Cyberpunk
                            padding: const EdgeInsets.symmetric(vertical: 12),
                            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(22)),
                            elevation: 1,
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),

                      // Nút Bắt đầu dẫn đường Google Maps
                      Expanded(
                        flex: 5,
                        child: OutlinedButton.icon(
                          onPressed: () {
                            ScaffoldMessenger.of(context).showSnackBar(
                              SnackBar(
                                content: Text('Đang mô phỏng dẫn đường tuyến ${_selectedRoute?.routeId ?? ""}...'),
                                duration: const Duration(seconds: 2),
                              ),
                            );
                          },
                          icon: const Icon(Icons.navigation, color: Color(0xFF1A73E8), size: 18),
                          label: const Text(
                            'Bắt đầu',
                            style: TextStyle(color: Color(0xFF1A73E8), fontSize: 13, fontWeight: FontWeight.bold),
                          ),
                          style: OutlinedButton.styleFrom(
                            side: const BorderSide(color: Color(0xFF1A73E8), width: 1.5),
                            padding: const EdgeInsets.symmetric(vertical: 12),
                            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(22)),
                          ),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildInteractiveModeBtn({
    required String label,
    required int mode,
    required Color color,
  }) {
    final bool isActive = _interactionMode == mode;
    return InkWell(
      onTap: () {
        setState(() {
          _interactionMode = isActive ? 0 : mode;
        });
      },
      borderRadius: BorderRadius.circular(16),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        decoration: BoxDecoration(
          color: isActive ? color : Colors.white,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: isActive ? color : const Color(0xFFCBD5E1), width: 1.2),
          boxShadow: const [
            BoxShadow(color: Colors.black12, blurRadius: 4, offset: Offset(0, 1)),
          ],
        ),
        child: Text(
          label,
          style: TextStyle(
            fontSize: 11,
            fontWeight: FontWeight.bold,
            color: isActive ? Colors.white : const Color(0xFF334155),
          ),
        ),
      ),
    );
  }

  Widget _buildPresetChip(String label, VoidCallback onTap) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(16),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: const Color(0xFFCBD5E1)),
          boxShadow: const [
            BoxShadow(color: Colors.black12, blurRadius: 4, offset: Offset(0, 1)),
          ],
        ),
        child: Text(
          label,
          style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: Color(0xFF3C4043)),
        ),
      ),
    );
  }

  void _showAccidentPickerBottomSheet() {
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) {
        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 16),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    const Text('💥', style: TextStyle(fontSize: 22)),
                    const SizedBox(width: 8),
                    const Text(
                      'Tùy Chọn Điểm Tai Nạn (Sự Cố)',
                      style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Color(0xFF1E293B)),
                    ),
                    const Spacer(),
                    IconButton(
                      icon: const Icon(Icons.close),
                      onPressed: () => Navigator.pop(ctx),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                ListTile(
                  leading: const CircleAvatar(
                    backgroundColor: Color(0xFFFFEDD5),
                    child: Icon(Icons.touch_app, color: Color(0xFFEA580C)),
                  ),
                  title: const Text('Chạm chọn tự do trên bản đồ', style: TextStyle(fontWeight: FontWeight.bold)),
                  subtitle: const Text('Bật chế độ chạm vào bất kỳ tuyến phố nào trên bản đồ'),
                  onTap: () {
                    Navigator.pop(ctx);
                    setState(() => _interactionMode = 3);
                  },
                ),
                const Divider(),
                const Text(
                  'HOẶC CHỌN ĐIỂM ÙN TẮC TRỌNG ĐIỂM (DEMO HÀ NỘI):',
                  style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: Color(0xFF64748B)),
                ),
                const SizedBox(height: 6),
                _buildAccidentPresetTile(
                  ctx: ctx,
                  title: 'Ngã tư Trường Chinh – Tôn Thất Tùng',
                  subtitle: 'Điểm nghẽn kinh điển giữa Ngã Tư Sở và Bách Khoa',
                  point: const LatLng(21.0015, 105.8300),
                ),
                _buildAccidentPresetTile(
                  ctx: ctx,
                  title: 'Nút giao Ngã Tư Sở – Nguyễn Trãi',
                  subtitle: 'Điểm giao cắt lớn đầu tuyến xuất phát',
                  point: const LatLng(21.0022, 105.8190),
                ),
                _buildAccidentPresetTile(
                  ctx: ctx,
                  title: 'Nút giao Đại La – Giải Phóng',
                  subtitle: 'Nút giao cửa ngõ tiếp cận Đại học Bách Khoa',
                  point: const LatLng(21.0010, 105.8420),
                ),
                _buildAccidentPresetTile(
                  ctx: ctx,
                  title: 'Phố Chùa Bộc – Phạm Ngọc Thạch',
                  subtitle: 'Tuyến đường nhánh né tránh phía Bắc',
                  point: const LatLng(21.0080, 105.8280),
                ),
                if (_accidentPoint != null) ...[
                  const Divider(),
                  ListTile(
                    leading: const CircleAvatar(
                      backgroundColor: Color(0xFFFEE2E2),
                      child: Icon(Icons.delete_outline, color: Color(0xFFDC2626)),
                    ),
                    title: const Text('Xóa điểm tai nạn hiện tại', style: TextStyle(color: Color(0xFFDC2626), fontWeight: FontWeight.bold)),
                    onTap: () {
                      Navigator.pop(ctx);
                      _clearAccident();
                    },
                  ),
                ],
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _buildAccidentPresetTile({
    required BuildContext ctx,
    required String title,
    required String subtitle,
    required LatLng point,
  }) {
    final bool isCurrent = _accidentPoint != null &&
        (point.latitude - _accidentPoint!.latitude).abs() < 0.0005 &&
        (point.longitude - _accidentPoint!.longitude).abs() < 0.0005;

    return ListTile(
      dense: true,
      leading: Icon(
        isCurrent ? Icons.check_circle : Icons.warning_amber_rounded,
        color: isCurrent ? const Color(0xFF10B981) : const Color(0xFFDC2626),
      ),
      title: Text(title, style: TextStyle(fontWeight: isCurrent ? FontWeight.bold : FontWeight.w600, fontSize: 13)),
      subtitle: Text(subtitle, style: const TextStyle(fontSize: 11)),
      trailing: isCurrent ? const Chip(label: Text('Đang cắm', style: TextStyle(fontSize: 10, color: Colors.white)), backgroundColor: Color(0xFFDC2626)) : null,
      onTap: () {
        Navigator.pop(ctx);
        setState(() {
          _accidentPoint = point;
          _interactionMode = 0;
          _stopCarSimulation();
        });
        _fetchRoutes();
      },
    );
  }
}
