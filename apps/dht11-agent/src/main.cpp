#include "http_json.hpp"
#include "smarthouse/dht11/dht11.hpp"

#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <memory>
#include <sstream>
#include <string>
#include <thread>

namespace {

struct Options {
  std::string host{"127.0.0.1"};
  std::uint16_t port{18443};
  std::string device_id{"living-room-dht11"};
  std::string token;
  int pin{16};
  bool simulate{true};
  int interval_ms{1000};
};

Options parse(int argc, char** argv) {
  Options opt;
  if (const char* env_token = std::getenv("SMART_HOUSE_AGENT_TOKEN")) {
    opt.token = env_token;
  }
  for (int i = 1; i < argc; ++i) {
    const std::string arg = argv[i];
    auto next = [&]() -> std::string {
      if (i + 1 >= argc) return {};
      return argv[++i];
    };
    if (arg == "--host") opt.host = next();
    else if (arg == "--port") opt.port = static_cast<std::uint16_t>(std::stoi(next()));
    else if (arg == "--device-id") opt.device_id = next();
    else if (arg == "--token") opt.token = next();
    else if (arg == "--pin") opt.pin = std::stoi(next());
    else if (arg == "--gpio") opt.simulate = false;
    else if (arg == "--simulate") opt.simulate = true;
    else if (arg == "--interval-ms") opt.interval_ms = std::stoi(next());
    else if (arg == "--help") {
      std::cout <<
          "dht11-agent --host 127.0.0.1 --port 18443 --device-id living-room-dht11 "
          "[--token TOKEN] [--simulate|--gpio --pin 16]\n";
      std::exit(0);
    }
  }
  return opt;
}

std::int64_t now_ms() {
  using namespace std::chrono;
  return duration_cast<milliseconds>(system_clock::now().time_since_epoch()).count();
}

std::string sample_json(const std::string& device_id, const smarthouse::dht11::Reading& reading, int error_code,
                        std::string_view error_message) {
  std::ostringstream json;
  json << "{\"device_id\":\"" << device_id << "\",\"unix_ms\":" << now_ms()
       << ",\"source\":\"agent\",\"error_code\":" << error_code << ",\"error_message\":\"" << error_message
       << "\",\"metrics\":["
       << "{\"name\":\"temperature_c\",\"value\":" << reading.temperature_c << ",\"unit\":\"°C\"},"
       << "{\"name\":\"humidity_pct\",\"value\":" << reading.humidity_pct << ",\"unit\":\"%\"}"
       << "]}";
  return json.str();
}

}  // namespace

int main(int argc, char** argv) {
  const auto opt = parse(argc, argv);
  std::unique_ptr<smarthouse::dht11::Reader> reader;
  if (opt.simulate) {
    reader = std::make_unique<smarthouse::dht11::SimulatorReader>(static_cast<unsigned>(opt.pin + 3));
    std::clog << "dht11-agent: simulator mode for " << opt.device_id << '\n';
  } else {
#if defined(__linux__)
    reader = std::make_unique<smarthouse::dht11::GpioReader>(opt.pin);
    std::clog << "dht11-agent: GPIO pin " << opt.pin << " for " << opt.device_id << '\n';
#else
    std::cerr << "GPIO backend is only built on Linux. Use --simulate on this host.\n";
    return 1;
#endif
  }

  if (opt.token.empty()) {
    std::clog << "dht11-agent: no --token / SMART_HOUSE_AGENT_TOKEN; hub ingest may return 401\n";
  }

  while (true) {
    const auto result = reader->read();
    smarthouse::dht11::Reading reading{};
    int error_code = 0;
    std::string error_message;
    if (result) {
      reading = *result;
    } else {
      error_code = static_cast<int>(result.error());
      error_message = std::string(smarthouse::dht11::to_string(result.error()));
    }
    const auto body = sample_json(opt.device_id, reading, error_code, error_message);
    std::string err;
    if (!smarthouse::agent::post_json(opt.host, opt.port, "/v1/samples", body, &err, opt.token)) {
      std::cerr << "push failed: " << err << '\n';
    } else {
      std::clog << opt.device_id << " t=" << reading.temperature_c << "C rh=" << reading.humidity_pct << "%\n";
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(opt.interval_ms));
  }
}
