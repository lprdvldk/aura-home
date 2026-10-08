FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/hub:/app/agent \
    SMART_HOUSE_GRPC_TARGET=hub:18551 \
    SMART_HOUSE_HOUSE_CONFIG=/app/config/house.json

COPY apps/hub/requirements.txt /tmp/hub-requirements.txt
COPY apps/sensor-agent/requirements.txt /tmp/agent-requirements.txt
RUN pip install --no-cache-dir -r /tmp/hub-requirements.txt -r /tmp/agent-requirements.txt

COPY config /app/config
COPY apps/hub /app/hub
COPY apps/sensor-agent /app/agent

WORKDIR /app/agent
CMD ["python", "-m", "smarthouse_sensor_agent", "--target", "hub:18551", "--config", "/app/config/house.json"]
