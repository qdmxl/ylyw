#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将 V4 专著内容按《嵌入式系统原理》正式排版格式重排。
策略：以模板 docx 为基底（保留其全部样式/编号/页面设置），清空其正文，
      再把 V4 内容按模板样式重新灌入。
样式映射：
  章标题(H1) -> Heading 1（自动编号 第N章，去掉手写前缀）
  节标题(H2) -> Heading 2（自动编号 N.M）
  三级标题(H3)-> Heading 3（自动编号 N.M.K）
  正文       -> #M-正文-通用
  图题       -> #G-图名-通用
  表题       -> #T-表名-通用
  图片段落   -> #G-图片
  表格       -> #T-表格-常规，表头 #T-首行文字-居中，单元格 #T-表内文字-居中
  公式       -> #P-公式-居中
输入: 嵌入式系统原理.docx (模板)  +  易理研物-20260911-V4-含汉语语义章.docx (内容)
输出: 易理研物-正式排版-20260911.docx
"""
import re, copy
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

BASE = '/home/lijinhan/MXL/科研/ylyw/paper'
TPL = BASE + '/嵌入式系统原理.docx'
SRC = BASE + '/易理研物-20260911-V4-含汉语语义章.docx'
OUT = BASE + '/易理研物-正式排版-20260911.docx'

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'


def w(tag):
    return '{%s}%s' % (W, tag)


# ---------- 备份模板中的页面/编号（保留在基底中即可） ----------

def clear_body(doc):
    """删除 body 中除 sectPr 外的所有内容。"""
    body = doc.element.body
    for child in list(body):
        if child.tag == w('sectPr'):
            continue
        body.remove(child)


def ensure_style(doc, name):
    try:
        doc.styles[name]
        return name
    except KeyError:
        return None


def set_run_font(run, size=None, bold=None):
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold


def set_page_break_before(p):
    """给段落加 pageBreakBefore，使每章另起一页。"""
    pPr = p._p.get_or_add_pPr()
    if pPr.find(qn('w:pageBreakBefore')) is None:
        el = OxmlElement('w:pageBreakBefore')
        pPr.append(el)


def add_para(doc, text, style):
    p = doc.add_paragraph(style=style)
    if text:
        p.add_run(text)
    return p


def strip_chapter_prefix(t):
    # 第N章 标题 -> 标题
    return re.sub(r'^第[〇一二三四五六七八九十百零\d]+章[\s　:：]*', '', t).strip()


def strip_section_prefix(t):
    # N.M 标题 -> 标题
    return re.sub(r'^\d+\.\d+[\s　]*', '', t).strip()


def strip_subsection_prefix(t):
    # N.M.K 标题 -> 标题
    return re.sub(r'^\d+\.\d+\.\d+[\s　]*', '', t).strip()


def is_fig_caption(t):
    return re.match(r'^(图)\s*\d+[.\-–—]\d+', t.strip()) is not None or \
           re.match(r'^图\s*\d+\s*[　 ]', t.strip()) is not None


def is_tab_caption(t):
    return re.match(r'^(表)\s*\d+[.\-–—]\d+', t.strip()) is not None or \
           re.match(r'^表\s*\d+\s*[　 ]', t.strip()) is not None


def add_picture_para(doc, src_para, src_doc=None):
    """把源段落中的图片拷入新的 #G-图片 段落，并为输出文档建立正确的图片关系。"""
    drawing = src_para._p.find('.//' + w('drawing'))
    if drawing is None:
        return None
    p = doc.add_paragraph(style='#G-图片')
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    new_drawing = copy.deepcopy(drawing)
    _remap_blips(new_drawing, src_doc, doc)
    run._r.append(new_drawing)
    return p


def _remap_blips(drawing_el, src_doc, dst_doc):
    """将 drawing 中所有 a:blip 的 r:embed/r:link 重映射到输出文档的新关系 ID。
    src_doc: 源 Document；dst_doc: 输出 Document。"""
    A = 'http://schemas.openxmlformats.org/drawingml/2006/main'
    R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    blips = drawing_el.findall('.//{%s}blip' % A)
    for blip in blips:
        for attr in ('{%s}embed' % R, '{%s}link' % R):
            rid = blip.get(attr)
            if not rid:
                continue
            try:
                rel = src_doc.part.rels[rid]
            except Exception:
                continue
            if rel.reltype.endswith('/image') or rel.is_external:
                if rel.is_external:
                    new_rid = dst_doc.part.relate_to(rel.target_ref, rel.reltype,
                                                     is_external=True)
                else:
                    new_rid = dst_doc.part.relate_to(rel.target_part, rel.reltype)
                blip.set(attr, new_rid)


def add_formula_para(doc, src_para):
    """把源段落中的公式拷入 #P-公式-居中 段落。"""
    omaths = src_para._p.findall('.//{http://schemas.openxmlformats.org/officeDocument/2006/math}oMath')
    if not omaths:
        return None
    p = doc.add_paragraph(style='#P-公式-居中')
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for om in omaths:
        p._p.append(copy.deepcopy(om))
    return p


