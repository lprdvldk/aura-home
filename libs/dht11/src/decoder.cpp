#include "smarthouse/dht11/dht11.hpp"

#include <algorithm>

namespace smarthouse::dht11 {

bool checksum_ok(std::span<const std::uint8_t, 5> bytes) noexcept {
  const unsigned sum = static_cast<unsigned>(bytes[0]) + bytes[1] + bytes[2] + bytes[3];
  return static_cast<std::uint8_t>(sum) == bytes[4];
}

std::expected<Reading, Error> decode(std::span<const std::uint8_t, 5> bytes) {
  if (!checksum_ok(bytes)) {
    return std::unexpected(Error::checksum);
  }
  // DHT11: integral bytes only. DHT22 uses a 16-bit scaled format; we stay with DHT11.
  Reading reading;
  reading.humidity_pct = static_cast<double>(bytes[0]);
  reading.temperature_c = static_cast<double>(bytes[2]);
  std::copy(bytes.begin(), bytes.end(), reading.raw.begin());
  if (reading.humidity_pct > 100.0 || reading.temperature_c > 60.0) {
    return std::unexpected(Error::checksum);
  }
  return reading;
}

std::array<std::uint8_t, 5> pack_bits(std::span<const int, 40> bits) {
  std::array<std::uint8_t, 5> bytes{};
  for (int i = 0; i < 40; ++i) {
    bytes[static_cast<std::size_t>(i / 8)] =
        static_cast<std::uint8_t>((bytes[static_cast<std::size_t>(i / 8)] << 1) | (bits[static_cast<std::size_t>(i)] ? 1 : 0));
  }
  return bytes;
}

}  // namespace smarthouse::dht11
