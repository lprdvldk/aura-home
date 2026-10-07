FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/apps/hub \
    SMART_HOUSE_DATA=/app/data/users \
    SMART_HOUSE_HTTP_HOST=0.0.0.0 \
    SMART_HOUSE_HTTP_PORT=18443 \
    SMART_HOUSE_GRPC_PORT=18551

COPY apps/hub/requirements.txt /app/apps/hub/requirements.txt
RUN pip install --no-cache-dir -r /app/apps/hub/requirements.txt

COPY proto /app/proto
COPY config /app/config
COPY apps/hub /app/apps/hub

EXPOSE 18443 18551
CMD ["python", "-m", "smarthouse_hub"]
