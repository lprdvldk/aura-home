find_package(Qt6 REQUIRED COMPONENTS Widgets Charts WebSockets Network)

qt_standard_project_setup()

qt_add_executable(smarthouse_desktop
  src/main.cpp
  src/HubClient.cpp
  src/TelemetryStore.cpp
  src/KpiCard.cpp
  src/ClimateChart.cpp
  src/MainWindow.cpp
)

target_include_directories(smarthouse_desktop PRIVATE src)
target_link_libraries(smarthouse_desktop PRIVATE
  Qt6::Widgets
  Qt6::Charts
  Qt6::WebSockets
  Qt6::Network
)
target_compile_features(smarthouse_desktop PRIVATE cxx_std_23)

set_target_properties(smarthouse_desktop PROPERTIES
  WIN32_EXECUTABLE TRUE
  MACOSX_BUNDLE TRUE
  MACOSX_BUNDLE_BUNDLE_NAME "Smart House"
  MACOSX_BUNDLE_GUI_IDENTIFIER "dev.smarthouse.desktop"
  MACOSX_BUNDLE_BUNDLE_VERSION ${PROJECT_VERSION}
  MACOSX_BUNDLE_SHORT_VERSION_STRING ${PROJECT_VERSION}
  OUTPUT_NAME "SmartHouse"
)

install(TARGETS smarthouse_desktop
  BUNDLE DESTINATION .
  RUNTIME DESTINATION bin
)
