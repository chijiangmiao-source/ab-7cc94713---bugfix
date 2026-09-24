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


class SameXJunctionTest(unittest.TestCase):
    """两簇框在同一条竖线上交接：内部公共边不计，未覆盖段不丢失。"""

    def test_high_density_duplicate_clusters_area200_perimeter70(self):
        # 验收缺陷构型：两簇各 8 个标识不同、几何重复的框在 x=10 交接，
        # 只共 y∈[5,10] 一段边；上下各有一段外露竖边（各 5）。
        rects = [Rect(f"L{i}", 0, 0, 10, 10) for i in range(8)]
        rects += [Rect(f"R{i}", 10, 5, 20, 15) for i in range(8)]
        self.assertEqual(audit_rectangles(rects), (200, 70))

    def test_same_x_partial_overlap_keeps_two_exposed_vertical_segments(self):
        # 单框版：部分重叠的竖边重合 5，上、下外露竖边各 5。
        rects = [Rect("a", 0, 0, 10, 10), Rect("b", 10, 5, 20, 15)]
        self.assertEqual(audit_rectangles(rects), (200, 70))

    def test_same_x_full_edge_contact_is_internal(self):
        # 完全相接：整条竖边都是内部公共边，并集为 10x20 矩形。
        rects = [Rect("a", 0, 0, 10, 10), Rect("b", 10, 0, 20, 10)]
        self.assertEqual(audit_rectangles(rects), (200, 60))

    def test_same_x_disjoint_corner_junction_keeps_both_edges(self):
        # 不相交交接（仅角点相碰）：两条竖边全部外露，周长为两框之和。
        rects = [Rect("a", 0, 0, 10, 10), Rect("b", 10, 10, 20, 20)]
        self.assertEqual(audit_rectangles(rects), (200, 80))

    def test_same_x_mixed_enter_leave_with_multiplicity(self):
        # 同 x 上离开簇与进入簇的净增减抵消，也不能把外露段吞掉：
        # 重复倍数不同（8 vs 3）时结果仍只取决于几何并集。
        rects = [Rect(f"L{i}", 0, 0, 10, 10) for i in range(8)]
        rects += [Rect(f"R{i}", 10, 5, 20, 15) for i in range(3)]
        self.assertEqual(audit_rectangles(rects), (200, 70))

    def test_three_clusters_two_junctions_on_same_x(self):
        # x=10 上同时有进入与离开、且覆盖多段 y 区间的复合交接。
        rects = [
            Rect("a", 0, 0, 10, 4),
            Rect("b", 0, 6, 10, 10),
            Rect("c", 10, 2, 20, 8),
        ]
        # 面积 40+40+60=140；与网格预言机对照。
        self.assertEqual(audit_rectangles(rects), brute_force(rects))


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

    def test_random_sets_with_geometric_duplicates(self):
        # 每个随机底框复制 1~8 份（标识各不相同）：高密度重复不得改变
        # 并集结果；同时强制制造同 x 的进入/离开混合交接。
        rng = random.Random(424242)
        uid = 0
        for trial in range(150):
            bases = []
            for _ in range(rng.randint(1, 5)):
                x1 = rng.randint(-3, 3)
                x2 = x1 + rng.randint(1, 4)
                y1 = rng.randint(-3, 3)
                y2 = y1 + rng.randint(1, 4)
                bases.append((x1, y1, x2, y2))
            rects = []
            for x1, y1, x2, y2 in bases:
                for _ in range(rng.randint(1, 8)):
                    rects.append(Rect(f"d{uid}", x1, y1, x2, y2))
                    uid += 1
            unique = [Rect(f"u{k}", *b) for k, b in enumerate(bases)]
            with self.subTest(trial=trial, bases=bases):
                self.assertEqual(
                    audit_rectangles(rects),
                    brute_force(unique),
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
