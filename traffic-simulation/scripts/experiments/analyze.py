#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, io
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
"""
analyze.py – Phân tích kết quả sau mô phỏng SUMO
==================================================
Script này phân tích hai nguồn dữ liệu:
  1. output/tripinfo_THx.xml  : SUMO xuất thông tin từng chuyến đi
  2. output/traffic_THx.csv   : Dữ liệu TraCI thu thập theo thời gian

Tính các chỉ số đánh giá theo Báo cáo 1, mục 8:
  - ATT  : Average Travel Time (thời gian di chuyển trung bình)
  - AWT  : Average Waiting Time (thời gian chờ trung bình)
  - ARL  : Average Route Length (độ dài tuyến trung bình)
  - timeLoss: Thời gian mất do ùn tắc so với đi với tốc độ tự do

In bảng kết quả so sánh 6 kịch bản.

Sử dụng:
    python scripts/analyze.py                    # phân tích tất cả kịch bản
    python scripts/analyze.py --scenario TH3     # chỉ phân tích TH3
    python scripts/analyze.py --plot             # vẽ biểu đồ (cần matplotlib)
"""

import csv
import os
import sys
import argparse
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional


# ─────────────────────────────────────────────────────────────────
# Cấu hình đường dẫn
# ─────────────────────────────────────────────────────────────────

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR  = PROJECT_DIR / "output"

ALL_SCENARIOS = ["TH1", "TH2", "TH3", "TH4", "TH5", "TH6"]

DEMAND_MAP = {
    "TH1": 200, "TH2": 400, "TH3": 600,
    "TH4": 800, "TH5": 1000, "TH6": 1200,
}


# ─────────────────────────────────────────────────────────────────
# Phân tích tripinfo.xml
# ─────────────────────────────────────────────────────────────────

def parse_tripinfo(xml_path: Path) -> Optional[Dict]:
    """
    Đọc file tripinfo.xml và tính các chỉ số trung bình.

    Các trường được SUMO định nghĩa trong TripInfo output:
      - duration      : tổng thời gian từ depart đến arrive (s)
      - routeLength   : chiều dài tuyến đường đã đi (m)
      - waitingTime   : tổng thời gian chờ trong chuyến đi (s)
      - timeLoss      : thời gian mất so với tốc độ tự do (s)
      - waitingCount  : số lần phải dừng chờ

    Args:
        xml_path: Đường dẫn file tripinfo_THx.xml

    Returns:
        Dictionary chứa các chỉ số tóm tắt, hoặc None nếu lỗi
    """
    if not xml_path.exists():
        return None

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except ET.ParseError as e:
        print(f"  [LỖI] Không đọc được {xml_path}: {e}")
        return None

    trips = root.findall("tripinfo")
    if not trips:
        return None

    n = len(trips)
    total_duration    = 0.0
    total_route_len   = 0.0
    total_waiting     = 0.0
    total_time_loss   = 0.0
    total_wait_count  = 0

    for trip in trips:
        total_duration   += float(trip.get("duration",    0))
        total_route_len  += float(trip.get("routeLength", 0))
        total_waiting    += float(trip.get("waitingTime", 0))
        total_time_loss  += float(trip.get("timeLoss",    0))
        total_wait_count += int(  trip.get("waitingCount", 0))

    return {
        "n_vehicles":      n,
        "att":             round(total_duration   / n, 2),   # ATT
        "arl":             round(total_route_len  / n, 2),   # ARL
        "awt":             round(total_waiting    / n, 2),   # AWT
        "avg_time_loss":   round(total_time_loss  / n, 2),
        "avg_wait_count":  round(total_wait_count / n, 2),
        "total_time_loss": round(total_time_loss,      2),
    }


# ─────────────────────────────────────────────────────────────────
# Phân tích traffic.csv (dữ liệu TraCI)
# ─────────────────────────────────────────────────────────────────

