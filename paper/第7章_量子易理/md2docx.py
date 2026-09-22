#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第7章 Markdown -> DOCX 转换器
匹配专著《易理研物》的排版格式：
- Heading1: 黑体 18pt 加粗 居中
- Heading2: 黑体 15pt 加粗
- Heading3: 黑体 13pt 加粗
- Heading4: 黑体 12pt 加粗
- 正文: 宋体 11pt, 首行缩进2字符
- 表格: Table Grid
- 插图: 居中 + 图题
"""
import re
import os
import sys
from docx import Document
from docx.shared import Pt, RGBColor, Cm, Emu
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import omml as OMML

BASE = os.path.dirname(os.path.abspath(__file__))
MD = os.path.join(BASE, '第7章_量子易理.md')
OUT = os.path.join(BASE, '第7章_量子易理.docx')

FONT_HEI = '黑体'
FONT_SONG = '宋体'


def set_cn(run, font, size=None, bold=None, color=None):
    run.font.name = font
    run._element.rPr.rFonts.set(qn('w:eastAsia'), font)
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold
    if color is not None:
        run.font.color.rgb = color


def _add_inline(p, text, size=11, font=None):
    """处理行内 **bold** 与 $...$ 行内公式"""
    font = font or FONT_SONG
    # 先按公式切分，再按加粗切分
    tokens = re.split(r'(\*\*[^*]+\*\*|\$[^$]+\$)', text)
    for tok in tokens:
        if not tok:
            continue
        if tok.startswith('**') and tok.endswith('**'):
            r = p.add_run(tok[2:-2]); set_cn(r, font, size, bold=True)
        elif tok.startswith('$') and tok.endswith('$') and len(tok) > 2:
            try:
                om = OMML.latex_to_omml(tok[1:-1])
                p._p.append(om)
            except Exception:
                r = p.add_run(tok.strip('$')); set_cn(r, font, size)
        else:
            r = p.add_run(tok); set_cn(r, font, size)
    return p


def add_body(doc, text):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.first_line_indent = Pt(22)  # 2字符
    pf.space_after = Pt(6)
    pf.line_spacing = 1.5
    _add_inline(p, text)
    return p


def add_heading(doc, text, level):
    sizes = {1: 18, 2: 15, 3: 13, 4: 12}
    p = doc.add_paragraph(style=f'Heading {level}')
    if level == 1:
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(text)
    set_cn(r, FONT_HEI, sizes.get(level, 12), bold=True)
    return p


def add_caption(doc, text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(10)
    parts = re.split(r'(\*\*[^*]+\*\*)', text)
    for part in parts:
        if not part:
            continue
        if part.startswith('**') and part.endswith('**'):
            r = p.add_run(part[2:-2]); set_cn(r, FONT_SONG, 10.5, bold=True)
        else:
            r = p.add_run(part); set_cn(r, FONT_SONG, 10.5)
    return p


def add_image(doc, path, width_cm=14):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run()
    r.add_picture(path, width=Cm(width_cm))
    return p


def add_table(doc, rows):
    ncols = len(rows[0])
    t = doc.add_table(rows=len(rows), cols=ncols)
    t.style = 'Table Grid'
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, row in enumerate(rows):
        for j, cell_text in enumerate(row):
            if j >= ncols:
                continue
            cell = t.rows[i].cells[j]
            cell.text = ''
            p = cell.paragraphs[0]
            for part in re.split(r'(\*\*[^*]+\*\*)', cell_text):
                if not part:
                    continue
                if part.startswith('**') and part.endswith('**'):
                    r = p.add_run(part[2:-2]); set_cn(r, FONT_SONG, 9.5, bold=True)
                else:
                    r = p.add_run(part); set_cn(r, FONT_SONG, 9.5)
            if i == 0:
                for r in p.runs:
                    r.font.bold = True
    return t


def add_sep(doc):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run('——————————————————————————————')
    set_cn(r, FONT_SONG, 9)


def parse_md(doc, lines):
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i].rstrip('\n')
        s = line.strip()
        if not s:
            i += 1
            continue
        # 图片
        m = re.match(r'!\[.*?\]\((.*?)\)', s)
        if m:
            img = os.path.join(BASE, m.group(1))
            if os.path.exists(img):
                add_image(doc, img)
            i += 1
            continue
        # 标题
        m = re.match(r'^(#{1,4})\s+(.*)$', s)
        if m:
            add_heading(doc, m.group(2).strip(), len(m.group(1)))
            i += 1
            continue
        # 表格
        if s.startswith('|'):
            tbl = []
            while i < n and lines[i].strip().startswith('|'):
                row = lines[i].strip()
                if re.match(r'^\|[\s:\-\|]+\|$', row):
                    i += 1
                    continue
                cells = [c.strip() for c in row.strip('|').split('|')]
                tbl.append(cells)
                i += 1
            if tbl:
                add_table(doc, tbl)
            continue
        # 分隔线
        if set(s) <= set('-—') and len(s) >= 3:
            add_sep(doc)
            i += 1
            continue
        # 图题/表题
        if s.startswith('**图') or s.startswith('**表'):
            add_caption(doc, s)
            i += 1
            continue
        # 列表
        m = re.match(r'^(\d+)\.\s+(.*)$', s)
        if m:
            p = doc.add_paragraph(style='List Number')
            for part in re.split(r'(\*\*[^*]+\*\*)', m.group(2)):
                if not part: continue
                if part.startswith('**') and part.endswith('**'):
                    r = p.add_run(part[2:-2]); set_cn(r, FONT_SONG, 11, bold=True)
                else:
                    r = p.add_run(part); set_cn(r, FONT_SONG, 11)
            i += 1
            continue
        if s.startswith('- '):
            p = doc.add_paragraph(style='List Bullet')
            for part in re.split(r'(\*\*[^*]+\*\*)', s[2:]):
                if not part: continue
                if part.startswith('**') and part.endswith('**'):
                    r = p.add_run(part[2:-2]); set_cn(r, FONT_SONG, 11, bold=True)
                else:
                    r = p.add_run(part); set_cn(r, FONT_SONG, 11)
            i += 1
            continue
        # 公式块（以 $$ 包裹的整行）——渲染为 Word 原生数学公式
        if s.startswith('$$') and s.endswith('$$') and len(s) > 4:
            latex = s.strip('$').strip()
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            try:
                om = OMML.latex_to_omml(latex)
                p._p.append(om)
            except Exception as e:
                r = p.add_run(latex); set_cn(r, FONT_SONG, 11)
            i += 1
            continue
        # 普通正文
        add_body(doc, s)
        i += 1


def main():
    with open(MD, encoding='utf-8') as f:
        lines = f.readlines()
    doc = Document()
    # 页面设置 A4
    sec = doc.sections[0]
    sec.page_width = Cm(21); sec.page_height = Cm(29.7)
    sec.left_margin = Cm(2.5); sec.right_margin = Cm(2.5)
    sec.top_margin = Cm(2.5); sec.bottom_margin = Cm(2.5)
    parse_md(doc, lines)
    doc.save(OUT)
    print('saved:', OUT)


if __name__ == '__main__':
    main()
