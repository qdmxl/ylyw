#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
为正式排版文档设置页眉：
  - 第0节（封面+目录，前置部分）：页眉留空。
  - 第1节（序）及第2节（各章）：页眉显示当前章标题（STYLEREF "Heading 1"）。
需要为不同节创建独立的 header 部件（原文档三节共用同一组页眉）。
用法: python3 fix_headers.py <docx>
"""
import sys, copy
from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

DOCX = sys.argv[1] if len(sys.argv) > 1 else \
    '/home/lijinhan/MXL/科研/ylyw/paper/易理研物-正式排版-20260911.docx'
W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
PKGREL = 'http://schemas.openxmlformats.org/package/2006/relationships'
HDR_TYPE = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/header'


def heading1_name(doc):
    for s in doc.styles:
        try:
            if s.name == 'Heading 1':
                nm = s.element.find(qn('w:name'))
                return nm.get(qn('w:val')) if nm is not None else 'Heading 1'
        except Exception:
            pass
    return 'Heading 1'


def make_blank_hdr_part(sec, doc, idx):
    """为节新建一个空白 header 部件，返回 part。"""
    from docx.opc.part import Part
    from docx.opc.packuri import PackURI
    package = doc.part.package
    partname = PackURI('/word/header_blank_%s.xml' % idx)
    xml = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<w:hdr xmlns:w="%s"><w:p><w:pPr><w:pStyle w:val="153"/></w:pPr></w:p></w:hdr>' % W)
    part = Part(partname, 'application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml',
                xml.encode('utf-8'), package)
    return part


def make_styleref_hdr_part(sec, style_name, doc, idx):
    from docx.opc.part import Part
    from docx.opc.packuri import PackURI
    package = doc.part.package
    partname = PackURI('/word/header_ch_%s.xml' % idx)
    xml = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<w:hdr xmlns:w="%s">'
           '<w:p><w:pPr><w:pStyle w:val="153"/><w:jc w:val="center"/></w:pPr>'
           '<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
           '<w:r><w:instrText xml:space="preserve"> STYLEREF "%s" \\* MERGEFORMAT </w:instrText></w:r>'
           '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
           '<w:r><w:t></w:t></w:r>'
           '<w:r><w:fldChar w:fldCharType="end"/></w:r>'
           '</w:p></w:hdr>' % (W, style_name))
    part = Part(partname, 'application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml',
                xml.encode('utf-8'), package)
    return part


def relink_section(sec, doc, blank, si):
    """把节的所有 headerReference 替换为新部件的引用。"""
    sectPr = sec._sectPr
    docpart = doc.part
    for ref in list(sectPr.findall(qn('w:headerReference'))):
        sectPr.remove(ref)
    style_name = heading1_name(doc)
    for i, htype in enumerate(('default', 'even', 'first')):
        idx = '%d_%d' % (si, i)
        part = make_blank_hdr_part(sec, doc, idx) if blank \
            else make_styleref_hdr_part(sec, style_name, doc, idx)
        rId = docpart.relate_to(part, HDR_TYPE)
        ref = OxmlElement('w:headerReference')
        ref.set(qn('w:type'), htype)
        ref.set(qn('r:id'), rId)
        sectPr.insert(0, ref)


def main():
    d = Document(DOCX)
    sn = heading1_name(d)
    print('Heading 1 样式名:', repr(sn))
    for si, sec in enumerate(d.sections):
        blank = (si == 0)
        relink_section(sec, d, blank=blank, si=si)
        print(f'  sec{si}: 页眉 ->', '空白' if blank else 'STYLEREF 章标题')
    d.save(DOCX)
    print('saved:', DOCX)


if __name__ == '__main__':
    main()
