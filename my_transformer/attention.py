# AUTOGENERATED! DO NOT EDIT! File to edit: ../notebooks/attention.ipynb.

# %% auto 0
__all__ = ['unidirectional_mask', 'attention', 'MultiHeadAttention', 'LayerNormalization', 'DecoderTransformer', 'Trainer']

# %% ../notebooks/attention.ipynb 2
import os
from typing import Optional
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from torch.nn import functional as F
from dataclasses import dataclass
from .utils import save_model, load_model
from .tokenizers import BPETokenizer

from torch.utils.tensorboard import SummaryWriter
import math
from tqdm import tqdm

# %% ../notebooks/attention.ipynb 15
def unidirectional_mask(seq_len: int) -> torch.Tensor:
    # inverse_mask = torch.triu(torch.ones((1, seq_len, seq_len)), diagonal=1)  # .type(torch.uint8)
    # inverse_mask = torch.tril(torch.ones((T, T)))
    # ic(inverse_mask)
    # tmask = inverse_mask == 0
    # ic(tmask)
    mask = torch.tril(torch.ones((1, seq_len, seq_len)))
    return mask

# %% ../notebooks/attention.ipynb 17
def attention(
    query: torch.Tensor,
    key: torch.Tensor,
    value: torch.Tensor,
    mask: Optional[torch.Tensor] = None,
    softmax: torch.nn.Module = nn.Softmax(dim=-1),
    dropout: Optional[torch.nn.Module] = None,
) -> tuple[torch.Tensor, torch.Tensor]:
    """compute multi-head attention weigths and attention weights applied to value tensor.

    Arguments:
        query -- query tensor in batch_size, head_nb, seq_len, d_k shape
        key -- same shape structure as query
        value -- same shape structure as query
        mask -- mask of tokens (default: {None})
        softmax -- softmax module (default: {nn.Softmax(dim=-1)})
        dropout -- dropout ratio (default: {None})

    Returns:
        attention -- attention weight applied to value
        attn-weights
    """
    # d_k is the size of atttention per head (=d//nb heads, where d is the size of attn model)
    # IT SHOULD BE, batch_size, head_nb, seq_len , d_k
    batch_size, head_nb, seq_len, d_k = query.shape

    scores = (query @ key.transpose(-2, -1)) * (d_k**-0.5)
    if mask is not None:
        # mask scores with -inf when mask is False. If we masked_fill(mask, -inf), it would mask when mask ==1 (is true). We want to mask when it's 0 (false).
        scores = scores.masked_fill(mask == 0, float("-inf"))
    attn_weights = softmax(scores)  # , dim=-1)
    if dropout is not None:
        attn_weights = dropout(attn_weights)

    atn = attn_weights @ value
    # ic(atn.shape, attn_weights.shape, value.shape)
    assert torch.all(
        torch.eq(atn.shape, query.shape)
    ), f"atn shape {atn.shape} should be the same as input tensors key, query and value shapes. Query shape: {query.shape}"
    return atn, attn_weights

