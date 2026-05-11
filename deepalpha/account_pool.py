# -*- coding: utf-8 -*-
"""
X 实时情报系统 - 账号池管理与健康度监控
================================================
真正的"账号 + 住宅IP + 浏览器指纹"三元组隔离

核心功能：
  - 账号健康度实时监控
  - 自动降级和失效剔除
  - S级账号专属身份池
  - 频率安全上限强制控制
  - 账号状态自动切换
"""

import os
import json
import time
import threading
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

import hashlib


# ============================================================
# 1. 账号状态枚举
# ============================================================

class AccountStatus(Enum):
    """账号状态"""
    ACTIVE = "active"           # 正常可用
    COOLDOWN = "cooldown"       # 冷却中（被限流）
    SUSPECTED = "suspected"     # 疑似被限制
    BANNED = "banned"          # 被封禁
    EXPIRED = "expired"        # Cookie过期
    MAINTENANCE = "maintenance" # 维护中


# ============================================================
# 2. 账号健康度模型
# ============================================================

@dataclass
class AccountHealth:
    """账号健康度"""
    success_count: int = 0
    fail_count: int = 0
    rate_limit_count: int = 0
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    last_rate_limit: Optional[datetime] = None

    consecutive_successes: int = 0
    consecutive_failures: int = 0

    avg_response_time: float = 0.0
    response_times: List[float] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        """成功率"""
        total = self.success_count + self.fail_count
        if total == 0:
            return 1.0
        return self.success_count / total

    @property
    def health_score(self) -> float:
        """
        综合健康度评分 (0-100)

        计算方式：
          - 成功率权重 50%
          - 最近活跃度权重 20%
          - 响应时间权重 15%
          - 限流次数权重 15%
        """
        success_score = self.success_rate * 50

        recency_score = 20
        if self.last_success:
            hours_since = (datetime.now() - self.last_success).total_seconds() / 3600
            recency_score = max(0, 20 - hours_since * 2)

        response_score = 15
        if self.response_times:
            avg = sum(self.response_times) / len(self.response_times)
            if avg < 1.0:
                response_score = 15
            elif avg < 3.0:
                response_score = 12
            elif avg < 5.0:
                response_score = 8
            else:
                response_score = 4

        limit_score = 15 - min(self.rate_limit_count * 3, 15)

        return success_score + recency_score + response_score + limit_score

    def record_success(self, response_time: float = 0.0):
        """记录成功"""
        self.success_count += 1
        self.last_success = datetime.now()
        self.consecutive_successes += 1
        self.consecutive_failures = 0

        if response_time > 0:
            self.response_times.append(response_time)
            if len(self.response_times) > 10:
                self.response_times.pop(0)
            self.avg_response_time = sum(self.response_times) / len(self.response_times)

    def record_failure(self, is_rate_limit: bool = False):
        """记录失败"""
        self.fail_count += 1
        self.last_failure = datetime.now()
        self.consecutive_failures += 1
        self.consecutive_successes = 0

        if is_rate_limit:
            self.rate_limit_count += 1
            self.last_rate_limit = datetime.now()


# ============================================================
# 3. 账号单元
# ============================================================

