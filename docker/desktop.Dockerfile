FROM ubuntu:24.04 AS build
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      g++ cmake make ca-certificates \
      qt6-base-dev qt6-charts-dev qt6-websockets-dev \
      libgl1-mesa-dev libopengl-dev \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src
COPY CMakeLists.txt CMakePresets.json ./
COPY libs ./libs
COPY apps ./apps
RUN cmake -S . -B /build -DCMAKE_BUILD_TYPE=Release -DSMART_HOUSE_BUILD_DESKTOP=ON \
    && cmake --build /build --target smarthouse_desktop -j"$(nproc)"

FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      libqt6widgets6 libqt6gui6 libqt6core6 libqt6network6 \
      libqt6charts6 libqt6websockets6 libgl1 libopengl0 \
      ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /build/apps/desktop/SmartHouse /usr/local/bin/SmartHouse
ENV QT_QPA_PLATFORM=offscreen \
    HUB_HOST=127.0.0.1 \
    HUB_PORT=18443
ENTRYPOINT ["/usr/local/bin/SmartHouse"]