# %% ../notebooks/attention.ipynb 21
class MultiHeadAttention(nn.Module):
    """Multihead attention module as defined in Formal algorithm for transformers (https://arxiv.org/abs/2207.09238)
    It can be used for different attention architectures like encoder-decoder/seq-to-seq (very first transformer),
    encoder-only (bert), decoder-only (gpt-*, gopher).

    It splits weights into h heads.
    """

    def __init__(self, d: int, h: int, dropout: float = 0.0, bias: bool = True):
        """_summary_

        Arguments:
            d -- dimension of hidden state (aka model dimension)
            h -- nb of heads

        Keyword Arguments:
            dropout -- dropout rate (default: {0.0})
            bias -- do we include bias in linear computations (default: {True})
        """
        super().__init__()
        self.d = d
        self.h = h
        assert (
            d % h == 0
        ), f"Model dim {d} must be a multiple of nb of heads {h}. d_k {d//h} is the model dim per head, because we split by nb of heads."
        self.d_k = d // h  # model dim on one head.
        self.wq = nn.Linear(d, d, bias=bias)
        self.wk = nn.Linear(d, d, bias=bias)
        self.wv = nn.Linear(d, d, bias=bias)
        self.wo = nn.Linear(d, d, bias=bias)  # linear projection of output matrix.
        self.dropout = nn.Dropout(dropout)

    def forward(
        self, x: torch.Tensor, z: torch.Tensor, mask: Optional[torch.Tensor] = None
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """_summary_

        Args:
            x (torch.Tensor): primary sequence
            z (torch.Tensor): context sequence, only for encoder-decoder architecture.
            mask (torch.Tensor, optional): _description_. Defaults to None.
        """

        batch_size, seq_len, d = x.size()
        if z is None:
            # in decoder only context is the primary sequence.
            z = x
        q = self.wq(x)
        k = self.wk(z)
        v = self.wk(z)
        # shape has to be batch, h, seq_len, d_k (d//h)
        # first view to : batch,seq_len,h,d_k , then transpose h and seq_len so we got per head q,k,v
        q = q.view(batch_size, seq_len, self.h, self.d_k).transpose(1, 2)
        k = k.view(batch_size, seq_len, self.h, self.d_k).transpose(1, 2)
        v = v.view(batch_size, seq_len, self.h, self.d_k).transpose(1, 2)

        # attention has to be done on each head.
        mh_attn, mh_attn_weight = attention(q, k, v, mask=mask, dropout=self.dropout)
        assert mh_attn_weight.size == (batch_size, self.h, seq_len, seq_len)
        # we need to create a contiguous memory space for tensor after transpose so we can apply view.
        concat_attn = (
            mh_attn.transpose(2, 1)
            .contiguous()
            .view(batch_size, seq_len, self.h * self.d_k)
        )
        concat_attn_weight = torch.sum(mh_attn_weight, dim=1)
        assert concat_attn.size() == (batch_size, seq_len, d)
        # apply linear layer on concatenated attention.
        output = self.dropout(self.wo(concat_attn))
        return output, concat_attn_weight

# %% ../notebooks/attention.ipynb 26
class LayerNormalization(nn.Module):
    def __init__(self, d: int, eps: float = 1e-05) -> None:
        super().__init__()
        self.d = d
        self.eps = eps
        self.gamma = torch.nn.Parameter(torch.ones(d, dtype=torch.float))  # scale
        self.beta = torch.nn.Parameter(torch.zeros(d, dtype=torch.float))  # offset

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # normalization across features (independently) for each sample. We compute mean and var on the last 2 axis, so we have it per sampel
        mean = x.mean((-1), keepdim=True)  # .unsqueeze(-1)
        # pytorch use welford method (with unbiased=False) which is numerically more robust for small differences and edge cases
        var = x.var((-1), unbiased=False, keepdim=True)
        x_hat = (
            torch.mul(((x - mean) / torch.sqrt(var + self.eps)), self.gamma) + self.beta
        )

    return x_hat

# %% ../notebooks/attention.ipynb 29
class DecoderTransformer(nn.Module):
    def __init__(
        self,
        vocab_size: int,
        max_seq_len: int,
        model_size: int,
        nb_heads: int = 1,
        nb_layers: int = 1,
        dropout: float = 0.0,
        bias: bool = True,
    ) -> None:
        super().__init__()
        self.max_seq_len = max_seq_len
        self.tok_emb = nn.Embedding(vocab_size, embedding_dim=model_size)
        self.pos_enc = PositionalEncoder(
            max_seq_len=max_seq_len,
            embedding_dim=model_size,
            dropout=dropout,
            is_learned=True,
        )
        self.layers = nn.Sequential(
            *[
                DecoderLayer(
                    model_size=model_size, nb_heads=nb_heads, dropout=dropout, bias=bias
                )
                for i in range(nb_layers)
            ]
        )
        self.layer_norm = LayerNormalization(model_size)
        self.unembedding = nn.Linear(model_size, vocab_size)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        b, l = x.size()
        emb = self.tok_emb(x)
        x = self.pos_enc(emb)
        mask = unidirectional_mask(seq_len=l).to(x.device)
        for layer in self.layers:
            x = layer(x, mask)
        x = self.layer_norm(x)
        logits = self.unembedding(x)
        return logits

    def generate(self, x: torch.Tensor, max_new_tokens: int):
        for i in range(max_new_tokens):
            # we take at most max_seq_len tokens
            x_block = x[:, -self.max_seq_len :]
            logits = self(x_block)
            # we take the logit for last token, used to predict token.
            logits = logits[:, -1, :]
            probs = F.softmax(logits, dim=-1)
            tok_next = torch.multinomial(probs, num_samples=1)
            x = torch.cat((x, tok_next), dim=1)
        return x

# %% ../notebooks/attention.ipynb 39
# trainer class for pytorch model that encapsulate training loop


class Trainer:
    def __init__(
        self,
        model: nn.Module,
        optimizer: torch.optim.Optimizer,
        train_dl: DataLoader,
        test_dl: DataLoader,
        model_version: str,
        model_name: str,
        eval_interval: int = 500,
        eval_iters: int = 200,
        max_iters: int = 5000,
        loss_fn=F.cross_entropy,
        do_save_model: bool = True,
        device: str = "cpu",
    ) -> None:
        self.model = model
        self.optimizer = optimizer
        self.loss_fn = loss_fn
        self.train_dl = train_dl
        self.test_dl = test_dl
        self.eval_interval = eval_interval
        self.eval_iters = eval_iters
        self.max_iters = max_iters
        self.do_save_model = do_save_model
        self.model_name = model_name
        self.model_version = model_version
        self.device = device

        self.writer = None

    def compute_loss(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        B, T, C = logits.shape
        logits = logits.view(B * T, C)
        targets = targets.view(B * T)
        loss = self.loss_fn(logits, targets)
        return loss

    @torch.no_grad()
    def estimate_loss(self, i: int):
        out = {}
        self.model.eval()
        for split in ["train", "test"]:
            dl = self.train_dl if split == "train" else self.test_dl
            losses = torch.zeros(self.eval_iters)
            for k in range(self.eval_iters):
                x, y = next(iter(dl))
                logits = self.model(x)
                loss = self.compute_loss(logits, y)
                losses[k] = loss.item()
            loss_mean = losses.mean()
            out[split] = loss_mean
            self.writer.add_scalar(f"{split} loss", loss_mean, i)
        self.model.train()
        return out

    def train(self, from_iter: int = 0):
        self.writer = SummaryWriter(
            f"../runs/{self.model_name}_{self.model_version}/{datetime.now().strftime('%m-%d-%Y_%H:%M:%S')}"
        )
        ex_x, ex_y = next(iter(self.train_dl))
        self.writer.add_graph(self.model, (ex_x), use_strict_trace=False)
        self.writer.flush()
        for i in range(last_iter + 1, self.max_iters):
            # every once in a while evaluate the loss on train and val sets
            if i % self.eval_interval == 0:
                losses = self.estimate_loss(i)
                print(
                    f"step {i}: train loss {losses['train']:.4f}, val loss {losses['test']:.4f}"
                )
                save_model(self.model, self.model_name, self.model_version, i)

                for name, weight in self.model.named_parameters():
                    self.writer.add_histogram(name, weight, i)

            # sample a batch of data
            xb, yb = next(iter(self.train_dl))

            logits = self.model(xb)
            loss = self.compute_loss(logits, yb)
            self.optimizer.zero_grad(set_to_none=True)
            loss.backward()
            self.optimizer.step()

        if self.do_save_model:
            save_model(self.model, self.model_name, self.model_version, i)
