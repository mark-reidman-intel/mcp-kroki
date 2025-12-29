#!/usr/bin/env python3
"""
Kroki MCP Server - A Model Context Protocol server for diagram generation using Kroki.io
"""
import base64
import zlib
from pathlib import Path
from typing import Optional
import httpx
from mcp.server.fastmcp import FastMCP

KROKI_BASE_URL = "https://kroki.io"

# Initialize FastMCP server
mcp = FastMCP(
    name="kroki-server",
    instructions="A Model Context Protocol server that converts Mermaid diagrams and other formats to SVG/PNG/PDF using Kroki.io. This server provides tools to generate diagram URLs and download diagram files.",
)


class KrokiError(Exception):
    """Custom exception for Kroki-related errors"""
    pass


def validate_diagram_type(diagram_type: str) -> None:
    """Validate the diagram type is supported by Kroki"""
    valid_types = [
        'mermaid', 'plantuml', 'graphviz', 'c4plantuml',
        'excalidraw', 'erd', 'svgbob', 'nomnoml', 'wavedrom',
        'blockdiag', 'seqdiag', 'actdiag', 'nwdiag', 'packetdiag',
        'rackdiag', 'umlet', 'ditaa', 'vega', 'vegalite'
    ]
    
    if diagram_type not in valid_types:
        raise KrokiError(
            f"Invalid diagram type. Must be one of: {', '.join(valid_types)}"
        )


def validate_output_format(output_format: str) -> None:
    """Validate the output format is supported"""
    valid_formats = ['svg', 'png', 'pdf', 'jpeg', 'base64']
    
    if output_format not in valid_formats:
        raise KrokiError(
            f"Invalid output format. Must be one of: {', '.join(valid_formats)}"
        )


def encode_diagram_content(content: str) -> str:
    """
    Compress and encode diagram content for Kroki URL
    
    Args:
        content: Raw diagram content
        
    Returns:
        Base64-encoded compressed content with URL-safe characters
    """
    # Compress using zlib (equivalent to pako.deflate)
    compressed = zlib.compress(content.encode('utf-8'), level=9)
    # Base64 encode and make URL-safe
    encoded = base64.b64encode(compressed).decode('ascii')
    # Replace characters for URL safety
    encoded = encoded.replace('+', '-').replace('/', '_')
    return encoded


