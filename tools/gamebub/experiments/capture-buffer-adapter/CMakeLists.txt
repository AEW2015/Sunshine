cmake_minimum_required(VERSION 3.20)
project(gamebub_capture_buffer_adapter LANGUAGES CXX)

include(CTest)

add_library(capture_buffer_adapter capture_buffer.cpp)
target_compile_features(capture_buffer_adapter PUBLIC cxx_std_20)
target_include_directories(capture_buffer_adapter PUBLIC "${CMAKE_CURRENT_SOURCE_DIR}")

if(BUILD_TESTING)
    add_executable(test_capture_buffer_adapter test_capture_buffer.cpp)
    target_link_libraries(test_capture_buffer_adapter PRIVATE capture_buffer_adapter)
    add_test(NAME capture_buffer_adapter COMMAND test_capture_buffer_adapter)
endif()
