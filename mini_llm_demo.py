"""
增强版迷你 LLM（Mini GPT Demo）— 现代 LLM 技术全演示
=====================================================
在保持单文件、纯 CPU/GPU 可运行的前提下，
集成了现代大型语言模型的核心技术。

核心技术
  ✓ 字符级 Tokenizer（CharTokenizer）
  ✓ RoPE 旋转位置编码（Rotary Position Embedding）
  ✓ RMSNorm 归一化（替代 LayerNorm）
  ✓ SwiGLU 门控激活函数（替代 GELU）
  ✓ Flash Attention（PyTorch 2.0 SDPA + 因果掩码）
  ✓ KV Cache（推理阶段加速，附对比）

训练技术
  ✓ AdamW 优化器（解耦权重衰减）
  ✓ 学习率 Warmup + Cosine Decay 调度
  ✓ Dropout 正则化
  ✓ 梯度裁剪（Gradient Clipping）
  ✓ 混合精度训练（AMP，仅 CUDA 时启用）
"""

import io, os, sys, time, math, argparse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, TensorDataset

try:
    from tqdm import tqdm
except ImportError:
    # 简单回退：逐行输出进度
    def tqdm(iterable, desc="", **kwargs):
        total = kwargs.get('total') or (len(iterable) if hasattr(iterable, '__len__') else None)
        if total:
            print(f"  {desc}: 0/{total} (0%)")
            for i, item in enumerate(iterable):
                cur = i + 1
                if cur % max(1, total // 10) == 0 or cur == total:
                    print(f"\r  {desc}: {cur}/{total} ({cur*100//total}%)", end="", flush=True)
                yield item
            print()
        else:
            for item in iterable:
                yield item

# ========================== 超参数 ==========================
class Config:
    embed_dim = 64          # 嵌入维度
    n_heads = 4             # 注意力头数
    head_dim = embed_dim // n_heads  # 每头维度
    block_size = 64         # 上下文窗口
    n_layers = 4            # Transformer 层数
    dropout = 0.1           # Dropout 比例
    lr = 5e-4               # 峰值学习率
    weight_decay = 0.1      # AdamW 权重衰减
    warmup_iters = 30       # Warmup 步数
    max_epochs = 30         # 训练轮数
    grad_clip = 1.0         # 梯度裁剪阈值
    batch_size = 8          # 批次大小
    device = "cuda" if torch.cuda.is_available() else "cpu"


# ========================== 训练文本 ==========================
CN_NOVEL_FILE = os.path.join(os.path.dirname(__file__) or ".", "校花的贴身高手.txt")
EN_ALICE_FILE = os.path.join(os.path.dirname(__file__) or ".", "alice_in_wonderland.txt")
MAX_TRAIN_CHARS = 50000  # 截取前 N 字符（None = 全量）


def _load_training_text():
    """依次尝试加载中文小说 → 英文爱丽丝 → 默认回退"""

    # 1) 优先加载中文小说
    if os.path.exists(CN_NOVEL_FILE):
        print(f"  ✓ 加载中文训练文本: {CN_NOVEL_FILE}")
        text = open(CN_NOVEL_FILE, 'r', encoding='utf-8').read()
        # 去掉 BOM
        if text.startswith('﻿'):
            text = text[1:]
        if MAX_TRAIN_CHARS is not None and len(text) > MAX_TRAIN_CHARS:
            print(f"  文本过长 ({len(text):,} 字符)，截取前 {MAX_TRAIN_CHARS:,} 字符")
            text = text[:MAX_TRAIN_CHARS]
        return text.strip()

    # 2) 回退：英文爱丽丝漫游仙境
    if os.path.exists(EN_ALICE_FILE):
        print(f"  ✓ 加载英文训练文本: {EN_ALICE_FILE}")
        text = open(EN_ALICE_FILE, 'r', encoding='utf-8').read()
        start = text.find("*** START")
        end = text.find("*** END")
        if start != -1:
            text = text[start:]
        if end != -1:
            text = text[:end]
        first_content = text.find("***")
        if first_content != -1:
            text = text[first_content:]
            text = text.split("\n", 1)[-1] if "\n" in text else text
        return text.strip()

    # 3) 最终回退
    print(f"  ⚠ 未找到训练文本文件，使用默认简短文本")
    return (
        "Alice was beginning to get very tired of sitting by her sister on the bank, "
        "and of having nothing to do: once or twice she had peeped into the book her "
        "sister was reading, but it had no pictures or conversations in it, "
        "\"and what is the use of a book,\" thought Alice \"without pictures or conversations?\""
    )


TRAIN_TEXT = _load_training_text()


# ======================== 1. 字符级 Tokenizer ========================
class CharTokenizer:
    """字符级 Tokenizer — 演示用
    将文本按字符切分，建立字符 ↔ ID 的映射。
    真实 LLM 使用 BPE / SentencePiece 等子词分词器。
    """
    def __init__(self, text):
        chars = sorted(set(text))
        self.vocab_size = len(chars)
        self.stoi = {ch: i for i, ch in enumerate(chars)}  # char → id
        self.itos = {i: ch for i, ch in enumerate(chars)}  # id → char

    def encode(self, s):
        """将字符串转为 token ID 列表"""
        return [self.stoi[c] for c in s]

    def decode(self, ids):
        """将 token ID 列表还原为字符串"""
        return ''.join(self.itos[i] for i in ids)

    def __repr__(self):
        return f"CharTokenizer(vocab_size={self.vocab_size})"


# ======================== 2. RMSNorm ========================
class RMSNorm(nn.Module):
    """Root Mean Square Layer Normalization
    相比 LayerNorm 省去了均值计算（居中步骤），
    是 Llama、Mistral 等现代 LLM 的默认归一化方案。
    公式: output = x * rsqrt(mean(x²) + eps) * weight
    """
    def __init__(self, dim, eps=1e-6):
        super().__init__()
        self.eps = eps
        self.weight = nn.Parameter(torch.ones(dim))

    def forward(self, x):
        # x: (B, T, dim)
        rms = torch.sqrt(x.pow(2).mean(dim=-1, keepdim=True) + self.eps)
        return x / rms * self.weight


# ======================== 3. RoPE 旋转位置编码 ========================
def precompute_rope_freqs(dim, max_seq_len, theta=10000.0):
    """预计算 RoPE 的 cos/sin 查找表
    RoPE 通过旋转矩阵编码位置信息，
    相比可学习位置嵌入，具有更好的外推能力。
    """
    dim = dim // 2  # 每个 pair 共享一个频率
    freqs = 1.0 / (theta ** (torch.arange(0, dim, dtype=torch.float32) / dim))
    t = torch.arange(max_seq_len, dtype=torch.float32)
    freqs = torch.outer(t, freqs)  # (max_seq_len, dim)
    return freqs.cos(), freqs.sin()  # 各 (max_seq_len, dim)

def apply_rope(x, cos, sin):
    """对 Q 或 K 应用 RoPE 旋转
    x:   (B, nh, T, hs) 或 (B, T, D)
    cos: (T, hs//2)
    sin: (T, hs//2)

    对每对维度 (x_i, x_{i+hs//2}) 执行二维旋转:
      x'_i     = x_i * cos - x_{i+hs//2} * sin
      x'_{i+hs//2} = x_i * sin + x_{i+hs//2} * cos
    """
    half = x.shape[-1] // 2
    x1, x2 = x[..., :half], x[..., half:]
    cos = cos[:x.shape[-2], ...]  # 截取到当前序列长度
    sin = sin[:x.shape[-2], ...]
    # 对齐维度方便广播
    while cos.dim() < x.dim():
        cos, sin = cos.unsqueeze(0), sin.unsqueeze(0)
    x_rotated = torch.cat([x1 * cos - x2 * sin, x1 * sin + x2 * cos], dim=-1)
    return x_rotated


# ======================== 4. SwiGLU 门控激活 ========================
class SwiGLU(nn.Module):
    """Swish-Gated Linear Unit
    SwiGLU(x) = silu(x @ W_gate) * (x @ W_value)
    相比 GELU 在相同参数量下效果更好，是 PaLM、Llama 等使用的 FFN 变体。

    实现方式：单个 Linear 输出 2×hidden_dim，
    然后 chunk 为 gate 和 value 两部分相乘。
    """
    def __init__(self, hidden_dim):
        super().__init__()
        self.hidden_dim = hidden_dim

    def forward(self, x):
        gate, value = x.chunk(2, dim=-1)
        return F.silu(gate) * value


# ======================== 5. 多头自注意力 ========================
class MultiHeadAttention(nn.Module):
    """多头自注意力（集成 RoPE + Flash Attention + KV Cache）

    现代 LLM 注意力层的标准实现，包含：
    - RoPE 位置编码（替代可学习位置嵌入）
    - PyTorch 2.0 Flash Attention（`scaled_dot_product_attention`）
    - KV Cache 支持（推理时缓存 K/V 矩阵避免重复计算）
    - Dropout 正则化
    """
    def __init__(self, config: Config):
        super().__init__()
        self.n_heads = config.n_heads
        self.head_dim = config.head_dim
        self.embed_dim = config.embed_dim
        self.dropout_p = config.dropout

        # QKV 统一投影
        self.qkv = nn.Linear(config.embed_dim, config.embed_dim * 3, bias=False)
        # 输出投影
        self.proj = nn.Linear(config.embed_dim, config.embed_dim, bias=False)

        # 预计算 RoPE 表
        cos, sin = precompute_rope_freqs(self.head_dim, config.block_size)
        self.register_buffer("cos", cos, persistent=False)
        self.register_buffer("sin", sin, persistent=False)

    def forward(self, x, kv_cache=None):
        """
        x: (B, T, embed_dim)
        kv_cache: {'k': Tensor | None, 'v': Tensor | None} — 推理缓存
        """
        B, T, C = x.shape

        # 1) QKV 投影
        qkv = self.qkv(x).split(self.embed_dim, dim=-1)
        q, k, v = qkv  # 各 (B, T, embed_dim)

        # 2) 分头: (B, nh, T, hs)
        q = q.view(B, T, self.n_heads, self.head_dim).transpose(1, 2)
        k = k.view(B, T, self.n_heads, self.head_dim).transpose(1, 2)
        v = v.view(B, T, self.n_heads, self.head_dim).transpose(1, 2)

        # 3) RoPE（对 Q 和 K 应用旋转位置编码）
        q = apply_rope(q, self.cos, self.sin)
        k = apply_rope(k, self.cos, self.sin)

        # 4) KV Cache
        if kv_cache is not None:
            # 首次调用时 cache 为 None，后续调用拼接历史 K/V
            if kv_cache['k'] is not None:
                k = torch.cat([kv_cache['k'], k], dim=2)
                v = torch.cat([kv_cache['v'], v], dim=2)
            kv_cache['k'] = k
            kv_cache['v'] = v

        # 5) Flash Attention（PyTorch 2.0 SDPA）
        # is_causal=True 自动生成上三角因果掩码
        # 当使用 KV Cache 且 T_q=1 时不需要掩码（已是最新位置）
        is_causal = (kv_cache is None) and (T > 1)
        attn_out = F.scaled_dot_product_attention(
            q, k, v,
            dropout_p=self.dropout_p if self.training else 0.0,
            is_causal=is_causal,
        )

        # 6) 合并头 + 输出投影
        out = attn_out.transpose(1, 2).contiguous().view(B, T, C)
        return self.proj(out)


# ======================== 6. Transformer 块 ========================
class TransformerBlock(nn.Module):
    """Transformer 解码器块
    Pre-Norm 结构：先归一化再进入子层，残差连接在外。
    顺序: RMSNorm → Attention → 残差 → RMSNorm → SwiGLU FFN → 残差
    """
    def __init__(self, config: Config):
        super().__init__()
        self.ln1 = RMSNorm(config.embed_dim)
        self.ln2 = RMSNorm(config.embed_dim)
        self.attn = MultiHeadAttention(config)

        # SwiGLU FFN: Linear → SwiGLU → Linear
        hidden_dim = int(config.embed_dim * 4)
        self.mlp = nn.Sequential(
            nn.Linear(config.embed_dim, hidden_dim * 2, bias=False),  # 2× 给 SwiGLU 门控
            SwiGLU(hidden_dim),
            nn.Linear(hidden_dim, config.embed_dim, bias=False),
        )
        self.dropout = nn.Dropout(config.dropout)

    def forward(self, x, kv_cache=None):
        x = x + self.dropout(self.attn(self.ln1(x), kv_cache=kv_cache))
        x = x + self.dropout(self.mlp(self.ln2(x)))
        return x


# ======================== 7. MiniLLM 模型 ========================
class MiniLLM(nn.Module):
    """迷你 LLM — 现代 GPT 解码器架构

    架构: Token Embedding → N×TransformerBlock → RMSNorm → Linear Head
    注意：位置信息通过 RoPE 编码（在 Attention 内部），
    因此不再需要可学习的位置嵌入。
    """
    def __init__(self, config: Config, vocab_size: int):
        super().__init__()
        self.config = config
        self.vocab_size = vocab_size

        self.token_emb = nn.Embedding(vocab_size, config.embed_dim)
        self.blocks = nn.ModuleList([
            TransformerBlock(config) for _ in range(config.n_layers)
        ])
        self.ln_final = RMSNorm(config.embed_dim)
        self.head = nn.Linear(config.embed_dim, vocab_size, bias=False)

        # 权重初始化（现代 LLM 的标准做法）
        self.apply(self._init_weights)

    def _init_weights(self, module):
        if isinstance(module, nn.Linear):
            nn.init.normal_(module.weight, mean=0.0, std=0.02)
            if module.bias is not None:
                nn.init.zeros_(module.bias)
        elif isinstance(module, nn.Embedding):
            nn.init.normal_(module.weight, mean=0.0, std=0.02)

    def forward(self, idx, kv_caches=None):
        """
        idx: (B, T) token ID 序列
        kv_caches: list[dict | None] — 各层的 KV 缓存
        """
        B, T = idx.shape
        x = self.token_emb(idx)  # (B, T, embed_dim)

        for i, block in enumerate(self.blocks):
            cache = kv_caches[i] if kv_caches is not None else None
            x = block(x, kv_cache=cache)

        x = self.ln_final(x)
        logits = self.head(x)  # (B, T, vocab_size)
        return logits

    @torch.no_grad()
    def generate(self, idx, max_new_tokens, use_kv_cache=False, temperature=1.0, top_k=None):
        """自回归生成文本

        Args:
            idx: (B, T) 初始 prompt token
            max_new_tokens: 生成的新 token 数
            use_kv_cache: 是否使用 KV Cache 加速
            temperature: 采样温度（>1 更随机，<1 更确定）
            top_k: 只从概率最高的 k 个 token 中采样
        """
        if use_kv_cache:
            return self._generate_with_cache(idx, max_new_tokens, temperature, top_k)
        else:
            return self._generate_no_cache(idx, max_new_tokens, temperature, top_k)

    def _generate_no_cache(self, idx, max_new_tokens, temperature, top_k):
        """无 KV Cache 的朴素生成（每步重新计算所有位置）"""
        for _ in range(max_new_tokens):
            idx_crop = idx[:, -self.config.block_size:]
            logits = self(idx_crop)  # (B, T, vocab_size)
            logits = logits[:, -1, :] / temperature  # 取最后一位

            # Top-K 采样
            if top_k is not None:
                v, _ = torch.topk(logits, min(top_k, logits.size(-1)))
                logits[logits < v[:, [-1]]] = float('-inf')

            probs = F.softmax(logits, dim=-1)
            next_token = torch.multinomial(probs, num_samples=1)
            idx = torch.cat((idx, next_token), dim=1)
        return idx

    def _generate_with_cache(self, idx, max_new_tokens, temperature, top_k):
        """使用 KV Cache 加速生成
        首次前向处理完整 prompt 并缓存 K/V，
        后续每步只处理最后 1 个 token。
        """
        # 初始化各层的 KV 缓存
        kv_caches = [{'k': None, 'v': None} for _ in range(self.config.n_layers)]

        generated = idx.clone()
        B, T = idx.shape

        # 第一步：处理 prompt（完整序列，填充缓存）
        logits = self(idx, kv_caches=kv_caches)
        next_logit = logits[:, -1, :] / temperature

        if top_k is not None:
            v, _ = torch.topk(next_logit, min(top_k, next_logit.size(-1)))
            next_logit[next_logit < v[:, [-1]]] = float('-inf')

        probs = F.softmax(next_logit, dim=-1)
        next_token = torch.multinomial(probs, num_samples=1)
        generated = torch.cat((generated, next_token), dim=1)

        # 后续步骤：每次只送入最后 1 个 token
        for _ in range(max_new_tokens - 1):
            logits = self(next_token, kv_caches=kv_caches)  # T=1
            next_logit = logits[:, -1, :] / temperature

            if top_k is not None:
                v, _ = torch.topk(next_logit, min(top_k, next_logit.size(-1)))
                next_logit[next_logit < v[:, [-1]]] = float('-inf')

            probs = F.softmax(next_logit, dim=-1)
            next_token = torch.multinomial(probs, num_samples=1)
            generated = torch.cat((generated, next_token), dim=1)

        return generated


# ======================== 8. 数据准备 ========================
def prepare_data(text, tokenizer, config: Config):
    """将文本切分为重叠的 (input, target) 序列对"""
    tokens = tokenizer.encode(text)
    print(f"  文本长度: {len(text)} 字符, {len(tokens)} tokens")

    # 滑动窗口创建序列（50% 重叠）
    stride = config.block_size // 2
    seqs = []
    for i in range(0, len(tokens) - config.block_size, stride):
        seq = tokens[i:i + config.block_size + 1]
        seqs.append(seq)

    data = torch.tensor(seqs, dtype=torch.long)
    x = data[:, :-1]  # 输入
    y = data[:, 1:]   # 目标（右移一位）

    dataset = TensorDataset(x, y)
    loader = DataLoader(dataset, batch_size=config.batch_size, shuffle=True)
    print(f"  生成 {len(dataset)} 条序列, {len(loader)} 批次/轮")
    return loader


# ======================== 9. 学习率调度（Warmup + Cosine） ========================
class WarmupCosineLR:
    """学习率 Warmup + Cosine Decay 调度器
    前 warmup_iters 步线性从 0 升到 peak_lr，
    后按半余弦曲线衰减到 min_lr。
    """
    def __init__(self, optimizer, warmup_iters, max_iters, peak_lr, min_lr=0):
        self.optimizer = optimizer
        self.warmup_iters = warmup_iters
        self.max_iters = max_iters
        self.peak_lr = peak_lr
        self.min_lr = min_lr
        self.current_lr = 0.0

    def step(self, it):
        if it < self.warmup_iters:
            # 线性上升
            self.current_lr = self.peak_lr * it / max(1, self.warmup_iters)
        else:
            # Cosine 衰减
            progress = (it - self.warmup_iters) / max(1, self.max_iters - self.warmup_iters)
            self.current_lr = self.min_lr + 0.5 * (self.peak_lr - self.min_lr) * (
                1 + math.cos(math.pi * progress)
            )
        for param_group in self.optimizer.param_groups:
            param_group['lr'] = self.current_lr

    def get_lr(self):
        return self.current_lr


MODEL_PATH = os.path.join(os.path.dirname(__file__) or ".", "mini_llm_checkpoint.pt")


def save_checkpoint(model, tokenizer, train_text, path=MODEL_PATH):
    """保存模型权重 + tokenizer + 数据指纹 到文件"""
    checkpoint = {
        'model_state_dict': model.state_dict(),
        'vocab_size': tokenizer.vocab_size,
        'stoi': tokenizer.stoi,
        'itos': tokenizer.itos,
        'data_hash': hash(train_text),  # 训练文本指纹，用于检测数据是否变更
    }
    torch.save(checkpoint, path)
    print(f"  ✓ 模型已保存到 {path}")


def load_checkpoint(path, train_text, device='cpu'):
    """从文件加载模型权重和 tokenizer，校验数据指纹"""
    checkpoint = torch.load(path, map_location=device, weights_only=True)
    # 校验训练文本是否一致（数据变了就忽略缓存）
    if checkpoint.get('data_hash') != hash(train_text):
        print(f"  ⚠ 训练数据已变更，忽略旧缓存")
        return None, None
    tokenizer = CharTokenizer.__new__(CharTokenizer)
    tokenizer.vocab_size = checkpoint['vocab_size']
    tokenizer.stoi = checkpoint['stoi']
    tokenizer.itos = {int(k): v for k, v in checkpoint['itos'].items()}
    return checkpoint['model_state_dict'], tokenizer


# ======================== 10. 主程序 ========================
def main():
    config = Config()
    parser = argparse.ArgumentParser(description="迷你 LLM 演示")
    parser.add_argument('--retrain', action='store_true',
                        help='强制重新训练（默认：已有检查点时跳过训练）')
    args = parser.parse_args()
    print("=" * 60)
    print("  增强版迷你 LLM — 现代 LLM 技术全演示")
    print("=" * 60)

    # ---- 1. 初始化 Tokenizer ----
    print("\n[1/5] 初始化 Tokenizer...")
    tokenizer = CharTokenizer(TRAIN_TEXT)
    print(f"  {tokenizer}")
    vocab_size = tokenizer.vocab_size

    # ---- 2. 创建模型 ----
    print("\n[2/5] 创建模型...")
    model = MiniLLM(config, vocab_size).to(config.device)
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"  设备: {config.device}")
    print(f"  总参数量: {total_params:,} ({total_params/1e3:.1f}K)")
    print(f"  可训练参数: {trainable_params:,} ({trainable_params/1e3:.1f}K)")
    print(f"  架构: {config.n_layers} 层 × {config.n_heads} 头, "
          f"embed_dim={config.embed_dim}, block_size={config.block_size}")

    # ---- 检查是否有保存的模型 + 训练 ----
    need_train = True
    if os.path.exists(MODEL_PATH) and not args.retrain:
        print(f"\n  发现已保存模型 ({MODEL_PATH})，加载中...")
        state_dict, _ = load_checkpoint(MODEL_PATH, TRAIN_TEXT, config.device)
        if state_dict is not None:
            model.load_state_dict(state_dict)
            print(f"  ✓ 已加载训练好的模型，跳过训练")
            need_train = False
        else:
            print(f"  → 训练数据已变更，将重新训练")
    elif args.retrain:
        print(f"\n  --retrain 参数指定，重新训练...")

    if need_train:
        # ---- 3. 数据准备 ----
        print("\n[3/5] 准备数据...")
        train_loader = prepare_data(TRAIN_TEXT, tokenizer, config)

        # ---- 4. 训练 ----
        print("\n[4/5] 开始训练...")

        # 优化器: AdamW（带解耦权重衰减）
        optimizer = torch.optim.AdamW(
            model.parameters(),
            lr=config.lr,
            weight_decay=config.weight_decay,
            betas=(0.9, 0.95),
        )

        # 学习率调度器
        total_iters = config.max_epochs * len(train_loader)
        scheduler = WarmupCosineLR(
            optimizer,
            warmup_iters=config.warmup_iters,
            max_iters=total_iters,
            peak_lr=config.lr,
            min_lr=config.lr * 0.1,
        )

        # 混合精度（仅 CUDA 时启用）
        use_amp = (config.device == "cuda")
        scaler = torch.amp.GradScaler(config.device, enabled=use_amp)

        loss_fn = nn.CrossEntropyLoss()

        # 训练循环
        model.train()
        step = 0
        overall_pct_interval = max(1, total_iters // 100)
        for epoch in range(1, config.max_epochs + 1):
            epoch_loss = 0.0
            num_batches = 0

            for x, y in tqdm(train_loader, desc=f"  Epoch {epoch:3d}/{config.max_epochs}", leave=False):
                x, y = x.to(config.device), y.to(config.device)

                # 混合精度前向
                with torch.amp.autocast(device_type=config.device, enabled=use_amp):
                    logits = model(x)  # (B, T, vocab_size)
                    loss = loss_fn(logits.view(-1, vocab_size), y.view(-1))

                # 反向传播（AMP scaler）
                scaler.scale(loss).backward()

                # 梯度裁剪
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(), config.grad_clip)

                # 更新参数
                scaler.step(optimizer)
                scaler.update()
                optimizer.zero_grad()

                # 更新学习率
                scheduler.step(step)
                step += 1

                # 显示总体训练百分比
                if step % overall_pct_interval == 0:
                    overall_pct = step / total_iters * 100
                    print(f"    总体训练进度: {overall_pct:.1f}%")

                epoch_loss += loss.item()
                num_batches += 1

            avg_loss = epoch_loss / num_batches
            if epoch % 10 == 0 or epoch == 1 or epoch == config.max_epochs:
                print(f"    Epoch {epoch:3d}/{config.max_epochs} ({epoch/config.max_epochs*100:.0f}%), "
                      f"Loss: {avg_loss:.4f}, "
                      f"LR: {scheduler.get_lr():.6f}")

        # 训练完成后保存模型到文件（下次启动直接加载）
        save_checkpoint(model, tokenizer, TRAIN_TEXT)

    # ---- 5. 生成测试 ----
    print("\n[5/5] 生成测试...")

    # 训练前：用同一个模型（刚初始化时），但我们已经训练完了。
    # 无法展示"训练前"状态，但可以用一个随机初始化的副本来对比。
    # 更简单的方式：用训练好的模型生成几个不同 prompt 的结果。

    model.eval()

    # 测试 prompt（从训练文本中选取）
    test_prompts = [
        "校花的贴身高手",
        "一个大山里走出来的",
        "林逸是一名",
        "内容简介",
    ]

    print("\n  --- 训练后生成 ---")
    for prompt in test_prompts:
        prompt_ids = torch.tensor(
            [tokenizer.encode(prompt)], dtype=torch.long, device=config.device
        )
        out = model.generate(
            prompt_ids,
            max_new_tokens=40,
            use_kv_cache=True,
            temperature=0.5,
            top_k=10,
        )
        generated_text = tokenizer.decode(out[0].tolist())
        print(f"\n  Prompt: \"{prompt}\"")
        print(f"  生成:   {generated_text}")

    # ---- 6. KV Cache 速度对比 ----
    print("\n  --- KV Cache 速度对比 ---")
    prompt_ids = torch.tensor(
        [tokenizer.encode("校花的贴身")], dtype=torch.long, device=config.device
    )

    # 无缓存
    torch.cuda.synchronize() if config.device == "cuda" else None
    start = time.time()
    _ = model.generate(prompt_ids, max_new_tokens=100, use_kv_cache=False, temperature=0.5)
    torch.cuda.synchronize() if config.device == "cuda" else None
    time_no_cache = time.time() - start

    # 有缓存
    torch.cuda.synchronize() if config.device == "cuda" else None
    start = time.time()
    _ = model.generate(prompt_ids, max_new_tokens=100, use_kv_cache=True, temperature=0.5)
    torch.cuda.synchronize() if config.device == "cuda" else None
    time_with_cache = time.time() - start

    print(f"  无 KV Cache: {time_no_cache:.3f}s")
    print(f"  有 KV Cache: {time_with_cache:.3f}s")
    print(f"  加速比: {time_no_cache / max(time_with_cache, 1e-6):.1f}x")

    # ---- 总结 ----
    print("\n" + "=" * 60)
    print("  演示结束 — 技术清单")
    print("=" * 60)
    techniques = [
        ("CharTokenizer", "字符级分词"),
        ("RMSNorm", "均方根归一化"),
        ("RoPE", "旋转位置编码"),
        ("SwiGLU", "门控激活函数"),
        ("Flash Attention", "PyTorch 2.0 SDPA"),
        ("KV Cache", "推理加速缓存"),
        ("AdamW", "解耦权重衰减优化器"),
        ("Warmup + Cosine", "学习率调度"),
        ("Dropout", "正则化"),
        ("Gradient Clipping", "梯度裁剪"),
        ("AMP", "混合精度训练"),
    ]
    for name, desc in techniques:
        print(f"  ✓ {name:20s} — {desc}")


if __name__ == "__main__":
    main()
