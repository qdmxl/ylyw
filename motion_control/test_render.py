#!/usr/bin/env python3
"""最小化测试：验证PyBullet渲染"""
import pybullet as p, pybullet_data, time

# 不要opengl2，先试默认
cid = p.connect(p.GUI)
print(f"Connected: {cid}")
print(f"PyBullet version info: {p.getAPIVersion()}")

p.setAdditionalSearchPath(pybullet_data.getDataPath())
p.setGravity(0, 0, -9.81)

# 地面
p.loadURDF("plane.urdf")
# 大红球
vs = p.createVisualShape(p.GEOM_SPHERE, radius=0.5, rgbaColor=[1, 0, 0, 1])
cs = p.createCollisionShape(p.GEOM_SPHERE, radius=0.5)
p.createMultiBody(baseMass=0, baseCollisionShapeIndex=cs, baseVisualShapeIndex=vs, basePosition=[0, 0, 1.5])

# 简单摄像头
p.resetDebugVisualizerCamera(cameraDistance=3, cameraYaw=45, cameraPitch=-25, cameraTargetPosition=[0, 0, 1])
p.configureDebugVisualizer(p.COV_ENABLE_GUI, 0)

print("\n你应该看到：灰色地面 + 一个红色大球悬浮在空中")
print("看到红球了吗？按Ctrl+C退出")

try:
    for i in range(10000):
        p.stepSimulation()
        time.sleep(0.02)
except KeyboardInterrupt:
    pass

p.disconnect(cid)
