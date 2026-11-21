from pathlib import Path
from collections import Counter
import csv
import gzip
import json
import math
import xml.etree.ElementTree as ET

from docx import Document
from docx.shared import Cm, Pt, RGBColor
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from reportlab.graphics.shapes import Drawing, String
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics import renderSVG
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'report'
QA = OUT / 'qa'
QA.mkdir(parents=True, exist_ok=True)


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


groups = [
    ('B1', 'Không có sự cố', 'full', {51, 52, 53}),
    ('B2', 'Một tai nạn cố định', 'incident', {51, 52, 53}),
    ('B3', 'Ba tai nạn cố định', 'multi-incident/verification', {51}),
    ('B4', 'Tai nạn động và 13.169 xe', 'regional-incident/verification', {51}),
    ('B5', 'Tai nạn động và 8.779 xe', 'regional-incident-reduced/verification', {51}),
]
data = {}
checks = {}
for code, title, directory, seeds in groups:
    runs = {}
    for summary in sorted((ROOT / directory).glob('*/summary.csv')):
        for m in read_csv(summary):
            if m['policy'] not in ('original', 'adaptive') or m['complete'] != 'True':
                continue
            key = (int(m['seed']), m['policy'])
            assert key not in runs, (code, key)
            folder = summary.parent / m['policy']
            decisions = read_csv(folder / 'decisions.csv')
            requirements = {r['vehicle']: (r['class'], r['origin'], r['destination']) for r in decisions}
            assert len(requirements) == len(decisions) == int(m['requested'])
            trips, times = {}, []
            with gzip.open(folder / 'tripinfo.xml.gz', 'rb') as f:
                for _, node in ET.iterparse(f, events=('end',)):
                    if node.tag != 'tripinfo':
                        continue
                    a = node.attrib
                    assert float(a['arrival']) >= 0 and float(a['depart']) >= 0 and not a['vaporized']
                    scheduled = round(float(a['depart']) - float(a['departDelay']), 2)
                    assert a['id'] not in trips
                    trips[a['id']] = (scheduled, a['vType'], a['speedFactor'])
                    times.append(float(a['arrival']) - scheduled)
                    node.clear()
            assert set(trips) == set(requirements)
            times.sort()
            total = sum(times)
            assert abs(total - float(m['total_s'])) < .01
            assert abs(total / len(times) - float(m['mean_s'])) < .00051
            assert times[math.ceil(.95 * len(times)) - 1] == float(m['p95_s'])
            for field in ('requested', 'considered', 'finished_in_sumo', 'arrived', 'loaded'):
                assert int(m[field]) == len(times)
            for field in ('unfinished', 'ended_by_teleport', 'removed_other', 'rejected', 'colliding_vehicle_events'):
                assert int(m[field]) == 0, (code, key, field)
            jumps = read_csv(folder / 'teleports.csv')
            jumped = {r['vehicle'] for r in jumps}
            assert len(jumps) == int(m['teleports'])
            assert len(jumped) == int(m['teleported_vehicles'])
            assert len(times) - len(jumped) == int(m['arrived_without_teleport'])
            events = read_csv(folder / 'incidents.csv') if (folder / 'incidents.csv').exists() else []
            plan = read_csv(folder / 'incident-plan.csv') if (folder / 'incident-plan.csv').exists() else []
            m.update(source=str(summary.relative_to(ROOT)), raw_count=len(times), raw_total_s=total)
            runs[key] = m
            checks[code, key] = (requirements, trips, events, plan)
    assert set(runs) == {(s, p) for s in seeds for p in ('original', 'adaptive')}, code
    for seed in sorted(seeds):
        assert checks[code, (seed, 'original')] == checks[code, (seed, 'adaptive')], (code, seed)
    data[code] = runs

for policy in ('original', 'adaptive'):
    assert checks['B4', (51, policy)][2:] == checks['B5', (51, policy)][2:]
assert len(checks['B4', (51, 'original')][3]) == 13
for seed in (51, 52, 53):
    assert checks['B1', (seed, 'original')][:2] == checks['B2', (seed, 'original')][:2]


def pooled(code, policy):
    rows = [r for (_, p), r in data[code].items() if p == policy]
    count = sum(int(r['requested']) for r in rows)
    total = sum(r['raw_total_s'] for r in rows)
    return total / count / 60, total


def num(value, digits=2):
    return f'{value:,.{digits}f}'.replace(',', '_').replace('.', ',').replace('_', '.')


