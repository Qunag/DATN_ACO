import 'package:flutter/material.dart';
import 'package:latlong2/latlong.dart';

/// Phân đoạn màu sắc giao thông thời gian thực trên tuyến đường (Xanh - Vàng - Cam - Đỏ - Đỏ sẫm)
class RouteSegment {
  final List<LatLng> points;
  final Color color;
  final double speedKmh;
  final String desc;

  RouteSegment({
    required this.points,
    required this.color,
    required this.speedKmh,
    required this.desc,
  });

  factory RouteSegment.fromJson(Map<dynamic, dynamic> json) {
    var rawPts = json['points'] as List? ?? [];
    List<LatLng> pts = rawPts.map((p) {
      final arr = p as List;
      return LatLng((arr[0] as num).toDouble(), (arr[1] as num).toDouble());
    }).toList();

    String hex = json['color']?.toString() ?? '#10B981';
    Color parsedColor = const Color(0xFF10B981);
    try {
      hex = hex.replaceAll('#', '');
      if (hex.length == 6) {
        parsedColor = Color(int.parse('0xFF$hex'));
      }
    } catch (_) {}

    return RouteSegment(
      points: pts,
      color: parsedColor,
      speedKmh: (json['speed_kmh'] as num?)?.toDouble() ?? 40.0,
      desc: json['desc']?.toString() ?? '',
    );
  }
}

/// Đại diện cho 1 tuyến đường gợi ý trong Top-K của giải thuật T-ACO
class RouteOption {
  final String routeId;
  final String name;
  final String label;
  final double lengthM;
  final int travelTimeSec;
  final double minutes;
  final double probability;
  final double probabilityPct;
  final List<LatLng> coordinates;
  final List<RouteSegment> segments;
  final bool isBlocked;
  final bool hasAccident;
  final String statusDesc;

  RouteOption({
    required this.routeId,
    required this.name,
    required this.label,
    required this.lengthM,
    required this.travelTimeSec,
    required this.minutes,
    required this.probability,
    required this.probabilityPct,
    required this.coordinates,
    required this.segments,
    this.isBlocked = false,
    this.hasAccident = false,
    this.statusDesc = 'Bình thường',
  });

  factory RouteOption.fromJson(Map<dynamic, dynamic> json) {
    var rawCoords = json['polyline_coords'] as List? ?? [];
    List<LatLng> coords = rawCoords.map((pt) {
      final p = pt as List;
      return LatLng((p[0] as num).toDouble(), (p[1] as num).toDouble());
    }).toList();

    var rawSegs = json['segments'] as List? ?? [];
    List<RouteSegment> segments = rawSegs
        .map((s) => RouteSegment.fromJson(s as Map<dynamic, dynamic>))
        .toList();

    // Nếu không có segments từ backend, tự động tạo segment mặc định
    if (segments.isEmpty && coords.isNotEmpty) {
      final defaultColor = (json['has_accident'] == true)
          ? const Color(0xFFDC2626)
          : const Color(0xFF1A73E8);
      segments = [
        RouteSegment(
          points: coords,
          color: defaultColor,
          speedKmh: 40.0,
          desc: json['status_desc']?.toString() ?? '',
        )
      ];
    }

    return RouteOption(
      routeId: json['route_id']?.toString() ?? '',
      name: json['name']?.toString() ?? '',
      label: json['label']?.toString() ?? '',
      lengthM: (json['length_m'] as num?)?.toDouble() ?? 0.0,
      travelTimeSec: (json['estimated_travel_time_sec'] as num?)?.toInt() ?? 0,
      minutes: (json['estimated_minutes'] as num?)?.toDouble() ?? 0.0,
      probability: (json['probability'] as num?)?.toDouble() ?? 0.0,
      probabilityPct: (json['probability_pct'] as num?)?.toDouble() ?? 0.0,
      coordinates: coords,
      segments: segments,
      isBlocked: json['is_blocked'] == true,
      hasAccident: json['has_accident'] == true,
      statusDesc: json['status_desc']?.toString() ?? 'Bình thường',
    );
  }

  Color get routeColor {
    if (hasAccident || isBlocked) return const Color(0xFFDC2626); // Đỏ kẹt tai nạn
    if (probability >= 0.5) return const Color(0xFF1A73E8); // Xanh Google Maps khuyên dùng
    if (probability >= 0.2) return const Color(0xFFF59E0B); // Cam phân tải
    return const Color(0xFF70757A); // Xám dự phòng
  }
}

/// Thông tin so sánh tối ưu hóa thuật toán T-ACO với Dijkstra cổ điển
class OptimizationComparison {
  final String dijkstraRouteId;
  final double dijkstraMinutes;
  final double dijkstraLengthKm;
  final bool dijkstraHasAccident;
  final String dijkstraStatus;

  final String tacoRouteId;
  final double tacoMinutes;
  final double tacoLengthKm;
  final bool tacoHasAccident;
  final String tacoStatus;

