FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/hub:/app/reader \
    SMART_HOUSE_GRPC_TARGET=hub:18551 \
    SMART_HOUSE_HOUSE_CONFIG=/app/config/house.json

COPY apps/hub/requirements.txt /tmp/hub-requirements.txt
COPY apps/device-reader/requirements.txt /tmp/reader-requirements.txt
RUN pip install --no-cache-dir -r /tmp/hub-requirements.txt -r /tmp/reader-requirements.txt

COPY config /app/config
COPY apps/hub /app/hub
COPY apps/device-reader /app/reader

WORKDIR /app/reader
CMD ["python", "-m", "smarthouse_device_reader", "--target", "hub:18551", "--config", "/app/config/house.json"]