def convert_table(doc, src_tbl, src_doc=None):
    nrow = len(src_tbl.rows)
    ncol = len(src_tbl.columns)
    t = doc.add_table(rows=nrow, cols=ncol)
    t.style = '#T-表格-常规'
    t.alignment = 1
    for ri, row in enumerate(src_tbl.rows):
        for ci, cell in enumerate(row.cells):
            txt = cell.text.strip()
            dst = t.cell(ri, ci)
            dst.text = ''
            para = dst.paragraphs[0]
            if ri == 0:
                para.style = doc.styles['#T-首行文字-居中']
            else:
                para.style = doc.styles['#T-表内文字-居中']
            # 单元格内图片
            drawings = cell._tc.findall('.//' + w('drawing'))
            if drawings:
                for dg in drawings:
                    new_dg = copy.deepcopy(dg)
                    _remap_blips(new_dg, src_doc, doc)
                    para.add_run()._r.append(new_dg)
                continue
            if txt:
                para.add_run(txt)
    return t


def has_drawing(p):
    return p._p.find('.//' + w('drawing')) is not None


def has_math(p):
    return p._p.find('.//{http://schemas.openxmlformats.org/officeDocument/2006/math}oMath') is not None


def clean_header_footer(doc):
    """清除页眉/页脚中 STYLEREF 域的缓存结果（w:t），使其在 Word 中自动刷新。
    策略：遇到 fldChar separate 后、在下一个 fldChar end 之前的 w:t 清空。"""
    def clean_para(p):
        state = 'before'
        for el in p._p.iter():
            tag = el.tag.split('}')[-1]
            if tag == 'fldChar':
                t = el.get(qn('w:fldCharType'))
                if t == 'separate':
                    state = 'inresult'
                elif t == 'end':
                    state = 'after'
                elif t == 'begin':
                    state = 'instr'
            elif tag == 't' and state == 'inresult':
                el.text = ''
    for sec in doc.sections:
        for part in (sec.header, sec.footer, sec.first_page_header,
                     sec.first_page_footer, sec.even_page_header, sec.even_page_footer):
            try:
                for p in part.paragraphs:
                    clean_para(p)
                for tbl in part.tables:
                    for row in tbl.rows:
                        for cell in row.cells:
                            for p in cell.paragraphs:
                                clean_para(p)
            except Exception:
                pass


def main():
    tpl = Document(TPL)
    # 校验模板样式齐备
    needed = ['Heading 1', 'Heading 2', 'Heading 3', 'Heading 4', '#M-正文-通用',
              '#A-003',
              '#G-图名-通用', '#T-表名-通用', '#G-图片',
              '#T-表格-常规', '#T-首行文字-居中', '#T-表内文字-居中', '#P-公式-居中']
    for n in needed:
        assert ensure_style(tpl, n) is not None, '模板缺少样式: ' + n

    src = Document(SRC)
    clear_body(tpl)

    # 建立 body 段落与表格的原始顺序表（按 XML 顺序遍历）
    body = src.element.body
    items = []
    for child in body.iterchildren():
        if child.tag == w('p'):
            items.append(('p', child))
        elif child.tag == w('tbl'):
            items.append(('tbl', child))

    # 建立 XML 元素 -> Paragraph/Table 对象的映射
    from docx.text.paragraph import Paragraph
    from docx.table import Table
    para_map = {p._p: p for p in src.paragraphs}
    tbl_map = {t._tbl: t for t in src.tables}

    in_front = True  # 未遇到第一个正式章前，均为前置部分
    cover_zone = True  # 首个标题之前为封面区（保留大字格式）
    for kind, el in items:
        if kind == 'tbl':
            convert_table(tpl, tbl_map[el], src_doc=src)
            continue
        p = para_map.get(el)
        if p is None:
            continue
        style = p.style.name
        text = p.text.strip()

        # 图片段落
        if has_drawing(p):
            if text:
                # 图文混排段：整体拷贝子节点并重映射图片关系
                np_ = tpl.add_paragraph(style='#M-正文-通用')
                for child in p._p.iterchildren():
                    if child.tag in (w('r'),
                                     '{http://schemas.openxmlformats.org/officeDocument/2006/math}oMath',
                                     '{http://schemas.openxmlformats.org/officeDocument/2006/math}oMathPara'):
                        nc = copy.deepcopy(child)
                        for dg in nc.findall('.//' + w('drawing')):
                            _remap_blips(dg, src, tpl)
                        np_._p.append(nc)
            else:
                add_picture_para(tpl, p, src_doc=src)
            continue

        # 公式段落（无文字）
        if has_math(p) and not text:
            add_formula_para(tpl, p)
            continue

        if style == 'Heading 1':
            if text.startswith('序'):
                # 前置部分的“序”不参与章号（同模板“前言”用 Heading 4）
                in_front = True
                cover_zone = False
                add_para(tpl, '序', 'Heading 4')
            else:
                in_front = False
                cover_zone = False
                hp = add_para(tpl, strip_chapter_prefix(text), 'Heading 1')
                set_page_break_before(hp)
        elif style == 'Heading 2':
            if in_front:
                # 前置 0.x 节不编号
                cover_zone = False
                add_para(tpl, re.sub(r'^0\.\d+[\s　]*', '', text).strip(), 'Heading 4')
            else:
                add_para(tpl, strip_section_prefix(text), 'Heading 2')
        elif style == 'Heading 3':
            add_para(tpl, strip_subsection_prefix(text), '#A-003')
        else:
            # 封面区（第一个标题之前）：保留原大字/居中格式
            if cover_zone:
                np_ = tpl.add_paragraph(style='#M-正文-通用')
                if p.alignment is not None:
                    np_.alignment = p.alignment
                if not text:
                    np_.add_run('')
                else:
                    for r in p.runs:
                        nr = np_.add_run(r.text)
                        if r.font.size is not None:
                            nr.font.size = r.font.size
                        if r.font.bold is not None:
                            nr.font.bold = r.font.bold
                        if r.font.name:
                            nr.font.name = r.font.name
                continue
            # 正文/题注
            if is_fig_caption(text) and text.startswith('图'):
                add_para(tpl, text, '#G-图名-通用')
            elif is_tab_caption(text) and text.startswith('表'):
                add_para(tpl, text, '#T-表名-通用')
            elif has_math(p):
                # 含行内公式的正文：整段保留（文字+公式）
                np_ = tpl.add_paragraph(style='#M-正文-通用')
                # 复制原段落的全部 run 内容（含 oMath）
                for child in p._p.iterchildren():
                    if child.tag in (w('r'), '{http://schemas.openxmlformats.org/officeDocument/2006/math}oMath',
                                     '{http://schemas.openxmlformats.org/officeDocument/2006/math}oMathPara'):
                        np_._p.append(copy.deepcopy(child))
            else:
                add_para(tpl, text, '#M-正文-通用')

    # 目录域：保留模板原有？模板正文清空了；需在开头插入目录。
    prepend_toc(tpl, src)
    clean_header_footer(tpl)
    set_update_fields(OUT, tpl)
    fix_static_headers(OUT)
    print('saved:', OUT)
    print('段落:', len(tpl.paragraphs), '表:', len(tpl.tables), '图:',
          len(tpl.inline_shapes))


