#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, io
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
"""
gui.py – Mở SUMO-GUI cho bất kỳ kịch bản hoặc mạng nào
=========================================================
Giải quyết vấn đề 'sumo-gui' không có trong PATH trên Windows.

Sử dụng:
    python scripts/gui.py                        # Ngã tư TH3 (mặc định)
    python scripts/gui.py --scenario TH5         # Ngã tư TH5
    python scripts/gui.py --scenario rush        # Giờ cao điểm
    python scripts/gui.py --scenario mixed       # Hỗn hợp phương tiện
    python scripts/gui.py --network grid         # Mạng lưới 3x3
    python scripts/gui.py --osm                  # Mở OSM Web Wizard
"""

import os, sys, subprocess, argparse
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent.resolve()

# ─── Tìm SUMO ─────────────────────────────────────────────────────
def get_sumo_home():
    sumo_home = os.environ.get("SUMO_HOME")
    if not sumo_home:
        for c in ["C:/Program Files (x86)/Eclipse/Sumo",
                  "C:/Program Files/Eclipse/Sumo", "C:/sumo"]:
            if Path(c).exists():
                sumo_home = c
                os.environ["SUMO_HOME"] = c
                break
    if not sumo_home:
        raise EnvironmentError(
            "[LOI] Khong tim thay SUMO.\n"
            "Set bien moi truong: $env:SUMO_HOME = 'C:\\Program Files (x86)\\Eclipse\\Sumo'"
        )
    return sumo_home

def get_sumo_gui_exe():
    """Trả về đường dẫn đầy đủ tới sumo-gui.exe."""
    sumo_home = get_sumo_home()
    gui_exe = Path(sumo_home) / "bin" / "sumo-gui.exe"
    if not gui_exe.exists():
        raise FileNotFoundError(
            f"[LOI] Khong tim thay sumo-gui.exe tai: {gui_exe}\n"
            f"Kiem tra lai thu muc SUMO: {sumo_home}"
        )
    return str(gui_exe)

# ─── Mapping kịch bản → file routes ──────────────────────────────
SCENARIO_ROUTES = {
    "TH1": "routes/routes_TH1.rou.xml",
    "TH2": "routes/routes_TH2.rou.xml",
    "TH3": "routes/routes_TH3.rou.xml",
    "TH4": "routes/routes_TH4.rou.xml",
    "TH5": "routes/routes_TH5.rou.xml",
    "TH6": "routes/routes_TH6.rou.xml",
    "rush":  "routes/routes_rush.rou.xml",
    "mixed": "routes/routes_mixed.rou.xml",
}

# ─── Mở SUMO-GUI cho ngã tư ──────────────────────────────────────
def open_intersection(scenario="TH3"):
    gui_exe = get_sumo_gui_exe()
    cfg     = PROJECT_DIR / "intersection.sumocfg"

    if scenario not in SCENARIO_ROUTES:
        print(f"[LOI] Kich ban khong hop le: {scenario}")
        print(f"Cac kich ban ho tro: {', '.join(SCENARIO_ROUTES.keys())}")
        return

    routes = PROJECT_DIR / SCENARIO_ROUTES[scenario]
    if not routes.exists():
        print(f"[LOI] Khong tim thay file routes: {routes}")
        return

    demand_map = {"TH1":200,"TH2":400,"TH3":600,"TH4":800,
                  "TH5":1000,"TH6":1200,"rush":"gio cao diem","mixed":"hon hop"}

    print(f"\n  Mo SUMO-GUI: Nga tu 4 huong")
    print(f"  Kich ban   : {scenario} ({demand_map.get(scenario,'?')} xe/h)")
    print(f"  Routes     : {routes.name}")
    print(f"\n  Nhan Play (▶) trong SUMO-GUI de bat dau chay.")
    print(f"  Ctrl+C de thoat.\n")

    cmd = [gui_exe,
           "--configuration-file", str(cfg),
           "--route-files",        str(routes),
           "--start",              # Tự động bắt đầu (không cần nhấn Play thủ công)
           "--quit-on-end",        # Tự đóng khi simulation xong
           "--delay", "50",        # Làm chậm 50ms/bước để dễ quan sát
    ]
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\n  [OK] SUMO-GUI da duoc dong.")

