#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""通过 LibreOffice UNO 打开 docx，更新目录域，另存 docx 并导出 PDF。"""
import os, sys, time, subprocess

SRC = os.path.abspath(sys.argv[1])
OUT_DOCX = os.path.abspath(sys.argv[2])
OUT_PDF = os.path.abspath(sys.argv[3])

PROFILE = "/tmp/lo_uno_profile"
SOCKET = "socket,host=localhost,port=2002;urp;StarOffice.ComponentContext"

# 启动 soffice listener
proc = subprocess.Popen([
    "soffice", "--headless", "--invisible", "--nologo", "--nofirststartwizard",
    "-env:UserInstallation=file://" + PROFILE,
    "--accept=" + SOCKET,
], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

import uno
from com.sun.star.beans import PropertyValue

ctx = None
localContext = uno.getComponentContext()
resolver = localContext.ServiceManager.createInstanceWithContext(
    "com.sun.star.bridge.UnoUrlResolver", localContext)
for _ in range(60):
    try:
        ctx = resolver.resolve("uno:" + SOCKET)
        break
    except Exception:
        time.sleep(1)
assert ctx is not None, "无法连接 LibreOffice"

smgr = ctx.ServiceManager
desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)

def pv(name, val):
    p = PropertyValue(); p.Name = name; p.Value = val; return p

url = uno.systemPathToFileUrl(SRC)
doc = desktop.loadComponentFromURL(url, "_blank", 0, (pv("Hidden", True),))

# 更新所有索引（目录）
try:
    doc.refresh()
except Exception:
    pass
try:
    indexes = doc.getDocumentIndexes()
    for i in range(indexes.getCount()):
        indexes.getByIndex(i).update()
except Exception as e:
    print("update index warn:", e)

# 保存 docx
doc.storeToURL(uno.systemPathToFileUrl(OUT_DOCX), (pv("FilterName", "MS Word 2007 XML"),))
# 导出 PDF
doc.storeToURL(uno.systemPathToFileUrl(OUT_PDF), (pv("FilterName", "writer_pdf_Export"),))
doc.close(False)
try:
    desktop.terminate()
except Exception:
    pass
print("OK ->", OUT_DOCX, OUT_PDF)
