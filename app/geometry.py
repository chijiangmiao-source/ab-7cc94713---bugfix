"""矩形并集面积与外露周长的扫描线引擎。

只用 Python 标准库；不铺开单位网格、不逐对切割矩形、不调用几何求解库。

算法
----
把所有矩形的左/右边归一为扫描事件，纵坐标压缩后用线段树维护：

* cover  —— 节点对应区间上的覆盖次数（懒标记，作用于整段）；
* length —— 该节点覆盖次数大于 0 的 y 区间总长度；
* pieces —— 覆盖区间内的连续覆盖段数；
* lc/rc  —— 该节点 y 区间左右端点是否被覆盖（用于跨子节点合并段数）。

同一横坐标的进入/离开事件先分别取同向边并集，再在整组应用*前*的
树上裁决进入边、整组应用*后*的树上裁决离开边：两矩形共边（甚至多
重叠压）时各自外侧都有覆盖，计 0；而同竖线只共一段边的"换班"交接，
两端外露竖边分别落在两次查询里，不会被根节点的净变化（恒为 0）吞掉。

面积 = Σ 覆盖总长 × 板宽（宽 = 相邻事件横坐标之差）。

周长在同一次扫描中同步得到：

* 水平边：板 (x_prev, x) 内覆盖集恒定，每个连续段上下各一条外露
  水平边，故累加 ``2 × pieces × 板宽``；
* 竖直边：逐条边判其**外侧紧邻半平面**的覆盖度是否为 0——
  进入边（矩形左边）用该横坐标整组事件应用*之前*的树，
  离开边（矩形右边）用整组应用*之后*的树，查该边 y 区间内
  "覆盖度为 0 的长度"。共边（外侧被邻框覆盖）、覆盖 2→1 的
  内部接缝（外侧仍有框）都计 0；仅角点接触时两侧外侧皆空，
  两条边各自计入，不会被"总长度没变"吞掉。
"""

from __future__ import annotations

from dataclasses import dataclass


class GeometryError(Exception):
    """输入矩形非法时抛出，message 为面向调用方的稳定错误信息。

    ``location`` 为结构化输入位置（如 ``{"index": 3, "id": "r7"}``），
    便于调用方定位；无更细位置时为 ``None``。
    """

    def __init__(self, message: str, location: dict | None = None) -> None:
        super().__init__(message)
        self.location = location


@dataclass(frozen=True)
class Rect:
    id: str
    x1: int
    y1: int
    x2: int
    y2: int


class _Node:
    __slots__ = ("cover", "length", "pieces", "lc", "rc")

    def __init__(self) -> None:
        self.cover = 0
        self.length = 0
        self.pieces = 0
        self.lc = False
        self.rc = False


