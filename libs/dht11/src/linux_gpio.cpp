#include "smarthouse/dht11/dht11.hpp"

#if defined(__linux__)

#include <array>
#include <chrono>
#include <cstring>
#include <fcntl.h>
#include <linux/gpio.h>
#include <sys/ioctl.h>
#include <thread>
#include <unistd.h>

namespace smarthouse::dht11 {
namespace {

using ns = std::chrono::nanoseconds;
using clock = std::chrono::steady_clock;

int read_level(int line_fd) {
  gpio_v2_line_values values{};
  values.mask = 1;
  if (ioctl(line_fd, GPIO_V2_LINE_GET_VALUES_IOCTL, &values) < 0) {
    return -1;
  }
  return static_cast<int>(values.bits & 1u);
}

bool wait_for_level(int line_fd, int wanted, ns timeout) {
  const auto start = clock::now();
  while (clock::now() - start < timeout) {
    const int level = read_level(line_fd);
    if (level < 0) return false;
    if (level == wanted) return true;
  }
  return false;
}

void busy_wait(ns duration) {
  const auto start = clock::now();
  while (clock::now() - start < duration) {
  }
}

bool set_direction(int line_fd, bool output, int value) {
  gpio_v2_line_config config{};
  if (output) {
    config.flags = GPIO_V2_LINE_FLAG_OUTPUT | GPIO_V2_LINE_FLAG_BIAS_PULL_UP;
    config.num_attrs = 1;
    config.attrs[0].attr.id = GPIO_V2_LINE_ATTR_ID_OUTPUT_VALUES;
    config.attrs[0].attr.values = value ? 1 : 0;
    config.attrs[0].mask = 1;
  } else {
    config.flags = GPIO_V2_LINE_FLAG_INPUT | GPIO_V2_LINE_FLAG_BIAS_PULL_UP;
  }
  return ioctl(line_fd, GPIO_V2_LINE_SET_CONFIG_IOCTL, &config) >= 0;
}

}  // namespace

GpioReader::GpioReader(int pin, const char* chip_path) : pin_(pin) {
  fd_ = ::open(chip_path, O_RDWR | O_CLOEXEC);
}

GpioReader::~GpioReader() {
  if (fd_ >= 0) {
    ::close(fd_);
  }
}

std::expected<Reading, Error> GpioReader::read() {
  if (fd_ < 0) {
    return std::unexpected(Error::gpio);
  }

  gpio_v2_line_request req{};
  req.num_lines = 1;
  req.offsets[0] = static_cast<std::uint32_t>(pin_);
  req.config.flags = GPIO_V2_LINE_FLAG_OUTPUT | GPIO_V2_LINE_FLAG_BIAS_PULL_UP;
  std::strncpy(req.consumer, "dht11", sizeof(req.consumer) - 1);
  if (ioctl(fd_, GPIO_V2_GET_LINE_IOCTL, &req) < 0) {
    return std::unexpected(Error::gpio);
  }
  const int line_fd = req.fd;

  if (!set_direction(line_fd, true, 0)) {
    ::close(line_fd);
    return std::unexpected(Error::gpio);
  }
  std::this_thread::sleep_for(std::chrono::milliseconds(20));
  if (!set_direction(line_fd, true, 1)) {
    ::close(line_fd);
    return std::unexpected(Error::gpio);
  }
  busy_wait(std::chrono::microseconds(30));
  if (!set_direction(line_fd, false, 0)) {
    ::close(line_fd);
    return std::unexpected(Error::gpio);
  }

  if (!wait_for_level(line_fd, 0, std::chrono::milliseconds(2)) ||
      !wait_for_level(line_fd, 1, std::chrono::milliseconds(2)) ||
      !wait_for_level(line_fd, 0, std::chrono::milliseconds(2))) {
    ::close(line_fd);
    return std::unexpected(Error::no_response);
  }

  std::array<int, 40> bits{};
  for (int i = 0; i < 40; ++i) {
    if (!wait_for_level(line_fd, 1, std::chrono::milliseconds(1))) {
      ::close(line_fd);
      return std::unexpected(Error::timeout);
    }
    const auto rise = clock::now();
    if (!wait_for_level(line_fd, 0, std::chrono::milliseconds(1))) {
      ::close(line_fd);
      return std::unexpected(Error::timeout);
    }
    bits[static_cast<std::size_t>(i)] = (clock::now() - rise) > std::chrono::microseconds(50) ? 1 : 0;
  }

  ::close(line_fd);
  return decode(pack_bits(bits));
}

}  // namespace smarthouse::dht11

#endif
