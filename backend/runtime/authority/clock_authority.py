"""
Clock Authority - 时钟权威

设计原则：
- 唯一的时间源
- 不允许任何组件自己调用 datetime.now() 或 time.time()
- 支持 LIVE / REPLAY 两种模式
"""

from enum import Enum
from datetime import datetime
from typing import Optional

from infrastructure.logging import get_logger

logger = get_logger("runtime.authority.clock")


class ClockMode(Enum):
    """时钟模式"""
    LIVE = "live"      # 实时模式：wall clock
    REPLAY = "replay"  # 回放模式：手动控制
    FROZEN = "frozen"  # 冻结模式：用于测试


class ClockAuthority:
    """
    时钟权威：唯一的时间源
    
    任何需要获取时间的组件必须通过这里
    """
    
    def __init__(self, mode: ClockMode = ClockMode.LIVE):
        self._mode = mode
        self._replay_time_ms: Optional[int] = None
        self._frozen_time_ms: Optional[int] = None
        self._last_time_ms: Optional[int] = None
        
        logger.info(f"ClockAuthority initialized in {mode.value} mode")
    
    @property
    def mode(self) -> ClockMode:
        """当前模式"""
        return self._mode
    
    def now_ms(self) -> int:
        """
        获取当前时间（唯一入口）
        
        Raises:
            ValueError: 时钟未初始化
        """
        if self._mode == ClockMode.LIVE:
            # LIVE 模式：使用 UTC wall clock
            return int(datetime.utcnow().timestamp() * 1000)
        
        elif self._mode == ClockMode.REPLAY:
            # REPLAY 模式：使用手动设置的时间
            if self._replay_time_ms is None:
                raise ValueError("Clock in REPLAY mode but no time set")
            return self._replay_time_ms
        
        elif self._mode == ClockMode.FROZEN:
            # FROZEN 模式：使用冻结的时间
            if self._frozen_time_ms is None:
                raise ValueError("Clock in FROZEN mode but not frozen")
            return self._frozen_time_ms
        
        else:
            raise ValueError(f"Unknown clock mode: {self._mode}")
    
    def advance_to(self, target_ms: int) -> None:
        """
        REPLAY 模式：时间前进
        
        Args:
            target_ms: 目标时间戳
        
        Raises:
            ValueError: 不是 REPLAY 模式，或时间倒退
        """
        if self._mode != ClockMode.REPLAY:
            raise ValueError(f"advance_to() only allowed in REPLAY mode, current: {self._mode}")
        
        if self._replay_time_ms is not None and target_ms < self._replay_time_ms:
            raise ValueError(
                f"Time cannot go backwards: {target_ms} < {self._replay_time_ms}"
            )
        
        self._replay_time_ms = target_ms
        self._last_time_ms = target_ms
        
        logger.debug(f"Clock advanced to {target_ms}")
    
    def freeze(self) -> None:
        """
        冻结时间（用于测试）
        
        冻结后，now_ms() 返回固定时间
        """
        if self._mode == ClockMode.FROZEN:
            return  # 已经冻结
        
        self._frozen_time_ms = self.now_ms()
        self._mode = ClockMode.FROZEN
        
        logger.info(f"Clock frozen at {self._frozen_time_ms}")
    
    def unfreeze(self) -> None:
        """
        解冻时间（恢复到之前的模式）
        """
        if self._mode != ClockMode.FROZEN:
            return  # 未冻结
        
        self._frozen_time_ms = None
        self._mode = ClockMode.LIVE  # 默认恢复到 LIVE 模式
        
        logger.info("Clock unfrozen")
    
    def switch_to_replay_mode(self, start_time_ms: int) -> None:
        """
        切换到 REPLAY 模式
        
        Args:
            start_time_ms: 回放起始时间
        """
        self._mode = ClockMode.REPLAY
        self._replay_time_ms = start_time_ms
        self._last_time_ms = start_time_ms
        
        logger.info(f"Clock switched to REPLAY mode, start time: {start_time_ms}")
    
    def switch_to_live_mode(self) -> None:
        """
        切换到 LIVE 模式
        """
        self._mode = ClockMode.LIVE
        self._replay_time_ms = None
        
        logger.info("Clock switched to LIVE mode")
    
    def __repr__(self) -> str:
        return f"ClockAuthority(mode={self._mode}, time={self.now_ms() if self._last_time_ms else 'uninitialized'})"
