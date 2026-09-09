#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, io
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
"""
build_network.py – Tự động build file mạng SUMO (intersection.net.xml)
========================================================================
Sử dụng netconvert để biên dịch nodes.nod.xml + edges.edg.xml
thành file mạng hoàn chỉnh có traffic light.

Chạy một lần trước khi dùng monitor.py:
    python scripts/build_network.py

Yêu cầu: SUMO đã được cài và SUMO_HOME đã được set trong biến môi trường.
"""

import subprocess
import sys
import os
from pathlib import Path


# ─────────────────────────────────────────────────────────────────
# Cấu hình đường dẫn
# ─────────────────────────────────────────────────────────────────

# Thư mục gốc của project
PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
NETWORK_DIR = PROJECT_DIR / "network"

NODES_FILE  = NETWORK_DIR / "nodes.nod.xml"
EDGES_FILE  = NETWORK_DIR / "edges.edg.xml"
NET_FILE    = NETWORK_DIR / "intersection.net.xml"


# ─────────────────────────────────────────────────────────────────
# Kiểm tra SUMO_HOME
# ─────────────────────────────────────────────────────────────────

def get_sumo_home() -> Path:
    """Tìm và trả về đường dẫn SUMO_HOME."""
    sumo_home = os.environ.get("SUMO_HOME")
    if sumo_home:
        return Path(sumo_home)

    # Thử các đường dẫn mặc định phổ biến trên Windows
    default_paths = [
        Path("C:/Program Files (x86)/Eclipse/Sumo"),
        Path("C:/Program Files/Eclipse/Sumo"),
        Path("C:/sumo"),
    ]
    for p in default_paths:
        if p.exists():
            return p

    raise EnvironmentError(
        "Không tìm thấy SUMO. Hãy cài SUMO và set biến môi trường SUMO_HOME.\n"
        "Tải tại: https://sumo.dlr.de/docs/Downloads.php"
    )


def get_netconvert_path() -> str:
    """Tìm đường dẫn tới netconvert executable."""
    try:
        sumo_home = get_sumo_home()
        netconvert = sumo_home / "bin" / "netconvert.exe"
        if netconvert.exists():
            return str(netconvert)
    except EnvironmentError:
        pass

    # Thử gọi trực tiếp (nếu đã có trong PATH)
    return "netconvert"


# ─────────────────────────────────────────────────────────────────
# Build mạng
# ─────────────────────────────────────────────────────────────────

def build_network():
    """Chạy netconvert để tạo file mạng SUMO."""

    print("=" * 60)
    print("  BUILD NETWORK – SUMO Traffic Simulation")
    print("=" * 60)
    print(f"  Nodes : {NODES_FILE}")
    print(f"  Edges : {EDGES_FILE}")
    print(f"  Output: {NET_FILE}")
    print()

    # Kiểm tra file đầu vào tồn tại
    for f in [NODES_FILE, EDGES_FILE]:
        if not f.exists():
            print(f"[LỖI] Không tìm thấy: {f}")
            sys.exit(1)

    netconvert = get_netconvert_path()

    # Lệnh netconvert với các tham số:
    # --node-files : file nodes
    # --edge-files : file edges
    # --output-file: file net output
    # --tls.default-type : loại đèn tín hiệu mặc định
    # --tls.cycle.time  : chu kỳ đèn mặc định (66 giây = 30+3+30+3)
    # --no-warnings    : tắt cảnh báo không quan trọng
    cmd = [
        netconvert,
        "--node-files",   str(NODES_FILE),
        "--edge-files",   str(EDGES_FILE),
        "--output-file",  str(NET_FILE),
        "--tls.default-type", "static",
        "--tls.cycle.time",   "66",
        "--no-warnings",
        "--junctions.corner-detail", "5",
        "--geometry.remove",
    ]

    print(f"Chạy lệnh:\n  {' '.join(cmd)}\n")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")

        if result.returncode == 0:
            print("[OK] Build mạng thành công!")
            print(f"     File: {NET_FILE}")
            if result.stdout:
                print("\nOutput:")
                print(result.stdout)
        else:
            print("[LỖI] netconvert thất bại!")
            print(result.stderr)
            sys.exit(1)

    except FileNotFoundError:
        print(f"[LỖI] Không tìm thấy netconvert tại: {netconvert}")
        print("Hãy đảm bảo SUMO đã được cài và SUMO_HOME được set đúng.")
        sys.exit(1)


if __name__ == "__main__":
    build_network()
