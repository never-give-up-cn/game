"""
文本预处理脚本：清洗项目下所有 TXT 小说，合并输出到 cleaned_novel.txt
自动排除已清洗文件自身。
"""

import os, re, glob

# ========================== 配置 ==========================
OUTPUT_FILE = "cleaned_novel.txt"
MAX_TRAIN_CHARS = 500000  # 总训练字符上限（None = 不限）
EXCLUDE = {OUTPUT_FILE, "alice_in_wonderland.txt"}  # 排除的文件


def clean_text(text):
    """清洗单段文本"""
    # 1. 去 BOM 和首尾空白
    text = text.lstrip("﻿").strip()
    # 2. 统一换行符
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # 3. 合并连续空白为单个半角空格
    text = re.sub(r'[　 \t]+', ' ', text)
    # 4. 合并多余换行（≥3个换行 → 2个）
    text = re.sub(r'\n{3,}', '\n\n', text)
    # 5. 去网页残留
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'http[s]?://\S+', '', text)
    text = re.sub(r'（本章完）|手机用户请浏览.*|最新章节.*', '', text)
    # 6. 过滤无意义短行
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        line = line.strip()
        if len(line) >= 2 and re.search(r'[一-鿿]', line):
            cleaned.append(line)
    return "\n".join(cleaned)


def main():
    # 发现所有 txt 文件
    txt_files = sorted(glob.glob("*.txt"))
    txt_files = [f for f in txt_files if f not in EXCLUDE]
    print(f"发现 {len(txt_files)} 个 TXT 文件：")
    for f in txt_files:
        size = os.path.getsize(f)
        print(f"  {f} ({size/1024/1024:.1f}MB)")

    # 逐个清洗，写入临时文件避免反复拼接内存爆炸
    temp_file = OUTPUT_FILE + ".tmp"
    total_written = 0

    for fname in txt_files:
        try:
            raw = open(fname, 'r', encoding='utf-8', errors='replace').read()
        except Exception as e:
            print(f"  ! 跳过 {fname}: {e}")
            continue

        cleaned = clean_text(raw)
        if not cleaned:
            continue

        # 按比例截取（均匀分配总预算）
        if MAX_TRAIN_CHARS is not None:
            max_per_file = max(100000, MAX_TRAIN_CHARS // len(txt_files))
            if len(cleaned) > max_per_file:
                print(f"  {fname}: {len(cleaned):,} → 截取 {max_per_file:,}")
                cleaned = cleaned[:max_per_file]
            else:
                print(f"  {fname}: {len(cleaned):,}")
        else:
            print(f"  {fname}: {len(cleaned):,}")

        # 追加写入
        with open(temp_file, 'a', encoding='utf-8') as out:
            out.write(cleaned)
            out.write("\n")
        total_written += len(cleaned)

    # 读取合并结果，做最终截取
    if os.path.exists(temp_file):
        combined = open(temp_file, 'r', encoding='utf-8').read()
        if MAX_TRAIN_CHARS is not None and len(combined) > MAX_TRAIN_CHARS:
            combined = combined[:MAX_TRAIN_CHARS]
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write(combined)
        os.remove(temp_file)
        print(f"\n合并完成: {OUTPUT_FILE} ({len(combined):,} 字符)")
        print(f"首 100 字: {combined[:100].encode('utf-8', errors='replace').decode('utf-8')}")
    else:
        print("没有生成任何训练数据")


if __name__ == "__main__":
    main()
