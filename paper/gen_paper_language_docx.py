#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_paper_language_docx.py — 把《YLYW汉语言文字处理新范式》md 导出为 docx
处理：一级/二级/三级/四级标题、表格、粗体、LaTeX公式块、正文段落。"""
import re
from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

MD = "YLYW汉语言文字处理新范式.md"
OUT = "YLYW汉语言文字处理新范式_全文_v2.docx"

doc = Document()
for sec in doc.sections:
    sec.top_margin = Cm(2.54); sec.bottom_margin = Cm(2.54)
    sec.left_margin = Cm(3.18); sec.right_margin = Cm(3.18)

# 默认中文字体（新宋体/宋体）
sty = doc.styles['Normal']
sty.font.name = 'Times New Roman'
sty.font.size = Pt(12)
sty._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
sty.paragraph_format.line_spacing = 1.5


def set_cn(run, name):
    run.font.name = name
    run._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'), name)


def add_heading_style_paragraph(text, size, bold=True, font='黑体', center=False, indent=None):
    p = doc.add_paragraph()
    if center:
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for seg in re.split(r'(\*\*.+?\*\*)', text):
        if not seg:
            continue
        if seg.startswith('**') and seg.endswith('**'):
            r = p.add_run(seg[2:-2]); r.bold = True
        else:
            r = p.add_run(seg); r.bold = bold
        r.font.size = Pt(size)
        set_cn(r, font)
    if indent:
        p.paragraph_format.first_line_indent = Cm(indent)
    p.paragraph_format.space_after = Pt(4)
    return p


def add_body(text, indent=True, ref_mode=False):
    p = doc.add_paragraph()
    if indent:
        p.paragraph_format.first_line_indent = Cm(0.74)
    p.paragraph_format.line_spacing = 1.5
    # 处理 粗体 / 公式片段 / [n]上标引用
    tokens = re.split(r'(\*\*.+?\*\*|\$[^$]+?\$|\[\d+\])', text)
    for tk in tokens:
        if not tk:
            continue
        if tk.startswith('**') and tk.endswith('**'):
            r = p.add_run(tk[2:-2]); r.bold = True
            set_cn(r, '宋体'); r.font.size = Pt(12)
        elif tk.startswith('$') and tk.endswith('$'):
            r = p.add_run(tk.strip('$')); r.italic = True
            set_cn(r, 'Cambria Math'); r.font.size = Pt(11)
        elif re.match(r'^\[\d+\]$', tk):
            # 引用标号：上标
            r = p.add_run(tk); r.font.size = Pt(9)
            from docx.oxml.ns import qn as _qn
            from docx.oxml import OxmlElement as _OE
            rPr = r._element.get_or_add_rPr()
            vert = _OE('w:vertAlign'); vert.set(_qn('w:val'), 'superscript')
            rPr.append(vert)
            set_cn(r, '宋体')
        else:
            r = p.add_run(tk)
            set_cn(r, '宋体'); r.font.size = Pt(12)
    return p


def add_formula_block(text):
    """$$ 公式块：居中、斜体、等宽数学字体"""
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(text.strip('$').strip())
    r.italic = True; r.font.size = Pt(11)
    set_cn(r, 'Cambria Math')
    p.paragraph_format.space_before = Pt(4); p.paragraph_format.space_after = Pt(4)


def add_table(rows):
    """rows: list[list[str]]"""
    cols = max(len(r) for r in rows)
    t = doc.add_table(rows=len(rows), cols=cols)
    t.style = 'Table Grid'
    for ri, row in enumerate(rows):
        for ci in range(cols):
            val = row[ci] if ci < len(row) else ''
            # 清 md 粗体/强调
            val = re.sub(r'\*\*(.+?)\*\*', r'\1', val)
            c = t.rows[ri].cells[ci]
            c.text = ''
            pp = c.paragraphs[0]
            pp.alignment = WD_ALIGN_PARAGRAPH.CENTER
            rr = pp.add_run(val); rr.font.size = Pt(10)
            set_cn(rr, '宋体')
            if ri == 0:
                rr.bold = True
    doc.add_paragraph()


def add_image(mdfile, caption=None):
    """插入图片（居中）+ 图名（居中斜体小字）"""
    import os
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), mdfile)
    if not os.path.exists(path):
        p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(f'[图片缺失: {mdfile}]'); set_cn(r, '宋体'); r.font.size = Pt(10)
        return
    from docx.shared import Inches
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    run.add_picture(path, width=Inches(6.0))
    if caption:
        cp = doc.add_paragraph(); cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        rr = cp.add_run(caption); rr.font.size = Pt(10); rr.italic = True
        set_cn(rr, '宋体')
    doc.add_paragraph()


def main():
    lines = open(MD, encoding='utf-8').read().split('\n')
    i = 0
    n = len(lines)
    blocks = []
    # 先解析成块：(type, content)
    while i < n:
        ln = lines[i]
        s = ln.strip()
        if s.startswith('|'):
            tbl = []
            while i < n and lines[i].strip().startswith('|'):
                row = [c.strip() for c in lines[i].strip().strip('|').split('|')]
                tbl.append(row)
                i += 1
            blocks.append(('table', tbl))
            continue
        if s.startswith('$$'):
            # 公式块：连续到下一个$$
            buf = []
            i += 1
            while i < n and not lines[i].strip().startswith('$$'):
                buf.append(lines[i].strip())
                i += 1
            i += 1  # 跳过关闭$$
            blocks.append(('formula', ' '.join(buf)))
            continue
        if s.startswith('# '):
            blocks.append(('h1', s[2:].strip())); i += 1; continue
        if s.startswith('#### '):
            blocks.append(('h4', s[5:].strip())); i += 1; continue
        if s.startswith('### '):
            blocks.append(('h3', s[4:].strip())); i += 1; continue
        if s.startswith('## '):
            blocks.append(('h2', s[3:].strip())); i += 1; continue
        # 图片 ![...](path)
        img = re.match(r'^!\[(.*?)\]\((.*?)\)$', s)
        if img:
            blocks.append(('image', (img.group(2).strip(), img.group(1).strip()))); i += 1; continue
        if s == '':
            i += 1; continue
        # 列表项以 - 或 1. 开头：作为正文（缩进略减）
        blocks.append(('para', s))
        i += 1

    # 渲染
    ref_mode = False
    for typ, cont in blocks:
        if typ == 'h1':
            ref_mode = False
            add_heading_style_paragraph(cont, 16, font='黑体', center=True)
        elif typ == 'h2':
            if cont == '摘要':
                p = add_heading_style_paragraph(cont, 14, font='黑体', center=True)
            elif cont.startswith('参考文献'):
                ref_mode = True
                add_heading_style_paragraph(cont, 14, font='黑体')
            else:
                ref_mode = False
                add_heading_style_paragraph(cont, 14, font='黑体')
        elif typ == 'h3':
            ref_mode = False
            add_heading_style_paragraph(cont, 12.5, font='黑体')
        elif typ == 'h4':
            add_heading_style_paragraph(cont, 12, font='黑体')
        elif typ == 'table':
            add_table(cont)
        elif typ == 'image':
            mdfile, name = cont
            add_image(mdfile)
        elif typ == 'formula':
            add_formula_block(cont)
        else:
            # 参考文献段不缩进；正文缩进2字符
            add_body(cont, indent=not ref_mode)

    doc.save(OUT)
    print(f"已生成 {OUT}")
    print(f"共渲染 {len(blocks)} 个块")


if __name__ == "__main__":
    main()
