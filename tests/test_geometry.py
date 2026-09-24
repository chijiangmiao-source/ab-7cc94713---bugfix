"""几何引擎测试：固定验收用例 + 随机用例对照单位网格暴力预言机。

注意：被验收的实现不铺开单位网格；网格法只作为测试里的小规模对照预言机。
"""

import random
import unittest

from app.geometry import Rect, audit_rectangles


def brute_force(rects):
    """单位网格并集 + 逐格外露边计数（仅用于小坐标测试对照）。"""
    cells = set()
    for r in rects:
        for x in range(r.x1, r.x2):
            for y in range(r.y1, r.y2):
                cells.add((x, y))
    area = len(cells)
    perimeter = 0
    for x, y in cells:
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if (nx, ny) not in cells:
                perimeter += 1
    return area, perimeter


class FixedCasesTest(unittest.TestCase):
    def test_overlapping_area10_perimeter14(self):
        # 验收构型：重叠面积 2。
        rects = [Rect("a", 0, 0, 3, 2), Rect("b", 1, 1, 4, 3)]
        self.assertEqual(audit_rectangles(rects), (10, 14))

    def test_adjacent_boxes_exclude_shared_edge(self):
        # 两个 2x3 方框并排：面积 12，周长 14（公共边 3 不计，两框各 10）。
        rects = [Rect("a", 0, 0, 2, 3), Rect("b", 2, 0, 4, 3)]
        self.assertEqual(audit_rectangles(rects), (12, 14))

    def test_adjacent_vertical_stack(self):
        rects = [Rect("a", 0, 0, 3, 2), Rect("b", 0, 2, 3, 4)]
        self.assertEqual(audit_rectangles(rects), (12, 14))

    def test_geometric_duplicate_no_increment(self):
        single = audit_rectangles([Rect("a", 0, 0, 2, 3)])
        dup = audit_rectangles([Rect("a", 0, 0, 2, 3), Rect("b", 0, 0, 2, 3)])
        self.assertEqual(single, (6, 10))
        self.assertEqual(dup, (6, 10))

    def test_triple_overlap_common_edge(self):
        rects = [
            Rect("a", 0, 0, 2, 2),
            Rect("b", 2, 0, 4, 2),
            Rect("c", 4, 0, 6, 2),
        ]
        self.assertEqual(audit_rectangles(rects), (12, 16))

    def test_nested_box_adds_nothing(self):
        rects = [Rect("o", 0, 0, 10, 10), Rect("i", 2, 2, 4, 4)]
        self.assertEqual(audit_rectangles(rects), (100, 40))

    def test_corner_touch_keeps_both_perimeters(self):
        # 仅角点接触：既不重面积，也不共边，周长 = 两框周长之和。
        self.assertEqual(
            audit_rectangles([Rect("a", 0, 0, 2, 2), Rect("b", 2, 2, 4, 4)]),
            (8, 16),
        )
        self.assertEqual(
            audit_rectangles([Rect("a", 2, 0, 4, 2), Rect("b", 0, 2, 2, 4)]),
            (8, 16),
        )

    def test_cross_shape(self):
        rects = [Rect("v", 1, 0, 3, 4), Rect("h", 0, 1, 4, 3)]
        self.assertEqual(audit_rectangles(rects), (12, 16))

    def test_negative_coordinates(self):
        rects = [Rect("s", -5, -5, 5, 5)]
        self.assertEqual(audit_rectangles(rects), (100, 40))

    def test_large_coordinates_exact_decimal(self):
        rects = [
            Rect("a", 0, 0, 10**9, 10**9),
            Rect("b", 10**9 - 1, 10**9 - 1, 10**9, 10**9),
        ]
        self.assertEqual(audit_rectangles(rects), (10**18, 4 * 10**9))

    def test_empty(self):
        self.assertEqual(audit_rectangles([]), (0, 0))

    def test_single_unit_rect(self):
        self.assertEqual(audit_rectangles([Rect("q", 0, 0, 1, 1)]), (1, 4))


class HighDensityJunctionTest(unittest.TestCase):
    """两簇高密度几何重复框在同一竖线上的混合交接（回归用例）。"""

    def _cluster(self, prefix, x1, y1, x2, y2, count=8):
        return [Rect(f"{prefix}{k}", x1, y1, x2, y2) for k in range(count)]

    def test_two_dense_clusters_partial_junction(self):
        # 8 个重复框覆盖 [0,10]x[0,10]，另 8 个覆盖 [10,20]x[5,15]。
        # 交接竖线 x=10 上仅 [5,10] 一段共边（内部，不计）；
        # 上下仍各有长度 5 的外露竖边，不能被"净长度没变"吞掉。
        rects = self._cluster("a", 0, 0, 10, 10)
        rects += self._cluster("b", 10, 5, 20, 15)
        self.assertEqual(audit_rectangles(rects), (200, 70))
        # 与无重复的同构两框（真实并集）完全一致。
        plain = [Rect("L", 0, 0, 10, 10), Rect("R", 10, 5, 20, 15)]
        self.assertEqual(audit_rectangles(plain), (200, 70))

    def test_dense_clusters_full_adjacency(self):
        # 两簇完全相接：整条公共边内部化，周长 60。
        rects = self._cluster("a", 0, 0, 10, 10)
        rects += self._cluster("b", 10, 0, 20, 10)
        self.assertEqual(audit_rectangles(rects), (200, 60))

    def test_dense_clusters_corner_touch(self):
        # 两簇仅角点相接：无共边，周长为两框周长之和 80。
        rects = self._cluster("a", 0, 0, 10, 10)
        rects += self._cluster("b", 10, 10, 20, 20)
        self.assertEqual(audit_rectangles(rects), (200, 80))