def analyze_traffic_csv(csv_path: Path) -> Optional[Dict]:
    """
    Đọc traffic_THx.csv và tính thống kê theo từng cạnh và toàn bộ.

    Args:
        csv_path: Đường dẫn file traffic_THx.csv

    Returns:
        Dictionary thống kê, hoặc None nếu file không tồn tại
    """
    if not csv_path.exists():
        return None

    rows = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    if not rows:
        return None

    # Tổng hợp theo từng cạnh
    edge_stats = {}
    for row in rows:
        edge = row["edge"]
        if edge not in edge_stats:
            edge_stats[edge] = {
                "vehicles": [], "speed": [], "waiting": [],
                "halting": [], "congestion": []
            }
        edge_stats[edge]["vehicles"].append(float(row["vehicles"]))
        edge_stats[edge]["speed"].append(float(row["speed"]))
        edge_stats[edge]["waiting"].append(float(row["waiting"]))
        edge_stats[edge]["halting"].append(float(row["halting"]))
        edge_stats[edge]["congestion"].append(float(row["congestion"]))

    # Tính trung bình và max từng cạnh
    per_edge = {}
    for edge, data in edge_stats.items():
        n = len(data["vehicles"])
        per_edge[edge] = {
            "avg_vehicles":   round(sum(data["vehicles"])   / n, 2),
            "avg_speed":      round(sum(data["speed"])      / n, 3),
            "avg_waiting":    round(sum(data["waiting"])    / n, 2),
            "avg_halting":    round(sum(data["halting"])    / n, 2),
            "avg_congestion": round(sum(data["congestion"]) / n, 4),
            "max_waiting":    round(max(data["waiting"]),       2),
            "max_halting":    int(max(data["halting"])),
            "max_congestion": round(max(data["congestion"]),    4),
            "n_steps":        n,
        }

    # Tổng hợp trên tất cả cạnh
    all_speed      = [float(r["speed"])      for r in rows]
    all_waiting    = [float(r["waiting"])    for r in rows]
    all_congestion = [float(r["congestion"]) for r in rows]
    n_all = len(rows)

    overall = {
        "avg_speed":        round(sum(all_speed)      / n_all, 3),
        "avg_waiting":      round(sum(all_waiting)    / n_all, 2),
        "avg_congestion":   round(sum(all_congestion) / n_all, 4),
        "max_waiting":      round(max(all_waiting),       2),
        "max_congestion":   round(max(all_congestion),    4),
    }

    return {"per_edge": per_edge, "overall": overall}


# ─────────────────────────────────────────────────────────────────
# In báo cáo chi tiết một kịch bản
# ─────────────────────────────────────────────────────────────────

def print_scenario_report(scenario: str, trip_data: Dict, traci_data: Dict):
    """In báo cáo chi tiết cho một kịch bản."""
    demand = DEMAND_MAP.get(scenario, 0)

    print(f"\n{'─'*60}")
    print(f"  KẾT QUẢ {scenario} – {demand} xe/h/hướng")
    print(f"{'─'*60}")

    # ── Thông tin từ tripinfo ──
    if trip_data:
        print(f"\n  [Tripinfo – Báo cáo 1, Mục 8]")
        print(f"  Số phương tiện hoàn thành chuyến đi : {trip_data['n_vehicles']}")
        print(f"  ATT – Thời gian di chuyển trung bình: {trip_data['att']:.2f}s")
        print(f"  AWT – Thời gian chờ trung bình       : {trip_data['awt']:.2f}s")
        print(f"  ARL – Độ dài tuyến trung bình        : {trip_data['arl']:.1f}m")
        print(f"  Time Loss trung bình                 : {trip_data['avg_time_loss']:.2f}s")
        print(f"  Số lần dừng chờ trung bình           : {trip_data['avg_wait_count']:.1f}")
    else:
        print(f"\n  [!] Không tìm thấy tripinfo_{scenario}.xml")

    # ── Thông tin từ TraCI CSV ──
    if traci_data:
        print(f"\n  [TraCI CSV – Báo cáo 2, Mục 9]")
        print(f"\n  {'Cạnh':<6} {'Xe(avg)':>9} {'Speed(m/s)':>11} "
              f"{'Wait(avg)':>10} {'Halt(avg)':>10} {'Cong':>8} {'Status':>12}")
        print(f"  {'-'*68}")

        for edge_id in ["N2C", "S2C", "E2C", "W2C"]:
            if edge_id in traci_data["per_edge"]:
                d = traci_data["per_edge"][edge_id]
                c = d["avg_congestion"]
                status = "✓ OK" if c < 0.2 else ("~ Vừa" if c < 0.4 else
                         ("! Đông" if c < 0.6 else "✗ Tắc"))
                print(
                    f"  {edge_id:<6} {d['avg_vehicles']:>9.1f} "
                    f"{d['avg_speed']:>11.3f} {d['avg_waiting']:>10.1f} "
                    f"{d['avg_halting']:>10.1f} {c:>8.4f} {status:>12}"
                )

        ov = traci_data["overall"]
        print(f"\n  Tổng hợp: AvgSpeed={ov['avg_speed']:.3f}m/s | "
              f"AvgWait={ov['avg_waiting']:.1f}s | "
              f"CongIdx={ov['avg_congestion']:.4f} | "
              f"MaxWait={ov['max_waiting']:.1f}s")
    else:
        print(f"\n  [!] Không tìm thấy traffic_{scenario}.csv")


