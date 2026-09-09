#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, io
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
"""
osm_setup.py – Mức 6: Hướng dẫn và tải dữ liệu OpenStreetMap
===============================================================
Script này tự động hóa quy trình lấy bản đồ thực tế từ OSM
và chuyển đổi sang định dạng SUMO.

Hai phương pháp:
  METHOD A – OSM Web Wizard (GUI, dễ nhất):
    Mở trình duyệt tới SUMO OSM Web Wizard
    Chọn vùng bản đồ bằng chuột → tải về → mở trực tiếp trong SUMO

  METHOD B – Python + osmium (tự động, không cần GUI):
    1. Tải file .osm.pbf từ Geofabrik
    2. Cắt vùng bằng osmium hoặc osmosis
    3. Chuyển đổi sang SUMO bằng netconvert
    4. Sinh nhu cầu giao thông bằng randomTrips.py

Vùng gợi ý: Một phần Hà Đông, Hà Nội
  Bounding box: 105.76, 20.96, 105.82, 21.02

Sử dụng:
    python scripts/osm_setup.py --method wizard   # Mở SUMO OSM Wizard
    python scripts/osm_setup.py --method auto     # Tự động tải và convert
    python scripts/osm_setup.py --info            # Chỉ in hướng dẫn
"""

import os, sys, subprocess, argparse, webbrowser
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
OSM_DIR = PROJECT_DIR / "osm"

# Bounding box cho một phần Hà Đông, Hà Nội
# (lon_min, lat_min, lon_max, lat_max)
HA_DONG_BBOX = (105.76, 20.96, 105.82, 21.02)

# ─── Tìm SUMO ─────────────────────────────────────────────────────
def get_sumo_home():
    sumo_home = os.environ.get("SUMO_HOME")
    if not sumo_home:
        for c in ["C:/Program Files (x86)/Eclipse/Sumo",
                  "C:/Program Files/Eclipse/Sumo", "C:/sumo"]:
            if Path(c).exists():
                sumo_home = c
                break
    return sumo_home

# ─── Method A: OSM Web Wizard ─────────────────────────────────────
def open_osm_wizard():
    """Mở SUMO OSM Web Wizard trong trình duyệt."""
    sumo_home = get_sumo_home()

    print("\n" + "═"*62)
    print("  METHOD A: SUMO OSM Web Wizard")
    print("═"*62)
    print("""
  Buoc 1: Mo OSM Web Wizard (tu dong mo trinh duyet)
  Buoc 2: Chon vung ban do:
            Vi du: "Ha Dong, Ha Noi" hoac nhap toa do thu cong:
            N: 21.02, S: 20.96, E: 105.82, W: 105.76
  Buoc 3: Chon "Generate Scenario"
  Buoc 4: Chon loai giao thong: car, motorcycle, bus...
  Buoc 5: Click "Start Simulation" – SUMO-GUI se tu mo

  File duoc luu tai: osm/
    osm.net.xml  – mang duong
    osm.rou.xml  – tuyen xe
    osm.sumocfg  – config
    """)

    # Thử mở OSM Wizard
    if sumo_home:
        wizard_path = Path(sumo_home) / "tools" / "osmWebWizard.py"
        if wizard_path.exists():
            print(f"  Tim thay OSM Wizard: {wizard_path}")
            print("  Dang khoi dong...")
            # Tao thu muc osm/ truoc (tranh WinError 267)
            OSM_DIR.mkdir(parents=True, exist_ok=True)
            # Chay OSM Wizard tu thu muc chua no (SUMO_HOME/tools)
            # vi osmWebWizard.py can cac file ben canh no
            wizard_dir = wizard_path.parent
            try:
                subprocess.Popen([sys.executable, str(wizard_path)],
                                 cwd=str(wizard_dir))
                print("  [OK] OSM Web Wizard da mo trong trinh duyet!")
            except Exception as e:
                print(f"  [LOI] Khong the khoi dong: {e}")
                print(f"  Chay thu cong: python \"{wizard_path}\"")
        else:
            print(f"  [!] Khong tim thay osmWebWizard.py trong {sumo_home}/tools")
            # Thử mở trình duyệt tới OSM
            webbrowser.open("https://sumo.dlr.de/userdoc/Tutorials/OSMWebWizard.html")
    else:
        print("  [!] SUMO_HOME chua duoc set.")