@dataclass
class AccountUnit:
    """
    账号单元

    包含账号的所有信息和状态
    """
    account_id: str
    username: str
    account_level: str  # S, A, B, C

    # Cookie 信息
    cookie_file: str
    cookie_data: dict = field(default_factory=dict)
    cookie_expires: Optional[datetime] = None

    # 代理信息
    proxy: Optional[str] = None
    proxy_type: str = "residential"  # residential, datacenter, mobile

    # 浏览器指纹
    fingerprint: dict = field(default_factory=dict)

    # 健康度
    health: AccountHealth = field(default_factory=AccountHealth)

    # 状态
    status: AccountStatus = AccountStatus.ACTIVE

    # 元数据
    created_at: datetime = field(default_factory=datetime.now)
    last_used: datetime = field(default_factory=datetime.now)
    use_count: int = 0

    # 配置
    min_interval: int = 300  # 最小使用间隔（秒）
    max_requests_per_hour: int = 60

    def __post_init__(self):
        if not self.account_id:
            self.account_id = hashlib.md5(
                f"{self.username}:{self.proxy or 'no_proxy'}".encode()
            ).hexdigest()[:12]

    @property
    def is_available(self) -> bool:
        """是否可用"""
        if self.status in [AccountStatus.BANNED, AccountStatus.MAINTENANCE]:
            return False

        if self.status == AccountStatus.COOLDOWN:
            return False

        if self.status == AccountStatus.EXPIRED:
            return False

        time_since_last_use = (datetime.now() - self.last_used).total_seconds()
        if time_since_last_use < self.min_interval:
            return False

        return True

    @property
    def is_cookie_valid(self) -> bool:
        """Cookie 是否有效"""
        if not self.cookie_data:
            return False

        if self.cookie_expires and datetime.now() >= self.cookie_expires:
            self.status = AccountStatus.EXPIRED
            return False

        for cookie in self.cookie_data:
            if cookie.get('name') == 'auth_token' and cookie.get('value'):
                return True

        return False

    def use(self) -> bool:
        """使用账号（检查是否可用）"""
        if not self.is_available:
            return False

        self.last_used = datetime.now()
        self.use_count += 1
        return True

    def report_success(self, response_time: float = 0.0):
        """报告成功"""
        self.health.record_success(response_time)
        self.status = AccountStatus.ACTIVE

    def report_failure(self, is_rate_limit: bool = False):
        """报告失败"""
        self.health.record_failure(is_rate_limit)

        if is_rate_limit:
            self.status = AccountStatus.COOLDOWN
        elif self.health.consecutive_failures >= 5:
            self.status = AccountStatus.SUSPECTED
        elif self.health.consecutive_failures >= 10:
            self.status = AccountStatus.BANNED

    def to_dict(self) -> dict:
        """转字典"""
        return {
            "account_id": self.account_id,
            "username": self.username,
            "account_level": self.account_level,
            "cookie_file": self.cookie_file,
            "proxy": self.proxy,
            "proxy_type": self.proxy_type,
            "status": self.status.value,
            "health_score": self.health.health_score,
            "success_rate": self.health.success_rate,
            "last_used": self.last_used.isoformat() if self.last_used else None,
            "use_count": self.use_count,
        }


# ============================================================
# 4. 账号池管理器
# ============================================================

