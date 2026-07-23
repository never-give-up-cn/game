"""
增强版迷你 LLM（Mini GPT Demo）— 现代 LLM 技术全演示
=====================================================
在保持单文件、纯 CPU/GPU 可运行的前提下，
集成了现代大型语言模型的核心技术。

核心技术
  ✓ 字符级 Tokenizer（CharTokenizer，含 UNK 保护）
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

交互功能
  ✓ --chat 交互式中文对话模式
  ✓ 检查点自动校验数据指纹 + 超参指纹
  ✓ Top-K + Top-P 双重采样
  ✓ 未知字符容错
  ✓ 边界保护（短文本、温度溢出、RoPE 越界）
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
    embed_dim = 192         # 嵌入维度（需整除 n_heads）
    n_heads = 4             # 注意力头数
    n_kv_heads = 2          # KV 头数（GQA: < n_heads 时可减少缓存）
    head_dim = embed_dim // n_heads  # 每头维度
    block_size = 256        # 上下文窗口（滑动窗口模式下可设 2048+，NTK-RoPE 支持外推）
    sliding_window = None   # 滑动窗口（None=全局注意，int=每 token 只看前 W 个，支持更长上下文）
    n_layers = 8            # Transformer 层数
    dropout = 0.1           # Dropout 比例
    lr = 3e-4               # 峰值学习率
    weight_decay = 0.1      # AdamW 权重衰减
    warmup_iters = 100      # Warmup 步数
    max_epochs = 50         # 训练轮数
    grad_clip = 1.0         # 梯度裁剪阈值
    batch_size = 8          # 批次大小
    gradient_accumulation_steps = 4  # 梯度累积步数（等效 batch = batch_size × accum）
    label_smoothing = 0.1   # 标签平滑（正则化，防止过拟合）
    compile_model = False   # torch.compile（Windows/CPU 不支持，CUDA/Linux 可开启）
    device = "cuda" if torch.cuda.is_available() else "cpu"


# ========================== 训练文本 ==========================
CN_NOVEL_FILE = os.path.join(os.path.dirname(__file__) or ".", "cleaned_novel.txt")
EN_ALICE_FILE = os.path.join(os.path.dirname(__file__) or ".", "alice_in_wonderland.txt")
MAX_TRAIN_CHARS = 500000  # 截取前 N 字符（None = 全量；与 preprocess.py 的配置一致）


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
UNK_TOKEN = '<UNK>'

class CharTokenizer:
    """字符级 Tokenizer — 演示用
    将文本按字符切分，建立字符 ↔ ID 的映射。
    真实 LLM 使用 BPE / SentencePiece 等子词分词器。
    修复: 遇到未知字符返回 <UNK> 而不是抛 KeyError。
    """
    def __init__(self, text):
        chars = sorted(set(text))
        self.vocab_size = len(chars) + 1  # +1 留给 UNK
        self.stoi = {ch: i for i, ch in enumerate(chars)}
        self.stoi[UNK_TOKEN] = len(chars)  # 最后一位
        self.itos = {i: ch for i, ch in enumerate(chars)}
        self.itos[len(chars)] = UNK_TOKEN
        self.unk_id = self.stoi[UNK_TOKEN]

    def encode(self, s):
        """将字符串转为 token ID 列表，未知字符替换为 UNK"""
        return [self.stoi.get(c, self.unk_id) for c in s]

    def decode(self, ids):
        """将 token ID 列表还原为字符串"""
        return ''.join(self.itos.get(i, UNK_TOKEN) for i in ids)

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
def precompute_rope_freqs(dim, max_seq_len, theta=10000.0, scale=1.0):
    """预计算 RoPE 的 cos/sin 查找表
    RoPE 通过旋转矩阵编码位置信息，
    相比可学习位置嵌入，具有更好的外推能力。

    Args:
        scale: NTK-aware 缩放因子。大于 1 时扩展频率范围，
               使模型在更长序列上保持位置区分度。
               scale = 目标长度 / 训练长度
    """
    dim = dim // 2
    # NTK-aware theta 缩放：保持高频细节，拉伸低频
    if scale > 1.0:
        theta = theta * (scale ** (dim / (dim - 1)))
    freqs = 1.0 / (theta ** (torch.arange(0, dim, dtype=torch.float32) / dim))
    t = torch.arange(max_seq_len, dtype=torch.float32)
    freqs = torch.outer(t, freqs)
    return freqs.cos(), freqs.sin()

def apply_rope(x, cos, sin):
    """对 Q 或 K 应用 RoPE 旋转
    x:   (B, nh, T, hs) 或 (B, T, D)
    cos: (T, hs//2)   — 预计算表
    sin: (T, hs//2)
    若序列长度超过预计算表，自动扩展 RoPE 频率表。
    """
    half = x.shape[-1] // 2
    x1, x2 = x[..., :half], x[..., half:]
    seq_len = x.shape[-2]

    # 越界时动态计算新位置的频率（而非简单复制末尾）
    if seq_len > cos.size(0):
        print(f"  ⚠ RoPE 动态扩展: {cos.size(0)} -> {seq_len}")
        old_len = cos.size(0)
        half_dim = cos.shape[-1]
        # 为新位置计算频率
        freqs = 1.0 / (10000.0 ** (torch.arange(0, half_dim, dtype=torch.float32, device=x.device) / half_dim))
        new_t = torch.arange(old_len, seq_len, dtype=torch.float32, device=x.device)
        new_freqs = torch.outer(new_t, freqs)
        cos = torch.cat([cos, new_freqs.cos()], dim=0)
        sin = torch.cat([sin, new_freqs.sin()], dim=0)

    cos_ = cos[:seq_len, ...]
    sin_ = sin[:seq_len, ...]
    while cos_.dim() < x.dim():
        cos_, sin_ = cos_.unsqueeze(0), sin_.unsqueeze(0)
    x_rotated = torch.cat([x1 * cos_ - x2 * sin_, x1 * sin_ + x2 * cos_], dim=-1)
    return x_rotated


# ======================== 4. SwiGLU FFN ========================
class SwiGLUFFN(nn.Module):
    """SwiGLU 门控前馈网络
    SwiGLU(x) = silu(x @ W_gate) * (x @ W_up) @ W_down
    相比 GELU 在相同参数量下效果更好，是 PaLM、Llama 等使用的 FFN 变体。
    使用独立的 gate/up 投影（不共用 Linear），语义更清晰。
    """
    def __init__(self, dim, hidden_dim):
        super().__init__()
        self.gate_proj = nn.Linear(dim, hidden_dim, bias=False)
        self.up_proj = nn.Linear(dim, hidden_dim, bias=False)
        self.down_proj = nn.Linear(hidden_dim, dim, bias=False)

    def forward(self, x):
        return self.down_proj(F.silu(self.gate_proj(x)) * self.up_proj(x))


# ======================== 5. 分组查询注意力 (GQA) ========================
class GroupedQueryAttention(nn.Module):
    """分组查询多头注意力（GQA），集成 RoPE + Flash Attention + KV Cache
    Llama 2/3 采用 GQA，用更少的 KV 头减少缓存，推理更快。
    """
    def __init__(self, config: Config):
        super().__init__()
        self.n_heads = config.n_heads
        self.n_kv_heads = config.n_kv_heads if hasattr(config, 'n_kv_heads') else config.n_heads
        self.head_dim = config.head_dim
        self.embed_dim = config.embed_dim
        self.dropout_p = config.dropout

        # Q 投影（全量头数）
        self.q_proj = nn.Linear(config.embed_dim, config.embed_dim, bias=False)
        # K/V 投影（更少的头数，节省缓存）
        kv_dim = self.n_kv_heads * self.head_dim
        self.k_proj = nn.Linear(config.embed_dim, kv_dim, bias=False)
        self.v_proj = nn.Linear(config.embed_dim, kv_dim, bias=False)
        self.o_proj = nn.Linear(config.embed_dim, config.embed_dim, bias=False)

        # 每组 Q 头数（用于将 KV 头重复广播到 Q 头数）
        self.n_rep = self.n_heads // self.n_kv_heads
        # 滑动窗口（None=全局注意，int=窗口大小）
        self.sliding_window = getattr(config, 'sliding_window', None)

        cos, sin = precompute_rope_freqs(self.head_dim, config.block_size * 2)  # 预计算 2 倍位置，支持外推
        self.register_buffer("cos", cos, persistent=False)
        self.register_buffer("sin", sin, persistent=False)

    @staticmethod
    def _repeat_kv(x, n_rep):
        """将 KV 头重复 n_rep 次以匹配 Q 头数"""
        if n_rep == 1:
            return x
        B, n_kv, T, head_dim = x.shape
        return x[:, :, None, :, :].expand(B, n_kv, n_rep, T, head_dim).reshape(B, n_kv * n_rep, T, head_dim)

    def forward(self, x, kv_cache=None):
        B, T, C = x.shape

        # 1) Q/K/V 独立投影
        q = self.q_proj(x).view(B, T, self.n_heads, self.head_dim).transpose(1, 2)
        k = self.k_proj(x).view(B, T, self.n_kv_heads, self.head_dim).transpose(1, 2)
        v = self.v_proj(x).view(B, T, self.n_kv_heads, self.head_dim).transpose(1, 2)

        # 2) RoPE
        q = apply_rope(q, self.cos, self.sin)
        k = apply_rope(k, self.cos, self.sin)

        # 3) KV Cache
        cache_len = 0
        if kv_cache is not None:
            if kv_cache['k'] is not None:
                cache_len = kv_cache['k'].shape[2]
                k = torch.cat([kv_cache['k'], k], dim=2)
                v = torch.cat([kv_cache['v'], v], dim=2)
            kv_cache['k'] = k
            kv_cache['v'] = v

        # 4) 重复 KV 头以匹配 Q 头数（GQA 核心）
        k = self._repeat_kv(k, self.n_rep)
        v = self._repeat_kv(v, self.n_rep)

        # 5) 构建注意力掩码（支持滑动窗口）
        attn_mask = None
        if kv_cache is not None:
            # 推理阶段：Q=T_q=1, K=T_k=cache_len+1
            # 只用因果掩码（最新 token 看所有缓存）
            is_causal = False
            if hasattr(self, 'sliding_window') and self.sliding_window is not None:
                # 滑动窗口：只保留最近 W 个位置
                kv_len = k.shape[2]
                if kv_len > self.sliding_window:
                    k = k[:, :, -self.sliding_window:]
                    v = v[:, :, -self.sliding_window:]
        elif T > 1:
            # 训练阶段：构建 (T, T) 掩码
            if hasattr(self, 'sliding_window') and self.sliding_window is not None:
                mask = torch.full((T, T), float('-inf'), device=x.device, dtype=q.dtype)
                for i in range(T):
                    lo = max(0, i - self.sliding_window + 1)
                    mask[i, lo:i+1] = 0.0
                attn_mask = mask
                is_causal = False
            else:
                is_causal = True
        else:
            is_causal = False

        attn_out = F.scaled_dot_product_attention(
            q, k, v,
            attn_mask=attn_mask,
            dropout_p=self.dropout_p if self.training else 0.0,
            is_causal=is_causal,
        )

        # 6) 合并头 + 输出投影
        out = attn_out.transpose(1, 2).contiguous().view(B, T, C)
        return self.o_proj(out)


# ======================== 6. Transformer 块 ========================
class TransformerBlock(nn.Module):
    """Transformer 解码器块
    Pre-Norm 结构：先归一化再进入子层，残差连接在外。
    """
    def __init__(self, config: Config):
        super().__init__()
        self.ln1 = RMSNorm(config.embed_dim)
        self.ln2 = RMSNorm(config.embed_dim)
        self.attn = GroupedQueryAttention(config)

        hidden_dim = int(config.embed_dim * 4)
        # 对齐到 128 的倍数（改善矩阵乘法效率）
        hidden_dim = ((hidden_dim + 127) // 128) * 128
        self.mlp = SwiGLUFFN(config.embed_dim, hidden_dim)
        self.dropout = nn.Dropout(config.dropout)

    def forward(self, x, kv_cache=None):
        x = x + self.dropout(self.attn(self.ln1(x), kv_cache=kv_cache))
        x = x + self.dropout(self.mlp(self.ln2(x)))
        return x


# ======================== 7. MiniLLM 模型 ========================
class MiniLLM(nn.Module):
    """迷你 LLM — 现代 GPT 解码器架构"""
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

        # 权重共享（Tie Embedding）：embed 和 head 共用权重
        # 标准实践，可减少参数量并提升训练稳定性
        self.head.weight = self.token_emb.weight

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
    def generate(self, idx, max_new_tokens, use_kv_cache=False,
                 temperature=1.0, top_k=None, top_p=None, repetition_penalty=1.0):
        """自回归生成文本

        Args:
            idx: (B, T) 初始 prompt token
            max_new_tokens: 生成的新 token 数
            use_kv_cache: 是否使用 KV Cache 加速
            temperature: 采样温度（>1 更随机，<1 更确定）
            top_k: 只从概率最高的 k 个 token 中采样
            top_p: 累积概率阈值（Nucleus Sampling），0~1
            repetition_penalty: 重复惩罚（>1.0 抑制重复，1.0=不惩罚）
        """
        # 边界保护：裁剪到 block_size
        idx = idx[:, -self.config.block_size:]

        # 温度下限保护
        temperature = max(temperature, 1e-2)

        if use_kv_cache:
            return self._generate_with_cache(idx, max_new_tokens, temperature, top_k, top_p, repetition_penalty)
        else:
            return self._generate_no_cache(idx, max_new_tokens, temperature, top_k, top_p, repetition_penalty)

    @staticmethod
    def _sample(logits, temperature, top_k, top_p, prev_token_mask=None, repetition_penalty=1.0):
        """统一的采样逻辑：重复惩罚 → 温度缩放 → Top-K → Top-P → 采样
        prev_token_mask: (1, vocab_size) 的 bool mask，已生成位置为 True
        """
        # 重复惩罚（tensor 操作，避免 Python 循环）
        if repetition_penalty != 1.0 and prev_token_mask is not None:
            logits = logits.clone()
            logits[prev_token_mask] /= repetition_penalty

        logits = logits / temperature

        # Top-K 过滤
        if top_k is not None:
            v, _ = torch.topk(logits, min(top_k, logits.size(-1)))
            logits[logits < v[:, [-1]]] = float('-inf')

        probs = F.softmax(logits, dim=-1)

        # Top-P (Nucleus) 过滤
        if top_p is not None:
            sorted_probs, sorted_indices = torch.sort(probs, descending=True, dim=-1)
            cumsum = torch.cumsum(sorted_probs, dim=-1)
            mask = cumsum - sorted_probs > top_p
            sorted_probs[mask] = 0.0
            sorted_probs = sorted_probs / sorted_probs.sum(dim=-1, keepdim=True)
            sampled_idx = torch.multinomial(sorted_probs, num_samples=1)
            next_token = torch.gather(sorted_indices, -1, sampled_idx)
            return next_token

        next_token = torch.multinomial(probs, num_samples=1)
        return next_token

    def _generate_no_cache(self, idx, max_new_tokens, temperature, top_k, top_p, repetition_penalty):
        """无 KV Cache 的朴素生成（每步重新计算所有位置）"""
        generated = idx.clone()
        vocab_size = self.vocab_size
        for _ in range(max_new_tokens):
            idx_crop = generated[:, -self.config.block_size:]
            logits = self(idx_crop)
            logits = logits[:, -1, :]
            # 重复惩罚 mask（tensor 操作）
            prev_mask = torch.zeros(1, vocab_size, dtype=torch.bool, device=logits.device)
            prev_mask.scatter_(1, generated, True)
            next_token = self._sample(logits, temperature, top_k, top_p, prev_mask, repetition_penalty)
            generated = torch.cat((generated, next_token), dim=1)
        return generated

    def _generate_with_cache(self, idx, max_new_tokens, temperature, top_k, top_p, repetition_penalty):
        """使用 KV Cache 加速生成
        每次调用创建全新的缓存字典，杜绝跨调用污染。
        """
        kv_caches = [{'k': None, 'v': None} for _ in range(self.config.n_layers)]

        generated = idx.clone()
        vocab_size = self.vocab_size

        # 第一步：处理 prompt（完整序列，填充缓存）
        logits = self(idx, kv_caches=kv_caches)
        prev_mask = torch.zeros(1, vocab_size, dtype=torch.bool, device=logits.device)
        prev_mask.scatter_(1, generated, True)
        next_token = self._sample(logits[:, -1, :], temperature, top_k, top_p, prev_mask, repetition_penalty)
        generated = torch.cat((generated, next_token), dim=1)

        # 后续步骤：每次只送入最后 1 个 token
        for _ in range(max_new_tokens - 1):
            logits = self(next_token, kv_caches=kv_caches)
            prev_mask = torch.zeros(1, vocab_size, dtype=torch.bool, device=logits.device)
            prev_mask.scatter_(1, generated, True)
            next_token = self._sample(logits[:, -1, :], temperature, top_k, top_p, prev_mask, repetition_penalty)
            generated = torch.cat((generated, next_token), dim=1)

        return generated


# ======================== 8. 数据准备 ========================
def prepare_data(text, tokenizer, config: Config, val_split=0.1):
    """将文本切分为重叠的 (input, target) 序列对，按比例划分训练/验证集

    Returns:
        train_loader, val_loader — 验证集为 None 当数据量不足时
    """
    tokens = torch.tensor(tokenizer.encode(text), dtype=torch.long)
    print(f"  文本长度: {len(text)} 字符, {len(tokens)} tokens")

    stride = config.block_size // 2
    n = len(tokens)

    # 边界保护
    if n < config.block_size + 1:
        print(f"  ⚠ 文本不足一条序列 ({n} tokens)，自动填充")
        tokens = F.pad(tokens, (0, config.block_size + 1 - n))
        n = len(tokens)

    max_start = n - config.block_size
    if max_start <= 0:
        max_start = 1

    # 向量化生成滑动窗口序列 (num_seqs, block_size+1)
    indices = torch.arange(config.block_size + 1).unsqueeze(0) +               torch.arange(0, max_start, stride).unsqueeze(1)
    data = tokens[indices]  # (num_seqs, block_size+1)

    x = data[:, :-1]  # 输入
    y = data[:, 1:]   # 目标

    # 训练/验证分割
    n_total = len(x)
    n_val = max(1, int(n_total * val_split))
    n_train = n_total - n_val

    # GPU 时开启多进程加载和 pin_memory 加速数据传输
    dl_kwargs = dict(
        batch_size=config.batch_size,
        num_workers=4 if config.device == "cuda" else 0,
        pin_memory=(config.device == "cuda"),
    )
    train_dataset = TensorDataset(x[:n_train], y[:n_train])
    train_loader = DataLoader(train_dataset, shuffle=True, **dl_kwargs)

    val_loader = None
    if n_val >= 1:
        val_dataset = TensorDataset(x[n_train:], y[n_train:])
        val_loader = DataLoader(val_dataset, shuffle=False, **dl_kwargs)

    print(f"  生成 {n_total} 条序列, 训练 {n_train} 条 / 验证 {n_val} 条")
    return train_loader, val_loader


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
            self.current_lr = self.peak_lr * it / max(1, self.warmup_iters)
        else:
            progress = (it - self.warmup_iters) / max(1, self.max_iters - self.warmup_iters)
            self.current_lr = self.min_lr + 0.5 * (self.peak_lr - self.min_lr) * (
                1 + math.cos(math.pi * progress)
            )
        for param_group in self.optimizer.param_groups:
            param_group['lr'] = self.current_lr

    def get_lr(self):
        return self.current_lr


# ======================== 检查点管理（含数据指纹 + 超参指纹） ========================
MODEL_PATH = os.path.join(os.path.dirname(__file__) or ".", "mini_llm_checkpoint.pt")


def _config_fingerprint(config):
    """生成超参指纹，用于检测超参变更"""
    return hash((
        config.embed_dim, config.n_heads, config.block_size,
        config.n_layers, config.dropout, config.lr,
        config.max_epochs, config.grad_clip,
    ))


def save_checkpoint(model, tokenizer, train_text, config, path=MODEL_PATH):
    """保存模型权重 + tokenizer + 数据指纹 + 超参指纹"""
    checkpoint = {
        'model_state_dict': model.state_dict(),
        'vocab_size': tokenizer.vocab_size,
        'stoi': tokenizer.stoi,
        'itos': tokenizer.itos,
        'data_hash': hash(train_text),
        'config_fingerprint': _config_fingerprint(config),
    }
    torch.save(checkpoint, path)
    print(f"  ✓ 模型已保存到 {path}")


def load_checkpoint(path, train_text, config, device='cpu'):
    """从文件加载模型权重和 tokenizer，校验指纹"""
    checkpoint = torch.load(path, map_location=device, weights_only=True)

    # 校验训练文本指纹
    if checkpoint.get('data_hash') != hash(train_text):
        print(f"  ⚠ 训练数据已变更，忽略旧缓存")
        return None, None

    # 校验超参指纹
    if checkpoint.get('config_fingerprint') != _config_fingerprint(config):
        print(f"  ⚠ 超参已变更，忽略旧缓存")
        return None, None

    tokenizer = CharTokenizer.__new__(CharTokenizer)
    tokenizer.vocab_size = checkpoint['vocab_size']
    tokenizer.stoi = checkpoint['stoi']
    tokenizer.itos = {int(k): v for k, v in checkpoint['itos'].items()}
    tokenizer.unk_id = tokenizer.stoi.get(UNK_TOKEN, tokenizer.vocab_size - 1)
    return checkpoint['model_state_dict'], tokenizer


# ======================== 10. 交互式对话 ========================
def run_chat_mode(model, tokenizer, config):
    """交互式中文对话：用户输入 prompt，模型续写"""
    print("\n" + "=" * 60)
    print("  交互式对话模式 — 输入中文 prompt，Ctrl+C 退出")
    print("=" * 60)
    model.eval()
    while True:
        try:
            prompt = input("\n  You: ").strip()
            if not prompt:
                continue
            prompt_ids = torch.tensor(
                [tokenizer.encode(prompt)], dtype=torch.long, device=config.device
            )
            out = model.generate(
                prompt_ids,
                max_new_tokens=80,
                use_kv_cache=True,
                temperature=0.7,
                top_k=20,
                top_p=0.9,
            )
            reply = tokenizer.decode(out[0].tolist())
            print(f"  LLM: {reply}")
        except KeyboardInterrupt:
            print("\n  退出对话模式")
            break


# ======================== 11. 主程序 ========================
def main():
    config = Config()
    parser = argparse.ArgumentParser(description="迷你 LLM 演示")
    parser.add_argument('--retrain', action='store_true',
                        help='强制重新训练（默认：有检查点时跳过）')
    parser.add_argument('--chat', action='store_true',
                        help='交互式对话模式（训练/加载后进入对话循环）')
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

    # ---- 检查是否有保存的模型 ----
    need_train = True
    if os.path.exists(MODEL_PATH) and not args.retrain:
        print(f"\n  发现已保存模型 ({MODEL_PATH})，加载中...")
        state_dict, tokenizer_loaded = load_checkpoint(MODEL_PATH, TRAIN_TEXT, config, config.device)
        if state_dict is not None:
            tokenizer = tokenizer_loaded  # 只有加载成功才替换 tokenizer
            model.load_state_dict(state_dict)
            print(f"  ✓ 已加载训练好的模型，跳过训练")
            need_train = False
        else:
            print(f"  → 将重新训练")
    elif args.retrain:
        print(f"\n  --retrain 参数指定，重新训练...")

    if need_train:
        # ---- 3. 数据准备 ----
        print("\n[3/5] 准备数据...")
        train_loader, val_loader = prepare_data(TRAIN_TEXT, tokenizer, config)

        # ---- 4. 训练（含验证集早停） ----
        print("\n[4/5] 开始训练...")

        optimizer = torch.optim.AdamW(
            model.parameters(),
            lr=config.lr,
            weight_decay=config.weight_decay,
            betas=(0.9, 0.95),
        )

        # 真实迭代步数（考虑梯度累积：每 accum_steps 个微批次才更新一次参数和 LR）
        total_iters = config.max_epochs * (len(train_loader) // config.gradient_accumulation_steps)
        scheduler = WarmupCosineLR(
            optimizer,
            warmup_iters=config.warmup_iters,
            max_iters=total_iters,
            peak_lr=config.lr,
            min_lr=config.lr * 0.1,
        )

        use_amp = (config.device == "cuda")
        scaler = torch.amp.GradScaler(config.device, enabled=use_amp)

        loss_fn = nn.CrossEntropyLoss(label_smoothing=config.label_smoothing)

        # 早停参数
        best_val_loss = float('inf')
        patience = 10
        stall_count = 0
        best_epoch = 0

        model.train()
        step = 0
        overall_pct_interval = max(1, total_iters // 100)
        accum_steps = config.gradient_accumulation_steps
        train_start_time = time.time()
        for epoch in range(1, config.max_epochs + 1):
            epoch_loss = 0.0
            num_batches = 0
            epoch_start_time = time.time()

            for micro_idx, (x, y) in enumerate(tqdm(train_loader, desc=f"  Epoch {epoch:3d}/{config.max_epochs}", leave=False)):
                x, y = x.to(config.device), y.to(config.device)

                with torch.amp.autocast(device_type=config.device, enabled=use_amp):
                    logits = model(x)
                    loss = loss_fn(logits.view(-1, vocab_size), y.view(-1)) / accum_steps

                scaler.scale(loss).backward()

                # 每 accum_steps 步更新一次参数
                if (micro_idx + 1) % accum_steps == 0:
                    scaler.unscale_(optimizer)
                    torch.nn.utils.clip_grad_norm_(model.parameters(), config.grad_clip)
                    scaler.step(optimizer)
                    scaler.update()
                    optimizer.zero_grad()

                    scheduler.step(step)
                    step += 1

                    if step % overall_pct_interval == 0:
                        overall_pct = step / total_iters * 100
                        print(f"    总体训练进度: {overall_pct:.1f}%")

                epoch_loss += loss.item() * accum_steps
                num_batches += 1

            avg_loss = epoch_loss / num_batches

            # 验证集评估
            val_loss = None
            if val_loader is not None:
                model.eval()
                val_loss_total = 0.0
                val_batches = 0
                with torch.no_grad():
                    for x_val, y_val in val_loader:
                        x_val, y_val = x_val.to(config.device), y_val.to(config.device)
                        logits = model(x_val)
                        loss_val = loss_fn(logits.view(-1, vocab_size), y_val.view(-1))
                        val_loss_total += loss_val.item()
                        val_batches += 1
                val_loss = val_loss_total / val_batches
                model.train()

            if epoch % 10 == 0 or epoch == 1 or epoch == config.max_epochs:
                elapsed = time.time() - epoch_start_time
                val_str = f", Val Loss: {val_loss:.4f}" if val_loss is not None else ""
                print(f"    Epoch {epoch:3d}/{config.max_epochs} ({epoch/config.max_epochs*100:.0f}%), "
                      f"Loss: {avg_loss:.4f}{val_str}, "
                      f"LR: {scheduler.get_lr():.6f}, "
                      f"Time: {elapsed:.1f}s")

            # 早停判断
            if val_loss is not None:
                if val_loss < best_val_loss:
                    best_val_loss = val_loss
                    best_epoch = epoch
                    stall_count = 0
                    save_checkpoint(model, tokenizer, TRAIN_TEXT, config)
                else:
                    stall_count += 1
                    if stall_count >= patience:
                        print(f"    ⏹ 早停: 验证 loss {patience} 轮未下降 (最佳 Epoch {best_epoch}, "
                              f"Val Loss {best_val_loss:.4f})")
                        break
        else:
            # 正常结束，保存最终模型
            save_checkpoint(model, tokenizer, TRAIN_TEXT, config)

    # ---- 如果指定 --chat 则进入交互模式 ----
    if args.chat:
        run_chat_mode(model, tokenizer, config)
        return

    # ---- 5. 生成测试 ----
    print("\n[5/5] 生成测试...")
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
            temperature=0.8,
            top_k=30,
            top_p=0.9,
            repetition_penalty=1.5,
        )
        generated_text = tokenizer.decode(out[0].tolist())
        print(f"\n  Prompt: \"{prompt}\"")
        print(f"  生成:   {generated_text}")

    # ---- 6. KV Cache 速度对比 ----
    print("\n  --- KV Cache 速度对比 ---")
    prompt_ids = torch.tensor(
        [tokenizer.encode("校花的贴身")], dtype=torch.long, device=config.device
    )

    torch.cuda.synchronize() if config.device == "cuda" else None
    start = time.time()
    _ = model.generate(prompt_ids, max_new_tokens=100, use_kv_cache=False, temperature=0.7)
    torch.cuda.synchronize() if config.device == "cuda" else None
    time_no_cache = time.time() - start

    torch.cuda.synchronize() if config.device == "cuda" else None
    start = time.time()
    _ = model.generate(prompt_ids, max_new_tokens=100, use_kv_cache=True, temperature=0.7)
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
        ("CharTokenizer+UNK", "字符级分词 + 未知字符容错"),
        ("RMSNorm", "均方根归一化"),
        ("RoPE", "旋转位置编码"),
        ("SwiGLU", "门控激活函数"),
        ("Flash Attention", "PyTorch 2.0 SDPA"),
        ("KV Cache", "推理加速缓存 + 隔离"),
        ("Top-K + Top-P", "双重采样策略"),
        ("AdamW", "解耦权重衰减优化器"),
        ("Warmup + Cosine", "学习率调度"),
        ("Dropout", "正则化"),
        ("Gradient Clipping", "梯度裁剪"),
        ("AMP", "混合精度训练"),
        ("Checkpoint", "数据/超参双指纹校验"),
    ]
    for name, desc in techniques:
        print(f"  ✓ {name:20s} — {desc}")

    # 提示 --chat 模式
    print("\n  💡 试试交互模式: python3 mini_llm_demo.py --chat")


if __name__ == "__main__":
    main()