# ─── Method B: Tự động tải OSM ────────────────────────────────────
def auto_download_convert():
    """Tự động tải OSM và convert sang SUMO."""
    sumo_home = get_sumo_home()
    OSM_DIR.mkdir(parents=True, exist_ok=True)

    print("\n" + "═"*62)
    print("  METHOD B: Tu dong tai va chuyen doi OSM")
    print("═"*62)

    bbox = HA_DONG_BBOX
    osm_file  = OSM_DIR / "ha_dong.osm"
    net_file  = OSM_DIR / "ha_dong.net.xml"
    rou_file  = OSM_DIR / "ha_dong.rou.xml"
    cfg_file  = OSM_DIR / "ha_dong.sumocfg"

    # ── Bước 1: Tải OSM từ Overpass API ──
    print(f"\n  [1/4] Tai du lieu OSM cho Bounding Box:")
    print(f"        Lon: {bbox[0]}–{bbox[2]}, Lat: {bbox[1]}–{bbox[3]}")

    if not osm_file.exists():
        try:
            import urllib.request
            overpass_url = (
                f"https://overpass-api.de/api/map?"
                f"bbox={bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}"
            )
            print(f"  URL: {overpass_url}")
            print("  Dang tai... (co the mat 30–60 giay)")
            urllib.request.urlretrieve(overpass_url, osm_file)
            size_mb = osm_file.stat().st_size / 1024 / 1024
            print(f"  [OK] Da tai: {osm_file} ({size_mb:.1f} MB)")
        except Exception as e:
            print(f"  [LOI] Khong the tai OSM: {e}")
            print(f"  Tai thu cong tu: https://www.openstreetmap.org/export")
            print(f"  Hoac: https://overpass-api.de/api/map?bbox={','.join(map(str,bbox))}")
            return
    else:
        print(f"  [SKIP] File da ton tai: {osm_file}")

    # ── Bước 2: Convert OSM → SUMO network ──
    print(f"\n  [2/4] Chuyen doi OSM sang SUMO network...")
    if sumo_home:
        nc = Path(sumo_home) / "bin" / "netconvert.exe"
        nc_path = str(nc) if nc.exists() else "netconvert"
    else:
        nc_path = "netconvert"

    nc_cmd = [
        nc_path,
        "--osm-files",     str(osm_file),
        "--output-file",   str(net_file),
        "--geometry.remove",
        "--roundabouts.guess",
        "--ramps.guess",
        "--junctions.join",
        "--tls.guess-signals",
        "--tls.discard-simple",
        "--tls.join",
        "--no-warnings",
        "--keep-edges.by-vclass", "passenger,motorcycle,bus",
    ]
    try:
        r = subprocess.run(nc_cmd, capture_output=True, text=True)
        if r.returncode == 0:
            print(f"  [OK] Network: {net_file}")
        else:
            print(f"  [LOI] netconvert: {r.stderr[:300]}")
            return
    except FileNotFoundError:
        print(f"  [LOI] Khong tim thay netconvert. Kiem tra SUMO.")
        return

    # ── Bước 3: Sinh tuyến đường ngẫu nhiên ──
    print(f"\n  [3/4] Sinh tuyen duong (randomTrips.py)...")
    if sumo_home:
        rt = Path(sumo_home) / "tools" / "randomTrips.py"
        if rt.exists():
            rt_cmd = [
                sys.executable, str(rt),
                "--net-file",    str(net_file),
                "--output-trip-file", str(OSM_DIR / "ha_dong_trips.xml"),
                "--route-file",  str(rou_file),
                "--begin", "0", "--end", "3600",
                "--period", "2",      # 1 xe mỗi 2 giây ≈ 1800 xe/h
                "--vehicle-class", "passenger",
                "--validate",
            ]
            r2 = subprocess.run(rt_cmd, capture_output=True, text=True)
            if r2.returncode == 0:
                print(f"  [OK] Routes: {rou_file}")
            else:
                print(f"  [!] randomTrips co canh bao (co the bo qua): {r2.stderr[:200]}")
        else:
            print(f"  [!] Khong tim thay randomTrips.py")

    # ── Bước 4: Tạo file config ──
    print(f"\n  [4/4] Tao file config SUMO...")
    cfg_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!-- ha_dong.sumocfg - Mo phong ban do Ha Dong, Ha Noi -->
