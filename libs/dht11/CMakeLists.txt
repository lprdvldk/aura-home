add_library(smarthouse_dht11
  src/decoder.cpp
  src/simulator.cpp
)

if(UNIX AND NOT APPLE)
  target_sources(smarthouse_dht11 PRIVATE src/linux_gpio.cpp)
  target_compile_definitions(smarthouse_dht11 PUBLIC SMART_HOUSE_DHT11_GPIO=1)
endif()

target_include_directories(smarthouse_dht11
  PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)

target_compile_features(smarthouse_dht11 PUBLIC cxx_std_23)

add_executable(smarthouse_dht11_tests tests/test_decoder.cpp)
target_link_libraries(smarthouse_dht11_tests PRIVATE smarthouse_dht11)

add_test(NAME dht11_decoder COMMAND smarthouse_dht11_tests)
