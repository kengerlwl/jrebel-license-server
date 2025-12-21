#!/usr/bin/env python3
"""
服务层模块
"""

from services.signer import JRebelSigner, JetBrainsSigner, SERVER_RANDOMNESS

# 全局签名器实例
jrebel_signer = JRebelSigner()
jetbrains_signer = JetBrainsSigner()

__all__ = ['jrebel_signer', 'jetbrains_signer', 'JRebelSigner', 'JetBrainsSigner', 'SERVER_RANDOMNESS']

