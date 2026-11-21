import 'package:flutter/material.dart';
import '../models/traffic_model.dart';

class RouteCardWidget extends StatelessWidget {
  final RouteOption route;
  final bool isSelected;
  final VoidCallback onTap;

  const RouteCardWidget({
    super.key,
    required this.route,
    required this.isSelected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final isRecommended = route.probability >= 0.5;

    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 250),
        margin: const EdgeInsets.symmetric(horizontal: 5, vertical: 2),
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
        decoration: BoxDecoration(
          color: isSelected
              ? route.routeColor.withOpacity(0.12)
              : Colors.white,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(
            color: isSelected ? route.routeColor : const Color(0xFFE2E8F0),
            width: isSelected ? 2.2 : 1.0,
          ),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity(isSelected ? 0.08 : 0.03),
              blurRadius: 8,
              offset: const Offset(0, 3),
            ),
          ],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header: Route ID + Badge xác suất phân luồng Boltzmann
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Row(
                  children: [
                    Container(
                      width: 10,
                      height: 10,
                      decoration: BoxDecoration(
                        color: route.routeColor,
                        shape: BoxShape.circle,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Text(
                      route.routeId,
                      style: const TextStyle(
                        fontWeight: FontWeight.bold,
                        fontSize: 14,
                        color: Color(0xFF1E293B),
                      ),
                    ),
                  ],
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: route.routeColor.withOpacity(0.15),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Text(
                    '${route.probabilityPct}% Lưu lượng',
                    style: TextStyle(
                      color: route.routeColor,
                      fontWeight: FontWeight.bold,
                      fontSize: 11.5,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 6),

            // Tên và nhãn tuyến đường
            Text(
              route.label,
              style: TextStyle(
                fontSize: 12,
                fontWeight: isRecommended ? FontWeight.bold : FontWeight.w500,
                color: isRecommended ? const Color(0xFF0F766E) : const Color(0xFF64748B),
              ),
            ),
            const SizedBox(height: 8),

            // Thời gian ước tính & Khoảng cách
            Row(
              children: [
                const Icon(Icons.timer_outlined, size: 16, color: Color(0xFF0D9488)),
                const SizedBox(width: 4),
                Text(
                  '${route.minutes} phút',
                  style: const TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.bold,
                    color: Color(0xFF0F172A),
                  ),
                ),
                const SizedBox(width: 14),
                const Icon(Icons.straighten, size: 16, color: Color(0xFF64748B)),
                const SizedBox(width: 4),
                Text(
                  '${(route.lengthM / 1000).toStringAsFixed(1)} km',
                  style: const TextStyle(
                    fontSize: 13,
                    color: Color(0xFF64748B),
                  ),
                ),
                if (route.isBlocked) ...[
                  const Spacer(),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                    decoration: BoxDecoration(
                      color: const Color(0xFFFEE2E2),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: const Text(
                      'TẮC NGHẼN',
                      style: TextStyle(
                        color: Color(0xFFDC2626),
                        fontWeight: FontWeight.bold,
                        fontSize: 10,
                      ),
                    ),
                  ),
                ],
              ],
            ),
          ],
        ),
      ),
    );
  }
}