class SameXMixedJunctionTest(unittest.TestCase):
    """同一横坐标上离开边与进入边混合：部分重叠 / 完全相接 / 不相交。"""

    def test_partial_overlap_junction(self):
        # 共边仅 [5,10] 长 5；左框上段 5、右框下段 5 仍外露。
        rects = [Rect("L", 0, 0, 10, 10), Rect("R", 10, 5, 20, 15)]
        self.assertEqual(audit_rectangles(rects), (200, 70))

    def test_partial_overlap_reversed_band(self):
        # 反向错位（左框偏高、右框偏低），同样只剩交错的两段外露竖边。
        rects = [Rect("L", 0, 5, 10, 15), Rect("R", 10, 0, 20, 10)]
        self.assertEqual(audit_rectangles(rects), (200, 70))

    def test_full_adjacency_junction(self):
        rects = [Rect("L", 0, 0, 10, 10), Rect("R", 10, 0, 20, 10)]
        self.assertEqual(audit_rectangles(rects), (200, 60))

    def test_corner_touch_junction(self):
        # 仅在角点 (10,10) 相接，竖边一条都不内化。
        rects = [Rect("L", 0, 0, 10, 10), Rect("R", 10, 10, 20, 20)]
        self.assertEqual(audit_rectangles(rects), (200, 80))

    def test_gapped_junction(self):
        # 同一横坐标但 y 区间留间隙：两块完全独立。
        rects = [Rect("L", 0, 0, 10, 5), Rect("R", 10, 10, 20, 15)]
        self.assertEqual(audit_rectangles(rects), (100, 60))

    def test_nested_same_x_edges(self):
        # 大框横跨 x=10；同 x 上一个内嵌框离开、另一个内嵌框进入，
        # 它们的竖边外侧始终被大框覆盖，不产生外露周长。
        rects = [
            Rect("big", 0, 0, 20, 20),
            Rect("in-l", 5, 5, 10, 15),
            Rect("in-r", 10, 5, 15, 15),
        ]
        self.assertEqual(audit_rectangles(rects), (400, 80))


class BruteForceFuzzTest(unittest.TestCase):
    def test_random_sets_match_grid_oracle(self):
        rng = random.Random(20260924)
        for trial in range(300):
            n = rng.randint(1, 10)
            rects = []
            for k in range(n):
                x1 = rng.randint(-4, 3)
                x2 = rng.randint(x1 + 1, x1 + 4)
                y1 = rng.randint(-4, 3)
                y2 = rng.randint(y1 + 1, y1 + 4)
                rects.append(Rect(f"r{k}", x1, y1, x2, y2))
            with self.subTest(trial=trial, rects=rects):
                self.assertEqual(
                    audit_rectangles(rects),
                    brute_force(rects),
                )

    def test_forced_shared_abscissa_junctions_match_oracle(self):
        # 强制所有竖边落在 {0,5,10,15}：x=5/10 上必然高密度混合
        # 进入/离开事件，专测同横坐标交接，结果仍须等于网格预言机。
        rng = random.Random(99)
        for trial in range(300):
            n = rng.randint(2, 12)
            rects = []
            for k in range(n):
                x1, x2 = 5, 5
                while x1 >= x2:
                    x1 = rng.choice((0, 5, 10))
                    x2 = rng.choice((5, 10, 15))
                y1 = rng.randint(-3, 6)
                y2 = rng.randint(y1 + 1, y1 + 5)
                rects.append(Rect(f"r{k}", x1, y1, x2, y2))
            with self.subTest(trial=trial, rects=rects):
                self.assertEqual(
                    audit_rectangles(rects),
                    brute_force(rects),
                )


class PerformanceTest(unittest.TestCase):
    def test_fifty_thousand_rects(self):
        import time

        rng = random.Random(7)
        rects = []
        for k in range(50000):
            x1 = rng.randint(-10**9, 10**9 - 2)
            x2 = x1 + rng.randint(1, 10**6)
            y1 = rng.randint(-10**9, 10**9 - 2)
            y2 = y1 + rng.randint(1, 10**6)
            rects.append(Rect(f"id-{k}", x1, y1, x2, y2))
        start = time.perf_counter()
        area, perimeter = audit_rectangles(rects)
        elapsed = time.perf_counter() - start
        self.assertGreater(area, 0)
        self.assertGreater(perimeter, 0)
        self.assertLess(elapsed, 15.0, f"sweep too slow: {elapsed:.2f}s")


if __name__ == "__main__":
    unittest.main()
