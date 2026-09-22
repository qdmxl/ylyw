#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
为《易理研物》正式排版文档加“章页眉”。
方案（用 python-docx 原生 API，确保 LibreOffice/Word/WPS 都能渲染）：
  1. 删除空的 Heading 1 段。
  2. 在“序”和每一章标题前建立 nextPage 分节。
  3. 对每一节：is_linked_to_previous=False（各自独立页眉），
     页眉段落=该节章标题静态文字（居中、9pt、底部细线，不使用 pStyle）。
  4. 前置部分（封面+目录）页眉留空。
用法: python3 add_chapter_headers.py <docx>
"""
import sys, re, copy
from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

DOCX = sys.argv[1] if len(sys.argv) > 1 else \
    '/home/lijinhan/MXL/科研/ylyw/paper/易理研物-正式排版-20260911.docx'
W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'


def chap_title(t):
    return re.sub(r'^第[〇一二三四五六七八九十百零\d]+章[\s　:：]*', '', t.strip()).strip()


def _style_hdr_para(p, text):
    pf = p.paragraph_format
    pf.alignment = 1  # center
    pPr = p._p.get_or_add_pPr()
    bdr = OxmlElement('w:pBdr')
    bottom = OxmlElement('w:bottom')
    bottom.set(qn('w:val'), 'single'); bottom.set(qn('w:sz'), '6')
    bottom.set(qn('w:space'), '1'); bottom.set(qn('w:color'), 'auto')
    bdr.append(bottom); pPr.append(bdr)
    if text:
        run = p.add_run(text)
        from docx.shared import Pt
        run.font.size = Pt(9)
        run.font.name = 'Times New Roman'
        rpr = run._r.get_or_add_rPr()
        rf = OxmlElement('w:rFonts')
        rf.set(qn('w:eastAsia'), '宋体'); rpr.append(rf)


def _set_one_header(hdr, text, unlink=True):
    if unlink:
        hdr.is_linked_to_previous = False
    for p in list(hdr.paragraphs):
        p._p.getparent().remove(p._p)
    p = hdr.add_paragraph()
    _style_hdr_para(p, text)


def clear_header(sec, text):
    """把 sec 的 首页/奇数/偶数 页眉均设为 text（空则留空）。"""
    _set_one_header(sec.header, text)
    _set_one_header(sec.first_page_header, text)
    _set_one_header(sec.even_page_header, text)


def main():
    d = Document(DOCX)

    # 0) 删除空 Heading 1
    rem = 0
    for p in list(d.paragraphs):
        if p.style.name == 'Heading 1' and not p.text.strip():
            p._p.getparent().remove(p._p); rem += 1
    print('删除空 H1:', rem)

    # 1) 基准 sectPr
    base = copy.deepcopy(d.sections[-1]._sectPr)
    for tag in ('w:headerReference', 'w:footerReference', 'w:type'):
        for e in base.findall(qn(tag)):
            base.remove(e)

    # 1b) 修复：文档原有的第 0 节分节符（para 243）缺少 w:type，
    #     补上 nextPage，避免 LibreOffice 把它与下一节合并。
    for p in d.paragraphs:
        pPr = p._p.find(qn('w:pPr'))
        if pPr is None:
            continue
        sp = pPr.find(qn('w:sectPr'))
        if sp is None:
            continue
        t = sp.find(qn('w:type'))
        if t is None:
            t = OxmlElement('w:type'); sp.insert(0, t)
        if not t.get(qn('w:val')):
            t.set(qn('w:val'), 'nextPage')
            print('补 nextPage 于原有分节符')

    paras = d.paragraphs
    h1 = [(i, p) for i, p in enumerate(paras) if p.style.name == 'Heading 1']
    print('H1 数:', len(h1))

    # 2) 分节：在“序”和每章标题前分节（在标题前一段挂 sectPr）
    for idx, p in reversed(h1):
        el = p._p
        prev = el.getprevious()
        if prev is None or prev.tag != qn('w:p'):
            holder = OxmlElement('w:p'); el.addprevious(holder)
        else:
            holder = prev
        pPr = holder.find(qn('w:pPr'))
        if pPr is None:
            pPr = OxmlElement('w:pPr'); holder.insert(0, pPr)
        if pPr.find(qn('w:sectPr')) is not None:
            continue
        sect = copy.deepcopy(base)
        typ = OxmlElement('w:type'); typ.set(qn('w:val'), 'nextPage')
        sect.insert(0, typ)
        pPr.append(sect)
    d.save(DOCX)
    print('分节完成。')

    # 3) 重新载入，按节设置页眉（用原生 API，从 LAST section 往前，
    #    因为设置 linked=False 会改变节关系）
    d = Document(DOCX)
    # 先全部 unlink，再逐个写
    texts = []
    # 计算每节标题：遍历 body 分组
    body = d.element.body
    groups, cur = [], []
    for el in body.iterchildren():
        if el.tag == qn('w:p'):
            cur.append(el)
            pPr = el.find(qn('w:pPr'))
            if pPr is not None and pPr.find(qn('w:sectPr')) is not None:
                groups.append(cur); cur = []
        elif el.tag == qn('w:tbl'):
            cur.append(el)
    groups.append(cur)
    raw_titles = []  # 每节第一个 Heading1 的原文（含“第X章”）
    for grp in groups:
        raw = ''
        for el in grp:
            if el.tag != qn('w:p'):
                continue
            pPr = el.find(qn('w:pPr'))
            st = None
            if pPr is not None:
                ps = pPr.find(qn('w:pStyle'))
                if ps is not None:
                    st = ps.get(qn('w:val'))
            if st == '3':  # Heading 1 styleId
                raw = ''.join(t.text or '' for t in el.iter(qn('w:t'))).strip()
                break
        raw_titles.append(raw)
    texts = [raw_titles[i] for i in range(len(raw_titles))]
    print('节数:', len(d.sections), '标题:', texts)

    # 生成页眉文字：
    #   - 序（raw=='序'）：'序'
    #   - 章（raw 以“第X章”开头）：'第X章　章名'（章号+全角空格+名）
    #   - 前置（封面/目录，raw=''）：''
    def hdr_text(raw, chap_no):
        if not raw:
            return ''
        if raw == '序':
            return '序'
        if chap_no is None:
            return raw
        return '第%s章　%s' % (chap_no, raw)

    # 章序号：按“序”之后的章节顺序编号（H1 文本不含自动章号，需自行推算）
    # 将中文数字：1→一 … 12→十二
    def cn(n):
        dg = '零一二三四五六七八九'
        if n <= 10:
            return '十' if n == 10 else dg[n]
        if n < 20:
            return '十' + dg[n - 10]
        return dg[n // 10] + '十' + (dg[n % 10] if n % 10 else '')

    for si, sec in enumerate(d.sections):
        raw = raw_titles[si] if si < len(raw_titles) else ''
        # 封面/目录（sec0）不设页眉；其余（序 + 各章）设页眉
        if si == 0:
            t = ''
        else:
            t = hdr_text(raw, cn(si - 1) if si >= 2 else None)
        clear_header(sec, t)
        print(f'  sec{si} 页眉: {t!r}')
    d.save(DOCX)
    print('saved:', DOCX)


if __name__ == '__main__':
    main()
