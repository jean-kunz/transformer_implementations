# transformer_implementations

my implementation of transformer models based on https://arxiv.org/abs/2207.09238 and minGPT of https://github.com/karpathy/minGPT 

The project is developed using notebooks and nbdev to generate python from notebooks.

- utils: utils functions
- tokenizers: bpe implementation of tokenizer
- pos_encoding: positional encoding as defined in first attention paper
- attention: basic attention components (nn.Modules)
- model: use of all components to build a gpt2 like model to predict next token with shakespeare books.
