#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, io
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
"""
run_experiments.py – Chạy tuần tự 6 thí nghiệm TH1–TH6
=========================================================
Script này tự động hoá việc chạy tất cả 6 kịch bản thí nghiệm
theo Báo cáo 2, mục 5 (Thiết kế thí nghiệm lưu lượng):

    TH1: 200  xe/h
    TH2: 400  xe/h
    TH3: 600  xe/h
    TH4: 800  xe/h
    TH5: 1000 xe/h
    TH6: 1200 xe/h

Sau khi tất cả thí nghiệm hoàn tất, in bảng so sánh tóm tắt.

Sử dụng:
    python scripts/run_experiments.py               # chạy tất cả 6 kịch bản
    python scripts/run_experiments.py --scenarios TH1 TH2 TH3   # chỉ một số
    python scripts/run_experiments.py --duration 1800            # mô phỏng 30 phút
    python scripts/run_experiments.py --gui                      # bật GUI (chậm)
"""

import sys
import csv
import time
import argparse
from pathlib import Path
from typing import List, Dict, Optional


PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = PROJECT_DIR / "scripts"
EXP_DIR = Path(__file__).resolve().parent

if str(EXP_DIR) not in sys.path:
    sys.path.insert(0, str(EXP_DIR))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

try:
    from scripts.experiments.monitor import run_simulation, _scenario_demand, setup_sumo_path
except ImportError:
    try:
        from experiments.monitor import run_simulation, _scenario_demand, setup_sumo_path
    except ImportError:
        from monitor import run_simulation, _scenario_demand, setup_sumo_path


# ─────────────────────────────────────────────────────────────────
# Cấu hình
# ─────────────────────────────────────────────────────────────────

ALL_SCENARIOS = ["TH1", "TH2", "TH3", "TH4", "TH5", "TH6"]

OUTPUT_DIR  = PROJECT_DIR / "output"


# ─────────────────────────────────────────────────────────────────
# Hàm tính tóm tắt từ CSV của một kịch bản
# ─────────────────────────────────────────────────────────────────

def summarize_csv(csv_path: str, scenario: str) -> Dict:
    """
    Đọc file CSV và tính các chỉ số tóm tắt trung bình.

    Args:
        csv_path : Đường dẫn file traffic_THx.csv
        scenario : Tên kịch bản

    Returns:
        Dictionary chứa các chỉ số trung bình trên 4 cạnh
    """
    rows = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    if not rows:
        return {"scenario": scenario, "error": "CSV rỗng"}

    # Tính trung bình từng chỉ số trên tất cả bước thời gian và 4 cạnh
    n = len(rows)
    avg_vehicles   = sum(float(r["vehicles"])   for r in rows) / n
    avg_speed      = sum(float(r["speed"])      for r in rows) / n
    avg_waiting    = sum(float(r["waiting"])    for r in rows) / n
    avg_halting    = sum(float(r["halting"])    for r in rows) / n
    avg_congestion = sum(float(r["congestion"]) for r in rows) / n

    # Tính đỉnh (max) để quan sát tình trạng xấu nhất
    max_waiting    = max(float(r["waiting"])    for r in rows)
    max_halting    = max(float(r["halting"])    for r in rows)
    max_congestion = max(float(r["congestion"]) for r in rows)

    return {
        "scenario":      scenario,
        "demand_vph":    _scenario_demand(scenario),
        "avg_vehicles":  round(avg_vehicles,   2),
        "avg_speed":     round(avg_speed,      3),
        "avg_waiting":   round(avg_waiting,    2),
        "avg_halting":   round(avg_halting,    2),
        "avg_congestion":round(avg_congestion, 4),
        "max_waiting":   round(max_waiting,    2),
        "max_halting":   int(max_halting),
        "max_congestion":round(max_congestion, 4),
        "total_rows":    n,
    }


# ─────────────────────────────────────────────────────────────────
# Hàm in bảng so sánh
# ─────────────────────────────────────────────────────────────────

def print_comparison_table(summaries: List[Dict]):
    """In bảng so sánh kết quả 6 thí nghiệm ra console."""
    print()
    print("=" * 95)
    print("  BẢNG SO SÁNH KẾT QUẢ 6 THÍ NGHIỆM – Báo cáo 2, Mục 5")
    print("=" * 95)
    print(f"  {'KBản':<6} {'Xe/h':>6} {'Xe(avg)':>9} "
          f"{'Speed(m/s)':>11} {'Wait(avg,s)':>12} {'Halt(avg)':>10} "
          f"{'CongIdx':>9} {'Wait(max)':>10} {'Status':>12}")
    print(f"  {'-'*90}")

    for s in summaries:
        if "error" in s:
            print(f"  {s['scenario']:<6}  [LỖI: {s['error']}]")
            continue

        # Phân loại mức độ ùn tắc dựa trên chỉ số tổng hợp
        c = s["avg_congestion"]
        if c < 0.2:
            status = "✓ Thông thoáng"
        elif c < 0.4:
            status = "~ Trung bình"
        elif c < 0.6:
            status = "! Đông đúc"
        else:
            status = "✗ Ùn tắc"

        print(
            f"  {s['scenario']:<6} {s['demand_vph']:>6} "
            f"{s['avg_vehicles']:>9.1f} {s['avg_speed']:>11.3f} "
            f"{s['avg_waiting']:>12.1f} {s['avg_halting']:>10.1f} "
            f"{s['avg_congestion']:>9.4f} {s['max_waiting']:>10.1f} "
            f"{status:>12}"
        )

    print(f"  {'='*90}")
    print()
    print("  Ghi chú:")
    print("  - Speed   : Tốc độ trung bình trên cạnh (m/s)")
    print("  - Wait    : Thời gian chờ tổng trên cạnh (giây)")
    print("  - CongIdx : Chỉ số ùn tắc tổng hợp [0..1]")
    print("              (Công thức: Báo cáo 2, Mục 10)")
    print()


