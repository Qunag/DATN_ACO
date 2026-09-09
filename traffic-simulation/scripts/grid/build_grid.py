#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, io
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
"""
build_grid.py – Build mạng lưới 3×3 bằng netconvert
====================================================
Sử dụng:
    python scripts/build_grid.py
"""
import subprocess, sys, os
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
NETWORK_DIR = PROJECT_DIR / "network"

def get_netconvert():
    sumo_home = os.environ.get("SUMO_HOME")
    if not sumo_home:
        for c in ["C:/Program Files (x86)/Eclipse/Sumo",
                  "C:/Program Files/Eclipse/Sumo", "C:/sumo"]:
            if Path(c).exists():
                sumo_home = c
                os.environ["SUMO_HOME"] = c
                break
    if sumo_home:
        nc = Path(sumo_home) / "bin" / "netconvert.exe"
        if nc.exists():
            return str(nc)
    return "netconvert"

def build():
    nodes  = NETWORK_DIR / "grid_nodes.nod.xml"
    edges  = NETWORK_DIR / "grid_edges.edg.xml"
    output = NETWORK_DIR / "grid_net.xml"

    print("=" * 55)
    print("  BUILD GRID NETWORK 3×3")
    print("=" * 55)

    nc = get_netconvert()
    cmd = [nc,
           "--node-files",  str(nodes),
           "--edge-files",  str(edges),
           "--output-file", str(output),
           "--tls.default-type", "static",
           "--tls.cycle.time",   "66",
           "--no-warnings",
           "--junctions.corner-detail", "5"]

    print(f"Chay lenh: {' '.join(cmd)}\n")
    try:
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode == 0:
            print(f"[OK] Build thanh cong: {output}")
        else:
            print(f"[LOI] {r.stderr}")
            sys.exit(1)
    except FileNotFoundError:
        print(f"[LOI] Khong tim thay netconvert. Dam bao SUMO da cai.")
        sys.exit(1)

if __name__ == "__main__":
    build()
