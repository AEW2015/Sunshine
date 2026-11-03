cmake_minimum_required(VERSION 3.20)
project(gamebub_capture_buffer_adapter LANGUAGES CXX)

include(CTest)

add_library(capture_buffer_adapter capture_buffer.cpp)
target_compile_features(capture_buffer_adapter PUBLIC cxx_std_20)
target_include_directories(capture_buffer_adapter PUBLIC "${CMAKE_CURRENT_SOURCE_DIR}")

add_executable(bench_capture_buffer bench_capture_buffer.cpp)
target_link_libraries(bench_capture_buffer PRIVATE capture_buffer_adapter)

add_executable(dump_canvas_pattern dump_canvas_pattern.cpp)
target_link_libraries(dump_canvas_pattern PRIVATE capture_buffer_adapter)

add_executable(scale_raw_rgb scale_raw_rgb.cpp)
target_link_libraries(scale_raw_rgb PRIVATE capture_buffer_adapter)

if(BUILD_TESTING)
    add_executable(test_capture_buffer_adapter test_capture_buffer.cpp)
    target_link_libraries(test_capture_buffer_adapter PRIVATE capture_buffer_adapter)
    add_test(NAME capture_buffer_adapter COMMAND test_capture_buffer_adapter)
endif()
