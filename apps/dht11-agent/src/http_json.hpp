#pragma once

#include <cstdint>
#include <string>
#include <string_view>

namespace smarthouse::agent {

bool post_json(std::string_view host, std::uint16_t port, std::string_view path, std::string_view body,
               std::string* error, std::string_view agent_token = {});

}  // namespace smarthouse::agent
