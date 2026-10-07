#pragma once

#include <array>
#include <cstdint>
#include <expected>
#include <span>
#include <string_view>

namespace smarthouse::dht11 {

enum class Error : std::uint8_t {
  ok = 0,
  timeout = 1,
  checksum = 2,
  gpio = 3,
  no_response = 4,
};

[[nodiscard]] constexpr std::string_view to_string(Error error) noexcept {
  switch (error) {
    case Error::ok: return "ok";
    case Error::timeout: return "timeout";
    case Error::checksum: return "checksum";
    case Error::gpio: return "gpio";
    case Error::no_response: return "no_response";
  }
  return "unknown";
}

struct Reading {
  double temperature_c{};
  double humidity_pct{};
  std::array<std::uint8_t, 5> raw{};
};

[[nodiscard]] bool checksum_ok(std::span<const std::uint8_t, 5> bytes) noexcept;

/// Decode a 40-bit DHT11 frame: humidity_int, humidity_dec, temp_int, temp_dec, checksum.
[[nodiscard]] std::expected<Reading, Error> decode(std::span<const std::uint8_t, 5> bytes);

/// Reconstruct a frame from 40 one-wire bits (MSB first).
[[nodiscard]] std::array<std::uint8_t, 5> pack_bits(std::span<const int, 40> bits);

class Simulator {
 public:
  explicit Simulator(unsigned seed = 1) noexcept;
  [[nodiscard]] Reading read();

 private:
  unsigned seed_;
  int step_{};
};

class Reader {
 public:
  virtual ~Reader() = default;
  virtual std::expected<Reading, Error> read() = 0;
};

class SimulatorReader final : public Reader {
 public:
  explicit SimulatorReader(unsigned seed = 1) noexcept : simulator_(seed) {}
  std::expected<Reading, Error> read() override { return simulator_.read(); }

 private:
  Simulator simulator_;
};

#if defined(__linux__)
/// Bit-banged DHT11 reader on a Linux GPIO character device (Raspberry Pi).
class GpioReader final : public Reader {
 public:
  explicit GpioReader(int pin, const char* chip_path = "/dev/gpiochip0");
  ~GpioReader() override;
  GpioReader(const GpioReader&) = delete;
  GpioReader& operator=(const GpioReader&) = delete;
  std::expected<Reading, Error> read() override;

 private:
  int pin_{};
  int fd_{-1};
};
#endif

}  // namespace smarthouse::dht11
