import io
import json
import random
import unittest

from ssq_tool import generate_tickets, parse_official_history, read_history


class GenerateTicketsTests(unittest.TestCase):
    def test_tickets_follow_rules_and_are_unique(self):
        tickets = generate_tickets(20, random.Random(7))

        self.assertEqual(len(tickets), 20)
        self.assertEqual(len(set(tickets)), 20)
        for reds, blue in tickets:
            self.assertEqual(len(reds), 6)
            self.assertEqual(len(set(reds)), 6)
            self.assertEqual(tuple(sorted(reds)), reds)
            self.assertTrue(all(1 <= number <= 33 for number in reds))
            self.assertTrue(1 <= blue <= 16)

    def test_rejects_out_of_range_count(self):
        with self.assertRaises(ValueError):
            generate_tickets(0)
        with self.assertRaises(ValueError):
            generate_tickets(101)

    def test_historical_weights_influence_selection(self):
        class HighestWeightRandom(random.Random):
            def choices(self, population, weights=None, k=1):
                index = max(range(len(weights)), key=weights.__getitem__)
                return [population[index]]

        red_counts = {33: 10}
        blue_counts = {16: 10}
        (reds, blue), = generate_tickets(
            1,
            HighestWeightRandom(),
            red_weights=red_counts,
            blue_weights=blue_counts,
        )

        self.assertIn(33, reds)
        self.assertEqual(blue, 16)

    def test_requires_both_color_frequency_maps(self):
        with self.assertRaisesRegex(ValueError, "同时提供"):
            generate_tickets(1, red_weights={1: 2})


class ReadHistoryTests(unittest.TestCase):
    def test_reads_counts_and_ignores_blank_rows(self):
        data = (
            "date,red1,red2,red3,red4,red5,red6,blue\n"
            "2026-01-01,1,2,3,4,5,6,7\n"
            "2026-01-08,1,8,9,10,11,12,7\n"
            ",,,,,,,\n"
        )

        history = read_history(io.StringIO(data))

        self.assertEqual(history.draw_count, 2)
        self.assertEqual(history.red_counts[1], 2)
        self.assertEqual(history.red_counts[2], 1)
        self.assertEqual(history.blue_counts[7], 2)
        self.assertEqual(history.red_counts[33], 0)
        self.assertEqual(history.last_draw, ((1, 8, 9, 10, 11, 12), 7))

    def test_rejects_duplicate_red_numbers(self):
        data = "red1,red2,red3,red4,red5,red6,blue\n1,1,3,4,5,6,7\n"
        with self.assertRaisesRegex(ValueError, "不能重复"):
            read_history(io.StringIO(data))

    def test_rejects_missing_columns(self):
        with self.assertRaisesRegex(ValueError, "缺少列"):
            read_history(io.StringIO("red1,red2,blue\n1,2,3\n"))


class OfficialHistoryTests(unittest.TestCase):
    def test_sorts_official_draws_and_summarizes_history(self):
        payload = json.dumps(
            {
                "state": 0,
                "result": [
                    {
                        "name": "双色球",
                        "code": "2026002",
                        "date": "2026-01-08",
                        "red": "01,08,09,10,11,12",
                        "blue": "07",
                    },
                    {
                        "name": "双色球",
                        "code": "2026001",
                        "date": "2026-01-01",
                        "red": "01,02,03,04,05,06",
                        "blue": "07",
                    },
                ],
            }
        )

        history = parse_official_history(payload)

        self.assertEqual(history.draw_count, 2)
        self.assertEqual(history.latest_issue, "2026002")
        self.assertEqual(history.latest_date, "2026-01-08")
        self.assertEqual(history.last_draw, ((1, 8, 9, 10, 11, 12), 7))
        self.assertEqual(history.red_counts[1], 2)
        self.assertEqual(history.blue_counts[7], 2)

    def test_rejects_failed_official_response(self):
        with self.assertRaisesRegex(ValueError, "接口返回失败"):
            parse_official_history('{"state":1,"message":"failed","result":[]}')


if __name__ == "__main__":
    unittest.main()
