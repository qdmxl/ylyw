"""
感知子包

从仿真环境（PyBullet）中提取物体的物理特征，
作为先验手册的输入。
"""
from .feature_extractor import FeatureExtractor, ObjectFeatures

__all__ = ["FeatureExtractor", "ObjectFeatures"]
