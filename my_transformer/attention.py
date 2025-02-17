# AUTOGENERATED! DO NOT EDIT! File to edit: ../notebooks/attention.ipynb.

# %% auto 0
__all__ = ['unidirectional_mask', 'attention', 'MultiHeadAttention', 'LayerNormalization']

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
from .position_encoding import SinusoidalPositionalEncoder

from torch.utils.tensorboard import SummaryWriter
import math
from tqdm import tqdm

# %% ../notebooks/attention.ipynb 14
def unidirectional_mask(seq_len: int) -> torch.Tensor:
    # inverse_mask = torch.triu(torch.ones((1, seq_len, seq_len)), diagonal=1)  # .type(torch.uint8)
    # inverse_mask = torch.tril(torch.ones((T, T)))
    # ic(inverse_mask)
    # tmask = inverse_mask == 0
    # ic(tmask)
    mask = torch.tril(torch.ones((1, seq_len, seq_len)))
    return mask

# %% ../notebooks/attention.ipynb 16
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
    assert (
        atn.shape == query.shape
    ), f"atn shape {atn.shape} should be the same as input tensors key, query and value shapes. Query shape: {query.shape}"
    return atn, attn_weights

# %% ../notebooks/attention.ipynb 20
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
        assert mh_attn_weight.size() == torch.Size(
            [batch_size, self.h, seq_len, seq_len]
        )
        # we need to create a contiguous memory space for tensor after transpose so we can apply view.
        concat_attn = (
            mh_attn.transpose(2, 1)
            .contiguous()
            .view(batch_size, seq_len, self.h * self.d_k)
        )
        concat_attn_weight = torch.sum(mh_attn_weight, dim=1)
        assert concat_attn.size() == torch.Size([batch_size, seq_len, d])
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
