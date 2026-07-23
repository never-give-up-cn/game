# Mini LLM Demo — 迷你中文 GPT

从零实现的轻量级 GPT 解码器，**纯 CPU 可运行**，集成现代 LLM 核心技术，
训练数据为中文网络小说《校花的贴身高手》（鱼人二代）。

## 特性

- **纯字符级 Tokenizer**（含 `<UNK>` 容错）
- **RoPE** 旋转位置编码
- **RMSNorm** 归一化
- **SwiGLU** 门控激活函数
- **Flash Attention**（PyTorch 2.0 SDPA）
- **KV Cache** 推理加速 + 隔离保护
- **AdamW** + **Warmup + Cosine Decay** 学习率调度
- **混合精度训练**（AMP，CUDA 自动启用）
- **Top-K + Top-P** 双重采样 + **重复惩罚**
- **验证集早停**（10% 数据作验证）
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

## 架构参数

| 组件 | 值 |
|------|-----|
| `embed_dim` | 192 |
| `n_heads` | 4 |
| `block_size` | 256 |
| `n_layers` | 8 |
| 参数量 | ~120 万 |
| 训练数据 | 清洗后 20 万字小说 |

## 项目文件

| 文件 | 说明 |
|------|------|
| `mini_llm_demo.py` | 主脚本：模型定义、训练、生成 |
| `preprocess.py` | 文本预处理（去 BOM、去网页残留、过滤短行） |
| `cleaned_novel.txt` | 清洗后的训练文本（20 万字） |
| `alice_in_wonderland.txt` | 备选英文训练文本 |
| `mini_llm_checkpoint.pt` | 训练好的模型检查点（自动管理） |

## 技术清单

- CharTokenizer + UNK 容错
- RMSNorm（Root Mean Square Layer Normalization）
- RoPE 旋转位置编码
- SwiGLU 门控激活函数
- Flash Attention（PyTorch `scaled_dot_product_attention`）
- KV Cache + 调用隔离
- Top-K + Top-P 双重采样
- 重复惩罚（Repetition Penalty）
- AdamW 解耦权重衰减
- Warmup + Cosine Decay 学习率调度
- Dropout 正则化
- 梯度裁剪（Gradient Clipping）
- 混合精度训练（AMP）
- 验证集早停（Patience=10）
- 检查点数据指纹 + 超参指纹

## 依赖

- Python 3.8+
- PyTorch 2.0+（CPU 版即可）
- `tqdm`（可选，无则自动降级）