# ─────────────────────────────────────────────────────────────────
# In bảng tổng hợp so sánh các kịch bản
# ─────────────────────────────────────────────────────────────────

def print_master_table(results: List[Dict]):
    """In bảng so sánh tất cả kịch bản đã phân tích."""
    print(f"\n\n{'═'*100}")
    print(f"  BẢNG TỔNG HỢP SO SÁNH 6 THÍ NGHIỆM")
    print(f"  (Chỉ số đánh giá – Báo cáo 1, Mục 8 + Báo cáo 2, Mục 10)")
    print(f"{'═'*100}")
    print(
        f"  {'Kịch bản':<10} {'Xe/h':>6} {'N hoàn thành':>13} "
        f"{'ATT(s)':>8} {'AWT(s)':>8} {'TimeLoss':>9} "
        f"{'AvgSpeed':>9} {'CongIdx':>9} {'Đánh giá':>14}"
    )
    print(f"  {'─'*96}")

    for r in results:
        scenario = r["scenario"]
        demand   = DEMAND_MAP.get(scenario, 0)
        trip     = r.get("trip_data")
        traci    = r.get("traci_data")

        att       = f"{trip['att']:.1f}"      if trip  else "–"
        awt       = f"{trip['awt']:.1f}"      if trip  else "–"
        timeloss  = f"{trip['avg_time_loss']:.1f}" if trip else "–"
        n_veh     = str(trip['n_vehicles'])   if trip  else "–"
        avg_speed = f"{traci['overall']['avg_speed']:.3f}" if traci else "–"
        cong_idx  = f"{traci['overall']['avg_congestion']:.4f}" if traci else "–"

        # Đánh giá tổng thể
        if traci:
            c = traci["overall"]["avg_congestion"]
            rating = "✓✓ Thông thoáng" if c < 0.15 else (
                     "✓  Tốt"          if c < 0.25 else (
                     "~  Trung bình"   if c < 0.40 else (
                     "!  Đông đúc"     if c < 0.60 else
                     "✗  Ùn tắc nặng")))
        else:
            rating = "Không có data"

        print(
            f"  {scenario:<10} {demand:>6} {n_veh:>13} "
            f"{att:>8} {awt:>8} {timeloss:>9} "
            f"{avg_speed:>9} {cong_idx:>9} {rating:>14}"
        )

    print(f"  {'═'*96}")
    print()
    print("  Ghi chú:")
    print("  - ATT      : Average Travel Time = thời gian di chuyển tb (giây)")
    print("  - AWT      : Average Waiting Time = thời gian chờ tb (giây)")
    print("  - TimeLoss : Thời gian mất do tắc đường tb (giây)")
    print("  - CongIdx  : Chỉ số ùn tắc tổng hợp [0..1]")
    print("               0.0 = hoàn toàn thông, 1.0 = bão hòa")
    print()