class CoverageTree:
    """压缩纵坐标上的覆盖计数 / 覆盖总长 / 连续段数线段树。

    叶 [i, i+1) 对应压缩坐标 ``ys[i] .. ys[i+1]``，长度 ys[i+1]-ys[i]。
    """

    __slots__ = ("ys", "span", "nodes")

    def __init__(self, ys: list[int]):
        self.ys = ys
        self.span = len(ys) - 1
        self.nodes = [_Node() for _ in range(4 * max(1, self.span) + 1)]

    # -- 线段树 ----------------------------------------------------------

    def _pull(self, p: int, l: int, r: int) -> None:
        node = self.nodes[p]
        if node.cover > 0:
            node.length = self.ys[r] - self.ys[l]
            node.pieces = 1
            node.lc = node.rc = True
            return
        if r - l == 1:
            node.length = 0
            node.pieces = 0
            node.lc = node.rc = False
            return
        left, right = self.nodes[p << 1], self.nodes[p << 1 | 1]
        node.length = left.length + right.length
        node.pieces = left.pieces + right.pieces - (1 if left.rc and right.lc else 0)
        node.lc = left.lc
        node.rc = right.rc

    def _update(self, p: int, l: int, r: int, ql: int, qr: int, delta: int) -> None:
        if ql <= l and r <= qr:
            node = self.nodes[p]
            node.cover += delta
            self._pull(p, l, r)
            return
        mid = (l + r) >> 1
        if ql < mid:
            self._update(p << 1, l, mid, ql, qr, delta)
        if qr > mid:
            self._update(p << 1 | 1, mid, r, ql, qr, delta)
        self._pull(p, l, r)

    def add(self, lo: int, hi: int, delta: int) -> None:
        """对压缩索引区间 [lo, hi) 加 delta（+1 进入 / -1 离开）。"""
        if lo < hi:
            self._update(1, 0, self.span, lo, hi, delta)

    @property
    def covered_length(self) -> int:
        return self.nodes[1].length

    @property
    def covered_pieces(self) -> int:
        return self.nodes[1].pieces

    def covered_length_in(self, lo: int, hi: int) -> int:
        """压缩索引区间 [lo, hi) 内覆盖次数大于 0 的物理 y 长度。"""
        if lo >= hi:
            return 0
        return self._query(1, 0, self.span, lo, hi)

    def _query(self, p: int, l: int, r: int, ql: int, qr: int) -> int:
        node = self.nodes[p]
        if ql <= l and r <= qr:
            return node.length
        if node.cover > 0:
            # 整段被本层懒标记覆盖：直接返回与查询区间重叠的物理长度。
            lo = max(l, ql)
            hi = min(r, qr)
            return self.ys[hi] - self.ys[lo] if lo < hi else 0
        mid = (l + r) >> 1
        total = 0
        if ql < mid:
            total += self._query(p << 1, l, mid, ql, qr)
        if qr > mid:
            total += self._query(p << 1 | 1, mid, r, ql, qr)
        return total

    def apply_batch(self, changes: tuple[tuple[int, int, int], ...]) -> None:
        """落库同一横坐标的净覆盖变化（进入 +1 / 离开 -1）。"""
        for lo, hi, delta in changes:
            self.add(lo, hi, delta)

    def exposed_length(self, lo: int, hi: int) -> int:
        """边区间 [lo, hi) 上覆盖度为 0 的物理长度——即该侧外露竖边长。"""
        return (self.ys[hi] - self.ys[lo]) - self.covered_length_in(lo, hi)

