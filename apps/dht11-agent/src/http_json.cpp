#include "http_json.hpp"

#include <cstdint>
#include <sstream>
#include <string>

#if defined(_WIN32)
#include <winsock2.h>
#include <ws2tcpip.h>
#pragma comment(lib, "ws2_32.lib")
#else
#include <arpa/inet.h>
#include <netdb.h>
#include <sys/socket.h>
#include <unistd.h>
#endif

namespace smarthouse::agent {
namespace {

#if defined(_WIN32)
using socket_t = SOCKET;
constexpr socket_t kInvalid = INVALID_SOCKET;
void close_socket(socket_t fd) { closesocket(fd); }
#else
using socket_t = int;
constexpr socket_t kInvalid = -1;
void close_socket(socket_t fd) { ::close(fd); }
#endif

}  // namespace

bool post_json(std::string_view host, std::uint16_t port, std::string_view path, std::string_view body,
               std::string* error, std::string_view agent_token) {
#if defined(_WIN32)
  WSADATA wsa{};
  if (WSAStartup(MAKEWORD(2, 2), &wsa) != 0) {
    if (error) *error = "WSAStartup failed";
    return false;
  }
#endif

  addrinfo hints{};
  hints.ai_socktype = SOCK_STREAM;
  hints.ai_family = AF_UNSPEC;
  addrinfo* info = nullptr;
  const auto port_s = std::to_string(port);
  if (getaddrinfo(std::string(host).c_str(), port_s.c_str(), &hints, &info) != 0) {
    if (error) *error = "getaddrinfo failed";
#if defined(_WIN32)
    WSACleanup();
#endif
    return false;
  }

  socket_t fd = kInvalid;
  for (auto* p = info; p != nullptr; p = p->ai_next) {
    fd = ::socket(p->ai_family, p->ai_socktype, p->ai_protocol);
    if (fd == kInvalid) continue;
    if (::connect(fd, p->ai_addr, static_cast<int>(p->ai_addrlen)) == 0) break;
    close_socket(fd);
    fd = kInvalid;
  }
  freeaddrinfo(info);
  if (fd == kInvalid) {
    if (error) *error = "connect failed";
#if defined(_WIN32)
    WSACleanup();
#endif
    return false;
  }

  std::ostringstream req;
  req << "POST " << path << " HTTP/1.1\r\n"
      << "Host: " << host << "\r\n"
      << "Content-Type: application/json\r\n"
      << "Content-Length: " << body.size() << "\r\n";
  if (!agent_token.empty()) {
    req << "X-Agent-Token: " << agent_token << "\r\n";
  }
  req << "Connection: close\r\n\r\n" << body;
  const auto payload = req.str();
  const char* cursor = payload.data();
  std::size_t left = payload.size();
  while (left > 0) {
    const auto sent = ::send(fd, cursor, static_cast<int>(left), 0);
    if (sent <= 0) {
      close_socket(fd);
      if (error) *error = "send failed";
#if defined(_WIN32)
      WSACleanup();
#endif
      return false;
    }
    cursor += sent;
    left -= static_cast<std::size_t>(sent);
  }

  char buf[256];
  const auto n = ::recv(fd, buf, sizeof(buf) - 1, 0);
  close_socket(fd);
#if defined(_WIN32)
  WSACleanup();
#endif
  if (n <= 0) {
    if (error) *error = "empty response";
    return false;
  }
  buf[n] = '\0';
  const bool ok = std::string(buf).find(" 200 ") != std::string::npos ||
                  std::string(buf).find("HTTP/1.1 200") != std::string::npos;
  if (!ok && error) *error = buf;
  return ok;
}

}  // namespace smarthouse::agent
