FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app (original file with minimal 2PC additions)
COPY app.py .
COPY twopc_participant.py .
COPY start.sh .
RUN chmod +x start.sh

# Ensure data directory exists
RUN mkdir -p /data
# Note: protos/ is mounted as volume in docker-compose.yml

EXPOSE 5005 6002

# Original app.py now includes 2PC support (backward compatible)
CMD ["./start.sh"]
