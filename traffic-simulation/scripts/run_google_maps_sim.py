#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_google_maps_sim.py – Khởi chạy Máy chủ Mô phỏng Giao thông trên Google Maps
Đề tài DATN: "Điều hướng Giao thông bằng Giải thuật Đàn Kiến (ACO)"
"""

import os
import sys
import io
import time
import socket
import webbrowser
from pathlib import Path

# Fix console encoding trên Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

PROJECT_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = PROJECT_DIR / "web"
INDEX_FILE = WEB_DIR / "index.html"

def find_available_port(start_port=8050, max_attempts=20):
    """
    Kiểm tra cổng trống bằng bind() - tức thì trong 0.001s, không bị nghẽn bởi Proxy/Firewall.
    """
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(('0.0.0.0', port))
                return port
            except OSError:
                continue
    return start_port

def run_flask_server(port):
    from flask import Flask, send_from_directory, jsonify
    import logging

    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)

    app = Flask(__name__, static_folder=str(WEB_DIR), static_url_path="")

    @app.route("/")
    def index():
        return send_from_directory(str(WEB_DIR), "index.html")

    @app.route("/<path:filename>")
    def static_files(filename):
        return send_from_directory(str(WEB_DIR), filename)

    @app.route("/api/health")
    def health():
        return jsonify({"status": "ok", "app": "ACO Traffic Simulation"})

    # Lắng nghe trên 0.0.0.0 để tránh bị proxy Windows chặn 127.0.0.1
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False, threaded=True)

def main():
    port = find_available_port(8050)
    local_url = f"http://localhost:{port}/"
    ip_url = f"http://127.0.0.1:{port}/"
    file_url = INDEX_FILE.as_uri()

    print("=" * 72)
    print("   HỆ THỐNG MÔ PHỎNG GIAO THÔNG THÔNG MINH TRÊN GOOGLE MAPS")
    print("   Đề tài: Điều Hướng Giao Thông Bằng Giải Thuật Đàn Kiến (ACO)")
    print("=" * 72)
    print(f"[*] Thư mục giao diện: {WEB_DIR}")
    print(f"[*] Máy chủ đang chạy tại: {local_url}")
    print("=" * 72)
    print("  👉 BẠN CÓ THỂ MỞ BẰNG CÁC ĐƯỜNG DẪN SAU TRÊN TRÌNH DUYỆT:")
    print(f"     1. {local_url}   (Khuyên dùng - tự động bỏ qua proxy)")
    print(f"     2. {ip_url}")
    print(f"     3. {file_url}   (Mở trực tiếp file không cần mạng)")
    print("=" * 72)
    print("  Nhấn Ctrl+C để dừng máy chủ.\n")
    sys.stdout.flush()

    # Mở trình duyệt sau 1 giây
    try:
        import threading
        def open_browser():
            time.sleep(0.8)
            webbrowser.open(local_url)
        threading.Thread(target=open_browser, daemon=True).start()
    except Exception as e:
        print(f"[!] Không thể tự mở trình duyệt: {e}")

    try:
        run_flask_server(port)
    except KeyboardInterrupt:
        print("\n[*] Đang tắt máy chủ mô phỏng... Cảm ơn bạn đã sử dụng!")

if __name__ == "__main__":
    main()
