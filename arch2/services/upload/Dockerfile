FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
COPY twopc_coordinator.py .
COPY start.sh .
RUN chmod +x start.sh
# Note: protos/ is mounted as volume in docker-compose.yml
CMD ["./start.sh"]