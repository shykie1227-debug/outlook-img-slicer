"""
B1 回归测试：_distribute_units 在 remainder<0 且所有 units==1 时不得死循环

根因（html_assembler.py _distribute_units）：remainder<0 时仅 `elif units[target]>1`
分支能减；当所有 units 都 == 1 时两个分支都不执行 → remainder 永不变、idx 自增
→ 无限循环。触发条件：display_w 极小而 cell 极多（如 display_w=10、20 个窄 cell）。

修复：加迭代上限 guard（progress_made / max_iter），并在无法收敛时退化为「尽量均分、
末段吃余数」的确定性结果，保证 sum == total_units、不挂起。
"""
import concurrent.futures

from html_assembler import _distribute_units


def _run_with_watchdog(fn, timeout: float = 5.0):
    """在独立线程执行 fn，超时则判定为死循环（不会卡住整个测试进程）。"""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(fn)
        try:
            return fut.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            raise AssertionError("死循环：_distribute_units 在超时内未返回（B1 未修复）")


def test_distribute_units_terminates_when_all_units_one():
    """display_w=10、20 个窄 cell：旧实现会无限循环；修复后必须终止且 sum 守恒。"""
    raw = [0.5] * 20  # int 后都=0 → max(1,0)=1，total_units=10 → remainder=-10
    total_units = 10

    result = _run_with_watchdog(lambda: _distribute_units(raw, total_units))

    assert len(result) == len(raw)
    assert sum(result) == total_units, "返回值之和必须等于 total_units"
    assert all(r >= 0 for r in result), "退化兜底允许 0，但不应为负"


def test_distribute_units_normal_case_unchanged():
    """正常用例行为不变（保证收敛结果与原实现一致）。"""
    raw = [1.0, 2.0, 3.0]
    result = _distribute_units(raw, 6)
    assert result == [1, 2, 3]
    assert sum(result) == 6


def test_distribute_units_extreme_narrow_cells_does_not_hang():
    """更极端：display_w=8、50 个等宽 cell，仍必须终止且 sum 守恒。"""
    raw = [1.0] * 50
    total_units = 8
    result = _run_with_watchdog(lambda: _distribute_units(raw, total_units))
    assert sum(result) == total_units
    assert len(result) == 50
