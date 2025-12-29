# Python Implementation Testing Guide

This document provides examples and tests for the Python implementation of the MCP Kroki server.

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Or install the package
pip install -e .
```

## Running the Server

```bash
# Run directly
python src/kroki_server.py

# Or use the installed command (if installed with pip install -e .)
kroki-server
```

## Basic Functionality Tests

### 1. Encoding Test

The server uses zlib compression and base64 encoding with URL-safe characters:

```python
from src.kroki_server import encode_diagram_content

content = "graph TD; A-->B; B-->C;"
encoded = encode_diagram_content(content)
print(f"Encoded: {encoded}")
# Output: eNpLL0osyFAIcbFWcNTVtXOyVnACUs7WAFBEBfQ=
```

### 2. Validation Tests

```python
from src.kroki_server import validate_diagram_type, validate_output_format, KrokiError

# Valid diagram types
try:
    validate_diagram_type('mermaid')  # ✓ Passes
    validate_diagram_type('plantuml')  # ✓ Passes
    validate_diagram_type('invalid')  # ✗ Raises KrokiError
except KrokiError as e:
    print(f"Error: {e}")

# Valid output formats
try:
    validate_output_format('svg')  # ✓ Passes
    validate_output_format('png')  # ✓ Passes
    validate_output_format('invalid')  # ✗ Raises KrokiError
except KrokiError as e:
    print(f"Error: {e}")
```

### 3. URL Generation Test

```python
import asyncio
from src.kroki_server import generate_diagram_url

async def test_url():
    content = "graph TD; A-->B; B-->C;"
    url = await generate_diagram_url('mermaid', content, 'svg')
    print(f"Generated URL: {url}")
    # The URL can be opened in a browser to view the diagram

asyncio.run(test_url())
```

### 4. Diagram Download Test

```python
import asyncio
from src.kroki_server import get_diagram_data
from pathlib import Path

async def test_download():
    content = "graph TD; A-->B; B-->C;"
    
    # Get diagram data
    data, format = await get_diagram_data('mermaid', content, 'svg')
    
    # Save to file
    output_path = Path('/tmp/test_diagram.svg')
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'wb') as f:
        f.write(data)
    
    print(f"Diagram saved to: {output_path}")
    print(f"Size: {len(data)} bytes")

asyncio.run(test_download())
```

### 5. SVG Scaling Test

```python
import asyncio
from src.kroki_server import get_diagram_data
from pathlib import Path

async def test_scaling():
    content = "graph TD; A-->B; B-->C;"
    
    # Get diagram with 2x scaling
    data, format = await get_diagram_data('mermaid', content, 'svg', scale=2.0)
    
    # The SVG width and height attributes should be doubled
    svg_content = data.decode('utf-8')
    print("Scaled SVG preview:")
    print(svg_content[:200])

asyncio.run(test_scaling())
```

## MCP Tool Usage Examples

When used as an MCP server with Claude Desktop or other MCP clients:

### Tool 1: generate_diagram_url_tool

```json
{
  "name": "generate_diagram_url_tool",
  "arguments": {
    "type": "mermaid",
    "content": "graph TD; A-->B; B-->C; C-->D;",
    "outputFormat": "svg"
  }
}
```

Expected response:
```
Diagram URL generated and content verified. No errors found.
URL: https://kroki.io/mermaid/svg/eNpLL0osyFAIcbFWcNTVtXOyVnACUs7WAFBEBfQ=
```

### Tool 2: download_diagram

```json
{
  "name": "download_diagram",
  "arguments": {
    "type": "mermaid",
    "content": "graph TD; A-->B; B-->C; C-->D;",
    "outputPath": "/tmp/my_diagram.svg",
    "outputFormat": "svg",
    "scale": 1.5
  }
}
```

Expected response:
```
Diagram saved to /tmp/my_diagram.svg
```

## Supported Diagram Types

- mermaid
- plantuml
- graphviz
- c4plantuml
- excalidraw
- erd
- svgbob
- nomnoml
- wavedrom
- blockdiag
- seqdiag
- actdiag
- nwdiag
- packetdiag
- rackdiag
- umlet
- ditaa
- vega
- vegalite

## Supported Output Formats

- svg (Scalable Vector Graphics)
- png (Portable Network Graphics)
- pdf (Portable Document Format)
- jpeg (JPEG image)
- base64 (Base64-encoded SVG)

## Error Handling

The Python implementation includes comprehensive error handling:

1. **Invalid diagram type**: Raises `KrokiError` with list of valid types
2. **Invalid output format**: Raises `KrokiError` with list of valid formats
3. **Syntax errors in diagram**: Detects and reports errors from Kroki API
4. **HTML error pages**: Parses and extracts error messages from HTML responses
5. **SVG error detection**: Checks for error text within SVG content
6. **Network errors**: Catches and reports connection issues

## Differences from TypeScript Implementation

The Python implementation maintains the same functionality as the TypeScript version with these adaptations:

1. **Compression**: Uses `zlib` instead of `pako`
2. **HTTP Client**: Uses `httpx` (async) instead of `axios`
3. **File Operations**: Uses `pathlib` and standard `open()` instead of `fs/promises`
4. **MCP Framework**: Uses `FastMCP` instead of `@modelcontextprotocol/sdk`
5. **Type Hints**: Uses Python type hints instead of TypeScript types
6. **Error Messages**: All translated from Japanese to English

## Configuration for Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "mcp-kroki": {
      "command": "python",
      "args": ["/path/to/mcp-kroki/src/kroki_server.py"]
    }
  }
}
```

Or if installed as a package:

```json
{
  "mcpServers": {
    "mcp-kroki": {
      "command": "kroki-server",
      "args": []
    }
  }
}
```
