#include "smarthouse/dht11/dht11.hpp"

#include <array>
#include <cstdlib>
#include <iostream>

namespace {

int fail(const char* message) {
  std::cerr << "FAIL: " << message << '\n';
  return EXIT_FAILURE;
}

}  // namespace

int main() {
  const std::array<std::uint8_t, 5> good{45, 0, 23, 0, 68};
  const auto decoded = smarthouse::dht11::decode(good);
  if (!decoded) {
    return fail("valid DHT11 frame rejected");
  }
  if (decoded->temperature_c != 23.0 || decoded->humidity_pct != 45.0) {
    return fail("decoded values mismatch");
  }

  const std::array<std::uint8_t, 5> bad{45, 0, 23, 0, 0};
  if (smarthouse::dht11::decode(bad)) {
    return fail("bad checksum accepted");
  }

  std::array<int, 40> bits{};
  const std::array<std::uint8_t, 5> source{40, 0, 21, 0, 61};
  for (int i = 0; i < 40; ++i) {
    bits[static_cast<std::size_t>(i)] = (source[static_cast<std::size_t>(i / 8)] >> (7 - (i % 8))) & 1;
  }
  const auto packed = smarthouse::dht11::pack_bits(bits);
  if (packed != source) {
    return fail("bit pack round-trip failed");
  }

  smarthouse::dht11::SimulatorReader reader{7};
  const auto sample = reader.read();
  if (!sample) {
    return fail("simulator failed");
  }
  if (sample->humidity_pct < 20.0 || sample->humidity_pct > 90.0) {
    return fail("simulator humidity out of range");
  }

  std::cout << "dht11 decoder tests ok\n";
  return EXIT_SUCCESS;
}
