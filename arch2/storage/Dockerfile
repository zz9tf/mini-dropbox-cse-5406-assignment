# Use lightweight Python 3 image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY app.py .
COPY twopc_participant.py .
COPY start.sh .
RUN chmod +x start.sh

# Create storage directory in container
RUN mkdir -p /storage
# Note: protos/ is mounted as volume in docker-compose.yml

# Expose Flask port and 2PC participant port
EXPOSE 5006 6001

# Run app (original app.py now includes 2PC support - backward compatible)
CMD ["./start.sh"]