async def get_diagram_data(
    diagram_type: str,
    content: str,
    output_format: str = 'svg',
    scale: float = 1.0
) -> tuple[bytes, str]:
    """
    Fetch diagram data from Kroki API with error checking and optional SVG scaling
    
    Args:
        diagram_type: Type of diagram (e.g., 'mermaid', 'plantuml')
        content: Diagram content in the specified format
        output_format: Output format (svg, png, pdf, jpeg, base64)
        scale: Scaling factor for SVG output (default: 1.0)
        
    Returns:
        Tuple of (diagram_data, output_format)
        
    Raises:
        KrokiError: If validation fails or Kroki returns an error
    """
    validate_diagram_type(diagram_type)
    validate_output_format(output_format)
    
    # Encode diagram content
    encoded_content = encode_diagram_content(content)
    url = f"{KROKI_BASE_URL}/{diagram_type}/{output_format}/{encoded_content}"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            
            data = response.content
            content_type = response.headers.get('content-type', '').lower()
            
            # --- HTML error page detection ---
            # Check if Content-Type is HTML, or if content starts with HTML tags
            if content_type.startswith('text/html') or \
               data[:100].decode('utf-8', errors='ignore').strip().startswith(('<html', '<!DOCTYPE html')):
                # Try to extract error message from HTML content
                html_content = data.decode('utf-8', errors='ignore')
                
                # Extract title
                title_match = None
                if '<title>' in html_content:
                    start = html_content.find('<title>') + 7
                    end = html_content.find('</title>', start)
                    if end > start:
                        title_match = html_content[start:end].strip()
                
                extracted_message = title_match or 'Unknown error (HTML response)'
                
                # Check for "Unable to decode" message
                if 'unable to decode' in html_content.lower():
                    extracted_message = "Decoding error: Kroki was unable to decode the source. Please check the diagram format and content."
                    # Try to extract more details from <pre> tag
                    if '<pre>' in html_content:
                        pre_start = html_content.find('<pre>') + 5
                        pre_end = html_content.find('</pre>', pre_start)
                        if pre_end > pre_start:
                            pre_content = html_content[pre_start:pre_end].strip()
                            if pre_content:
                                extracted_message += f"\nDetails:\n---\n{pre_content}\n---"
                
                raise KrokiError(f"Kroki error: {extracted_message}")
            
            # --- SVG error checking and scaling ---
            if output_format in ('svg', 'base64') and data:
                svg_content = data.decode('utf-8')
                
                # Check for error text in SVG
                if 'class="error"' in svg_content or 'fill="red"' in svg_content:
                    # Extract error message
                    import re
                    error_pattern = r'<text[^>]*(?:class="error"|fill="red")[^>]*>([\s\S]*?)</text>'
                    error_match = re.search(error_pattern, svg_content, re.IGNORECASE)
                    if error_match:
                        raw_error_message = error_match.group(1).strip()
                        # Decode HTML entities
                        decoded_error = (raw_error_message
                                       .replace('&lt;', '<')
                                       .replace('&gt;', '>')
                                       .replace('&amp;', '&')
                                       .replace('<br/>', '\n'))
                        raise KrokiError(
                            f"Diagram generation error (in SVG):\n{decoded_error}\n\n"
                            "Please check your diagram content."
                        )
                
                # --- Scaling processing (only for scale > 1 and SVG format) ---
                if scale > 1.0 and output_format == 'svg':  # Don't scale base64
                    try:
                        import re
                        
                        def replace_svg_tag(match):
                            attributes = match.group(1)
                            new_attrs = attributes
                            
                            # Handle width attribute
                            width_match = re.search(r'width="([^"]+)"', attributes)
                            if width_match:
                                width_val_str = width_match.group(1)
                                # Extract numeric value and unit
                                width_num_match = re.match(r'([0-9.]+)(.*)', width_val_str)
                                if width_num_match:
                                    width_val = float(width_num_match.group(1))
                                    width_unit = width_num_match.group(2) or 'px'
                                    new_width = f'width="{width_val * scale:.2f}{width_unit}"'
                                    new_attrs = new_attrs.replace(width_match.group(0), new_width)
                            
                            # Handle height attribute
                            height_match = re.search(r'height="([^"]+)"', attributes)
                            if height_match:
                                height_val_str = height_match.group(1)
                                # Extract numeric value and unit
                                height_num_match = re.match(r'([0-9.]+)(.*)', height_val_str)
                                if height_num_match:
                                    height_val = float(height_num_match.group(1))
                                    height_unit = height_num_match.group(2) or 'px'
                                    new_height = f'height="{height_val * scale:.2f}{height_unit}"'
                                    new_attrs = new_attrs.replace(height_match.group(0), new_height)
                            
                            return f'<svg{new_attrs}>'
                        
                        svg_content = re.sub(r'<svg([^>]*)>', replace_svg_tag, svg_content)
                        data = svg_content.encode('utf-8')
                        print(f"[KrokiServer] Applied scale {scale} to SVG.", flush=True)
                    except Exception as e:
                        print(f"[KrokiServer] Failed to apply scale {scale} to SVG: {e}", flush=True)
                        # On scaling failure, use original data
            
            # TODO: Error detection for binary formats like PNG/JPEG/PDF is difficult
            
            return data, output_format
            
        except httpx.HTTPStatusError as error:
            status = error.response.status_code
            detail = f"Kroki API request failed (status: {status})"
            kroki_message = ''
            
            # Try to read error response body as text
            try:
                response_text = error.response.content.decode('utf-8', errors='ignore')
                if response_text and len(response_text) < 500:
                    kroki_message = response_text.strip()
            except Exception:
                pass
            
            # 400 Bad Request likely indicates a syntax error
            if status == 400:
                user_message = (
                    "There appears to be an error in the diagram syntax (Kroki HTTP 400).\n"
                )
                if kroki_message:
                    user_message += f"Details from Kroki:\n---\n{kroki_message}\n---\n"
                else:
                    user_message += "No detailed error location was provided by Kroki.\n"
                user_message += "Please check your diagram content."
            else:
                user_message = detail
                if kroki_message:
                    user_message += f"\nMessage from Kroki: {kroki_message}"
            
            raise KrokiError(user_message)
        except httpx.RequestError as error:
            raise KrokiError(f"Failed to fetch diagram from Kroki: {str(error)}")


