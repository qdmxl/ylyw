#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LaTeX -> MathML -> OMML 转换器
用于在 python-docx 生成的 .docx 中插入 Word 原生数学公式（OMML）。
"""
from lxml import etree
import latex2mathml.converter as l2m

M_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/math'
W_NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
NSMAP = {'m': M_NS, 'w': W_NS}


def _m(tag):
    return '{%s}%s' % (M_NS, tag)


def _w(tag):
    return '{%s}%s' % (W_NS, tag)


def _clean_text(t):
    return (t or '').strip()


# 操作符映射：MathML 实体/字符 -> OMML 需要的文本
def _mi_el(text, kind='i'):
    el = etree.Element(_m('r'))
    # Word 用 m:rPr 设置样式
    rpr = etree.SubElement(el, _m('rPr'))
    if kind == 'i':
        sty = etree.SubElement(rpr, _m('sty'))
        sty.set(_m('val'), 'i')
    elif kind == 'p':
        sty = etree.SubElement(rpr, _m('sty'))
        sty.set(_m('val'), 'p')
    else:  # n: normal (upright)
        nor = etree.SubElement(rpr, _m('nor'))
    t = etree.SubElement(el, _m('t'))
    t.text = text
    return el


def _run(text, italic=True):
    el = etree.Element(_m('r'))
    rpr = etree.SubElement(el, _m('rPr'))
    if not italic:
        etree.SubElement(rpr, _m('nor'))
    t = etree.SubElement(el, _m('t'))
    if text.startswith(' ') or text.endswith(' '):
        t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
    t.text = text
    return el


def mathml_to_omml(mathml_str):
    root = etree.fromstring(mathml_str.encode('utf-8'))
    omml = etree.Element(_m('oMath'), nsmap=NSMAP)
    _convert_children(root, omml)
    return omml


def _convert_children(src, dst, wrapper=None):
    for child in src:
        _convert_node(child, dst, wrapper)


def _convert_node(node, dst, wrapper=None):
    tag = etree.QName(node).localname
    if tag in ('math', 'mrow', 'mstyle', 'semantics'):
        # 透明容器
        _convert_children(node, dst, wrapper)
    elif tag in ('mi',):
        was_stretchy = node.get('mathvariant')  # noqa
        variant = node.get('mathvariant')
        text = _clean_text(node.text)
        if variant == 'normal' or (len(text) > 1 and text.isalpha()):
            dst.append(_run(text, italic=(len(text) == 1)))
        else:
            # 单个字母默认斜体；函数名直立
            funcs = {'sin', 'cos', 'tan', 'log', 'ln', 'exp', 'det', 'dim', 'max', 'min', 'arg'}
            dst.append(_run(text, italic=(text not in funcs)))
    elif tag == 'mn':
        dst.append(_run(_clean_text(node.text), italic=False))
    elif tag == 'mo':
        dst.append(_run(_clean_text(node.text), italic=False))
    elif tag == 'mtext':
        dst.append(_run(node.text or '', italic=False))
    elif tag == 'mspace':
        dst.append(_run(' ', italic=False))
    elif tag == 'msup':
        base = node.find('{http://www.w3.org/1998/Math/MathML}*')
        children = list(node)
        sup = etree.SubElement(dst, _m('sSup'))
        e = etree.SubElement(sup, _m('e'))
        _convert_node(children[0], e)
        s = etree.SubElement(sup, _m('sup'))
        _convert_node(children[1], s)
    elif tag == 'msub':
        children = list(node)
        sub = etree.SubElement(dst, _m('sSub'))
        e = etree.SubElement(sub, _m('e'))
        _convert_node(children[0], e)
        s = etree.SubElement(sub, _m('sub'))
        _convert_node(children[1], s)
    elif tag == 'msubsup':
        children = list(node)
        ss = etree.SubElement(dst, _m('sSubSup'))
        e = etree.SubElement(ss, _m('e'))
        _convert_node(children[0], e)
        s = etree.SubElement(ss, _m('sub'))
        _convert_node(children[1], s)
        sp = etree.SubElement(ss, _m('sup'))
        _convert_node(children[2], sp)
    elif tag == 'mfrac':
        children = list(node)
        fr = etree.SubElement(dst, _m('f'))
        num = etree.SubElement(fr, _m('num'))
        _convert_node(children[0], num)
        den = etree.SubElement(fr, _m('den'))
        _convert_node(children[1], den)
    elif tag == 'msqrt':
        rad = etree.SubElement(dst, _m('rad'))
        e = etree.SubElement(rad, _m('e'))
        _convert_children(node, e)
    elif tag == 'mroot':
        children = list(node)
        rad = etree.SubElement(dst, _m('rad'))
        deg = etree.SubElement(rad, _m('deg'))
        _convert_node(children[1], deg)
        e = etree.SubElement(rad, _m('e'))
        _convert_node(children[0], e)
    elif tag == 'munderover':
        children = list(node)
        lim = etree.SubElement(dst, _m('limLow'))  # approx
        e = etree.SubElement(lim, _m('e'))
        _convert_node(children[0], e)
        l = etree.SubElement(lim, _m('lim'))
        _convert_node(children[1], l)
    elif tag == 'munder':
        children = list(node)
        lim = etree.SubElement(dst, _m('limLow'))
        e = etree.SubElement(lim, _m('e'))
        _convert_node(children[0], e)
        l = etree.SubElement(lim, _m('lim'))
        _convert_node(children[1], l)
    elif tag == 'mover':
        children = list(node)
        lim = etree.SubElement(dst, _m('limUpp'))
        e = etree.SubElement(lim, _m('e'))
        _convert_node(children[0], e)
        l = etree.SubElement(lim, _m('lim'))
        _convert_node(children[1], l)
    elif tag == 'mfenced':
        children = list(node)
        openc = node.get('open', '(')
        closec = node.get('close', ')')
        seps = node.get('separators', ',')
        dst.append(_run(openc, italic=False))
        for i, ch in enumerate(children):
            if i > 0:
                dst.append(_run(seps[0] if seps else ',', italic=False))
            _convert_node(ch, dst)
        dst.append(_run(closec, italic=False))
    elif tag == 'mtable':
        # 简化：按行拼接
        for row in node:
            _convert_children(row, dst)
    elif tag == 'mtr':
        _convert_children(node, dst)
    elif tag == 'mtd':
        _convert_children(node, dst)
    elif tag == 'annotation':
        return
    else:
        # 未知节点：递归
        _convert_children(node, dst)


def latex_to_omml(latex_str):
    """LaTeX -> OMML 元素（lxml Element）"""
    mathml = l2m.convert(latex_str)
    return mathml_to_omml(mathml)


if __name__ == '__main__':
    om = latex_to_omml(r'\sum_{k=0}^{63} \alpha_k |k\rangle')
    print(etree.tostring(om, pretty_print=True).decode()[:800])