def gain(code, seed=None):
    if seed is None:
        a, b = (pooled(code, p)[1] for p in ('original', 'adaptive'))
    else:
        a, b = (float(data[code][seed, p]['total_s']) for p in ('original', 'adaptive'))
    return 100 * (1 - b / a)


manifest = {code: list(runs.values()) for code, runs in data.items()}
(QA / 'verified_results.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
print('PASS 18 complete runs and 9 matched pairs; raw totals, mean, P95, demand, vehicle parameters and event logs verified')
print('Routing gains', {code: round(gain(code), 4) for code in data})

# A standard grouped bar chart compares the two demand levels under one incident schedule.
pdfmetrics.registerFont(TTFont('Arial', r'C:\Windows\Fonts\arial.ttf'))
drawing = Drawing(550, 280)
chart = VerticalBarChart()
chart.x, chart.y, chart.width, chart.height = 65, 48, 440, 180
chart.data = [tuple(pooled(code, p)[0] for code in ('B5', 'B4')) for p in ('original', 'adaptive')]
chart.categoryAxis.categoryNames = ['8.779 xe', '13.169 xe']
chart.categoryAxis.labels.fontName = 'Arial'
chart.categoryAxis.labels.fontSize = 11
chart.valueAxis.valueMin, chart.valueAxis.valueMax, chart.valueAxis.valueStep = 0, 30, 5
chart.valueAxis.labels.fontName = 'Arial'
chart.valueAxis.labels.fontSize = 10
chart.valueAxis.visibleGrid = True
chart.valueAxis.gridStrokeColor = colors.HexColor('#dddddd')
chart.bars[0].fillColor = colors.HexColor('#707983')
chart.bars[1].fillColor = colors.HexColor('#1d5576')
chart.bars.strokeColor = None
chart.groupSpacing, chart.barSpacing = 30, 6
chart.barLabelFormat = lambda v: num(v)
chart.barLabels.fontName = 'Arial'
chart.barLabels.fontSize = 10
chart.barLabels.nudge = 6
drawing.add(chart)
drawing.add(String(65, 253, 'Thời gian trung bình mỗi xe theo mức nhu cầu', fontName='Arial', fontSize=13))
drawing.add(String(11, 130, 'Phút', fontName='Arial', fontSize=10))
drawing.add(String(110, 10, '■ Giữ tuyến gốc', fontName='Arial', fontSize=11, fillColor=colors.HexColor('#707983')))
drawing.add(String(315, 10, '■ Adaptive', fontName='Arial', fontSize=11, fillColor=colors.HexColor('#1d5576')))
renderSVG.drawToFile(drawing, str(QA / 'demand_comparison.svg'))

doc = Document()
sec = doc.sections[0]
sec.page_width, sec.page_height = Cm(21), Cm(29.7)
sec.top_margin, sec.bottom_margin = Cm(1.9), Cm(1.8)
sec.left_margin, sec.right_margin = Cm(2.3), Cm(2.0)
sec.footer_distance = Cm(.8)
for name, size in [('Normal', 12), ('Title', 23), ('Subtitle', 12), ('Heading 1', 16), ('Heading 2', 13), ('Caption', 10)]:
    style = doc.styles[name]
    style.font.name = 'Times New Roman'
    style.font.size = Pt(size)
    style.font.color.rgb = RGBColor(0, 0, 0)
    style._element.get_or_add_rPr().get_or_add_rFonts().set(qn('w:eastAsia'), 'Times New Roman')
    for fonts in style._element.xpath('.//w:rFonts'):
        for attr in ('asciiTheme', 'hAnsiTheme', 'eastAsiaTheme', 'cstheme'):
            fonts.attrib.pop(qn('w:' + attr), None)
    for border in style._element.xpath('.//w:pBdr'):
        border.getparent().remove(border)
    pf = style.paragraph_format
    pf.space_after = Pt(6)
    pf.line_spacing = 1.1
doc.styles['Normal'].paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
doc.styles['Title'].paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
doc.styles['Subtitle'].paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
for name in ('Heading 1', 'Heading 2'):
    doc.styles[name].paragraph_format.space_before = Pt(9)
    doc.styles[name].paragraph_format.keep_with_next = True
code_style = doc.styles.add_style('Commands', 1)
code_style.font.name, code_style.font.size = 'Consolas', Pt(9)
code_style.paragraph_format.space_after = Pt(3)
code_style.paragraph_format.line_spacing = 1.0
footer = sec.footer.paragraphs[0]
footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
footer.add_run('Trang ').font.size = Pt(10)
field = OxmlElement('w:fldSimple')
field.set(qn('w:instr'), 'PAGE')
footer._p.append(field)
doc.core_properties.title = 'Báo cáo thực nghiệm điều phối giao thông Bologna bằng ACO có xét giao thông'
doc.core_properties.subject = 'So sánh các mức nhu cầu và mô hình tai nạn trong SUMO'
doc.core_properties.author = ''


def p(text, style=None):
    return doc.add_paragraph(text, style)


def h(text, level=1):
    return doc.add_heading(text, level)


def page(title):
    doc.add_page_break()
    h(title)


def link(paragraph, label, target):
    if not target.startswith('https://'):
        assert (OUT / target).resolve().is_file(), target
    rel = paragraph.part.relate_to(target, RT.HYPERLINK, is_external=True)
    elem = OxmlElement('w:hyperlink')
    elem.set(qn('r:id'), rel)
    run = OxmlElement('w:r')
    props = OxmlElement('w:rPr')
    color = OxmlElement('w:color')
    color.set(qn('w:val'), '145578')
    props.append(color)
    run.append(props)
    text = OxmlElement('w:t')
    text.text = label
    run.append(text)
    elem.append(run)
    paragraph._p.append(elem)


def table(headers, rows, widths, font_size=10.5):
    tab = doc.add_table(rows=1, cols=len(headers))
    tab.alignment, tab.autofit = WD_TABLE_ALIGNMENT.CENTER, False
    for col, width in zip(tab.columns, widths):
        col.width = Cm(width)
    pr = tab._tbl.tblPr
    borders = OxmlElement('w:tblBorders')
    for side in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
        border = OxmlElement('w:' + side)
        for key, value in [('val', 'single'), ('sz', '4'), ('color', 'D9D9D9')]:
            border.set(qn('w:' + key), value)
        borders.append(border)
    pr.append(borders)
    for index, record in enumerate([headers, *rows]):
        row = tab.rows[0] if index == 0 else tab.add_row()
        rowpr = row._tr.get_or_add_trPr()
        rowpr.append(OxmlElement('w:cantSplit'))
        if index == 0:
            rowpr.append(OxmlElement('w:tblHeader'))
        for j, (cell, value) in enumerate(zip(row.cells, record)):
            cell.width = Cm(widths[j])
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            tcpr = cell._tc.get_or_add_tcPr()
            shade = OxmlElement('w:shd')
            shade.set(qn('w:fill'), 'DCE6EE' if index == 0 else ('F5F7F9' if index % 2 == 0 else 'FFFFFF'))
            tcpr.append(shade)
            margins = OxmlElement('w:tcMar')
            for side in ('top', 'left', 'bottom', 'right'):
                margin = OxmlElement('w:' + side)
                margin.set(qn('w:w'), '75')
                margin.set(qn('w:type'), 'dxa')
                margins.append(margin)
            tcpr.append(margins)
            para = cell.paragraphs[0]
            para.alignment = WD_ALIGN_PARAGRAPH.LEFT if j == 0 else WD_ALIGN_PARAGRAPH.CENTER
            para.paragraph_format.space_before = Pt(1)
            para.paragraph_format.space_after = Pt(1)
            para.paragraph_format.line_spacing = 1.0
            run = para.add_run(str(value))
            run.font.size, run.bold = Pt(font_size), index == 0
    p('') .paragraph_format.space_after = Pt(0)
    return tab


p('BÁO CÁO THỰC NGHIỆM\nĐIỀU PHỐI GIAO THÔNG BOLOGNA\nBẰNG ACO CÓ XÉT GIAO THÔNG', 'Title')
p('Mô phỏng SUMO với nhu cầu gốc và nhu cầu tăng cùng các kịch bản tai nạn', 'Subtitle')
p('Ngày tổng hợp 21 tháng 11 năm 2026')
p('Các phép thử cho thấy phương án adaptive cải thiện thời gian ở nhu cầu 8.779 xe, nhưng cho kết quả chậm hơn giữ tuyến gốc ở hai kịch bản 13.169 xe đã thử. Hiệu quả điều phối vì vậy cần được đánh giá theo mức tải và cấu hình sự cố. Báo cáo tổng hợp 18 lượt hoàn thành, ghép thành 9 cặp đối chứng trên mạng Bologna Andrea Costa.')
h('1 Mục tiêu và phạm vi')
p('Mục tiêu của đồ án là giảm tổng thời gian từ giờ xuất phát theo lịch đến khi kết thúc chuyến của toàn bộ phương tiện. Khi nhiều xe cùng chọn một tuyến đang nhanh, tải mới có thể làm tuyến đó chậm đi. Hệ thống cần dùng tình trạng giao thông và xác suất phân tuyến để hạn chế hiện tượng dồn xe vào một đường.')
p('Phạm vi thực nghiệm gồm mạng đường, luồng xe, xe buýt, điểm dừng và đèn tín hiệu của cấu hình Bologna có sẵn. Tai nạn được mô phỏng bằng giảm giới hạn tốc độ trên một đoạn đường. Các lượt đối chứng so sánh giữ tuyến gốc của SUMO với adaptive của dự án.')
table(['Mã', 'Nhu cầu mỗi lượt', 'Điều kiện', 'Hạt giống'], [
    ['B1', '8.779 xe', 'Không có sự cố', '51 52 53'],
    ['B2', '8.779 xe', 'Một tai nạn cố định', '51 52 53'],
    ['B3', '13.169 xe', 'Ba tai nạn cố định đồng thời', '51'],
    ['B4', '13.169 xe', 'Tai nạn động trong vùng', '51'],
    ['B5', '8.779 xe', 'Cùng lịch tai nạn động với B4', '51'],
], [1.2, 3, 8, 2.5])
p('Câu hỏi đánh giá là adaptive tiết kiệm được bao nhiêu thời gian trong từng điều kiện, các chuyến chậm bị ảnh hưởng ra sao và việc hoàn thành có phụ thuộc vào cơ chế dịch chuyển xe của SUMO hay không.')

page('2 Cơ chế điều phối hiện tại')
p('Mô phỏng dùng Eclipse SUMO 1.27.1. Python kết nối với SUMO qua TraCI để đọc tốc độ, xe đứng chờ và trạng thái xuất phát, đồng thời gửi tuyến thay thế hợp lệ cho phương tiện. Cấu hình đầu vào là scenarios/sumo-scenarios/bologna/acosta/run.sumocfg.')
p('Khi một xe xuất phát, hệ thống giữ điểm đầu và điểm cuối, loại phương tiện và các điểm dừng bắt buộc. Xe có tuyến dịch vụ cố định được giữ hành trình. Dijkstra dựng các hành lang thay thế trên những lượt rẽ được phép. ACO tìm tuyến trong tối đa ba hành lang bằng bốn kiến và ba vòng lặp. Cơ chế kiểm tra loại bỏ đường lặp và lượt quay đầu mới không có trong tuyến gốc.')
p('Chi phí của adaptive được tính theo thời gian thông thoáng, độ trễ quan sát, thời gian chờ ước tính ở lượt rẽ và phần tải từ các xe vừa được phân tuyến. Phần độ trễ quan sát và tải dự kiến được gộp bằng giá trị lớn hơn. Các tham số này là giả thiết mô phỏng, cần hiệu chỉnh bằng dữ liệu thực tế.')
table(['Thành phần', 'Thiết lập đang dùng'], [
    ['Lấy mẫu giao thông', 'Tối đa một lần mỗi 30 giây khi có xe xuất phát'],
    ['Làm trơn độ trễ', 'Hằng số thời gian 60 giây'],
    ['Ghi nhớ xe vừa được phân tuyến', 'Cửa sổ 120 giây'],
    ['Giới hạn đường vòng', 'Thời gian thông thoáng không quá 130% tuyến gốc cộng 15 giây'],
    ['Lợi ích tối thiểu để đổi tuyến', 'Phải vượt cả 15 giây và 10% chi phí tuyến gốc'],
    ['Thời điểm quyết định', 'Một lần khi xe xuất phát'],
], [5.2, 9.5])
p('Gọi Cg là chi phí tuyến gốc và Ct là chi phí tuyến thay thế, đều tính bằng giây. Lợi ích còn lại sau ngưỡng là G = max(0, Cg − Ct − max(15, 0,1 × Cg)). Xác suất đổi tuyến là p = 0,85 × G / (G + 30). Lợi ích lớn hơn làm xác suất đổi tuyến tăng; xác suất luôn dưới 85%.')
h('Cách dùng tên T ACO trong đồ án', 2)
p('ACO là phương pháp tối ưu dựa trên kiến ảo và pheromone [1]. Trong đồ án, có thể định nghĩa T-ACO là Traffic-Aware ACO, tức ACO được cấp chi phí có xét giao thông. Adaptive hiện kết hợp Dijkstra, ACO, quan sát giao thông và phân tuyến theo xác suất. Các phép thử này so sánh toàn bộ hệ thống adaptive với giữ tuyến gốc; chúng chưa tách riêng đóng góp của ACO hoặc kiểm chứng một biến thể T-ACO từ một bài báo cụ thể.')
p('Các xe đang đi tiếp tục chịu tốc độ mới khi có sự cố và giữ tuyến đã cấp. Chưa có quyết định đổi tuyến liên tục cho xe đang chạy. Hệ thống được kiểm chứng trong các lượt SUMO; giao diện web hiện chưa đồng bộ trực tiếp toàn bộ xe và sự cố của các lượt này.')

page('3 Thiết lập các kịch bản tai nạn')
p('B1 dùng nhu cầu gốc 8.779 xe và không thêm sự cố. B2 giữ nhu cầu này, hạ tốc độ còn 20% từ giây 900 đến trước giây 1.800 trên một đoạn chọn ngẫu nhiên. Với hạt giống 51, 52 và 53, các đoạn tương ứng là 200, 38 và 44. B3 dùng hệ số nhu cầu 1,5, tạo 13.169 xe cùng ba đoạn 200, 33 và 135 bị giảm tốc trong cùng khoảng thời gian.')
p('B4 và B5 dùng một lịch động giống nhau trong vùng chữ nhật 300 200 1500 1150 theo tọa độ SUMO địa phương, đơn vị mét. Vùng có 65 đoạn đủ điều kiện. Đoạn được chọn dài ít nhất 50 m, cho phép ô tô con, có đường vào và ra, toàn bộ đường hình học nằm trong vùng. Hệ thống thử tạo sự cố cách nhau 120–300 giây, từ giây 900 đến trước 3.600, tối đa năm sự cố đồng thời.')
table(['Mức độ', 'Tốc độ còn lại', 'Thời gian', 'Trọng số lấy mẫu'], [
    ['Nhẹ', '70%', '5 phút', '4'], ['Vừa', '40%', '10 phút', '3'],
    ['Nặng', '20%', '20 phút', '2'], ['Rất nặng', '10%', '30 phút', '1'],
], [3.5, 3.7, 3.7, 3.8])
p('Lịch được tạo trước khi chạy, độc lập với quyết định điều phối. Một đoạn đang có sự cố sẽ tạm bị loại khỏi danh sách chọn. Sau phục hồi, đoạn đó có thể được chọn lại. Tai nạn trong mô hình tác động lên toàn bộ các làn của đoạn một chiều bằng lệnh setMaxSpeed [2]. Đây là giả định giảm tốc, chưa mô phỏng va chạm vật lý, xe cứu hộ hoặc đóng từng làn.')
plan = checks['B4', (51, 'original')][3]
level_names = {'light': 'Nhẹ', 'moderate': 'Vừa', 'severe': 'Nặng', 'critical': 'Rất nặng'}
table(['Sự cố', 'Đoạn', 'Mức độ', 'Bắt đầu phút', 'Phục hồi phút'], [
    [r['id'].split('-')[-1], r['edge'], level_names[r['severity']], num(float(r['start_s']) / 60), num(float(r['end_s']) / 60)] for r in plan
], [1.7, 2.7, 3.1, 3.9, 3.3], font_size=10)
p('Có 13 sự cố gồm sáu nhẹ, ba vừa, ba nặng và một rất nặng. Sự cố cuối phục hồi ở phút 79. Giới hạn năm điểm là số đang hoạt động đồng thời, không phải tổng số sự cố của cả lượt.')

page('4 Kết quả tổng hợp')
p('Chỉ đưa các lượt complete=True vào bảng. Với B1 và B2, thời gian trung bình được gộp từ toàn bộ 26.337 chuyến của ba hạt giống cho mỗi chính sách. B3, B4 và B5 mỗi chính sách có một lượt. Mức cải thiện tính bằng 100 × (tổng thời gian gốc − tổng thời gian adaptive) / tổng thời gian gốc trong cùng nhóm; giá trị âm biểu thị adaptive chậm hơn.')
overview = []
for code, title, directory, seeds in groups:
    jumps = [sum(int(m['teleported_vehicles']) for (_, pol), m in data[code].items() if pol == policy) for policy in ('original', 'adaptive')]
    overview.append([code, num(pooled(code, 'original')[0]), num(pooled(code, 'adaptive')[0]), num(gain(code)) + '%', f'{jumps[0]} / {jumps[1]}'])
table(['Mã', 'Gốc phút mỗi xe', 'Adaptive phút mỗi xe', 'Cải thiện', 'Xe dịch chuyển gốc và adaptive'], overview, [1.2, 3.2, 3.5, 2.5, 4.3])
p('B1 cải thiện 5,24% và B2 cải thiện 6,78%, các lượt đều không có dịch chuyển. B3 có thời gian adaptive cao hơn 2,21%, số xe bị dịch chuyển tăng từ 4 lên 7. B4 cao hơn 9,41%, số xe bị dịch chuyển tăng từ 8 lên 66. B5 cải thiện 9,12%, có 0 xe bị dịch chuyển ở adaptive so với 1 ở giữ tuyến gốc.')
image_path = QA / 'demand_comparison.png'
if image_path.exists():
    para = p('')
    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = para.add_run()
    picture = run.add_picture(str(image_path), width=Cm(15.5))
    picture._inline.docPr.set('descr', 'Thời gian trung bình với cùng lịch tai nạn động. Với 8.779 xe, giữ tuyến gốc 7,73 phút và adaptive 7,02 phút. Với 13.169 xe, giữ tuyến gốc 23,46 phút và adaptive 25,67 phút.')
    p('Hình 1 Cùng lịch tai nạn động và hạt giống 51 ở hai mức nhu cầu', 'Caption')
p('Giảm từ 13.169 xuống 8.779 xe tương đương khoảng 33,3% số xe. Thời gian giảm giữa hai mức nhu cầu phản ánh việc giảm tải. Lợi ích của điều phối được xác định bằng cách so sánh hai chính sách tại cùng số xe. Không thể quy toàn bộ mức giảm giữa hai nhu cầu cho thuật toán.')

page('5 Chỉ số và số liệu chi tiết')
p('Thời gian một chuyến T được tính từ giờ xuất phát yêu cầu đến lúc tới đích bằng các trường của TripInfo [3]. T = arrival − depart + departDelay. Cách tính này bao gồm cả thời gian chờ để được đưa vào mạng. Tổng thời gian là tổng T của các xe; trung bình là tổng chia số chuyến. Trong báo cáo, P95 là giá trị tại vị trí làm tròn lên của 95% số chuyến sau khi sắp xếp tăng dần.')
details = []
for code, title, directory, seeds in groups:
    for seed in sorted(seeds):
        o, a = (data[code][seed, policy] for policy in ('original', 'adaptive'))
        details.append([f'{code}  seed {seed}', num(float(o['mean_s']) / 60), num(float(a['mean_s']) / 60), num(float(o['p95_s']) / 60), num(float(a['p95_s']) / 60), f"{o['teleported_vehicles']} / {a['teleported_vehicles']}", a['rerouted']])
table(['Nhóm và seed', 'TB gốc', 'TB adaptive', 'P95 gốc', 'P95 adaptive', 'Xe dịch chuyển gốc và adaptive', 'Xe đổi tuyến adaptive'], details, [3.0, 1.65, 2.0, 1.65, 2.0, 2.9, 2.0], font_size=9.8)
p('Bốn cột thời gian trong bảng dùng phút. P95 của từng lượt được tính từ dữ liệu chuyến gốc. Không lấy trung bình các P95 để tạo P95 chung. Các xe đổi tuyến là số xe được hệ thống gửi tuyến mới thành công.')
p('Cả 18 lượt kết thúc đủ số chuyến yêu cầu, không có xe chưa kết thúc, không có xe bị loại vì nguyên nhân khác và không có sự kiện từ chối tuyến. Chỉ số xe va chạm của SUMO bằng 0 trong các lượt này. Giá trị đó mô tả trạng thái mô phỏng, không chứng minh an toàn giao thông ngoài thực tế.')
h('Cách đọc các lần dịch chuyển xe', 2)
p('Teleport là cơ chế SUMO đưa xe ra khỏi dòng giao thông rồi tìm cách đưa trở lại tuyến, chẳng hạn khi xe đứng chờ quá lâu [4]. Một xe có thể bị dịch chuyển nhiều lần. Vì vậy cần phân biệt số xe bị ảnh hưởng với số sự kiện. B4 adaptive có 66 xe bị ảnh hưởng và 69 sự kiện, so với 8 xe và 8 sự kiện của tuyến gốc.')
p('Thời gian báo cáo vẫn bao gồm các chuyến từng bị dịch chuyển. Việc complete=True chỉ xác nhận nhu cầu đã kết thúc trong SUMO. Ở các lượt có teleport, kết quả cần được đọc cùng số xe bị ảnh hưởng. Khi tải cao, một số xe buýt của B4 adaptive còn được SUMO bỏ qua điểm dừng sau dịch chuyển, nên chưa thể kết luận chất lượng phục vụ vận tải công cộng được bảo đảm.')

page('6 Nhận định và hướng phát triển')
h('Những kết luận được số liệu hỗ trợ', 2)
p('Ở nhu cầu gốc 8.779 xe, adaptive cải thiện trung bình trong cả ba nhóm đã thử. Trường hợp một tai nạn được lặp ở ba hạt giống, còn trường hợp động trong vùng hiện có một hạt giống. Ở nhu cầu 13.169 xe, hai cấu hình đã thử đều cho adaptive chậm hơn giữ tuyến gốc. Kết quả cho thấy cần kiểm tra khả năng chịu tải và điều chỉnh phương án điều phối trước khi mở rộng kết luận.')
p('Giả thuyết cần kiểm tra là các tuyến vòng và nút giao thay thế không còn đủ khả năng tiếp nhận tải cao, trong khi ước lượng chi phí có độ trễ và mỗi xe chỉ được xét tuyến khi xuất phát. Muốn xác nhận, cần đọc hàng đợi, số xe qua nút và quyết định phân tuyến theo thời gian. Các kết quả tổng hợp hiện chưa xác định được một nguyên nhân riêng lẻ.')
h('Giới hạn của thí nghiệm', 2)
p('B3, B4 và B5 chỉ dùng hạt giống 51. Các mức giảm tốc và thời gian phục hồi được chọn để tạo thí nghiệm, chưa hiệu chỉnh từ thống kê tai nạn Bologna. Sự cố ảnh hưởng cả một đoạn đường và chưa mô tả hiện trường vật lý. Mạng là dữ liệu khu vực thực, nhưng kết quả vẫn là mô phỏng với nhu cầu và mô hình hành vi của kịch bản SUMO.')
p('Chưa có cặp 13.169 xe không sự cố trong bộ kết quả này để tách riêng tác động của tai nạn khi tải cao. B3 và B4 khác cả vị trí, thời gian và mức độ sự cố nên chưa thể dùng chênh lệch của chúng làm phép đo riêng cho ưu thế của mô hình động. Chưa có phép thử tách ACO khỏi Dijkstra và xác suất điều phối.')
h('Các bước đề xuất tiếp theo', 2)
p('Trước hết, lặp B3 đến B5 với nhiều hạt giống và bổ sung nền 13.169 xe không sự cố. Nếu muốn tách biến thiên giao thông khỏi biến thiên vị trí tai nạn, cần điều khiển riêng hạt giống tạo nhu cầu và hạt giống lịch sự cố. Đây là hướng mở rộng cần triển khai, không phải tùy chọn hiện có.')
p('Tiếp theo, dùng cycles.csv và decisions.csv để xác định nút tiếp nhận quá tải, hiệu chỉnh dự báo thời gian và mức phân tuyến. Sau đó mới thử đổi tuyến định kỳ cho xe đang chạy, kèm thời gian chờ giữa các lần đổi và ngưỡng lợi ích để hạn chế đổi qua lại. Cần giữ các ràng buộc loại xe, điểm dừng và hành trình dịch vụ.')
p('Cuối cùng, làm phép thử tách thành phần giữa giữ tuyến, Dijkstra theo giao thông và Dijkstra kết hợp ACO, đồng thời đo thời gian tính toán. Để tiến gần ứng dụng thực, cần kiểm chứng dữ liệu tốc độ thực, độ trễ quan sát và tỷ lệ tài xế làm theo gợi ý. Các bước này là đề xuất nghiên cứu, chưa có kết quả trong báo cáo.')

page('7 Cách tái lập và quan sát trong SUMO GUI')
p('Chạy trong PowerShell tại thư mục dự án, với SUMO, Python và SUMO_HOME đã được thiết lập. Khai báo các tham số chung và lịch động như sau.')
commands = '''Set-Location "D:\\study\\DATN\\traffic-simulation"
$cfg = "scenarios/sumo-scenarios/bologna/acosta/run.sumocfg"
$common = @("-B", "-m", "scripts.osm.osm_runner",
    "--mode", "fleet", "--cfg", $cfg, "--seed", "51")
$dynamic = @("--incident-dynamic", "--incident-area",
    "300", "200", "1500", "1150", "--incident-count", "5")

foreach ($policy in @("original", "adaptive")) {
    python @common @dynamic --nogui --policy $policy `
        --demand-scale 1 `
        --output-dir output/bologna/regional-incident-reduced/verification
}

python @common @dynamic --policy adaptive --demand-scale 1 `
    --gui-delay 5 --pause-at 3400 `
    --output-dir output/bologna/regional-incident-reduced/gui'''
for line in commands.splitlines():
    p(line, 'Commands')
(QA / 'reproduce.ps1').write_text(commands, encoding='utf-8-sig')
p('Để chạy B4, dùng các lệnh động trên với demand-scale bằng 1.5 và thư mục kết quả riêng. B5 dùng 1. Mỗi lần chạy tạo thư mục có thời gian riêng, thuận tiện giữ lại các lượt kiểm chứng.')
table(['Nhóm', 'Thiết lập khác trên tham số chung'], [
    ['B1', 'Không thêm $dynamic, demand-scale 1, chạy seed 51 52 53'],
    ['B2', 'Không thêm $dynamic, dùng --incident, demand-scale 1, seed 51 52 53'],
    ['B3', 'Không thêm $dynamic, dùng --incident --incident-count 3, demand-scale 1.5, seed 51'],
    ['B4', 'Thêm $dynamic, demand-scale 1.5, seed 51'],
    ['B5', 'Thêm $dynamic, demand-scale 1, seed 51'],
], [1.5, 13.2])
p('Trong GUI, vùng tai nạn có viền xanh. Đoạn đường và ghim chuyển vàng, cam, đỏ hoặc đỏ sẫm theo mức độ, rồi được gỡ khi phục hồi. Xe đổi tuyến có màu xanh ngọc. Lệnh minh họa dừng ở giây 3.400, lúc có năm sự cố đang hoạt động; nhấn nút chạy để tiếp tục.')
p('Không đặt duration cho các lượt đánh giá đầy đủ. Lượt dừng ở 120 giây chỉ kiểm tra khả năng chạy. Các tệp cần đọc là summary.csv, tripinfo.xml.gz, decisions.csv, cycles.csv, teleports.csv, incidents.csv và incident-plan.csv của chế độ động.')

page('8 Nguồn dữ liệu và tài liệu tham khảo')
p('Các nguồn dưới đây trỏ đến bảng tổng hợp gốc. Thư mục chính sách cạnh mỗi bảng chứa nhật ký chuyến, phân tuyến, hàng đợi và sự cố. Các lượt GUI trùng kết quả được loại khỏi phép gộp để tránh đếm lại cùng một thí nghiệm.')
for code, title, directory, seeds in groups:
    para = p(f'{code}  {title}. ')
    unique = {}
    for (seed, policy), m in data[code].items():
        unique.setdefault((seed, m['source']), []).append(policy)
    for n, ((seed, source), policies) in enumerate(sorted(unique.items())):
        if n:
            para.add_run('  |  ')
        name = 'hai chính sách' if len(policies) == 2 else policies[0]
        link(para, f'Seed {seed} {name}', '../' + source.replace('\\', '/'))
p('Đã tính lại tổng thời gian, trung bình và P95 của 18 lượt từ tripinfo.xml.gz. Các cặp đối chứng đã được so mã xe, điểm đi và đến, giờ xuất phát yêu cầu, loại xe và hệ số tốc độ. Lịch và nhật ký sự cố khớp giữa hai chính sách trong từng cặp. Lịch động B4 và B5 cũng khớp nhau.')
h('Tài liệu phương pháp và mô phỏng', 2)
references = [
    ('[1] Dorigo M Di Caro G và Gambardella L M 1999 Ant Colony Optimization A New Meta Heuristic', 'https://www.cs.yale.edu/homes/lans/readings/routing/dorigo-ants-1999.pdf'),
    ('[2] Eclipse SUMO Change Lane State', 'https://sumo.dlr.de/docs/TraCI/Change_Lane_State.html'),
    ('[3] Eclipse SUMO TripInfo Output', 'https://sumo.dlr.de/docs/Simulation/Output/TripInfo.html'),
    ('[4] Eclipse SUMO Why Vehicles are teleporting', 'https://sumo.dlr.de/docs/Simulation/Why_Vehicles_are_teleporting.html'),
]
for label, url in references:
    para = p('')
    link(para, label, url)
p('Tài liệu SUMO được truy cập ngày 21 tháng 11 năm 2026. Định nghĩa P95 và cách gộp các lượt trong báo cáo được nêu tại phần chỉ số; các trường depart, departDelay và arrival lấy từ TripInfo.')
h('Các phần mã nguồn liên quan', 2)
for label, target in [('Điểm vào lệnh osm_runner.py', '../../../scripts/osm/osm_runner.py'), ('Điều phối và tổng hợp fleet.py', '../../../scripts/osm/fleet.py'), ('Mô hình sự cố incidents.py', '../../../scripts/osm/incidents.py'), ('Lõi ACO osm_graph.py', '../../../scripts/core/osm_graph.py')]:
    para = p('')
    link(para, label, target)

output = OUT / 'bao-cao-thuc-nghiem-bologna.docx'
doc.save(output)
print('Saved', output)