<configuration>
    <input>
        <net-file value="ha_dong.net.xml"/>
        <route-files value="ha_dong.rou.xml"/>
    </input>
    <output>
        <tripinfo-output value="../output/tripinfo_hadong.xml"/>
    </output>
    <time>
        <begin value="0"/>
        <end value="3600"/>
        <step-length value="1"/>
    </time>
    <processing>
        <time-to-teleport value="300"/>
    </processing>
</configuration>"""
    cfg_file.write_text(cfg_content, encoding="utf-8")
    print(f"  [OK] Config: {cfg_file}")

    print(f"\n  HOAN THANH! Chay simulation:")
    print(f"  sumo-gui \"{cfg_file}\"")

# ─── In hướng dẫn ─────────────────────────────────────────────────
def print_info():
    print("""
╔══════════════════════════════════════════════════════════════╗
║   MUC 6: BAN DO THUC TE (OpenStreetMap + SUMO)              ║
╚══════════════════════════════════════════════════════════════╝

VUONG HOI PHONG: Ha Dong, Ha Noi
  Lon: 105.76 – 105.82
  Lat: 20.96  – 21.02
  (khoang 6km × 6km, bao gom nhieu nut giao lon)

BUOC 1 – Tai ban do:
  Option A: SUMO OSM Web Wizard (GUI)
    python scripts/osm_setup.py --method wizard

  Option B: Tu dong qua Overpass API
    python scripts/osm_setup.py --method auto

BUOC 2 – Chay simulation:
  sumo-gui osm/ha_dong.sumocfg

BUOC 3 – Ket hop voi ACO:
  Thay vi mang nhan tao, ACO se duoc chay tren ban do thuc te.
  TraCI van hoat dong tuong tu, chi thay:
    intersection.sumocfg → osm/ha_dong.sumocfg

LUONG DU LIEU:
  OSM → netconvert → ha_dong.net.xml
                              ↓
                    Python + TraCI (monitor.py)
                              ↓
                    ACO routing engine
                              ↓
                    Xe thay doi tuyen duong

YEU CAU THEM:
  pip install osmium         # (neu can cat bbox thu cong)
  pip install requests       # (neu can tai programmatically)
""")

# ─── CLI ─────────────────────────────────────────────────────────
def parse_args():
    p = argparse.ArgumentParser(description="Muc 6: OSM Setup")
    p.add_argument("--method", choices=["wizard","auto"],
                   help="Phuong phap: wizard (GUI) hoac auto (tu dong)")
    p.add_argument("--info", action="store_true",
                   help="In huong dan")
    p.add_argument("--bbox", nargs=4, type=float,
                   metavar=("LON_MIN","LAT_MIN","LON_MAX","LAT_MAX"),
                   default=list(HA_DONG_BBOX),
                   help="Bounding box tuy chinh (mac dinh: Ha Dong)")
    return p.parse_args()

if __name__ == "__main__":
    args = parse_args()
    if args.bbox:
        HA_DONG_BBOX = tuple(args.bbox)

    if args.info or (not args.method):
        print_info()
    elif args.method == "wizard":
        open_osm_wizard()
    elif args.method == "auto":
        auto_download_convert()
