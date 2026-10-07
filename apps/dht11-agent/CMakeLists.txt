add_executable(smarthouse_dht11_agent
  src/main.cpp
  src/http_json.cpp
)

target_link_libraries(smarthouse_dht11_agent PRIVATE smarthouse_dht11)
target_include_directories(smarthouse_dht11_agent PRIVATE src)
target_compile_features(smarthouse_dht11_agent PRIVATE cxx_std_23)

if(WIN32)
  target_link_libraries(smarthouse_dht11_agent PRIVATE ws2_32)
endif()