# ─────────────────────────────────────────────────────────────────
# Vẽ biểu đồ (tùy chọn, cần matplotlib)
# ─────────────────────────────────────────────────────────────────

def plot_results(results: List[Dict]):
    """Vẽ biểu đồ so sánh 6 kịch bản (cần matplotlib)."""
    try:
        import matplotlib.pyplot as plt
        import matplotlib.ticker as ticker
    except ImportError:
        print("  [!] matplotlib chưa được cài. Chạy: pip install matplotlib")
        return

    valid = [r for r in results if r.get("traci_data")]
    if not valid:
        print("  [!] Không có dữ liệu để vẽ biểu đồ")
        return

    scenarios  = [r["scenario"] for r in valid]
    demands    = [DEMAND_MAP.get(r["scenario"], 0) for r in valid]
    avg_speed  = [r["traci_data"]["overall"]["avg_speed"]      for r in valid]
    avg_wait   = [r["traci_data"]["overall"]["avg_waiting"]     for r in valid]
    cong_idx   = [r["traci_data"]["overall"]["avg_congestion"]  for r in valid]
    att_vals   = [r["trip_data"]["att"]      if r.get("trip_data") else 0 for r in valid]
    awt_vals   = [r["trip_data"]["awt"]      if r.get("trip_data") else 0 for r in valid]
    loss_vals  = [r["trip_data"]["avg_time_loss"] if r.get("trip_data") else 0 for r in valid]

    colors = ["#2ecc71", "#27ae60", "#f39c12", "#e67e22", "#e74c3c", "#8e44ad"][:len(valid)]

    fig, axes = plt.subplots(2, 3, figsize=(16, 10))
    fig.suptitle(
        "Phân tích Mô phỏng SUMO – Đề tài DATN\n"
        "Ảnh hưởng của Lưu lượng Giao thông đến Hiệu suất Nút Giao",
        fontsize=14, fontweight="bold", y=0.98
    )

    def bar_plot(ax, values, title, ylabel, xlabel="Kịch bản", fmt=".1f"):
        bars = ax.bar(scenarios, values, color=colors, edgecolor="black", linewidth=0.5)
        ax.set_title(title, fontsize=11, fontweight="bold", pad=8)
        ax.set_xlabel(xlabel, fontsize=9)
        ax.set_ylabel(ylabel, fontsize=9)
        ax.set_ylim(0, max(values) * 1.15 if values else 1)
        for bar, val in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(values)*0.01,
                    f"{val:{fmt}}", ha="center", va="bottom", fontsize=8)
        # Thêm nhãn lưu lượng trên trục x
        ax.set_xticklabels([f"{s}\n({DEMAND_MAP.get(s,0)} xe/h)" for s in scenarios],
                           fontsize=8)
        ax.grid(axis="y", alpha=0.3)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    bar_plot(axes[0, 0], avg_speed,  "Tốc độ Trung bình (m/s)",
             "Tốc độ (m/s)", fmt=".3f")
    bar_plot(axes[0, 1], avg_wait,   "Thời gian Chờ Trung bình (s)",
             "Thời gian chờ (s)")
    bar_plot(axes[0, 2], cong_idx,   "Chỉ số Ùn tắc Tổng hợp [0–1]",
             "Congestion Index", fmt=".4f")
    bar_plot(axes[1, 0], att_vals,   "ATT – T.g. Di chuyển Trung bình (s)",
             "ATT (giây)")
    bar_plot(axes[1, 1], awt_vals,   "AWT – T.g. Chờ Trung bình (s)",
             "AWT (giây)")
    bar_plot(axes[1, 2], loss_vals,  "TimeLoss Trung bình (s)",
             "TimeLoss (giây)")

    plt.tight_layout(rect=[0, 0, 1, 0.95])

    plot_file = OUTPUT_DIR / "analysis_plot.png"
    plt.savefig(plot_file, dpi=150, bbox_inches="tight")
    plt.show()
    print(f"\n  Đã lưu biểu đồ: {plot_file}")


