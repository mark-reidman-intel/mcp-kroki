# Python-based Kroki MCP Server
FROM python:3.11-slim

# Create app directory
WORKDIR /app

# Install app dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Bundle app source
COPY src/ ./src/

# Run the MCP server
CMD ["python", "./src/kroki_server.py"]
