#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tex2docx.py (v2) —— LaTeX -> docx: 章节编号、首行缩进、OMML公式、图注编号、图插入
"""
import os, re, sys
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

BASE = os.path.dirname(os.path.abspath(__file__))
src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BASE, "paper", "zh", "main.tex")
out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(BASE, "paper", "main.docx")
zh = "zh" in src or "/zh/" in src

txt = open(src, encoding="utf-8").read()

doc = Document()
st = doc.styles["Normal"]
st.font.name = "SimSun" if zh else "Times New Roman"
st.element.rPr.rFonts.set(qn("w:eastAsia"), "SimSun")
st.font.size = Pt(10.5)
st.paragraph_format.line_spacing = 1.35

# 计数
sec_n = 0; sub_n = 0
fig_n = 0; tab_n = 0
fig_map = {}

# 图 → 章节映射 (把 12 张图插到合适位置)
# 我们在解析到对应 section 时注入
FIG_BY_SECTION = {
    "理论框架": ["fig1_framework.png", "fig2_yao_operators.png"],
    "方法": ["fig7_layer_heatmap.png"],
    "实验": ["fig10_main_results.png", "fig8_fewshot.png", "fig3_yaobian_vs_ortho.png"],
    "消融与分析": ["fig4_knowledge_ladder.png", "fig9_sensitive_radar.png",
                  "fig5_online_curve.png", "fig11_subtype.png"],
}
FIG_CAPTION = {
    "fig1_framework.png": "六爻传感器框架总览。",
    "fig2_yao_operators.png": "六爻算子示意。",
    "fig3_yaobian_vs_ortho.png": "爻变判据与正交判据对比。",
    "fig4_knowledge_ladder.png": "知识载体阶梯：随机卷积→手工卷积→手工六爻→预训练。",
    "fig5_online_curve.png": "在线学习曲线（峰值判据 vs 正交判据）。",
    "fig6_coldstart.png": "冷启动污染鲁棒性。",
    "fig7_layer_heatmap.png": "各层六爻贡献热图。",
    "fig8_fewshot.png": "少样本性能曲线。",
    "fig9_sensitive_radar.png": "各物品敏感爻指纹（零手调自动学出）。",
    "fig10_main_results.png": "四类主结果对比。",
    "fig11_subtype.png": "缺陷子类 AUROC 分解。",
    "fig12_lightweight.png": "轻量化对比（存储与推理时延）。",
}
ALL_FIGS = ["fig1_framework.png", "fig2_yao_operators.png", "fig3_yaobian_vs_ortho.png",
            "fig4_knowledge_ladder.png", "fig5_online_curve.png", "fig6_coldstart.png",
            "fig7_layer_heatmap.png", "fig8_fewshot.png", "fig9_sensitive_radar.png",
            "fig10_main_results.png", "fig11_subtype.png", "fig12_lightweight.png"]
_used_figs = set()


def add_indent(p):
    p.paragraph_format.first_line_indent = Pt(21)   # ~2字符
    p.paragraph_format.line_spacing = 1.35
    return p


def clean_inline(s):
    s = s.replace("\\\\", "")
    s = re.sub(r"\\tbd\{([^}]*)\}", r"【\1】", s)
    s = re.sub(r"\\textbf\{([^}]*)\}", r"\1", s)
    s = re.sub(r"\\emph\{([^}]*)\}", r"\1", s)
    s = re.sub(r"\\textit\{([^}]*)\}", r"\1", s)
    s = re.sub(r"\\texttt\{([^}]*)\}", r"\1", s)
    s = re.sub(r"\\cite\{[^}]*\}", "", s)
    s = re.sub(r"\\ref\{([^}]*)\}", r"[引用:\1]", s)
    s = re.sub(r"\\label\{[^}]*\}", "", s)
    s = re.sub(r"\\includegraphics\[[^\]]*\]\{([^}]*)\}", "", s)
    s = re.sub(r"\\[a-zA-Z]+\*?\{([^}]*)\}", r"\1", s)
    s = re.sub(r"\\[a-zA-Z]+", "", s)
    s = s.replace("$", "").replace("{", "").replace("}", "")
    s = s.replace("~", " ").replace("---", "—").replace("--", "–")
    return s.strip()


def insert_figure(fname):
    """插入图片 + 编号图注。"""
    global fig_n
    path = os.path.join(BASE, "figures_paper", fname)
    if not os.path.exists(path) or fname in _used_figs:
        return
    _used_figs.add(fname)
    fig_n += 1
    try:
        doc.add_picture(path, width=Inches(4.5))
        doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    except Exception:
        doc.add_paragraph("[图片缺失: " + fname + "]")
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(f"图 {fig_n}  {FIG_CAPTION.get(fname, fname)}")
    r.italic = True; r.font.size = Pt(9)


def eq_clean(s):
    """公式美化: 处理 frac / sqrt / max / abs 等为 Unicode 近似。"""
    s = re.sub(r"\\frac\{([^{}]*)\}\{([^{}]*)\}", r"(\1)/(\2)", s)
    s = re.sub(r"\\sqrt\{([^{}]*)\}", r"√(\1)", s)
    s = re.sub(r"\\max", "max", s)
    s = re.sub(r"\\min", "min", s)
    s = re.sub(r"\\mathrm\{([^}]*)\}", r"\1", s)
    s = re.sub(r"\\text\{([^}]*)\}", r"\1", s)
    s = re.sub(r"\\bar\{?\s*([A-Za-z])\}?", lambda m: m.group(1) + "\u0304", s)
    s = re.sub(r"\\hat\{?\s*([A-Za-z])\}?", lambda m: m.group(1) + "\u0302", s)
    s = re.sub(r"\\sum", "Σ", s)
    s = re.sub(r"\\pm", "±", s)
    s = re.sub(r"\\times", "×", s)
    s = re.sub(r"\\cdot", "·", s)
    s = re.sub(r"\\\|\s*\|?", "|", s)         # \| -> |
    s = re.sub(r"\\,|\\;|\\!|\\quad|\\qquad|\\ ", " ", s)
    s = re.sub(r"\\left|\\right", "", s)
    s = re.sub(r"\\frac", "", s)
    s = re.sub(r"\\\\", " ; ", s)
    s = s.replace("&", " ").replace("{", "").replace("}", "").replace("$", "")
    s = re.sub(r"\\emph\s*\{?", "", s)
    s = re.sub(r"\\([a-zA-Z]+)", r"\1", s)   # 剩余命令去反斜杠
    s = re.sub(r"\b(notag|emph|text|mathrm|label|quad|qquad)\b", "", s)
    s = re.sub(r"\s+", " ", s).strip().rstrip(".").rstrip(";").strip()
    return s


def add_equation(text):
    """用 OMML 生成一个居中的公式段落(简单线性文本, 作为公式体)。"""
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(text)
    r.italic = True
    r.font.name = "Cambria Math"
    return p


def flush_para(buf):
    if not buf:
        return
    text = " ".join(buf) if not zh else "".join(buf)
    add_indent(doc.add_paragraph(clean_inline(text)))


lines = txt.split("\n")
i = 0
buf = []
cur_sec = ""


def emit_section_figs(sec_name):
    for f in FIG_BY_SECTION.get(sec_name, []):
        insert_figure(f)


while i < len(lines):
    ln = lines[i].strip()

    if ln.startswith("%") or not ln:
        flush_para(buf); buf = []
        i += 1; continue

    if re.match(r"\\(title|author|section|subsection|begin|end|item|bibitem|maketitle)", ln):
        flush_para(buf); buf = []

    if ln.startswith("\\title"):
        t = re.sub(r"\\title\{", "", ln).rstrip("}").replace("\\\\", " ")
        p = doc.add_heading(clean_inline(t), level=0)
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        i += 1; continue

    if ln.startswith("\\author"):
        a = clean_inline(re.sub(r"\\author\{", "", ln).rstrip("}"))
        if a.strip(",").strip():
            p = doc.add_paragraph(a); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        i += 1; continue

    if ln.startswith("\\section"):
        h = clean_inline(re.sub(r"\\section\*?\{", "", ln).rstrip("}"))
        sec_n += 1; sub_n = 0
        cur_sec = h
        doc.add_heading(f"{sec_n}  {h}", level=1)
        # 本章对应的图放在章首(保证编号递增)
        emit_section_figs(h)
        i += 1; continue

    if ln.startswith("\\subsection"):
        sub_n += 1
        h = clean_inline(re.sub(r"\\subsection\*?\{", "", ln).rstrip("}"))
        doc.add_heading(f"{sec_n}.{sub_n}  {h}", level=2)
        i += 1; continue

    if ln.startswith("\\begin{abstract}"):
        flush_para(buf); buf = []
        doc.add_heading("摘要" if zh else "Abstract", level=1)
        i += 1; abuf = []
        while i < len(lines) and not lines[i].strip().startswith("\\end{abstract}"):
            abuf.append(lines[i]); i += 1
        add_indent(doc.add_paragraph(clean_inline(" ".join(abuf))))
        i += 1; continue

    if ln.startswith("\\begin{IEEEkeywords}"):
        flush_para(buf); buf = []
        i += 1; kbuf = []
        while i < len(lines) and not lines[i].strip().startswith("\\end{IEEEkeywords}"):
            kbuf.append(lines[i]); i += 1
        add_indent(doc.add_paragraph(("关键词: " if zh else "Keywords: ") + clean_inline(" ".join(kbuf))))
        i += 1; continue

    # -------- 公式 --------
    if ln.startswith("\\begin{equation}") or ln.startswith("\\begin{align}"):
        env = "equation" if "equation" in ln else "align"
        i += 1; eq = []
        while i < len(lines) and "\\end{" + env + "}" not in lines[i]:
            s = lines[i].strip()
            if s and not s.startswith("\\notag") and not s.startswith("\\label"):
                s = re.sub(r"\\\\", " ; ", s)
                s = re.sub(r"\\text\{([^}]*)\}", r"\1", s)
                s = s.replace("{}", "")
                if s: eq.append(eq_clean(s))
            i += 1
        add_equation("   ;   ".join(eq))
        i += 1; continue

    # -------- 表格 --------
    if ln.startswith("\\begin{table}") or ln.startswith("\\begin{table*}"):
        cap = ""
        j = i
        while j < len(lines) and "\\end{table" not in lines[j]:
            if lines[j].strip().startswith("\\caption"):
                cap = re.sub(r"\\caption\{", "", lines[j]).rstrip("}")
            j += 1
        k = i; tab = ""; in_tab = False
        while k < len(lines) and "\\end{table" not in lines[k]:
            if "\\begin{tabular}" in lines[k]: in_tab = True
            elif "\\end{tabular}" in lines[k]: in_tab = False
            elif in_tab: tab += lines[k] + " "
            k += 1
        tab_n += 1
        tab = re.sub(r"\\toprule|\\midrule|\\bottomrule|\\hline", " ", tab)
        tab = re.sub(r"\\cmidrule(?:\([^)]*\))?\{[^}]*\}", " ", tab)
        rows = [r.strip().split("&") for r in tab.split(r"\\")]
        data = []
        for r in rows:
            cells = [clean_inline(c) for c in r]
            if any(cells) and not any("rule" in c for c in cells):
                data.append(cells)
        if cap:
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r = p.add_run(f"表 {tab_n}  {clean_inline(cap)}"); r.italic = True; r.font.size = Pt(9)
        if data:
            ncol = max(len(r) for r in data)
            tb = doc.add_table(rows=0, cols=ncol)
            tb.style = "Light Grid Accent 1"
            for r in data:
                cells = tb.add_row().cells
                for ci in range(ncol):
                    cells[ci].text = r[ci] if ci < len(r) else ""
                    for cp in cells[ci].paragraphs:
                        for run in cp.runs: run.font.size = Pt(9)
        i = j + 1; continue

    # -------- 算法 --------
    if ln.startswith("\\begin{algorithm}"):
        cap = ""; code = []
        j = i
        while j < len(lines) and "\\end{algorithm}" not in lines[j]:
            s = lines[j].strip()
            if s.startswith("\\caption"):
                cap = re.sub(r"\\caption\{", "", s).rstrip("}")
            elif s and "\\begin{algorithm" not in s and not s.startswith("\\label"):
                c = re.sub(r"\\State|\\For|\\EndFor|\\EndIf|\\If|\\Else|\\ElsIf|\\Comment", "", s)
                c = re.sub(r"\\textbf\{([^}]*)\}", r"\1", c)
                c = re.sub(r"\\[a-zA-Z]+", "", c).replace("{", "").replace("}", "").replace("$", "").strip()
                if c: code.append(c)
            j += 1
        if cap:
            p = doc.add_paragraph(); r = p.add_run(clean_inline(cap)); r.bold = True
        for c in code:
            p = doc.add_paragraph(c)
            for run in p.runs:
                run.font.name = "Consolas"; run.font.size = Pt(9)
        i = j + 1; continue

    # -------- 列表 --------
    if ln.startswith("\\begin{itemize}") or ln.startswith("\\begin{enumerate}"):
        style = "List Bullet" if "itemize" in ln else "List Number"
        i += 1
        while i < len(lines) and not (lines[i].strip().startswith("\\end{itemize}") or
                                      lines[i].strip().startswith("\\end{enumerate}")):
            s = lines[i].strip()
            if s.startswith("\\item"):
                doc.add_paragraph(clean_inline(re.sub(r"\\item\s*", "", s)), style=style)
            elif s and not s.startswith("\\"):
                doc.paragraphs[-1].add_run(" " + clean_inline(s))
            i += 1
        i += 1; continue

    # -------- 参考文献 --------
    if ln.startswith("\\begin{thebibliography}"):
        doc.add_heading("参考文献" if zh else "References", level=1)
        i += 1
        while i < len(lines) and "\\end{thebibliography}" not in lines[i]:
            s = lines[i].strip()
            if s.startswith("\\bibitem"):
                s = re.sub(r"\\bibitem\{[^}]*\}", "", s)
                doc.add_paragraph(clean_inline(s), style="List Number")
            elif s and not s.startswith("\\"):
                try:
                    doc.paragraphs[-1].add_run(" " + clean_inline(s))
                except Exception:
                    pass
            i += 1
        i += 1; continue

    # -------- 图 (正文内显式 includegraphics) --------
    if ln.startswith("\\begin{figure}"):
        j = i; img = None; cap = ""
        while j < len(lines) and "\\end{figure}" not in lines[j]:
            m = re.search(r"\\includegraphics\[[^\]]*\]\{([^}]*)\}", lines[j])
            if m: img = m.group(1)
            if lines[j].strip().startswith("\\caption"):
                cap = re.sub(r"\\caption\{", "", lines[j].strip()).rstrip("}")
            j += 1
        if img:
            base = os.path.basename(img)
            if os.path.exists(os.path.join(BASE, img)):
                fig_n += 1; _used_figs.add(base)
                doc.add_picture(os.path.join(BASE, img), width=Inches(4.5))
                doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
                p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                r = p.add_run(f"图 {fig_n}  {clean_inline(cap)}"); r.italic = True; r.font.size = Pt(9)
        i = j + 1; continue

    if not ln.startswith("\\") and not ln.startswith("&"):
        buf.append(ln)
    i += 1

flush_para(buf)

# ---------- 尾部: 兜底插入尚未使用的图 ----------
for f in ALL_FIGS:
    insert_figure(f)

doc.save(out)
print("saved:", out, "| 图:", fig_n, "表:", tab_n)
