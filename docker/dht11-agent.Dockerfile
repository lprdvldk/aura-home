FROM debian:bookworm-slim AS build
RUN apt-get update && apt-get install -y --no-install-recommends \
      g++ cmake make ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src
COPY CMakeLists.txt CMakePresets.json ./
COPY libs ./libs
COPY apps/dht11-agent ./apps/dht11-agent
RUN cmake -S . -B /build -DCMAKE_BUILD_TYPE=Release -DSMART_HOUSE_BUILD_DESKTOP=OFF \
    && cmake --build /build --target smarthouse_dht11_agent -j"$(nproc)"

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends libstdc++6 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /build/apps/dht11-agent/smarthouse_dht11_agent /usr/local/bin/smarthouse_dht11_agent
ENV HUB_HOST=hub \
    HUB_PORT=18443 \
    DEVICE_ID=living-room-dht11
ENTRYPOINT ["/usr/local/bin/smarthouse_dht11_agent"]
CMD ["--host", "hub", "--port", "18443", "--device-id", "living-room-dht11", "--simulate"]