def prepend_toc(tpl, src):
    """目录由 finalize_toc.py 统一生成，此处不再插入。
    仅保证正文前有一处分页（封面与正文分离）。"""
    from docx.enum.text import WD_BREAK
    body = tpl.element.body
    anchor = None
    for p in tpl.paragraphs:
        if p.style.name in ('Heading 4', 'Heading 1'):
            anchor = p._p
            break
    if anchor is None:
        return
    brk = tpl.add_paragraph()
    brk.add_run().add_break(WD_BREAK.PAGE)
    body.remove(brk._p)
    anchor.addprevious(brk._p)


def fix_static_headers(path):
    """将页眉中静态文字“嵌入式系统原理”替换为 STYLEREF(标题 1) 域。"""
    import zipfile, shutil, re
    tmpf = path + '.tmp'
    with zipfile.ZipFile(path, 'r') as zin:
        names = zin.namelist()
        data = {n: zin.read(n) for n in names}
    field = ('<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
             '<w:r><w:instrText xml:space="preserve"> STYLEREF "标题 1" \\n \\* MERGEFORMAT </w:instrText></w:r>'
             '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
             '<w:r><w:t></w:t></w:r>'
             '<w:r><w:fldChar w:fldCharType="end"/></w:r>')
    for n in list(names):
        if re.match(r'word/header\d+\.xml', n):
            s = data[n].decode('utf-8')
            if '嵌入式系统原理' in s and 'instrText' not in s:
                s2 = re.sub(r'<w:r>(?:(?!</w:r>).)*嵌入式系统原理.*?</w:r>', field, s, flags=re.S)
                if s2 == s:
                    s2 = s.replace('嵌入式系统原理', '')
                data[n] = s2.encode('utf-8')
    with zipfile.ZipFile(tmpf, 'w', zipfile.ZIP_DEFLATED) as zout:
        seen = set()
        for n in names:
            if n in seen:
                continue
            seen.add(n)
            zout.writestr(n, data[n])
    shutil.move(tmpf, path)


def set_update_fields(path, doc):
    """先保存后注入 updateFields，使打开时自动刷新域（目录/页眉）。"""
    import zipfile, shutil
    doc.save(path)
    tmpf = path + '.tmp'
    with zipfile.ZipFile(path, 'r') as zin:
        names = zin.namelist()
        data = {n: zin.read(n) for n in names}
    s = data['word/settings.xml'].decode('utf-8')
    if 'updateFields' not in s:
        pos = s.find('>', s.find('<w:settings')) + 1
        s = s[:pos] + '<w:updateFields w:val="true"/>' + s[pos:]
        data['word/settings.xml'] = s.encode('utf-8')
    with zipfile.ZipFile(tmpf, 'w', zipfile.ZIP_DEFLATED) as zout:
        for n in names:
            zout.writestr(n, data[n])
    shutil.move(tmpf, path)


if __name__ == '__main__':
    main()
