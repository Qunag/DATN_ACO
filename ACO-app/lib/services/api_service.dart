import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import '../models/traffic_model.dart';

class ApiService extends ChangeNotifier {
  // Cho phép chuyển đổi linh hoạt giữa localhost và IP máy tính LAN khi chạy trên điện thoại thật
  String _baseUrl = 'http://localhost:8050';

  String get baseUrl => _baseUrl;
  void setBaseUrl(String url) {
    _baseUrl = url.trim().replaceAll(RegExp(r'/+$'), '');
    notifyListeners();
  }

  /// Lấy danh sách trạng thái đường (màu sắc) và các xe đang lưu thông theo kịch bản SUMO
  Future<Map<String, dynamic>> fetchLiveTraffic({String scenario = 'TH3'}) async {
    try {
      final response = await http
          .get(Uri.parse('$_baseUrl/api/traffic/live-status?scenario=$scenario'))
          .timeout(const Duration(seconds: 4));

      if (response.statusCode == 200) {
        final data = json.decode(utf8.decode(response.bodyBytes));
        final rawEdges = data['edges_status'] as List? ?? [];
        final rawVehs = data['vehicles'] as List? ?? [];

        List<EdgeCongestion> edges =
            rawEdges.map((e) => EdgeCongestion.fromJson(e)).toList();
        List<VehicleMarker> vehs =
            rawVehs.map((v) => VehicleMarker.fromJson(v)).toList();

        return {
          'edges': edges,
          'vehicles': vehs,
          'timestamp': data['timestamp'] ?? 0.0,
        };
      }
    } catch (e) {
      debugPrint('[ApiService] Lỗi fetchLiveTraffic: $e');
    }
    return {'edges': <EdgeCongestion>[], 'vehicles': <VehicleMarker>[], 'timestamp': 0.0};
  }

  /// Gợi ý Top-K tuyến đường phân luồng xác suất T-ACO (hỗ trợ điểm tai nạn, kịch bản SUMO TH1-TH6)
  Future<Map<String, dynamic>> fetchStochasticRoutes({
    String origin = 'Điểm đi',
    String destination = 'Điểm đến',
    double? originLat,
    double? originLng,
    double? destLat,
    double? destLng,
    double? accidentLat,
    double? accidentLng,
    double accidentRadius = 180.0,
    String transportMode = 'driving',
    String scenario = 'TH3',
    int topK = 3,
  }) async {
    try {
      final Map<String, dynamic> requestBody = {
        'origin': origin,
        'destination': destination,
        'transport_mode': transportMode,
        'scenario': scenario,
        'top_k': topK,
      };

      if (originLat != null && originLng != null && destLat != null && destLng != null) {
        requestBody['origin_lat'] = originLat;
        requestBody['origin_lng'] = originLng;
        requestBody['dest_lat'] = destLat;
        requestBody['dest_lng'] = destLng;
      }

      if (accidentLat != null && accidentLng != null) {
        requestBody['accident_lat'] = accidentLat;
        requestBody['accident_lng'] = accidentLng;
        requestBody['accident_radius'] = accidentRadius;
      }

      final response = await http
          .post(
            Uri.parse('$_baseUrl/api/routing/stochastic-recommend'),
            headers: {'Content-Type': 'application/json'},
            body: json.encode(requestBody),
          )
          .timeout(const Duration(seconds: 5));

      if (response.statusCode == 200) {
        final data = json.decode(utf8.decode(response.bodyBytes)) as Map;
        final rawRoutes = (data['recommended_routes'] as List?) ?? [];
        final routes = <RouteOption>[];
        for (final r in rawRoutes) {
          if (r is Map) routes.add(RouteOption.fromJson(r));
        }
        OptimizationComparison? comparison;
        if (data['optimization_comparison'] is Map) {
          comparison = OptimizationComparison.fromJson(data['optimization_comparison'] as Map);
        }
        return {
          'routes': routes,
          'comparison': comparison,
          'accidents': data['accidents'] ?? [],
        };
      }
    } catch (e) {
      debugPrint('[ApiService] Lỗi fetchStochasticRoutes: $e');
    }
    return {'routes': <RouteOption>[], 'comparison': null, 'accidents': []};
  }

  /// Cắm điểm tai nạn / sự cố kẹt xe
  Future<bool> injectIncident({double? lat, double? lng, double radius = 180.0, String edgeId = 'ACCIDENT'}) async {
    try {
      final Map<String, dynamic> body = {
        'edge_id': edgeId,
        'severity': 'heavy',
        'radius': radius,
      };
      if (lat != null && lng != null) {
        body['lat'] = lat;
        body['lng'] = lng;
      }
      final response = await http.post(
        Uri.parse('$_baseUrl/api/simulation/inject-incident'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode(body),
      );
      return response.statusCode == 200;
    } catch (e) {
      debugPrint('[ApiService] Lỗi injectIncident: $e');
      return false;
    }
  }

  /// Xóa sự cố kẹt xe
  Future<bool> clearIncident() async {
    try {
      final response = await http.post(
        Uri.parse('$_baseUrl/api/simulation/clear-incident'),
      );
      return response.statusCode == 200;
    } catch (e) {
      debugPrint('[ApiService] Lỗi clearIncident: $e');
      return false;
    }
  }

  /// Lấy chỉ số thống kê mạng lưới toàn cục
  Future<NetworkStats?> fetchStats() async {
    try {
      final response = await http
          .get(Uri.parse('$_baseUrl/api/simulation/stats'))
          .timeout(const Duration(seconds: 3));

      if (response.statusCode == 200) {
        final data = json.decode(utf8.decode(response.bodyBytes));
        return NetworkStats.fromJson(data);
      }
    } catch (e) {
      debugPrint('[ApiService] Lỗi fetchStats: $e');
    }
    return null;
  }
}
