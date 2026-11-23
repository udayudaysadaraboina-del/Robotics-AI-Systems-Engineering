#include <gtest/gtest.h>
#include <array>
#include <cstdint>
#include <span>

// C++20 std::span check (zero-copy buffer view used in robotics firmware)
uint32_t sum_bytes(std::span<const uint8_t> data) {
    uint32_t total = 0;
    for (uint8_t b : data) total += b;
    return total;
}

TEST(EnvironmentCheck, Cpp20SpanAndSanitizerWork) {
    std::array<uint8_t, 4> packet{0xAA, 0x01, 0x02, 0x03};
    EXPECT_EQ(sum_bytes(packet), 0xAAu + 1u + 2u + 3u);
}
