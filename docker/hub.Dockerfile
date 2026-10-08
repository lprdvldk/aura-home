FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    SMART_HOUSE_HOUSE_CONFIG=config/house.json \
    SMART_HOUSE_DATA_DIR=data/users \
    SMART_HOUSE_HTTP_HOST=0.0.0.0 \
    SMART_HOUSE_HTTP_PORT=18443 \
    SMART_HOUSE_GRPC_PORT=18551 \
    SMART_HOUSE_REQUIRE_AGENT_TOKEN=true \
    SMART_HOUSE_CORS_ORIGINS=http://127.0.0.1:18443,http://localhost:18443

COPY apps/hub/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY config config
COPY apps/hub .

EXPOSE 18443 18551
CMD ["python", "-m", "smarthouse_hub"]
