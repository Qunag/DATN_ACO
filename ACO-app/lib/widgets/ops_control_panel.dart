import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/api_service.dart';
import '../models/traffic_model.dart';

class OpsControlPanel extends StatelessWidget {
  final NetworkStats? stats;
  final VoidCallback onRefresh;

  const OpsControlPanel({
    super.key,
    required this.stats,
    required this.onRefresh,
  });

  @override
  Widget build(BuildContext context) {
    final apiService = context.watch<ApiService>();
    final hasIncident = (stats?.activeIncidents ?? 0) > 0;

    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            // Thanh trạng thái chỉ số toàn mạng (Network KPIs)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              decoration: BoxDecoration(
                color: const Color(0xFF1E293B).withOpacity(0.92),
                borderRadius: BorderRadius.circular(16),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withOpacity(0.18),
                    blurRadius: 12,
                    offset: const Offset(0, 4),
                  ),
                ],
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  // KPI 1: Mean Speed
                  _buildKpiItem(
                    icon: Icons.speed,
                    label: 'Vận tốc TB',
                    value: '${stats?.meanSpeedKmh.toStringAsFixed(1) ?? "--"} km/h',
                    valueColor: const Color(0xFF34D399),
                  ),
                  _buildDivider(),
                  // KPI 2: Delay
                  _buildKpiItem(
                    icon: Icons.hourglass_bottom,
                    label: 'Độ trễ TB',
                    value: '${stats?.avgDelaySec.toStringAsFixed(0) ?? "--"}s',
                    valueColor: const Color(0xFFFBBF24),
                  ),
                  _buildDivider(),
                  // KPI 3: Status
                  _buildKpiItem(
                    icon: Icons.hub,
                    label: 'Mô hình T-ACO',
                    value: hasIncident ? 'Tái phân luồng' : 'Cân bằng tải',
                    valueColor: hasIncident ? const Color(0xFFF87171) : const Color(0xFF38BDF8),
                  ),
                  // Button cài đặt IP Backend
                  IconButton(
                    icon: const Icon(Icons.settings, color: Colors.white70, size: 20),
                    tooltip: 'Đổi IP Backend',
                    onPressed: () => _showIpDialog(context, apiService),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 8),

            // Nút kích hoạt sự cố giả định phục vụ demo
            Row(
              children: [
                Expanded(
                  child: ElevatedButton.icon(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: hasIncident
                          ? const Color(0xFF10B981)
                          : const Color(0xFFEF4444),
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(vertical: 10),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                      elevation: 3,
                    ),
                    icon: Icon(hasIncident ? Icons.check_circle : Icons.warning_amber),
                    label: Text(
                      hasIncident
                          ? 'Khôi phục thông thoáng'
                          : '⚡ Gây tắc đường Cầu Giấy (Demo)',
                      style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                    ),
                    onPressed: () async {
                      if (hasIncident) {
                        await apiService.clearIncident();
                      } else {
                        await apiService.injectIncident(edgeId: 'CauGiay');
                      }
                      onRefresh();
                    },
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildKpiItem({
    required IconData icon,
    required String label,
    required String value,
    required Color valueColor,
  }) {
    return Row(
      children: [
        Icon(icon, color: valueColor, size: 18),
        const SizedBox(width: 6),
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              label,
              style: const TextStyle(color: Colors.white60, fontSize: 10),
            ),
            Text(
              value,
              style: TextStyle(
                color: valueColor,
                fontWeight: FontWeight.bold,
                fontSize: 13,
              ),
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildDivider() {
    return Container(
      width: 1,
      height: 26,
      color: Colors.white24,
    );
  }

  void _showIpDialog(BuildContext context, ApiService apiService) {
    final controller = TextEditingController(text: apiService.baseUrl);
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Cấu hình Máy chủ Backend (Python)'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Nhập địa chỉ máy chủ chạy script Python backend (ví dụ khi kết nối qua WiFi chung):',
              style: TextStyle(fontSize: 13),
            ),
            const SizedBox(height: 10),
            TextField(
              controller: controller,
              decoration: const InputDecoration(
                border: OutlineInputBorder(),
                hintText: 'http://192.168.1.15:8050',
                labelText: 'Backend URL',
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            child: const Text('Đóng'),
            onPressed: () => Navigator.pop(ctx),
          ),
          ElevatedButton(
            child: const Text('Lưu'),
            onPressed: () {
              apiService.setBaseUrl(controller.text);
              Navigator.pop(ctx);
              onRefresh();
            },
          ),
        ],
      ),
    );
  }
}