class AccountPoolManager:
    """
    账号池管理器

    功能：
      - 账号注册和管理
      - 健康度监控
      - 自动降级和恢复
      - 频率控制
      - S级账号专属池
    """

    def __init__(self, cookie_dir: str = "./cookies/"):
        self.cookie_dir = cookie_dir
        self.accounts: Dict[str, AccountUnit] = {}
        self._lock = threading.RLock()

        self._level_pools: Dict[str, List[str]] = defaultdict(list)

        self._frequency_limits: Dict[str, int] = {
            "S": 4,   # S级：每小时最多4次（10-15分钟间隔）
            "A": 2,   # A级：每小时最多2次
            "B": 1,   # B级：每小时最多1次
            "C": 1,   # C级：每小时最多1次
        }

        self._global_request_count: Dict[str, int] = defaultdict(int)
        self._global_request_times: Dict[str, datetime] = {}

        os.makedirs(cookie_dir, exist_ok=True)
        self._load_accounts()

    def _load_accounts(self):
        """加载所有账号"""
        if not os.path.exists(self.cookie_dir):
            return

        for filename in os.listdir(self.cookie_dir):
            if not filename.endswith('.json'):
                continue

            filepath = os.path.join(self.cookie_dir, filename)
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)

                account = AccountUnit(
                    account_id=data.get('account_id', filename.replace('.json', '')),
                    username=data.get('username', ''),
                    account_level=data.get('level', 'C'),
                    cookie_file=filepath,
                    cookie_data=data.get('cookies', []),
                    proxy=data.get('proxy'),
                    proxy_type=data.get('proxy_type', 'residential'),
                    fingerprint=data.get('fingerprint', {}),
                    min_interval=self._get_min_interval(data.get('level', 'C')),
                    max_requests_per_hour=self._frequency_limits.get(
                        data.get('level', 'C'), 1
                    ),
                )

                if data.get('cookie_expires'):
                    account.cookie_expires = datetime.fromisoformat(
                        data['cookie_expires']
                    )

                self._register_account(account)

            except Exception as e:
                print(f"  ⚠️ 加载账号失败 {filename}: {e}")

    def _get_min_interval(self, level: str) -> int:
        """获取最小使用间隔"""
        intervals = {"S": 900, "A": 1800, "B": 3600, "C": 7200}
        return intervals.get(level, 3600)

    def _register_account(self, account: AccountUnit):
        """注册账号"""
        with self._lock:
            self.accounts[account.account_id] = account
            self._level_pools[account.account_level].append(account.account_id)

    def register_account(
        self,
        username: str,
        cookie_file: str,
        account_level: str = "C",
        proxy: str = None,
        fingerprint: dict = None
    ) -> AccountUnit:
        """注册新账号"""
        with open(cookie_file, 'r') as f:
            cookie_data = json.load(f)

        account = AccountUnit(
            account_id=hashlib.md5(username.encode()).hexdigest()[:12],
            username=username,
            account_level=account_level,
            cookie_file=cookie_file,
            cookie_data=cookie_data.get('cookies', cookie_data),
            proxy=proxy,
            fingerprint=fingerprint or {},
            min_interval=self._get_min_interval(account_level),
            max_requests_per_hour=self._frequency_limits.get(account_level, 1),
        )

        self._register_account(account)

        self._save_account_config(account)

        return account

    def _save_account_config(self, account: AccountUnit):
        """保存账号配置"""
        config_file = account.cookie_file
        data = {
            "account_id": account.account_id,
            "username": account.username,
            "level": account.account_level,
            "proxy": account.proxy,
            "proxy_type": account.proxy_type,
            "fingerprint": account.fingerprint,
            "cookie_expires": account.cookie_expires.isoformat() if account.cookie_expires else None,
        }

        try:
            existing = {}
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    existing = json.load(f)

            existing.update(data)

            with open(config_file, 'w') as f:
                json.dump(existing, f, indent=2)
        except:
            pass

    def get_account(self, level: str = None, force: bool = False) -> Optional[AccountUnit]:
        """
        获取可用账号

        Args:
            level: 账号级别（S/A/B/C）
            force: 是否强制获取（忽略频率限制）
        """
        with self._lock:
            candidates = []

            levels = [level] if level else ["S", "A", "B", "C"]

            for lvl in levels:
                for account_id in self._level_pools.get(lvl, []):
                    account = self.accounts.get(account_id)
                    if not account:
                        continue

                    if not account.is_available and not force:
                        continue

                    if not force:
                        if not self._check_frequency_limit(account):
                            continue

                    candidates.append((account.health.health_score, account))

            if candidates:
                candidates.sort(key=lambda x: x[0], reverse=True)
                selected = candidates[0][1]

                if selected.use():
                    return selected

        return None

    def _check_frequency_limit(self, account: AccountUnit) -> bool:
        """检查频率限制"""
        current_hour = datetime.now().strftime("%Y%m%d%H")
        key = f"{account.account_id}:{current_hour}"

        count = self._global_request_count[key]
        limit = account.max_requests_per_hour

        if count >= limit:
            return False

        return True

    def release_account(self, account_id: str, success: bool, response_time: float = 0.0):
        """释放账号并记录结果"""
        with self._lock:
            account = self.accounts.get(account_id)
            if not account:
                return

            current_hour = datetime.now().strftime("%Y%m%d%H")
            key = f"{account_id}:{current_hour}"
            self._global_request_count[key] += 1

            if success:
                account.report_success(response_time)
            else:
                account.report_failure(is_rate_limit=False)

    def mark_rate_limit(self, account_id: str):
        """标记账号被限流"""
        with self._lock:
            account = self.accounts.get(account_id)
            if account:
                account.report_failure(is_rate_limit=True)

                cooldown_seconds = 900 if account.account_level == "S" else 3600
                print(f"  ⚠️ 账号 @{account.username} 被限流，进入 {cooldown_seconds}秒 冷却")

    def get_pool_stats(self) -> dict:
        """获取账号池统计"""
        with self._lock:
            stats = {
                "total": len(self.accounts),
                "by_level": {},
                "by_status": {},
                "avg_health": 0,
            }

            level_counts = defaultdict(int)
            status_counts = defaultdict(int)
            total_health = 0

            for account in self.accounts.values():
                level_counts[account.account_level] += 1
                status_counts[account.status.value] += 1
                total_health += account.health.health_score

            stats["by_level"] = dict(level_counts)
            stats["by_status"] = dict(status_counts)
            stats["avg_health"] = total_health / max(len(self.accounts), 1)

            return stats

    def get_all_accounts(self) -> List[AccountUnit]:
        """获取所有账号"""
        with self._lock:
            return list(self.accounts.values())

    def remove_account(self, account_id: str):
        """移除账号"""
        with self._lock:
            account = self.accounts.pop(account_id, None)
            if account:
                self._level_pools[account.account_level].remove(account_id)

    def auto_recover(self):
        """
        自动恢复检测

        检查冷却中的账号，尝试恢复使用
        """
        with self._lock:
            for account in self.accounts.values():
                if account.status == AccountStatus.SUSPECTED:
                    if account.health.consecutive_failures == 0:
                        account.status = AccountStatus.ACTIVE
                        print(f"  ✓ 账号 @{account.username} 自动恢复")

                elif account.status == AccountStatus.COOLDOWN:
                    if account.last_used and (
                        datetime.now() - account.last_used
                    ).total_seconds() > 900:
                        account.status = AccountStatus.ACTIVE
                        print(f"  ✓ 账号 @{account.username} 冷却结束")

    def export_pool_config(self, output_file: str):
        """导出账号池配置"""
        with self._lock:
            data = {
                "export_time": datetime.now().isoformat(),
                "accounts": [a.to_dict() for a in self.accounts.values()],
                "stats": self.get_pool_stats(),
            }

        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2, default=str)

        print(f"  ✓ 账号池配置已导出: {output_file}")


