# transformer_implementations

my implementation of transformer models based on https://arxiv.org/abs/2207.09238 and minGPT of https://github.com/karpathy/minGPT 

The project is developed using notebooks and nbdev to generate python from notebooks.

- utils: utils functions
- tokenizers: bpe implementation of tokenizer
- pos_encoding: positional encoding as defined in first attention paper
- attention: basic attention components (nn.Modules)
- model: use of all components to build a gpt2 like model to predict next token with shakespeare books.


## installation

```bash
uv venv
source .venv/bin/activate
uv sync
```

## TensorBoard Integration

This project includes TensorBoard integration for visualizing training metrics. The following metrics are logged:

- Training loss
- Evaluation loss
- Learning rate
- Model parameters and gradients

### Using TensorBoard

To specify a custom log directory, use the `tensorboard_log_dir` parameter when creating an `EpochTrainer` instance:

```python
trainer = EpochTrainer(
    # other parameters...
    tensorboard_log_dir="path/to/log/dir"
)
```

To view the TensorBoard dashboard, run:

```bash
tensorboard --logdir=path/to/log/dir
```

If you don't specify a custom log directory, logs will be saved to `../runs/{model_name}_{model_version}/{timestamp}`.

You can then open your browser at http://localhost:6006 to view the metrics.