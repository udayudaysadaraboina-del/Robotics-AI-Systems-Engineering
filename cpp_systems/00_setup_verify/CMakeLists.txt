cmake_minimum_required(VERSION 3.22)
project(SetupVerify LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

enable_testing()
find_package(GTest REQUIRED)

add_executable(verify_setup_test verify_setup_test.cpp)
target_compile_options(verify_setup_test PRIVATE -Wall -Wextra -Werror -fsanitize=address,undefined)
target_link_options(verify_setup_test PRIVATE -fsanitize=address,undefined)
target_link_libraries(verify_setup_test PRIVATE GTest::gtest_main)

include(GoogleTest)
gtest_discover_tests(verify_setup_test)
