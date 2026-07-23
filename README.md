# Mini LLM Demo — 迷你中文 GPT

从零实现的轻量级 GPT 解码器，**纯 CPU 可运行**，集成现代 LLM 核心技术，
训练数据为 10 本中文网络小说（50 万字混合）。

## 特性

- **纯字符级 Tokenizer**（含 `<UNK>` 容错）
- **RoPE** 旋转位置编码（NTK-aware 缩放 + 动态扩展）
- **RMSNorm** 归一化
- **SwiGLU** 门控激活函数（独立 gate/up 投影）
- **GQA 分组查询注意力**（减少 KV 缓存）
- **滑动窗口注意力**（支持长上下文外推）
- **Flash Attention**（PyTorch 2.0 SDPA）
- **KV Cache** 推理加速 + 隔离保护
- **AdamW** + **Warmup + Cosine Decay** 学习率调度
- **梯度累积** + **混合精度训练**（AMP，CUDA 自动启用）
- **Top-K + Top-P** 双重采样 + **重复惩罚**
- **验证集早停**（10% 数据作验证，patience=10）
- **标签平滑**（Label Smoothing，正则化）
- **权重共享**（Tie Embedding）
- **检查点双指纹校验**（数据/超参变更自动重训）
- **交互式 `--chat` 对话模式**

## 快速开始

```bash
# 安装依赖
pip install torch

# 训练并测试
python mini_llm_demo.py

# 交互式对话
python mini_llm_demo.py --chat

# 强制重新训练
python mini_llm_demo.py --retrain
```

## 系统配置要求

### 最低配置（CPU 训练）

| 配置项 | 要求 | 说明 |
|--------|------|------|
| CPU | 4 核 2.0GHz+ | Intel/AMD x86_64 |
| 内存 | 8GB RAM | 模型加载约 200MB，训练约 2-4GB |
| Python | 3.8+ |  |
| PyTorch | 2.0+ | CPU 版即可 |

### 训练耗时参考（CPU，6 核 12 线程）

| 数据量 | block_size | 模型大小 | 每 epoch | 总时间（50 epoch） |
|--------|-----------|---------|---------|------------------|
| 20 万字 | 256 | 494 万参数 | ~2 分钟 | **~1.7 小时** |
| 50 万字 | 256 | 494 万参数 | ~5 分钟 | **~4.2 小时** |
| 50 万字 | 1024 (sw=256) | 494 万参数 | ~10 分钟 | **~8 小时** |
| 5 万字 | 256 | 494 万参数 | ~30 秒 | **~25 分钟** |

> CPU 型号：Intel 12代 Alder Lake，6 P-core + 6 E-core

### 配置建议

**追求速度（5-10 分钟）：**
```python
MAX_TRAIN_CHARS = 30000    # 3 万字
max_epochs = 30            # 30 轮
```

**平衡（1-2 小时）：**
```python
# preprocess.py 中
MAX_TRAIN_CHARS = 200000   # 20 万字
# Config 中
max_epochs = 30            # 30 轮
```

**最佳质量（4+ 小时，可挂着跑）：**
```python
# preprocess.py 中
MAX_TRAIN_CHARS = 500000   # 50 万字
# Config 中
max_epochs = 50            # 50 轮
```

### GPU 加速

如使用 CUDA GPU（需安装 CUDA 版 PyTorch），训练速度可提升 **5-10 倍**。
GPU 会自动检测，无需任何配置修改。

```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

## 项目文件

| 文件 | 说明 |
|------|------|
| `mini_llm_demo.py` | 主脚本：模型定义、训练、生成、对话 |
| `preprocess.py` | 文本预处理（去 BOM、去网页残留、过滤短行、多文件合并） |
| `cleaned_novel.txt` | 清洗后的合并训练文本（50 万字） |
| `mini_llm_checkpoint.pt` | 训练好的模型检查点（自动管理） |
| `README.md` | 本文件 |

## 架构参数（当前默认）

| 组件 | 值 |
|------|-----|
| `embed_dim` | 192 |
| `n_heads` / `n_kv_heads` | 4 / 2（GQA） |
| `block_size` | 256 |
| `sliding_window` | None（全局注意） |
| `n_layers` | 8 |
| 参数量 | **4,942,848（约 494 万）** |
| 训练数据 | 10 本小说混合，50 万字清洗文本 |

## 技术清单

- CharTokenizer + UNK 容错
- RMSNorm（Root Mean Square Layer Normalization）
- RoPE 旋转位置编码（NTK-aware 缩放）
- SwiGLU 门控激活（独立 gate/up 投影）
- GQA 分组查询注意力
- 滑动窗口注意力
- Flash Attention（PyTorch `scaled_dot_product_attention`）
- KV Cache + 调用隔离
- Top-K + Top-P 双重采样
- 重复惩罚（Repetition Penalty）
- AdamW 解耦权重衰减
- Warmup + Cosine Decay 学习率调度
- 梯度累积（Gradient Accumulation）
- 标签平滑（Label Smoothing）
- Dropout 正则化
- 梯度裁剪（Gradient Clipping）
- 混合精度训练（AMP）
- 权重共享（Tie Embedding）
- 验证集早停（Patience=10）
- 检查点数据指纹 + 超参指纹
- torch.compile 支持（CUDA + Linux）

## 依赖

- Python 3.8+
- PyTorch 2.0+（CPU 版即可）
- `tqdm`（可选，无则自动降级）
