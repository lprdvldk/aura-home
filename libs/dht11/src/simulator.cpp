#include "smarthouse/dht11/dht11.hpp"

#include <algorithm>
#include <cmath>

namespace smarthouse::dht11 {

Simulator::Simulator(unsigned seed) noexcept : seed_(seed == 0 ? 1 : seed) {}

Reading Simulator::read() {
  seed_ = seed_ * 1664525u + 1013904223u;
  const double noise = static_cast<double>(seed_ % 1000) / 1000.0;
  const double t = static_cast<double>(step_++) / 8.0;
  const auto temperature = static_cast<int>(std::lround(21.0 + 2.0 * std::sin(t / 9.0) + (noise - 0.5) * 0.4));
  const auto humidity = static_cast<int>(std::lround(45.0 + 6.0 * std::sin(t / 11.0 + 0.7) + (noise - 0.5) * 0.6));
  Reading reading;
  reading.temperature_c = static_cast<double>(std::clamp(temperature, 0, 50));
  reading.humidity_pct = static_cast<double>(std::clamp(humidity, 20, 90));
  reading.raw[0] = static_cast<std::uint8_t>(reading.humidity_pct);
  reading.raw[2] = static_cast<std::uint8_t>(reading.temperature_c);
  const unsigned sum = static_cast<unsigned>(reading.raw[0]) + reading.raw[1] + reading.raw[2] + reading.raw[3];
  reading.raw[4] = static_cast<std::uint8_t>(sum);
  return reading;
}

}  // namespace smarthouse::dht11
