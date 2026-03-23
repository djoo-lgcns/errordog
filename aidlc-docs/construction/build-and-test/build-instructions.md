# Build Instructions - Unit 1: Core MCP Server & ESF

## Prerequisites
- **Python**: 3.13+
- **Package Manager**: uv
- **OS**: macOS, Linux, or Windows

## Build Steps

### 1. Install Dependencies
```bash
uv sync
```

### 2. Verify Build Success
```bash
uv run python -c "from errordog.models import ErrorSnapshot, Frame; print('Import OK')"
uv run python -c "from errordog.server import create_server; print('Server OK')"
```

- **Expected Output**: Both commands print "OK" without errors
- **Build Artifacts**: `.venv/` directory with installed dependencies, `errordog` package installed in editable mode

### 3. Start MCP Server (Manual Verification)
```bash
uv run python -m errordog
```
- Server starts and listens on stdio for MCP protocol messages
- Press Ctrl+C to stop

## Troubleshooting

### uv sync fails with Python version error
- **Cause**: System default Python is too new (e.g., 3.15 alpha)
- **Solution**: Create venv with specific Python version:
  ```bash
  uv venv --python 3.13 .venv
  uv sync
  ```

### Import errors after install
- **Cause**: Package not installed or wrong venv
- **Solution**: Ensure `uv sync` completed successfully and use `uv run` prefix
