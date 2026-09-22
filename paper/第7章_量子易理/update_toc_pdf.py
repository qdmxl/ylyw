#!/usr/bin/env python3
# 通过 LibreOffice UNO 宏更新目录后导出 PDF
import subprocess, os, sys, time

SRC = sys.argv[1]
OUT = sys.argv[2]

# LibreOffice Basic 宏方案：用 --convert-to 前先让 LO 打开更新域不可行
# 改用 unoconv 风格：调用 soffice 的 macro
macro = r'''
import uno
'''
# 直接使用 LibreOffice 的 headless + macro 不方便，改用 python3-uno
try:
    import uno
except Exception as e:
    print("no uno:", e)
