import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_its_app/models/traffic_model.dart';

void main() {
  test('RouteOption model parsing test', () {
    final route = RouteOption.fromJson({
      'route_id': 'T-ACO-R1',
      'name': 'Route 1',
      'label': 'Tuyến chính',
      'length_m': 3200,
      'base_time': 600,
      'estimated_travel_time_sec': 660,
      'estimated_minutes': 11.0,
      'probability': 0.55,
      'probability_pct': 55.0,
      'polyline_coords': [
        [21.0368, 105.7825],
        [21.0320, 105.8200],
      ],
    });

    expect(route.routeId, equals('T-ACO-R1'));
    expect(route.minutes, equals(11.0));
    expect(route.probabilityPct, equals(55.0));
    expect(route.coordinates.length, equals(2));
  });
}
