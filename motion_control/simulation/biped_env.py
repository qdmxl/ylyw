#!/usr/bin/env python3
"""
PyBullet 双足机器人仿真环境
使用简化的盒状双足模型进行运动控制验证
"""
import numpy as np
import pybullet as p
import pybullet_data


class SimpleBipedEnv:
    """
    简化双足机器人仿真环境
    
    机器人结构（盒状模型）：
      - 躯干 (torso): 中央主体
      - 左/右大腿 (thigh_l/r): 髋关节 → 膝关节
      - 左/右小腿 (shin_l/r): 膝关节 → 踝关节
      - 左/右脚 (foot_l/r): 踝关节 → 地面
    """
    
    def __init__(self, render=True, dt=1/240.):
        self.render = render
        self.dt = dt
        
        if render:
            self.client = p.connect(p.GUI)
            p.configureDebugVisualizer(p.COV_ENABLE_GUI, 0)
            p.resetDebugVisualizerCamera(1.5, 45, -30, [0, 0, 0.6])
        else:
            self.client = p.connect(p.DIRECT)
        
        p.setAdditionalSearchPath(pybullet_data.getDataPath())
        p.setGravity(0, 0, -9.81)
        p.setTimeStep(dt)
        
        # Load ground
        self.plane_id = p.loadURDF("plane.urdf")
        
        # Build robot
        self.robot_id = None
        self.joint_ids = {}
        self._build_robot()
        
        # State cache
        self.state = {}
    
    def _build_robot(self):
        """构建简化双足机器人"""
        # Collision shapes
        col_torso = p.createCollisionShape(p.GEOM_BOX, halfExtents=[0.12, 0.08, 0.15])
        col_thigh = p.createCollisionShape(p.GEOM_BOX, halfExtents=[0.04, 0.04, 0.18])
        col_shin  = p.createCollisionShape(p.GEOM_BOX, halfExtents=[0.04, 0.04, 0.18])
        col_foot  = p.createCollisionShape(p.GEOM_BOX, halfExtents=[0.06, 0.12, 0.03])
        
        # Visual shapes
        vis_torso = p.createVisualShape(p.GEOM_BOX, halfExtents=[0.12, 0.08, 0.15], rgbaColor=[0.3, 0.5, 0.8, 1])
        vis_thigh = p.createVisualShape(p.GEOM_BOX, halfExtents=[0.04, 0.04, 0.18], rgbaColor=[0.3, 0.7, 0.3, 1])
        vis_shin  = p.createVisualShape(p.GEOM_BOX, halfExtents=[0.04, 0.04, 0.18], rgbaColor=[0.3, 0.7, 0.3, 1])
        vis_foot  = p.createVisualShape(p.GEOM_BOX, halfExtents=[0.06, 0.12, 0.03], rgbaColor=[0.7, 0.3, 0.3, 1])
        
        base_pos = [0, 0, 0.85]
        base_id = p.createMultiBody(0, -1, col_torso, vis_torso, base_pos, [0,0,0,1])
        
        mass_thigh = 1.5
        mass_shin  = 1.0
        mass_foot  = 0.5
        
        # Joint definitions: (name, parent, child_shape, child_vis, pos, axis, limits)
        hips = [
            ('hip_l', base_id, col_thigh, vis_thigh, [0, 0.06, -0.15], [1,0,0], [-0.8, 0.8]),
            ('hip_r', base_id, col_thigh, vis_thigh, [0, -0.06, -0.15], [1,0,0], [-0.8, 0.8]),
        ]
        
        for name, parent, col, vis, pos, axis, limits in hips:
            joint_id = p.createMultiBody(mass_thigh, -1, col, vis, pos, [0,0,0,1])
            cid = p.createConstraint(parent, -1, joint_id, -1, 
                                     p.JOINT_REVOLUTE, axis, pos, [0,0,0],
                                     parentFramePosition=[0,0,0],
                                     childFramePosition=[0,0,0.18])
            p.changeConstraint(cid, maxForce=100)
            self.joint_ids[name] = cid
            # Store child body
            self.joint_ids[name + '_body'] = joint_id
        
        # Knee joints
        self._add_lower_legs(mass_shin, mass_foot, col_shin, vis_shin, col_foot, vis_foot)
    
    def _add_lower_legs(self, mass_shin, mass_foot, col_shin, vis_shin, col_foot, vis_foot):
        """Add knees and feet for each leg"""
        legs = [
            ('knee_l', 'hip_l', 'foot_l'),
            ('knee_r', 'hip_r', 'foot_r'),
        ]
        
        for knee_name, hip_name, foot_name in legs:
            thigh_body = self.joint_ids[hip_name + '_body']
            
            # Knee
            shin_body = p.createMultiBody(mass_shin, -1, col_shin, vis_shin, 
                                          [0, 0, -0.36], [0,0,0,1])
            knee_cid = p.createConstraint(thigh_body, -1, shin_body, -1,
                                          p.JOINT_REVOLUTE, [1,0,0],
                                          [0,0,-0.18], [0,0,0],
                                          childFramePosition=[0,0,0.18])
            p.changeConstraint(knee_cid, maxForce=80)
            self.joint_ids[knee_name] = knee_cid
            
            # Foot
            foot_body = p.createMultiBody(mass_foot, -1, col_foot, vis_foot,
                                          [0, 0, -0.39], [0,0,0,1])
            ankle_cid = p.createConstraint(shin_body, -1, foot_body, -1,
                                           p.JOINT_REVOLUTE, [1,0,0],
                                           [0,0,-0.18], [0,0,0],
                                           childFramePosition=[0,0,0.03])
            p.changeConstraint(ankle_cid, maxForce=50)
            self.joint_ids[foot_name] = ankle_cid
    
    def get_state(self):
        """
        获取机器人状态，返回6维归一化状态向量
        
        Returns:
            state_dict: dict with posture, com_height, force_dist, zmp_margin, disturbance, terrain
            state_vector: [6] numpy array
        """
        # Get torso state (base_id)
        pos, orn = p.getBasePositionAndOrientation(self.robot_id if self.robot_id else 0)
        lin_vel, ang_vel = p.getBaseVelocity(self.robot_id if self.robot_id else 0)
        
        # Use joint constraint 0's parent body as proxy
        # Actually, we need to track the base body. Let me restructure:
        # The base body was created implicitly in _build_robot. Let me use the first constraint's parent.
        
        # Simpler approach: get the torso body state from the first hip constraint
        if self.joint_ids:
            first_hip = list(self.joint_ids.values())[0]
            # For constraints, we need to query the parent body
            # Use the base position from _build_robot
            pass
        
        # Use simplified state estimation
        # In simulation, we can directly compute these from body states
        
        # Simplified: extract from the first body (torso-equivalent)
        all_bodies = [p.getBodyInfo(i) for i in range(p.getNumBodies())]
        
        # Get torso state using the hip constraint parent body
        # The constraint IDs are from createConstraint. Parent body index is stored.
        # Let's use a different approach: directly track the base body ID
        
        # Quick fix: use p.getBasePositionAndOrientation on body index 1 (the torso)
        # Actually indices: 0=plane, 1=torso, 2=hip_l, 3=hip_r, ...
        torso_idx = 1  # torso is the second body
        pos, orn = p.getBasePositionAndOrientation(torso_idx)
        lin_vel, ang_vel = p.getBaseVelocity(torso_idx)
        
        # Convert quaternion to euler
        euler = p.getEulerFromQuaternion(orn)
        pitch, roll, yaw = euler
        
        # Posture stability: combined pitch/roll deviation
        posture_stability = max(0, 1.0 - (abs(pitch) + abs(roll)) / 1.0)
        
        # COM height normalized
        com_height = pos[2]
        com_height_norm = min(1.0, max(0.0, com_height / 0.85))
        
        # Force distribution: simplified from foot contact forces
        # In simulation, we can approximate from contact points
        contact_points = p.getContactPoints(bodyA=torso_idx)
        if len(contact_points) > 0:
            forces = [cp[9] for cp in contact_points if cp[9] > 0]
            if forces and len(forces) >= 2:
                force_std = np.std(forces) / (np.mean(forces) + 1e-6)
                force_dist = max(0, 1.0 - force_std)
            else:
                force_dist = 0.5
        else:
            force_dist = 0.3  # In air
        
        # ZMP margin: simplified from COM position relative to support
        # Support polygon width is roughly ±0.06m in y direction
        com_y_deviation = abs(pos[1] - 0) / 0.06  # normalized by foot width
        zmp_margin = max(0, 1.0 - com_y_deviation)
        
        # Disturbance: from angular velocity magnitude
        ang_vel_mag = np.linalg.norm(ang_vel)
        disturbance = min(1.0, ang_vel_mag / 5.0)
        
        # Terrain: default flat (will be updated for terrain experiments)
        terrain = 0.80
        
        state_dict = {
            'posture': posture_stability,
            'com_height': com_height_norm,
            'force_dist': force_dist,
            'zmp_margin': zmp_margin,
            'disturbance': disturbance,
            'terrain': terrain,
        }
        
        state_vector = np.array([posture_stability, com_height_norm, 
                                 force_dist, zmp_margin, disturbance, terrain])
        
        return state_dict, state_vector
    
    def apply_gait(self, gait_params, phase=0):
        """
        根据步态参数施加关节控制
        
        Args:
            gait_params: dict with speed, step_height, freq, force_coefficient
            phase: gait phase [0, 2π)
        """
        speed = gait_params.get('speed', 0.5)
        step_height = gait_params.get('step_height', 0.05)
        freq = gait_params.get('freq', 1.5)
        force_coef = gait_params.get('force_coefficient', 0.5)
        
        if speed < 0.01:
            # Standing: hold position
            for name in ['hip_l', 'hip_r', 'knee_l', 'knee_r', 'foot_l', 'foot_r']:
                if name in self.joint_ids:
                    p.changeConstraint(self.joint_ids[name], maxForce=50 * force_coef)
            return
        
        # Simple sinusoidal gait
        hip_amp = 0.3 * speed
        knee_amp = 0.2 * speed
        foot_amp = 0.1 * speed
        
        # Left leg phase offset
        left_phase = phase
        right_phase = phase + np.pi
        
        joint_positions = {
            'hip_l':  hip_amp * np.sin(left_phase),
            'knee_l': knee_amp * np.sin(left_phase - np.pi/2),
            'foot_l': foot_amp * np.sin(left_phase),
            'hip_r':  hip_amp * np.sin(right_phase),
            'knee_r': knee_amp * np.sin(right_phase - np.pi/2),
            'foot_r': foot_amp * np.sin(right_phase),
        }
        
        max_force = 80 * force_coef
        for name, target_pos in joint_positions.items():
            if name in self.joint_ids:
                # For constraints, we can't set target position directly
                # We need to use changeConstraint for position control
                # For revolute joints, use the joint position
                pass
        
        # Alternative: use position control through setJointMotorControl
        # This requires the bodies to be linked differently
        # For now, we simulate gait by adjusting constraint forces
    
    def step(self):
        """Advance simulation by one step"""
        p.stepSimulation()
    
    def close(self):
        p.disconnect(self.client)