# ============================================================
# 5. 频率控制器
# ============================================================

class FrequencyController:
    """
    频率控制器

    功能：
      - 强制频率上限
      - S级账号降频保护
      - 动态调整
    """

    def __init__(self):
        self._request_log: Dict[str, List[datetime]] = defaultdict(list)

        self._max_requests = {
            "S": 4,    # 每小时最多4次（15分钟/次）
            "A": 4,    # 每小时最多4次
            "B": 2,    # 每小时最多2次
            "C": 1,    # 每小时最多1次
        }

        self._user_overrides: Dict[str, int] = {}

        self._lock = threading.Lock()

    def can_request(self, account_id: str, level: str) -> tuple:
        """
        检查是否可以请求

        Returns:
            (can_request: bool, wait_seconds: int, reason: str)
        """
        with self._lock:
            current_time = datetime.now()
            hour_ago = current_time - timedelta(hours=1)

            log = self._request_log[account_id]
            recent_requests = [t for t in log if t > hour_ago]

            max_allowed = self._user_overrides.get(
                account_id,
                self._max_requests.get(level, 1)
            )

            if len(recent_requests) >= max_allowed:
                oldest = min(recent_requests)
                wait_seconds = int((oldest + timedelta(hours=1) - current_time).total_seconds())
                return False, max(0, wait_seconds), f"频率超限（{max_allowed}/小时）"

            return True, 0, ""

    def record_request(self, account_id: str):
        """记录请求"""
        with self._lock:
            self._request_log[account_id].append(datetime.now())

            for account_id in list(self._request_log.keys()):
                hour_ago = datetime.now() - timedelta(hours=1)
                self._request_log[account_id] = [
                    t for t in self._request_log[account_id] if t > hour_ago
                ]

    def set_limit(self, level: str, max_per_hour: int):
        """设置频率上限"""
        self._max_requests[level] = max_per_hour

    def set_user_override(self, account_id: str, max_per_hour: int):
        """设置用户自定义上限"""
        self._user_overrides[account_id] = max_per_hour

    def get_remaining(self, account_id: str, level: str) -> int:
        """获取剩余请求次数"""
        with self._lock:
            current_time = datetime.now()
            hour_ago = current_time - timedelta(hours=1)

            log = self._request_log[account_id]
            recent_requests = [t for t in log if t > hour_ago]

            max_allowed = self._user_overrides.get(
                account_id,
                self._max_requests.get(level, 1)
            )

            return max(0, max_allowed - len(recent_requests))


# ============================================================
# 6. 全局实例
# ============================================================

_pool_manager: Optional[AccountPoolManager] = None
_freq_controller: Optional[FrequencyController] = None


def get_pool_manager() -> AccountPoolManager:
    """获取全局账号池管理器"""
    global _pool_manager
    if _pool_manager is None:
        _pool_manager = AccountPoolManager()
    return _pool_manager


def get_frequency_controller() -> FrequencyController:
    """获取全局频率控制器"""
    global _freq_controller
    if _freq_controller is None:
        _freq_controller = FrequencyController()
    return _freq_controller


# ============================================================
# 7. 测试
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  账号池管理与健康度监控 - 测试")
    print("=" * 60)

    manager = get_pool_manager()

    print("\n  1. 账号池统计:")
    stats = manager.get_pool_stats()
    print(f"     总账号数: {stats['total']}")
    print(f"     按级别: {stats['by_level']}")
    print(f"     按状态: {stats['by_status']}")
    print(f"     平均健康度: {stats['avg_health']:.1f}")

    print("\n  2. 测试获取账号:")
    account = manager.get_account(level="S")
    if account:
        print(f"     获取到账号: @{account.username} (健康度: {account.health.health_score:.1f})")
        manager.release_account(account.account_id, success=True, response_time=0.5)
    else:
        print("     未获取到可用账号")

    print("\n  3. 频率控制测试:")
    controller = get_frequency_controller()
    can_req, wait, reason = controller.can_request("test_account", "S")
    print(f"     可请求: {can_req}, 等待: {wait}秒, 原因: {reason}")
