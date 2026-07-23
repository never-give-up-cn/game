"""
极简迷你 LLM（Mini GPT Demo）— 纯 CPU 可运行
==============================================
只演示核心原理：Token 嵌入 + 多头自注意力 + Transformer 解码器（GPT 结构）
参数量很小，无法真正流畅对话，仅用于理解底层逻辑。
"""

import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import torch
import torch.nn as nn
import torch.nn.functional as F

# -------------------------- 超参数 --------------------------
vocab_size = 64       # 词表大小
embed_dim = 32        # 嵌入维度
n_heads = 2           # 注意力头数
block_size = 16       # 上下文窗口长度
n_layers = 2          # Transformer 层数
device = "cpu"        # 纯 CPU 运行

# -------------------------- 多头自注意力 --------------------------
class MultiHeadAttention(nn.Module):
    def __init__(self):
        super().__init__()
        self.head_size = embed_dim // n_heads
        self.qkv = nn.Linear(embed_dim, embed_dim * 3)
        self.proj = nn.Linear(embed_dim, embed_dim)
        # 因果掩码，防止看到未来 token
        self.register_buffer("mask", torch.tril(torch.ones(block_size, block_size)))

    def forward(self, x):
        B, T, C = x.shape
        qkv = self.qkv(x).split(embed_dim, dim=-1)
        q, k, v = qkv
        # 分头: (B, T, n_heads, head_size) -> (B, n_heads, T, head_size)
        q = q.view(B, T, n_heads, self.head_size).transpose(1, 2)
        k = k.view(B, T, n_heads, self.head_size).transpose(1, 2)
        v = v.view(B, T, n_heads, self.head_size).transpose(1, 2)

        # 注意力分数
        attn = q @ k.transpose(-2, -1) / (self.head_size ** 0.5)
        attn = attn.masked_fill(self.mask[:T, :T] == 0, float('-inf'))
        attn = F.softmax(attn, dim=-1)
        out = attn @ v
        out = out.transpose(1, 2).contiguous().view(B, T, C)
        return self.proj(out)

# -------------------------- Transformer 块 --------------------------
class Block(nn.Module):
    def __init__(self):
        super().__init__()
        self.attn = MultiHeadAttention()
        self.ln1 = nn.LayerNorm(embed_dim)
        self.ln2 = nn.LayerNorm(embed_dim)
        self.mlp = nn.Sequential(
            nn.Linear(embed_dim, embed_dim * 4),
            nn.GELU(),
            nn.Linear(embed_dim * 4, embed_dim),
        )

    def forward(self, x):
        x = x + self.attn(self.ln1(x))  # 自注意力 + 残差
        x = x + self.mlp(self.ln2(x))   # FFN + 残差
        return x

# -------------------------- 迷你 LLM 主体 (GPT) --------------------------
class MiniLLM(nn.Module):
    def __init__(self):
        super().__init__()
        self.token_emb = nn.Embedding(vocab_size, embed_dim)
        self.pos_emb = nn.Embedding(block_size, embed_dim)
        self.blocks = nn.Sequential(*[Block() for _ in range(n_layers)])
        self.ln_final = nn.LayerNorm(embed_dim)
        self.head = nn.Linear(embed_dim, vocab_size)

    def forward(self, idx):
        B, T = idx.shape
        tok_emb = self.token_emb(idx)                             # (B, T, embed_dim)
        pos_emb = self.pos_emb(torch.arange(T, device=device))    # (T, embed_dim)
        x = tok_emb + pos_emb
        x = self.blocks(x)
        x = self.ln_final(x)
        logits = self.head(x)     # (B, T, vocab_size)
        return logits

    @torch.no_grad()
    def generate(self, idx, max_new_tokens):
        """自回归生成：每次预测下一个 token，拼回去继续预测"""
        for _ in range(max_new_tokens):
            idx_crop = idx[:, -block_size:]          # 只取最后 block_size 个 token
            logits = self(idx_crop)                  # (B, T, vocab_size)
            logits = logits[:, -1, :]                # 只取最后一个位置的预测
            probs = F.softmax(logits, dim=-1)        # 转概率
            next_token = torch.multinomial(probs, num_samples=1)  # 采样
            idx = torch.cat((idx, next_token), dim=1)
        return idx


# -------------------------- 训练一个玩具数据集 --------------------------
def make_toy_data():
    """
    造一组简单的模式供模型学习：
    - 序列 = [start_id, a, b, a+b, ...] 的循环
    - 让模型学到"数数"的规律，而不是随机输出
    """
    data = []
    for a in range(1, 11):
        for b in range(1, 11):
            seq = [0, a % vocab_size, b % vocab_size, (a + b) % vocab_size]
            data.append(seq)
    return torch.tensor(data, dtype=torch.long)


# -------------------------- 主程序 --------------------------
if __name__ == "__main__":
    model = MiniLLM().to(device)
    print(f"模型参数量: {sum(p.numel() for p in model.parameters()):,}")
    print(f"设备: {device}")

    # ---- 1. 先看未训练时生成什么 ----
    start_tokens = torch.randint(0, vocab_size, (1, 4), device=device)
    output = model.generate(start_tokens, max_new_tokens=10)
    print(f"\n[未训练] 生成 token 序列: {output.tolist()[0]}")

    # ---- 2. 简单训练几步 ----
    data = make_toy_data()
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.CrossEntropyLoss()

    print(f"\n开始训练（{len(data)} 条玩具数据, 200 轮）...")
    model.train()
    for epoch in range(200):
        total_loss = 0.0
        for seq in data:
            x = seq[:-1].unsqueeze(0).to(device)      # 输入: [0, a, b]
            y = seq[1:].unsqueeze(0).to(device)        # 目标: [a, b, a+b]
            logits = model(x)                          # (1, 3, vocab_size)
            loss = loss_fn(logits.view(-1, vocab_size), y.view(-1))
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
        if (epoch + 1) % 10 == 0:
            print(f"  Epoch {epoch+1:2d}, Loss: {total_loss / len(data):.4f}")

    # ---- 3. 训练后生成（用固定 prompt 观察是否学会"数数"）----
    model.eval()
    test_prompts = [
        [0, 3, 5],    # 期望学到 3+5=8 → 下一个 token 接近 8
        [0, 7, 2],    # 7+2=9
        [0, 4, 9],    # 4+4=8
    ]
    print("\n[训练后] 测试生成（prompt=[start, a, b]，看模型能否预测 a+b）:")
    for prompt in test_prompts:
        x = torch.tensor([prompt], dtype=torch.long, device=device)
        out = model.generate(x, max_new_tokens=1)
        pred = out[0, -1].item()
        a, b = prompt[1], prompt[2]
        print(f"  {a} + {b} = {pred}  (期望: {(a+b) % vocab_size})")

    print("\n== 演示结束 ==")
    print("这个模型只学了简单的加法模式，")
    print("但它的架构（嵌入 + 多头注意力 + Transformer 解码器）")
    print("和真正的 GPT 完全一致。")
