# 技能：gstack-openclaw-investigate

> OpenClaw 技能  ·  系统性调试 + 根因调查  ·  安装：`clawhub install gstack-openclaw-investigate`

---

## Iron Law

> **NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST.**

Fixing symptoms creates whack-a-mole debugging. Every fix that doesn't address root cause makes the next bug harder to find.

**不查根因不修代码。**

## 4 阶段流程

### Phase 1: Root Cause Investigation

收集上下文，不形成假设。

1. **收集症状**：读错误信息、堆栈跟踪、复现步骤
   - 如果用户没提供足够上下文，**一次只问一个问题**
   - **不要一次问五个问题**

2. **读代码**：从症状回溯到可能原因
   - 搜索所有引用
   - 读失败点附近的逻辑

3. **检查最近变更**：
   ```bash
   git log --oneline -20 -- <affected-files>
   ```
   - 之前能工作吗？什么变了？
   - 回归 = 根因在 diff 里

### Phase 2: Analyze

**Hypothesize based on actual evidence, not guesses.**

- 列出 3-5 个可能根因
- 每个根因列证据 + 验证方法
- 排除无证据的猜测

### Phase 3: Hypothesize

- 优先级排序
- 选**最可能**的根因
- 给出可执行验证步骤

### Phase 4: Implement

- 修复后跑测试
- **复现原症状确认修复**
- 写新测试覆盖回归

## 5 步调查协议（V4.6.9 实战）

适用场景：用户报告"现象 X"但未给出根因时。

### Step 1：打印最终产物

```python
print(f"{'path':<30} {'sort_key':<10} {'width':<7} {'height':<7} {'href'}")
for path, k in slices:
    name = os.path.basename(path)
    w, h = Image.open(path).size
    print(f'{name:<30} {k:<10} {w:<7} {h:<7} {href}')
```

### Step 2：生成示意图 + 拼接顺序

```python
# 画 ASCII 示意图
print('  ┌────┬────┬───────┬─────┬─────┐')
print('  │s001│s002│ s003  │s004 │s005 │')
print('  │200 │100 │ 400   │100  │200  │')
print('  │    │A   │普通   │B    │     │')
print('  └────┴────┴───────┴─────┴─────┘')
```

### Step 3：验证总和 = 原图

```python
total_w = sum(Image.open(path).size[0] for path, _ in slices)
heights = [Image.open(path).size[1] for path, _ in slices]
assert total_w == ORIG_W, f'总宽 {total_w} != {ORIG_W}'
assert max(heights) == min(heights), '高不一致！'
```

### Step 4：验证 HTML 结构

```python
trs = re.findall(r'<tr>.*?</tr>', html, re.S)
print(f'<tr> 数量 = {len(trs)}')
print(f'每 <tr> 内 <td> 数量 = {[len(re.findall(r"<td[^>]*>", tr)) for tr in trs]}')
```

**对比预期**：
- 横向拼接：1 个 `<tr>` 多 `<td>`
- 纵向堆叠：多 `<tr>` 单 `<td>`

### Step 5：定位根因 + 报告

- 不修代码
- 输出根因 + 证据 + 修复方案 + 风险评估
- 等用户确认方案再实施

## V4.6.9 Bug 4 实战案例

### 调查流程
1. **Step 1**：打印 hs_001/hs_002/hs_003 → 切割正确
2. **Step 2**：画 ASCII 拼接图 → 视觉预期 = 横向 3 段
3. **Step 3**：总宽 1000 ✓、高一致 500 ✓
4. **Step 4**：`trs` 数量 = 3，`<td>` 数量 = [1, 1, 1] → **根因命中**
5. **Step 5**：报告"每段独占 `<tr>` 纵向堆叠" + 修复方案 A

### 之前 V4.6.9 a351cd7 的失败
- 修 Bug 3（多段宽度按比例）就认为 OK
- 没主动调查"碎片化"
- 直接改代码
- **违反 Iron Law**

### 这次的修正
- 按 5 步调查协议逐项排除嫌疑
- Step 4 直接打印 `<tr>` 数量才命中根因
- 报告根因给用户，等确认方案 A 才改

## 何时用

| 场景 | 用？ |
|------|------|
| 用户报告 bug 但未给根因 | ✓ |
| 修代码前必须复现 | ✓ |
| 多模块跨 session 调查 | ✓ |
| 重构后排查回归 | ✓ |
| 性能问题 | ✓ |
| 用户只说"功能不对"没具体表现 | ✓（Step 1-5 强制收集证据） |

## 何时不用

- 用户已给出根因 + 修复方案 → 直接修
- 紧急 hotfix → 走"快速缓解 + 后置调查"
- 探索性开发 → 不适用

## 与其他技能的关系

| 技能 | 关系 |
|------|------|
| `bug-fix-protocol` | 4 阶段类似但侧重**测试-修复-测试**闭环；gstack 侧重**调查-根因-修复** |
| `superpowers-systematic-debugging` | 更老的版本，与 gstack 互补 |
| `refactor-safely` | 修完 bug 后用，避免技术债累积 |

## 关联

- [V4.6.9-修复总结.md](./V4.6.9-修复总结.md) — gstack 实战案例
- [bug-4-HTML横向拼接.md](./bug-4-HTML横向拼接.md) — 5 步调查协议实战

---

_最后更新：2026-06-02_
