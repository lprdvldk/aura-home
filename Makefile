PYTHON ?= python3
VENV ?= .venv
PY := $(VENV)/bin/python
HTTP_PORT ?= 18443
GRPC_PORT ?= 18551

.PHONY: venv proto hub test dht11 desktop compose compose-up

venv:
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/pip install -r apps/hub/requirements.txt

proto:
	$(PY) scripts/generate_proto.py

hub:
	PYTHONPATH=apps/hub $(PY) -m smarthouse_hub.main --http-port $(HTTP_PORT) --grpc-port $(GRPC_PORT)

test:
	PYTHONPATH=apps/hub $(VENV)/bin/pytest apps/hub/tests -q
	cmake -S . -B build-agent -DSMART_HOUSE_BUILD_DESKTOP=OFF
	cmake --build build-agent
	cd build-agent && ctest --output-on-failure

dht11:
	cmake -S . -B build-agent -DSMART_HOUSE_BUILD_DESKTOP=OFF
	cmake --build build-agent --target smarthouse_dht11_agent smarthouse_dht11_tests

desktop:
	cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
	cmake --build build --target smarthouse_desktop

compose:
	docker compose build hub dht11-agent

compose-up:
	docker compose up --build