# ─── Mở SUMO-GUI cho mạng lưới 3×3 ──────────────────────────────
def open_grid():
    gui_exe = get_sumo_gui_exe()
    cfg     = PROJECT_DIR / "grid.sumocfg"
    net     = PROJECT_DIR / "network" / "grid_net.xml"

    if not net.exists():
        print("[!] Chua build mang luoi 3x3.")
        print("    Chay truoc: python scripts/build_grid.py")
        return

    print(f"\n  Mo SUMO-GUI: Mang luoi 3x3 (A-B-C / D-E-F / G-H-I)")
    print(f"  Config: {cfg.name}")
    print(f"  Nhan Play (▶) trong SUMO-GUI de bat dau.\n")

    cmd = [gui_exe,
           "--configuration-file", str(cfg),
           "--start",
           "--delay", "30",
    ]
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\n  [OK] SUMO-GUI da duoc dong.")

# ─── Mở OSM Web Wizard ───────────────────────────────────────────
def open_osm_wizard():
    sumo_home = get_sumo_home()
    wizard    = Path(sumo_home) / "tools" / "osmWebWizard.py"
    osm_dir   = PROJECT_DIR / "osm"
    osm_dir.mkdir(parents=True, exist_ok=True)

    if not wizard.exists():
        print(f"[LOI] Khong tim thay osmWebWizard.py tai: {wizard}")
        return

    print(f"\n  Mo OSM Web Wizard...")
    print(f"  Trinh duyet se tu dong mo toi: http://localhost:8080")
    print(f"""
  HUONG DAN:
    1. Nhap vi tri: "Ha Dong, Ha Noi" vao o tim kiem
       Hoac keo chon vung tren ban do
    2. Chon cac loai giao thong (car, motorcycle, bus)
    3. Dieu chinh Through Traffic Factor (1 = binh thuong, 5 = dong)
    4. Nhan "Generate Scenario"
    5. SUMO-GUI se tu dong mo voi ban do thuc te
  """)

    # Chạy wizard từ thư mục của nó (cần thiết để tìm được các file templates)
    subprocess.Popen([sys.executable, str(wizard)],
                     cwd=str(wizard.parent))
    print("  [OK] OSM Web Wizard dang chay. Kiem tra trinh duyet!")

# ─── CLI ─────────────────────────────────────────────────────────
def parse_args():
    p = argparse.ArgumentParser(
        description="Mo SUMO-GUI (giai quyet loi sumo-gui khong co trong PATH)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Vi du:
  python scripts/gui.py                    # Nga tu TH3
  python scripts/gui.py --scenario TH5    # Nga tu 1000 xe/h
  python scripts/gui.py --scenario rush   # Gio cao diem
  python scripts/gui.py --scenario mixed  # Hon hop xe may/o to/bus
  python scripts/gui.py --network grid    # Mang luoi 3x3
  python scripts/gui.py --osm             # OSM Web Wizard (ban do thuc te)
        """
    )
    g = p.add_mutually_exclusive_group()
    g.add_argument("--scenario", default="TH3",
                   choices=list(SCENARIO_ROUTES.keys()),
                   help="Kich ban nga tu 1 nut (mac dinh: TH3)")
    g.add_argument("--network", choices=["grid"],
                   help="Mo mang luoi: grid = 3x3")
    g.add_argument("--osm", action="store_true",
                   help="Mo OSM Web Wizard (ban do thuc te)")
    return p.parse_args()

if __name__ == "__main__":
    args = parse_args()
    try:
        if args.osm:
            open_osm_wizard()
        elif args.network == "grid":
            open_grid()
        else:
            open_intersection(args.scenario)
    except (EnvironmentError, FileNotFoundError) as e:
        print(e)
        sys.exit(1)