# ─────────────────────────────────────────────────────────────────
# Hàm chính
# ─────────────────────────────────────────────────────────────────

def analyze(scenarios: List[str], do_plot: bool = False) -> List[Dict]:
    """
    Phân tích kết quả từ các kịch bản đã chạy.

    Args:
        scenarios: Danh sách kịch bản cần phân tích
        do_plot  : Có vẽ biểu đồ không

    Returns:
        Danh sách kết quả phân tích
    """
    print()
    print("╔" + "═"*54 + "╗")
    print("║   PHÂN TÍCH KẾT QUẢ MÔ PHỎNG SUMO                  ║")
    print("╚" + "═"*54 + "╝")
    print(f"\n  Thư mục output: {OUTPUT_DIR}")

    results = []

    for scenario in scenarios:
        tripinfo_file = OUTPUT_DIR / f"tripinfo_{scenario}.xml"
        csv_file      = OUTPUT_DIR / f"traffic_{scenario}.csv"

        trip_data  = parse_tripinfo(tripinfo_file)
        traci_data = analyze_traffic_csv(csv_file)

        result = {
            "scenario":   scenario,
            "trip_data":  trip_data,
            "traci_data": traci_data,
        }
        results.append(result)

        # In báo cáo chi tiết
        print_scenario_report(scenario, trip_data, traci_data)

    # In bảng tổng hợp
    print_master_table(results)

    # Lưu kết quả phân tích ra CSV
    _save_analysis_csv(results)

    # Vẽ biểu đồ nếu được yêu cầu
    if do_plot:
        plot_results(results)

    return results


def _save_analysis_csv(results: List[Dict]):
    """Lưu kết quả phân tích ra file analysis_results.csv."""
    out_file = OUTPUT_DIR / "analysis_results.csv"
    fieldnames = [
        "scenario", "demand_vph", "n_vehicles",
        "att", "awt", "arl", "avg_time_loss", "avg_wait_count",
        "avg_speed_traci", "avg_waiting_traci",
        "avg_congestion", "max_waiting", "max_congestion",
    ]
    with open(out_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in results:
            row = {"scenario": r["scenario"], "demand_vph": DEMAND_MAP.get(r["scenario"], 0)}
            if r["trip_data"]:
                row.update({
                    "n_vehicles":    r["trip_data"]["n_vehicles"],
                    "att":           r["trip_data"]["att"],
                    "awt":           r["trip_data"]["awt"],
                    "arl":           r["trip_data"]["arl"],
                    "avg_time_loss": r["trip_data"]["avg_time_loss"],
                    "avg_wait_count":r["trip_data"]["avg_wait_count"],
                })
            if r["traci_data"]:
                ov = r["traci_data"]["overall"]
                row.update({
                    "avg_speed_traci":   ov["avg_speed"],
                    "avg_waiting_traci": ov["avg_waiting"],
                    "avg_congestion":    ov["avg_congestion"],
                    "max_waiting":       ov["max_waiting"],
                    "max_congestion":    ov["max_congestion"],
                })
            writer.writerow(row)
    print(f"  Đã lưu kết quả phân tích: {out_file}")


# ─────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Phân tích kết quả mô phỏng SUMO",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ví dụ:
  python scripts/analyze.py
  python scripts/analyze.py --scenario TH3
  python scripts/analyze.py --plot
        """
    )
    parser.add_argument(
        "--scenario", type=str, default=None,
        choices=ALL_SCENARIOS, metavar="THx",
        help="Chỉ phân tích một kịch bản (mặc định: tất cả)"
    )
    parser.add_argument(
        "--plot", action="store_true",
        help="Vẽ biểu đồ so sánh (cần matplotlib: pip install matplotlib)"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    scenarios = [args.scenario] if args.scenario else ALL_SCENARIOS
    analyze(scenarios=scenarios, do_plot=args.plot)