def _merge_intervals(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """同一竖直线上同向边的并集（几何重复框只形成一条边界）。"""
    if not intervals:
        return []
    intervals.sort()
    merged = [intervals[0]]
    for y1, y2 in intervals[1:]:
        last = merged[-1]
        if y1 <= last[1]:
            if y2 > last[1]:
                merged[-1] = (last[0], y2)
        else:
            merged.append((y1, y2))
    return merged


@dataclass(frozen=True)
class _EventGroup:
    x: int
    changes: tuple[tuple[int, int, int], ...]
    entering: tuple[tuple[int, int], ...]
    leaving: tuple[tuple[int, int], ...]


def _group_events(
    events: list[tuple[int, int, int, int]], index: dict[int, int]
) -> list[_EventGroup]:
    """把同一横坐标的扫描事件聚合为净变化与同向边并集。

    * ``changes``   —— 每个 y 区间上的净覆盖增减（几何重复框的同向
      事件先在此抵消，避免计数虚高）；
    * ``entering``/``leaving`` —— 该横坐标全部矩形左边/右边各自 y 区间
      的并集：几何重复框的重边只并成一条，而"既进又出"的混合交接
      （如部分重叠的两簇框在同一条竖线上换班）两边都保留，分别交给
      组前/组后的树裁决，任何一段外露竖边都不会被净变化吞掉。
    """
    groups: list[_EventGroup] = []
    i = 0
    while i < len(events):
        x = events[i][0]
        net: dict[tuple[int, int], int] = {}
        enter: list[tuple[int, int]] = []
        leave: list[tuple[int, int]] = []
        while i < len(events) and events[i][0] == x:
            _, delta, y1, y2 = events[i]
            key = (index[y1], index[y2])
            net[key] = net.get(key, 0) + delta
            (enter if delta > 0 else leave).append(key)
            i += 1
        changes = tuple(
            (lo, hi, delta)
            for (lo, hi), delta in sorted(net.items())
            if delta
        )
        groups.append(
            _EventGroup(x, changes, tuple(_merge_intervals(enter)),
                        tuple(_merge_intervals(leave)))
        )
    return groups


def _sweep(rects: list[Rect]) -> tuple[int, int]:
    """沿 x 扫描，同步返回 (并集面积, 外露周长)。

    每个事件横坐标上：先在"组前"树上为全部进入边（取并集）计量外侧
    未覆盖长度，整组事件落库后再在"组后"树上为全部离开边（取并集）
    计量；面积与水平边则用相邻事件横坐标之间的板宽计算。
    """
    events: list[tuple[int, int, int, int]] = []
    ys_set: set[int] = set()
    for rect in rects:
        events.append((rect.x1, 1, rect.y1, rect.y2))
        events.append((rect.x2, -1, rect.y1, rect.y2))
        ys_set.add(rect.y1)
        ys_set.add(rect.y2)
    events.sort(key=lambda e: e[0])

    ys = sorted(ys_set)
    index = {y: i for i, y in enumerate(ys)}
    tree = CoverageTree(ys)

    area = 0
    perimeter = 0
    prev_x = events[0][0]
    groups = _group_events(events, index)
    for group in groups:
        x = group.x
        width = x - prev_x
        if width:
            # 板 (prev_x, x) 内覆盖集恒定。
            area += tree.covered_length * width
            perimeter += 2 * tree.covered_pieces * width

        # 竖直边：逐条边判其外侧紧邻半平面的覆盖度。进入边（矩形左边）
        # 的外侧是左侧板，即整组应用*之前*的树；离开边（矩形右边）的
        # 外侧是右侧板，即整组应用*之后*的树。取边 y 区间内外侧覆盖度
        # 为 0 的长度。同竖线"既进又出"的混合交接由此分别裁决：重合段
        # 外侧都有框（计 0），换班两端各自外露的竖边一段都不会丢。
        for lo, hi in group.entering:
            perimeter += tree.exposed_length(lo, hi)

        tree.apply_batch(group.changes)

        for lo, hi in group.leaving:
            perimeter += tree.exposed_length(lo, hi)

        prev_x = x
    return area, perimeter


def audit_rectangles(rects: list[Rect]) -> tuple[int, int]:
    """返回 ``(并集面积, 外露周长)``，均为精确整数。"""
    if not rects:
        return 0, 0
    return _sweep(rects)


def audit_raw(records: list[dict]) -> tuple[str, str]:
    """校验并计算，返回十进制字符串 ``(area, perimeter)``。

    每条记录形如 ``{"id": ..., "x1": ..., "y1": ..., "x2": ..., "y2": ...}``。
    任何一条非法都抛出 ``GeometryError``，错误信息带输入位置（索引/ID），
    不返回任何部分结果。
    """
    if not isinstance(records, list):
        raise GeometryError("request body must be a JSON array of rectangles")
    if not 1 <= len(records) <= 50000:
        raise GeometryError(
            f"rectangle count must be between 1 and 50000, got {len(records)}"
        )

    rects: list[Rect] = []
    seen_ids: set[str] = set()
    required = ("x1", "y1", "x2", "y2")
    coord_bounds = 1_000_000_000

    for pos, rec in enumerate(records):
        loc: dict = {"index": pos}
        where = f"rectangles[{pos}]"
        if not isinstance(rec, dict):
            raise GeometryError(f"{where}: must be an object", loc)
        rid = rec.get("id")
        if not isinstance(rid, str) or not rid:
            raise GeometryError(
                f"{where}: 'id' must be a non-empty string", loc
            )
        loc["id"] = rid
        if rid in seen_ids:
            raise GeometryError(
                f"{where}: duplicate id {rid!r} (id must be unique)", loc
            )
        seen_ids.add(rid)

        coords = {}
        for key in required:
            val = rec.get(key)
            # 拒绝 bool（bool 是 int 子类）、拒绝浮点——坐标必须为整数。
            if isinstance(val, bool) or not isinstance(val, int):
                raise GeometryError(
                    f"{where} (id={rid!r}): '{key}' must be an integer", loc
                )
            if abs(val) > coord_bounds:
                raise GeometryError(
                    f"{where} (id={rid!r}): '{key}'={val} out of range "
                    f"[-1e9, 1e9]",
                    loc,
                )
            coords[key] = val
        if not coords["x1"] < coords["x2"]:
            raise GeometryError(
                f"{where} (id={rid!r}): require x1 < x2, got "
                f"x1={coords['x1']}, x2={coords['x2']}",
                loc,
            )
        if not coords["y1"] < coords["y2"]:
            raise GeometryError(
                f"{where} (id={rid!r}): require y1 < y2, got "
                f"y1={coords['y1']}, y2={coords['y2']}",
                loc,
            )
        rects.append(
            Rect(rid, coords["x1"], coords["y1"], coords["x2"], coords["y2"])
        )

    area, perimeter = audit_rectangles(rects)
    return str(area), str(perimeter)