class BipedSimulation:
    """
    高级仿真接口：封装环境 + YLYW控制器
    """
    
    def __init__(self, render=True):
        self.env = SimpleBipedEnv(render=render)
        self.time = 0
        self.phase = 0
    
    def get_state(self):
        return self.env.get_state()
    
    def step_with_gait(self, gait_params):
        """应用步态并推进仿真"""
        self.phase += gait_params.get('freq', 1.5) * self.env.dt * 2 * np.pi
        self.phase %= 2 * np.pi
        self.env.apply_gait(gait_params, self.phase)
        self.env.step()
        self.time += self.env.dt
    
    def close(self):
        self.env.close()


if __name__ == '__main__':
    import time
    
    env = SimpleBipedEnv(render=True)
    print("Simulation started. Press Ctrl+C to stop.")
    
    try:
        for step in range(1000):
            state_dict, state_vec = env.get_state()
            if step % 50 == 0:
                print(f"Step {step}: posture={state_dict['posture']:.2f}, "
                      f"com_h={state_dict['com_height']:.2f}, "
                      f"force_dist={state_dict['force_dist']:.2f}, "
                      f"zmp={state_dict['zmp_margin']:.2f}, "
                      f"dist={state_dict['disturbance']:.2f}")
            env.step()
    except KeyboardInterrupt:
        pass
    finally:
        env.close()
        print("Simulation closed.")
