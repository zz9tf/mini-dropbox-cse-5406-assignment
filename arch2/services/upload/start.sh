#!/bin/bash
# Generate protobuf code if proto file exists
if [ -f "/app/protos/twopc.proto" ]; then
    python -m grpc_tools.protoc -I/app/protos --python_out=/app --grpc_python_out=/app /app/protos/twopc.proto
fi
# Start the application
python app.py
