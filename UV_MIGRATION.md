# UV Migration Guide

Your project has been successfully migrated to use `uv` for Python package management.

## Key Changes Made

1. **Updated `pyproject.toml`**:
   - Changed build system from `setuptools` to `hatchling`
   - Added `[tool.hatch.build.targets.wheel]` configuration for package discovery
   - Kept all existing dependencies and optional dependencies

2. **Generated `uv.lock`**:
   - Created a lock file with exact versions of all dependencies
   - This ensures reproducible installations across environments

## Common UV Commands

### Environment Management
```bash
# Sync dependencies (install/update based on pyproject.toml)
uv sync

# Sync with dev dependencies
uv sync --extra dev

# Install the project in editable mode
uv sync --dev
```

### Package Management
```bash
# Add a new dependency
uv add package-name

# Add a dev dependency
uv add --dev package-name

# Remove a dependency
uv remove package-name

# Update all dependencies
uv sync --upgrade
```

### Running Commands
```bash
# Run Python scripts
uv run python script.py

# Run with specific extras
uv run --extra dev python script.py

# Run pytest
uv run pytest

# Run jupyter
uv run jupyter notebook
```

### Building and Publishing
```bash
# Build the package
uv build

# Publish to PyPI (if configured)
uv publish
```

## Migration Benefits

- **Faster**: `uv` is significantly faster than `pip` for dependency resolution and installation
- **Better dependency resolution**: More accurate conflict detection and resolution
- **Lock file**: `uv.lock` ensures reproducible environments
- **Modern tooling**: Built with Rust for performance and reliability

## Files You Can Now Remove

Since we're using `uv` and modern Python packaging, you can safely remove:
- `setup.py` (functionality moved to `pyproject.toml`)
- Any `requirements.txt` files (dependencies are now in `pyproject.toml`)

## Next Steps

1. Commit the changes to version control
2. Update your CI/CD pipelines to use `uv` commands
3. Update documentation for contributors to use `uv` instead of `pip`