async def generate_diagram_url(
    diagram_type: str,
    content: str,
    output_format: str = 'svg'
) -> str:
    """
    Generate a URL for a diagram using Kroki.io
    
    This function validates the diagram by fetching it first to check for errors,
    then returns the URL if validation succeeds.
    
    Args:
        diagram_type: Type of diagram (e.g., 'mermaid', 'plantuml')
        content: Diagram content in the specified format
        output_format: Output format (svg, png, pdf, jpeg, base64)
        
    Returns:
        URL to the diagram on Kroki.io
        
    Raises:
        KrokiError: If validation fails or diagram contains errors
    """
    validate_diagram_type(diagram_type)
    validate_output_format(output_format)
    
    # Validate by fetching the diagram (errors will be raised here)
    # For base64 format, check as SVG internally
    check_format = 'svg' if output_format == 'base64' else output_format
    await get_diagram_data(diagram_type, content, check_format)
    
    # If no errors, build and return the URL
    encoded_content = encode_diagram_content(content)
    return f"{KROKI_BASE_URL}/{diagram_type}/{output_format}/{encoded_content}"


@mcp.tool()
async def generate_diagram_url_tool(
    type: str,
    content: str,
    outputFormat: str = 'svg'
) -> str:
    """
    Generate a URL for a diagram using Kroki.io.
    
    This tool takes Mermaid diagram code or other supported diagram formats and returns
    a URL to the rendered diagram. The URL can be used to display the diagram in web
    browsers or embedded in documents.
    
    Args:
        type: Diagram type (e.g., "mermaid" for Mermaid diagrams, "plantuml" for PlantUML,
              "graphviz" for GraphViz DOT, "c4plantuml" for C4 architecture diagrams, and
              many more). See Kroki.io documentation for all supported formats.
        content: The diagram content in the specified format. For Mermaid diagrams, this
                would be the Mermaid syntax code (e.g., "graph TD; A-->B; B-->C;").
        outputFormat: The format of the output image. Options are: "svg" (vector graphics,
                     default), "png" (raster image), "pdf" (document format), "jpeg"
                     (compressed raster image), or "base64" (base64-encoded SVG for direct
                     embedding in HTML).
    
    Returns:
        Success message with the diagram URL
        
    Raises:
        KrokiError: If diagram validation fails or contains errors
    """
    try:
        url = await generate_diagram_url(type, content, outputFormat)
        return f"Diagram URL generated and content verified. No errors found.\nURL: {url}"
    except KrokiError as e:
        raise ValueError(str(e))


@mcp.tool()
async def download_diagram(
    type: str,
    content: str,
    outputPath: str,
    outputFormat: Optional[str] = None,
    scale: float = 1.0
) -> str:
    """
    Download a diagram image to a local file.
    
    This tool converts diagram code (such as Mermaid) into an image file and saves it to
    the specified location. Useful for generating diagrams for presentations, documentation,
    or other offline use. Includes an option to scale SVG output.
    
    Args:
        type: Diagram type (e.g., "mermaid", "plantuml", "graphviz"). Supports the same
              diagram types as Kroki.io.
        content: The diagram content in the specified format.
        outputPath: The complete file path where the diagram image should be saved
                   (e.g., "/Users/username/Documents/diagram.svg").
        outputFormat: Output image format. If unspecified, derived from outputPath extension.
                     Options: "svg", "png", "pdf", "jpeg".
        scale: Optional scaling factor to apply to the diagram dimensions. Default is 1.0
              (no scaling). This currently only affects SVG output format by attempting to
              modify width/height attributes. Minimum value is 0.1.
    
    Returns:
        Success message with the output path
        
    Raises:
        KrokiError: If diagram generation fails
        ValueError: If scale is less than minimum (0.1)
    """
    target_path = outputPath
    
    try:
        # Validate scale
        if scale < 0.1:
            raise ValueError("Scale must be at least 0.1")
        
        # Determine format from file extension if not specified
        if outputFormat is None:
            ext = Path(outputPath).suffix
            outputFormat = ext[1:] if ext else 'svg'
        
        # Get diagram data with error checking
        data, fmt = await get_diagram_data(type, content, outputFormat, scale)
        
        # Ensure output directory exists
        output_dir = Path(outputPath).parent
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Write data to file
        with open(outputPath, 'wb') as f:
            f.write(data)
        
        return f"Diagram saved to {outputPath}"
    except KrokiError as e:
        raise ValueError(f"Failed to download diagram to {target_path}: {str(e)}")
    except Exception as e:
        raise ValueError(f"Failed to download diagram to {target_path}: {str(e)}")


if __name__ == "__main__":
    # Run the MCP server
    mcp.run()


def main():
    """Entry point for the kroki-server command"""
    mcp.run()
