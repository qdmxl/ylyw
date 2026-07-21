#!/usr/bin/env python3
"""清理md文件中的LaTeX表格格式，替换为markdown表格"""
import re

with open('YLYW_obs_only_task_planning_paper.md', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. 删除所有LaTeX表格式控制符
content = content.replace('\\cline', '')
content = content.replace('\\hline', '')

# 2. 处理LaTeX表格环境——删除\begin{tabular}...\end{tabular}中的行尾换行标记
# 把 \\\\ 换成换行，但保留 | 分隔的表格内容
content = re.sub(r'\\\\\\\\\n', '\n', content)
content = re.sub(r'\\\\\n', '\n', content)

# 3. 删除LaTeX table环境标签和\centering
content = re.sub(r'\\begin\{table\}.*?\n', '', content)
content = re.sub(r'\\end\{table\}', '', content)
content = re.sub(r'\\begin\{tabular\}.*?\n', '', content)
content = re.sub(r'\\end\{tabular\}', '', content)
content = re.sub(r'\\centering\n?', '', content)
content = re.sub(r'\\label\{.*?\}', '', content)
content = re.sub(r'\\caption\{.*?\}', '', content)

# 4. 删除残留的\\和\{和\}
content = content.replace('\\}', '}')
content = content.replace('\\{', '{')
# 但是要保留正常的\（LaTeX命令）
content = re.sub(r'\\\\', '', content)  # 双反斜杠→空

# 5. 给关键表格加表名

# 表1: 句卦象（在"在句级推理中"段落之后）
mark1 = '在句级推理中，输出卦象代表整句的意图类别：\n\n'
idx1 = content.find(mark1)
if idx1 >= 0:
    # 找到下一个|行
    after_mark1 = content[idx1 + len(mark1):]
    # 第一个|行前插入表名
    lines = after_mark1.split('\n')
    new_lines = []
    for line in lines:
        new_lines.append(line)
        if line.startswith('| ') and '句子' in line:
            # 在表头前插入表名
            new_lines.insert(new_lines.index(line), '表1  句级卦象示例')
            break
    content = content[:idx1 + len(mark1)] + '\n'.join(new_lines) + '\n' + '\n'.join(lines[len(new_lines):])

# 表2: 易理模型作用
mark2 = '易理模型在系统各层次中的作用如下：\n\n'
idx2 = content.find(mark2)
if idx2 >= 0:
    after2 = content[idx2 + len(mark2):]
    lines2 = after2.split('\n')
    part2 = []
    for i, line in enumerate(lines2):
        if line.startswith('| '):
            if i == 0:
                part2.append('表2  易理模型在系统各层次中的作用')
            part2.append(line)
        else:
            break
    if part2:
        content = content[:idx2 + len(mark2)] + '\n'.join(part2) + '\n' + '\n'.join(lines2[len(part2):])

# 表3: 模糊规则
mark3 = '8条模糊推理规则。'
idx3 = content.find(mark3)
if idx3 >= 0:
    after3 = content[idx3 + len(mark3):]
    lines3 = after3.split('\n')
    part3 = []
    for i, line in enumerate(lines3):
        if line.startswith('| '):
            if i == 0:
                part3.append('表3  8条模糊推理规则')
            part3.append(line)
        else:
            break
    if part3:
        content = content[:idx3 + len(mark3)] + '\n'.join(part3) + '\n' + '\n'.join(lines3[len(part3):])

# 表4: 六爻编码
mark4 = '任务规划域中的六爻编码表征任务状态：\n\n'
idx4 = content.find(mark4)
if idx4 >= 0:
    after4 = content[idx4 + len(mark4):]
    lines4 = after4.split('\n')
    part4 = []
    for i, line in enumerate(lines4):
        if line.startswith('| '):
            if i == 0:
                part4.append('表4  任务规划域六爻编码')
            part4.append(line)
        else:
            break
    if part4:
        content = content[:idx4 + len(mark4)] + '\n'.join(part4) + '\n' + '\n'.join(lines4[len(part4):])

# 表5: 实验结果
mark5 = '表5  全量134场景实验数据\n\n'
# 已经由之前的替换加上了
if '表5  全量134场景实验数据' not in content:
    # 在"4.2 总体结果"下找到结果表
    mark5pos = content.find('| pick_clean_then_place_in_recep')
    if mark5pos >= 0:
        # 找表前
        pre_lines = content[:mark5pos].split('\n')
        # 找到上一个非空行
        for i in range(len(pre_lines)-1, -1, -1):
            if pre_lines[i].strip():
                pre_lines.insert(i+1, '表5  全量134场景实验数据')
                break
        content = '\n'.join(pre_lines) + content[mark5pos:]

# 表6: 易理与硬编码分界
mark6 = '当前最主要的硬编码瓶颈是'
idx6 = content.find(mark6) 
if idx6 >= 0:
    # 找前面的表格
    prefix = content[:idx6]
    last_table = prefix.rfind('| 知几学习')
    if last_table >= 0:
        # 在表格前加编号
        table_start = prefix.rfind('\n\n', 0, last_table) + 2
        table_line = prefix[table_start:]
        if table_line.startswith('| '):
            content = content[:table_start] + '表6  易理框架与工程硬编码的分界\n\n' + content[table_start:]

# 清理多余的空行
content = re.sub(r'\n{3,}', '\n\n', content)

with open('YLYW_obs_only_task_planning_paper.md', 'w', encoding='utf-8') as f:
    f.write(content)

print('OK')