# ─────────────────────────────────────────────────────────────────
# Hàm lưu bảng so sánh ra CSV
# ─────────────────────────────────────────────────────────────────

def save_comparison_csv(summaries: List[Dict]):
    """Lưu bảng so sánh ra output/comparison.csv."""
    out_file = OUTPUT_DIR / "comparison.csv"
    fieldnames = [
        "scenario", "demand_vph", "avg_vehicles", "avg_speed",
        "avg_waiting", "avg_halting", "avg_congestion",
        "max_waiting", "max_halting", "max_congestion", "total_rows"
    ]
    with open(out_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(s for s in summaries if "error" not in s)

    print(f"  Đã lưu bảng so sánh: {out_file}")
    return str(out_file)


# ─────────────────────────────────────────────────────────────────
# Hàm chính: Chạy batch
# ─────────────────────────────────────────────────────────────────

def run_experiments(
    scenarios: List[str] = ALL_SCENARIOS,
    use_gui:   bool = False,
    duration:  int  = 3600,
    report_step: int = 200,
) -> List[Dict]:
    """
    Chạy tuần tự các thí nghiệm và tổng hợp kết quả.

    Args:
        scenarios  : Danh sách kịch bản cần chạy
        use_gui    : Có mở SUMO-GUI không (chậm hơn nhiều)
        duration   : Số giây mô phỏng mỗi kịch bản
        report_step: In báo cáo console mỗi N bước

    Returns:
        Danh sách dictionary tóm tắt từng kịch bản
    """
    total = len(scenarios)
    summaries = []

    print()
    print("╔" + "═"*58 + "╗")
    print("║   SUMO TRAFFIC SIMULATION – Batch Experiment Runner   ║")
    print("║   Đề tài DATN: Điều hướng giao thông bằng ACO         ║")
    print("╚" + "═"*58 + "╝")
    print()
    print(f"  Số kịch bản: {total}")
    print(f"  Thời gian mỗi kịch bản: {duration}s")
    print(f"  SUMO-GUI: {'BẬT (chậm)' if use_gui else 'TẮT (nhanh)'}")
    print()

    wall_start = time.time()

    for i, scenario in enumerate(scenarios, 1):
        demand = _scenario_demand(scenario)
        print(f"\n[{i}/{total}] Bắt đầu {scenario} – {demand} xe/h/hướng")
        print(f"        {'─'*48}")

        t0 = time.time()
        try:
            csv_path = run_simulation(
                scenario    = scenario,
                use_gui     = use_gui,
                duration    = duration,
                report_step = report_step,
                output_dir  = OUTPUT_DIR,
            )
            elapsed = time.time() - t0
            print(f"\n  [{i}/{total}] {scenario} hoàn tất sau {elapsed:.0f}s wall-clock")

            # Tóm tắt kết quả
            summary = summarize_csv(csv_path, scenario)
            summaries.append(summary)

        except Exception as e:
            print(f"\n  [LỖI] Kịch bản {scenario}: {e}")
            summaries.append({"scenario": scenario, "error": str(e)})

    total_elapsed = time.time() - wall_start
    print(f"\n\n  Tất cả kịch bản hoàn tất sau {total_elapsed:.0f}s")

    # In và lưu bảng so sánh
    print_comparison_table(summaries)
    save_comparison_csv(summaries)

    return summaries


# ─────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Chạy batch 6 thí nghiệm SUMO (TH1–TH6)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ví dụ:
  python scripts/run_experiments.py
  python scripts/run_experiments.py --scenarios TH3 TH4 TH5
  python scripts/run_experiments.py --duration 1800
  python scripts/run_experiments.py --gui
        """
    )
    parser.add_argument(
        "--scenarios", nargs="+", default=ALL_SCENARIOS,
        choices=ALL_SCENARIOS, metavar="THx",
        help="Danh sách kịch bản cần chạy (mặc định: tất cả TH1-TH6)"
    )
    parser.add_argument(
        "--duration", type=int, default=3600,
        help="Số giây mô phỏng mỗi kịch bản (mặc định: 3600)"
    )
    parser.add_argument(
        "--gui", action="store_true",
        help="Bật SUMO-GUI (chậm hơn nhiều, chỉ dùng để quan sát)"
    )
    parser.add_argument(
        "--report-step", type=int, default=200,
        help="In báo cáo console mỗi N bước (mặc định: 200)"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_experiments(
        scenarios   = args.scenarios,
        use_gui     = args.gui,
        duration    = args.duration,
        report_step = args.report_step,
    )
