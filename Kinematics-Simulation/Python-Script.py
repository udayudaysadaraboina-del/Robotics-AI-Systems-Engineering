# # 23CSE207: Python Programming Lab
# # Scenario: Autonomous Rover Telemetry & Sensor Processing Hub

# def process_lidar_data(sensor_readings):
#     print("Initializing Central Telemetry Processing Pipeline...")
    
#     # Filtering sensor noise (simulating distance checks)
#     for sensor_id, distance in sensor_readings.items():
#         if distance < 0.5:
#             print(f"⚠️ ALERT: Obstacle detected near {sensor_id}! Distance: {distance}m - Triggering Brake Protocol.")
#         else:
#             print(f"✅ {sensor_id} Clear. Distance: {distance}m")

# # Simulated real-time distance inputs from Rover micro-sensors (in meters)
# mock_lidar_inputs = {
#     "Front_Sensor": 1.2,
#     "Left_Sensor": 0.3,
#     "Right_Sensor": 0.8
# }

# # Execute telemetry pipeline
# process_lidar_data(mock_lidar_inputs)


# a = 7
# b = 4
# print(a+b)
# print(a-b)
# print(a * b)
# print(a / b)
# print(a // b)
# print(a == b)
# print(a != b)
# print(a <= b)
# print(a >= b)
# print(a < b)
# print(a > b)

import matplotlib.pyplot as plt
x= [5, 2, 9, 4, 7]
y= [10,5, 8, 4, 2]
plt.scatter(x, y)
plt.savefig("kinematics_scatter.png", dpi=300)
print("\n[SUCCESS] Scatter graph saved to disk as kinematics_scatter.png")




