"""
文本预处理脚本：清洗《校花的贴身高手》原始 TXT
输出到 cleaned_novel.txt 供训练使用
"""
import re

with open("校花的贴身高手.txt", "r", encoding="utf-8") as f:
    text = f.read()

# 1. 去除 BOM 和首尾空白
text = text.lstrip("﻿").strip()

# 2. 统一换行符
text = text.replace("\r\n", "\n").replace("\r", "\n")

# 3. 合并连续的全角/半角空白为单个半角空格
text = re.sub(r'[　 \t]+', ' ', text)

# 4. 去除多余换行（两个以上换行合并为两个）
text = re.sub(r'\n{3,}', '\n\n', text)

# 5. 去掉明显的网页残留（如 HTML 标签、广告链接等）
text = re.sub(r'<[^>]+>', '', text)
text = re.sub(r'http[s]?://\S+', '', text)
text = re.sub(r'（本章完）|手机用户请浏览.*|最新章节.*', '', text)

# 6. 删除纯符号短行（长度<2 且不含中文字）
lines = text.split("\n")
cleaned_lines = []
for line in lines:
    line = line.strip()
    if len(line) >= 2 and re.search(r'[一-鿿]', line):
        cleaned_lines.append(line)
text = "\n".join(cleaned_lines)

# 7. 截取所需长度（20 万字符）
text = text[:200000]

# 8. 保存清洗后文件
with open("cleaned_novel.txt", "w", encoding="utf-8") as f:
    f.write(text)

print(f"清洗完成：{len(text):,} 字符")
print(f"首 200 字：{text[:200]}")