  final double timeSavedMinutes;
  final double timeSavedPct;
  final String summary;

  OptimizationComparison({
    required this.dijkstraRouteId,
    required this.dijkstraMinutes,
    required this.dijkstraLengthKm,
    required this.dijkstraHasAccident,
    required this.dijkstraStatus,
    required this.tacoRouteId,
    required this.tacoMinutes,
    required this.tacoLengthKm,
    required this.tacoHasAccident,
    required this.tacoStatus,
    required this.timeSavedMinutes,
    required this.timeSavedPct,
    required this.summary,
  });

  factory OptimizationComparison.fromJson(Map<dynamic, dynamic> json) {
    final d = (json['dijkstra'] as Map?) ?? {};
    final t = (json['t_aco'] as Map?) ?? {};
    return OptimizationComparison(
      dijkstraRouteId: d['route_id']?.toString() ?? 'Dijkstra',
      dijkstraMinutes: (d['minutes'] as num?)?.toDouble() ?? 0.0,
      dijkstraLengthKm: (d['length_km'] as num?)?.toDouble() ?? 0.0,
      dijkstraHasAccident: d['has_accident'] == true,
      dijkstraStatus: d['status']?.toString() ?? 'Bình thường',
      tacoRouteId: t['route_id']?.toString() ?? 'T-ACO',
      tacoMinutes: (t['minutes'] as num?)?.toDouble() ?? 0.0,
      tacoLengthKm: (t['length_km'] as num?)?.toDouble() ?? 0.0,
      tacoHasAccident: t['has_accident'] == true,
      tacoStatus: t['status']?.toString() ?? 'Thông thoáng',
      timeSavedMinutes: (json['time_saved_minutes'] as num?)?.toDouble() ?? 0.0,
      timeSavedPct: (json['time_saved_pct'] as num?)?.toDouble() ?? 0.0,
      summary: json['summary']?.toString() ?? '',
    );
  }
}

/// Trạng thái ùn tắc của từng cung đường thời gian thực
class EdgeCongestion {
  final String edgeId;
  final double speedKmh;
  final double densityPct;
  final String level; // free, medium, heavy
  final Color color;
  final List<LatLng> points;

  EdgeCongestion({
    required this.edgeId,
    required this.speedKmh,
    required this.densityPct,
    required this.level,
    required this.color,
    required this.points,
  });

  factory EdgeCongestion.fromJson(Map<String, dynamic> json) {
    String hexColor = json['color'] ?? '#10B981';
    int colorInt = int.parse(hexColor.replaceFirst('#', '0xFF'));

    var rawPts = json['points'] as List? ?? [];
    List<LatLng> pts = rawPts.map((p) {
      return LatLng((p[0] as num).toDouble(), (p[1] as num).toDouble());
    }).toList();

    return EdgeCongestion(
      edgeId: json['edge_id'] ?? '',
      speedKmh: (json['speed_kmh'] as num?)?.toDouble() ?? 0.0,
      densityPct: (json['density_pct'] as num?)?.toDouble() ?? 0.0,
      level: json['level'] ?? 'free',
      color: Color(colorInt),
      points: pts,
    );
  }
}

/// Vị trí và góc xoay của phương tiện đang di chuyển
class VehicleMarker {
  final String vehId;
  final String edgeId;
  final LatLng position;
  final double speedKmh;
  final double heading;

  VehicleMarker({
    required this.vehId,
    required this.edgeId,
    required this.position,
    required this.speedKmh,
    required this.heading,
  });

  factory VehicleMarker.fromJson(Map<String, dynamic> json) {
    return VehicleMarker(
      vehId: json['veh_id'] ?? '',
      edgeId: json['edge_id'] ?? '',
      position: LatLng(
        (json['lat'] as num).toDouble(),
        (json['lng'] as num).toDouble(),
      ),
      speedKmh: (json['speed_kmh'] as num?)?.toDouble() ?? 0.0,
      heading: (json['heading'] as num?)?.toDouble() ?? 0.0,
    );
  }
}

/// Thống kê chỉ số mạng lưới thời gian thực
class NetworkStats {
  final double meanSpeedKmh;
  final double avgDelaySec;
  final int activeIncidents;
  final double networkEfficiency;

  NetworkStats({
    required this.meanSpeedKmh,
    required this.avgDelaySec,
    required this.activeIncidents,
    required this.networkEfficiency,
  });

  factory NetworkStats.fromJson(Map<String, dynamic> json) {
    return NetworkStats(
      meanSpeedKmh: (json['mean_speed_kmh'] as num?)?.toDouble() ?? 25.0,
      avgDelaySec: (json['avg_delay_sec'] as num?)?.toDouble() ?? 50.0,
      activeIncidents: json['active_incidents'] ?? 0,
      networkEfficiency: (json['network_efficiency_pct'] as num?)?.toDouble() ?? 90.0,
    );
  }
}
