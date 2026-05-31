from pathlib import Path

from safeagent.local_worker.policy import PolicyEngine
from safeagent.shared.enums import NetworkMode, RiskLevel


def test_low_risk_task_allowed():
    decision = PolicyEngine(Path("E:/agents")).evaluate_task("查看 E:\\agents 当前目录")
    assert decision.allowed is True
    assert decision.risk_level == RiskLevel.LOW


def test_delete_task_blocked_as_high_risk():
    decision = PolicyEngine(Path("E:/agents")).evaluate_task("删除下载目录里的所有文件")
    assert decision.allowed is False
    assert decision.risk_level == RiskLevel.HIGH
    assert decision.requires_local_confirmation is True


def test_system_path_blocked():
    decision = PolicyEngine(Path("E:/agents")).evaluate_task("修改 C:\\Windows\\System32 里面的配置")
    assert decision.allowed is False
    assert decision.risk_level == RiskLevel.HIGH


def test_lockdown_blocks_all():
    decision = PolicyEngine(Path("E:/agents")).evaluate_task("查看文件", NetworkMode.LOCKDOWN)
    assert decision.allowed is False
    assert decision.risk_level == RiskLevel.EXTREME


def test_download_target_must_be_guarded():
    engine = PolicyEngine(Path("E:/agents"))
    assert engine.assert_download_target(Path("E:/agents/downloads/a.zip")).allowed is True
    assert engine.assert_download_target(Path("E:/outside/a.zip")).allowed is False

