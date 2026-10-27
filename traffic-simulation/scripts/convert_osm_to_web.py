#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
convert_osm_to_web.py – Trích xuất dữ liệu mạng SUMO net.xml thành JSON tọa độ GPS (WGS84)
cho ứng dụng mô phỏng trên Google Maps.
"""

import os
import sys
import io
import math
import json
import xml.etree.ElementTree as ET
from pathlib import Path

# Fix console encoding
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

PROJECT_DIR = Path(__file__).resolve().parent.parent
NET_FILE = PROJECT_DIR / "osm" / "map2.net.xml"
OUTPUT_DIR = PROJECT_DIR / "web" / "data"
OUTPUT_JSON = OUTPUT_DIR / "osm_network.json"

def utm48_to_latlon(easting: float, northing: float) -> tuple:
    """
    Chuyển đổi tọa độ UTM Zone 48N (WGS84) sang Vĩ độ (Lat) và Kinh độ (Lon) chuẩn WGS84.
    Độ chính xác milimet.
    """
    a = 6378137.0
    f = 1.0 / 298.257223563
    b = a * (1.0 - f)
    e = math.sqrt(1.0 - (b / a) ** 2)
    ep2 = (e * a / b) ** 2
    k0 = 0.9996

    x = easting - 500000.0  # Bỏ 500km false easting
    y = northing

    M = y / k0
    mu = M / (a * (1.0 - (e**2)/4.0 - 3.0*(e**4)/64.0 - 5.0*(e**6)/256.0))

    e1 = (1.0 - math.sqrt(1.0 - e**2)) / (1.0 + math.sqrt(1.0 - e**2))
    J1 = (3.0*e1/2.0 - 27.0*(e1**3)/32.0)
    J2 = (21.0*(e1**2)/16.0 - 55.0*(e1**4)/32.0)
    J3 = (151.0*(e1**3)/96.0)
    J4 = (1097.0*(e1**4)/512.0)

    fp = mu + J1*math.sin(2.0*mu) + J2*math.sin(4.0*mu) + J3*math.sin(6.0*mu) + J4*math.sin(8.0*mu)

    C1 = ep2 * (math.cos(fp)**2)
    T1 = math.tan(fp)**2
    R1 = a * (1.0 - e**2) / ((1.0 - (e * math.sin(fp))**2)**1.5)
    N1 = a / math.sqrt(1.0 - (e * math.sin(fp))**2)

    D = x / (N1 * k0)

    lat = fp - (N1 * math.tan(fp) / R1) * (
        D**2/2.0 - (5.0 + 3.0*T1 + 10.0*C1 - 4.0*C1**2 - 9.0*ep2)*(D**4)/24.0 +
        (61.0 + 90.0*T1 + 298.0*C1 + 45.0*T1**2 - 252.0*ep2 - 3.0*C1**2)*(D**6)/720.0
    )
    lon0 = math.radians(105.0) # Kinh tuyến trục Zone 48
    lon = lon0 + (
        D - (1.0 + 2.0*T1 + C1)*(D**3)/6.0 +
        (5.0 - 2.0*C1 + 28.0*T1 - 3.0*C1**2 + 8.0*ep2 + 24.0*T1**2)*(D**5)/120.0
    ) / math.cos(fp)

    return round(math.degrees(lat), 6), round(math.degrees(lon), 6)

def convert_net_to_json():
    print(f"[*] Đang đọc file: {NET_FILE}")
    if not NET_FILE.exists():
        print(f"[!] Không tìm thấy file: {NET_FILE}")
        return

    tree = ET.parse(str(NET_FILE))
    root = tree.getroot()

    # SUMO netOffset: netOffset="-584137.96,-2321015.55"
    # To get UTM: x_utm = x - (-584137.96) = x + 584137.96
    dx = 584137.96
    dy = 2321015.55

    # 1. Trích xuất Junctions (Nút)
    junctions = {}
    for j in root.findall('junction'):
        jtype = j.get('type', '')
        if jtype == 'internal':
            continue
        jid = j.get('id')
        x = float(j.get('x', 0)) + dx
        y = float(j.get('y', 0)) + dy
        lat, lng = utm48_to_latlon(x, y)
        
        # Xác định loại nút trực quan
        inc_lanes = j.get('incLanes', '').split()
        deg = len(inc_lanes)
        if deg <= 3:
            node_type = "INTERSECTION_3" # Ngã ba
        elif deg <= 4:
            node_type = "INTERSECTION_4" # Ngã tư
        elif deg >= 5:
            node_type = "INTERSECTION_5" # Ngã năm / nút phức tạp
        else:
            node_type = "INTERSECTION_4"

        junctions[jid] = {
            "id": jid,
            "name": f"Nút giao {jid}",
            "lat": lat,
            "lng": lng,
            "type": node_type,
            "has_signals": (jtype == 'traffic_light'),
            "degree": deg
        }

    # 2. Trích xuất Edges (Cạnh/Đường)
    edges = {}
    for e in root.findall('edge'):
        eid = e.get('id', '')
        if eid.startswith(':'):
            continue
        from_j = e.get('from')
        to_j = e.get('to')
        if from_j not in junctions or to_j not in junctions:
            continue

        lanes = e.findall('lane')
        if not lanes:
            continue

        lane0 = lanes[0]
        length = float(lane0.get('length', 10.0))
        speed = float(lane0.get('speed', 13.89)) # m/s
        speed_kmh = round(speed * 3.6, 1)

        # Trích xuất polyline tọa độ uốn lượn chính xác
        shape_str = lane0.get('shape', '')
        coords = []
        for pair in shape_str.split():
            if ',' in pair:
                px, py = pair.split(',')
                plat, plng = utm48_to_latlon(float(px) + dx, float(py) + dy)
                coords.append([plat, plng])

        if not coords:
            coords = [
                [junctions[from_j]["lat"], junctions[from_j]["lng"]],
                [junctions[to_j]["lat"], junctions[to_j]["lng"]]
            ]

        # Dung lượng ước tính theo chiều dài và số làn
        num_lanes = len(lanes)
        # 1 xe chiếm ~8m khi dừng, lưu thông thông suốt ~25m/xe => ~40 xe/km/làn
        capacity = max(5, int(length * num_lanes * 0.04))

        edges[eid] = {
            "id": eid,
            "from": from_j,
            "to": to_j,
            "length": round(length, 1),
            "speed_limit_kmh": speed_kmh,
            "lanes": num_lanes,
            "capacity": capacity,
            "free_flow_time": round(length / max(1.0, speed), 1),
            "points": coords
        }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "metadata": {
            "source": "SUMO map2.net.xml / OpenStreetMap Hanoi",
            "bounds": {
                "minlat": 20.9604, "maxlat": 21.0460,
                "minlng": 105.8036, "maxlng": 105.8479
            },
            "node_count": len(junctions),
            "edge_count": len(edges)
        },
        "junctions": junctions,
        "edges": edges
    }

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"[+] Đã xuất thành công: {OUTPUT_JSON}")
    print(f"    - Nút (Junctions): {len(junctions)}")
    print(f"    - Tuyến đường (Edges): {len(edges)}")

if __name__ == "__main__":
    convert_net_to_json()
