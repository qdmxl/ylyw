#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将第7章(量子易理)并入专著，并完成章节重编号。
输入:  易理研物-20260727-V2.docx  +  第7章_量子易理/第7章_量子易理.md
输出:  易理研物-20260910-V3(含量子易理章).docx
"""
import re, os, copy
from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from lxml import etree
import omml as OMML

BASE = '/home/lijinhan/MXL/科研/ylyw/paper'
CH7DIR = os.path.join(BASE, '第7章_量子易理')
SRC = os.path.join(BASE, '易理研物-20260727-V2.docx')
OUT = os.path.join(BASE, '易理研物-20260910-V3-含量子易理章.docx')

FONT_SONG = '宋体'
FONT_HEI = '黑体'
W_NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'


def _w(tag):
    return '{%s}%s' % (W_NS, tag)


def set_cn(run, font, size, bold=False, italic=False):
    run.font.name = font
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    rpr = run._element.get_or_add_rPr()
    rf = rpr.find(qn('w:rFonts'))
    if rf is None:
        rf = OxmlElement('w:rFonts'); rpr.insert(0, rf)
    rf.set(qn('w:eastAsia'), font)


def _add_inline(p, text, size=11, font=None):
    font = font or FONT_SONG
    tokens = re.split(r'(\*\*[^*]+\*\*)', text)
    for tok in tokens:
        if not tok:
            continue
        if tok.startswith('**') and tok.endswith('**'):
            inner = tok[2:-2]
            for sub in re.split(r'(\$[^$]+\$)', inner):
                if not sub:
                    continue
                if sub.startswith('$') and sub.endswith('$') and len(sub) > 2:
                    try:
                        om = OMML.latex_to_omml(sub[1:-1]); p._p.append(om)
                    except Exception:
                        r = p.add_run(sub); set_cn(r, font, size, bold=True)
                else:
                    r = p.add_run(sub); set_cn(r, font, size, bold=True)
        else:
            for sub in re.split(r'(\$[^$]+\$)', tok):
                if not sub:
                    continue
                if sub.startswith('$') and sub.endswith('$') and len(sub) > 2:
                    try:
                        om = OMML.latex_to_omml(sub[1:-1]); p._p.append(om)
                    except Exception:
                        r = p.add_run(sub); set_cn(r, font, size)
                else:
                    r = p.add_run(sub); set_cn(r, font, size)


# ---------- 解析 md 为块序列 ----------
def parse_md(path):
    lines = open(path, encoding='utf-8').read().split('\n')
    blocks = []
    i = 0
    while i < len(lines):
        s = lines[i].rstrip()
        st = s.strip()
        if not st:
            i += 1; continue
        if st == '---':
            i += 1; continue
        # 标题
        m = re.match(r'^(#{1,6})\s+(.*)$', st)
        if m:
            lvl = len(m.group(1)); blocks.append(('h', lvl, m.group(2).strip())); i += 1; continue
        # 图片
        m = re.match(r'^!\[[^\]]*\]\(([^)]+)\)$', st)
        if m:
            blocks.append(('img', m.group(1), None)); i += 1; continue
        # 图题/表题（加粗整行）
        # 独立公式
        if st.startswith('$$') and st.endswith('$$') and len(st) > 4:
            blocks.append(('formula', st.strip('$').strip(), None)); i += 1; continue
        # 引用
        if st.startswith('>'):
            blocks.append(('quote', st.lstrip('> ').strip(), None)); i += 1; continue
        # 表格
        if st.startswith('|'):
            tbl = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                tbl.append(lines[i].strip()); i += 1
            blocks.append(('table', tbl, None)); continue
        # 普通段落
        blocks.append(('p', st, None)); i += 1
    return blocks


# ---------- 插入块 ----------
def _style_id_map(doc):
    m = {}
    for s in doc.styles:
        if s.name:
            m[s.name] = s.style_id
    return m


def append_block(doc, block, prev_tbl=None):
    kind = block[0]
    if kind == 'h':
        lvl = block[1]
        p = doc.add_paragraph()
        p.style = doc.styles['Heading %d' % min(lvl, 3)]
        r = p.add_run(block[2])
        if lvl == 1:
            set_cn(r, FONT_HEI, 18, bold=True)
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        elif lvl == 2:
            set_cn(r, FONT_HEI, 15, bold=True)
        else:
            set_cn(r, FONT_HEI, 13, bold=True)
        return p
    elif kind == 'img':
        p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run()
        run.add_picture(os.path.join(CH7DIR, block[1]), width=Cm(14))
        return p
    elif kind == 'formula':
        p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        try:
            om = OMML.latex_to_omml(block[1]); p._p.append(om)
        except Exception:
            r = p.add_run(block[1]); set_cn(r, FONT_SONG, 11)
        return p
    elif kind == 'quote':
        p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _add_inline(p, block[1], 11)
        return p
    elif kind == 'table':
        return append_table(doc, block[1])
    else:  # p
        # 图题/表题识别
        txt = block[1]
        p = doc.add_paragraph()
        pf = p.paragraph_format
        is_caption = re.match(r'^\*\*(图|表)\d', txt)
        if is_caption:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            pf.first_line_indent = Pt(0)
            _add_inline(p, txt, 10.5)
        else:
            pf.first_line_indent = Pt(22)
            _add_inline(p, txt, 11)
        pf.space_after = Pt(6); pf.line_spacing = 1.5
        return p


def append_table(doc, rows):
    cells = []
    for r in rows:
        parts = [c.strip() for c in r.strip('|').split('|')]
        if all(re.match(r'^:?-{2,}:?$', c) or c == '' for c in parts):
            continue
        cells.append(parts)
    if not cells:
        return None
    ncol = max(len(r) for r in cells)
    t = doc.add_table(rows=len(cells), cols=ncol)
    t.style = 'Table Grid'
    t.alignment = 1
    for ri, r in enumerate(cells):
        for ci in range(ncol):
            val = r[ci] if ci < len(r) else ''
            cell = t.cell(ri, ci)
            cell.text = ''
            para = cell.paragraphs[0]
            _add_inline(para, val, 10)
            if ri == 0:
                for run in para.runs:
                    run.font.bold = True
    doc.add_paragraph()
    return t


# ---------- 章节重编号 ----------
def renumber_chapters(doc):
    """将原 7→8, 8→9, 9→10, 10→11。新插入的第7章(量子易理)保持不变。"""
    in_new_ch7 = False
    for p in doc.paragraphs:
        if not p.style.name.startswith('Heading'):
            continue
        t = p.text.strip()
        # 章标题
        m = re.match(r'^第(\d+)章(.*)$', t)
        if m:
            n = int(m.group(1))
            if t.startswith('第7章 量子易理'):
                in_new_ch7 = True
                continue
            if n >= 7:
                in_new_ch7 = False
                _set_heading_text(p, '第%d章%s' % (n + 1, m.group(2)))
            continue
        # 小节号
        m2 = re.match(r'^(\d+)\.(\d+)(.*)$', t)
        if m2:
            major = int(m2.group(1))
            if in_new_ch7:
                continue  # 新第7章内的小节号保持
            if major >= 7:
                _set_heading_text(p, '%d.%s%s' % (major + 1, m2.group(2), m2.group(3)))
            continue


def _set_heading_text(p, new_text):
    """保留首个 run 的格式，替换文本，删除其余 run。"""
    runs = p.runs
    if not runs:
        p.add_run(new_text); return
    runs[0].text = new_text
    for r in runs[1:]:
        r._element.getparent().remove(r._element)


# ---------- 主流程 ----------
def main():
    doc = Document(SRC)
    body = doc.element.body

    # 0) 找到旧第7章锚点（重编号前）
    anchor = None
    for p in doc.paragraphs:
        if p.style.name == 'Heading 1' and p.text.strip().startswith('第7章'):
            anchor = p._p
            break
    assert anchor is not None, '未找到第7章锚点'

    # 1) 解析第7章 md，直接 append 到目标文档末尾（sectPr 前）
    blocks = parse_md(os.path.join(CH7DIR, '第7章_量子易理.md'))
    # 标记插入起点：记录当前 body 子元素数
    before = list(body)
    for b in blocks:
        append_block(doc, b)
    after = list(body)
    # 新增元素 = after 中不在 before 里的（按身份）
    before_set = set(id(x) for x in before)
    new_nodes = [x for x in after if id(x) not in before_set]

    # 2) 逐个移动到 anchor 之前（保持顺序）
    for node in new_nodes:
        anchor.addprevious(node)

    # 3) 重编号：旧 7~10 → 8~11
    renumber_chapters(doc)

    # 4) 更新 0.3 结构导航
    update_nav(doc)

    # 4.5) 正文交叉引用重编号
    hit = renumber_intext_refs(doc)
    print('重编号交叉引用段落数:', hit)

    # 5) 另存
    doc.save(OUT)

    # 5.5) 设置 updateFields=true，使 Word/LibreOffice 打开时自动更新目录
    set_update_fields(OUT)

    print('saved:', OUT)
    print('段落:', len(doc.paragraphs), '表:', len(doc.tables), '图:', len(doc.inline_shapes))


def set_update_fields(path):
    """在 settings.xml 中插入 w:updateFields，使打开时刷新目录域。"""
    import zipfile, shutil, tempfile
    tmpf = path + '.tmp'
    with zipfile.ZipFile(path, 'r') as zin:
        names = zin.namelist()
        data = {n: zin.read(n) for n in names}
    s = data['word/settings.xml'].decode('utf-8')
    if 'updateFields' not in s:
        # 在 <w:settings ...> 后插入
        pos = s.find('>', s.find('<w:settings')) + 1
        s = s[:pos] + '<w:updateFields w:val="true"/>' + s[pos:]
        data['word/settings.xml'] = s.encode('utf-8')
    with zipfile.ZipFile(tmpf, 'w', zipfile.ZIP_DEFLATED) as zout:
        for n in names:
            zout.writestr(n, data[n])
    shutil.move(tmpf, path)


def update_nav(doc):
    """更新 0.3 结构导航：插入量子易理介绍，顺延后续章号。"""
    for p in doc.paragraphs:
        t = p.text.strip()
        # 原“第7章：用——层次化嵌套” → 改成 第7章量子易理 + 新增第8章层次化嵌套
        if t.startswith('第7章：用——'):
            body = t[len('第7章：用——'):]
            # body 形如“层次化嵌套。 从单个YLYW...”，去掉开头的重复标题
            body = re.sub(r'^层次化嵌套。\s*', '', body)
            new_full = ('第7章：量——量子易理。 将易理知识体系移植到量子计算范式——'
                        '两卦相重（张量积）与八卦相荡（酉变换干涉）的严格形式化，'
                        '从“道生一”到“八卦成”的逻辑缺环补全，以及 QYUF v3 在 ALFWorld '
                        '134 任务上的端到端验证（易理评分 100% 不低于经典）。'
                        '第8章：用——层次化嵌套。 ' + body)
            _set_paragraph_prefix(p, '第7章：', new_full)
            # 将“第8章：用——...”拆分为独立段落
            idx = new_full.find('第8章：用——')
            if idx > 0:
                p7_text = new_full[:idx].rstrip()
                p8_text = new_full[idx:]
                _set_paragraph_prefix(p, '第7章：', p7_text)
                _insert_paragraph_after(p, p8_text)
        elif t.startswith('第8章：辩——'):
            _set_paragraph_prefix(p, '第8章：', '第9章：' + t[len('第8章：'):])
        elif t.startswith('第9章：未来——'):
            _set_paragraph_prefix(p, '第9章：', '第10章：' + t[len('第9章：'):])
        elif t.startswith('第10章：界——'):
            _set_paragraph_prefix(p, '第10章：', '第11章：' + t[len('第10章：'):])


def _set_paragraph_prefix(p, old, new):
    """将段落文本整体重写为 new（new 已包含完整内容）。"""
    runs = p.runs
    if not runs:
        p.add_run(new); return
    runs[0].text = new
    for r in runs[1:]:
        r.text = ''


def renumber_intext_refs(doc):
    """将正文中的交叉引用 第7→8章…（仅限非新第7章区域）。"""
    in_new_ch7 = False
    hit = 0
    for p in doc.paragraphs:
        if p.style.name.startswith('Heading'):
            t = p.text.strip()
            if t.startswith('第7章 量子易理'):
                in_new_ch7 = True; continue
            if t.startswith('第8章 自组织') or t.startswith('第9章') \
               or t.startswith('第10章') or t.startswith('第11章'):
                in_new_ch7 = False
        full = p.text
        if not full or in_new_ch7:
            continue
        if p.style.name.startswith('Heading'):
            continue
        if not re.search(r'第(7|8|9|10)章', full) and not re.search(r'(?<![\d.])(7|8|9|10)\.\d', full):
            continue
        # 跳过 0.3 导航行（已由 update_nav 处理）
        if re.match(r'^第\d+章：', full.strip()):
            continue
        new_full = (full.replace('第10章', '第11章')
                        .replace('第9章', '第10章')
                        .replace('第8章', '第9章')
                        .replace('第7章', '第8章'))
        # 处理独立小节号（如 7.1 / 8.2）→ +1；仅 major≥7
        def _sec_sub(m):
            major = int(m.group(1))
            if major < 7:
                return m.group(0)
            return '%d.%s' % (major + 1, m.group(2))
        new_full = re.sub(r'(?<![\d.])(7|8|9|10)\.(\d+)', _sec_sub, new_full)
        if new_full != full:
            _rewrite_paragraph_text(p, new_full)
            hit += 1
    return hit


def _rewrite_paragraph_text(p, new_full):
    runs = p.runs
    if not runs:
        p.add_run(new_full); return
    runs[0].text = new_full
    for r in runs[1:]:
        r.text = ''


def _insert_paragraph_after(p, text):
    """在段落 p 之后插入一个新段落（拷贝 p 的样式与格式）。"""
    from docx.text.paragraph import Paragraph
    new_p = copy.deepcopy(p._p)
    # 清空 runs
    for t in new_p.findall('.//' + _w('t')):
        t.text = ''
    p._p.addnext(new_p)
    np = Paragraph(new_p, p._parent)
    # 保留首个 run 格式
    if np.runs:
        np.runs[0].text = text
        for r in np.runs[1:]:
            r.text = ''
    else:
        np.add_run(text)
    return np


if __name__ == '__main__':
    main()
