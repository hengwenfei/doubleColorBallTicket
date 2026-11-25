import csv
import json
import queue
import random
import threading
import tkinter as tk
from collections import Counter
from tkinter import filedialog, messagebox, scrolledtext, ttk
from typing import List, Mapping, NamedTuple, Optional, TextIO, Tuple
from urllib.error import URLError
from urllib.request import Request, urlopen


Ticket = Tuple[Tuple[int, ...], int]
REQUIRED_COLUMNS = ["red1", "red2", "red3", "red4", "red5", "red6", "blue"]
LOTTERY_HISTORY_URL = (
    "https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/"
    "findDrawNotice?name=ssq&issueCount=10000"
)


class HistoryData(NamedTuple):
    draw_count: int
    red_counts: Counter
    blue_counts: Counter
    last_draw: Ticket
    latest_issue: Optional[str] = None
    latest_date: Optional[str] = None


def _validate_draw(reds: List[int], blue: int, row_label: str) -> Ticket:
    if len(reds) != 6 or any(number < 1 or number > 33 for number in reds):
        raise ValueError("{} 红球必须是 1 到 33 之间的 6 个号码。".format(row_label))
    if len(set(reds)) != 6:
        raise ValueError("{} 红球不能重复。".format(row_label))
    if not 1 <= blue <= 16:
        raise ValueError("{} 蓝球必须在 1 到 16 之间。".format(row_label))
    return tuple(sorted(reds)), blue


def _weighted_sample(
    population: range,
    counts: Mapping[int, int],
    sample_size: int,
    rng: random.Random,
) -> List[int]:
    candidates = list(population)
    weights = []
    for number in candidates:
        frequency = counts.get(number, 0)
        if frequency < 0:
            raise ValueError("历史出现次数不能为负数。")
        weights.append(frequency + 1)

    selected = []
    for _ in range(sample_size):
        number = rng.choices(candidates, weights=weights, k=1)[0]
        index = candidates.index(number)
        selected.append(number)
        candidates.pop(index)
        weights.pop(index)
    return selected


def generate_tickets(
    count: int,
    rng: Optional[random.Random] = None,
    red_weights: Optional[Mapping[int, int]] = None,
    blue_weights: Optional[Mapping[int, int]] = None,
) -> List[Ticket]:
    if not 1 <= count <= 100:
        raise ValueError("每次生成数量需在 1 到 100 注之间。")
    if (red_weights is None) != (blue_weights is None):
        raise ValueError("红球和蓝球历史频次需要同时提供。")

    generator = rng if rng is not None else random.SystemRandom()
    tickets = set()
    while len(tickets) < count:
        if red_weights is None:
            reds = tuple(sorted(generator.sample(range(1, 34), 6)))
            blue = generator.randint(1, 16)
        else:
            reds = tuple(
                sorted(_weighted_sample(range(1, 34), red_weights, 6, generator))
            )
            blue = generator.choices(
                range(1, 17),
                weights=[blue_weights.get(number, 0) + 1 for number in range(1, 17)],
                k=1,
            )[0]
        tickets.add((reds, blue))
    return sorted(tickets)


def read_history(stream: TextIO) -> HistoryData:
    reader = csv.DictReader(stream)
    if not reader.fieldnames:
        raise ValueError("CSV 文件为空，或缺少表头。")

    reader.fieldnames = [name.strip().lower() if name else "" for name in reader.fieldnames]
    if len(set(reader.fieldnames)) != len(reader.fieldnames):
        raise ValueError("CSV 表头有重复列名。")
    missing = [name for name in REQUIRED_COLUMNS if name not in reader.fieldnames]
    if missing:
        raise ValueError("CSV 缺少列：" + ", ".join(missing))

    red_counts = Counter({number: 0 for number in range(1, 34)})
    blue_counts = Counter({number: 0 for number in range(1, 17)})
    draw_count = 0
    last_draw = None

    for row_number, row in enumerate(reader, start=2):
        values = [row.get(name) for name in REQUIRED_COLUMNS]
        if all(value is None or not value.strip() for value in values):
            continue
        if any(value is None or not value.strip() for value in values):
            raise ValueError("第 {} 行数据不完整。".format(row_number))

        try:
            reds = [int(row[name].strip()) for name in REQUIRED_COLUMNS[:6]]
            blue = int(row["blue"].strip())
        except ValueError:
            raise ValueError("第 {} 行包含非整数号码。".format(row_number))

        draw = _validate_draw(reds, blue, "第 {} 行".format(row_number))

        red_counts.update(draw[0])
        blue_counts.update([blue])
        draw_count += 1
        last_draw = draw

    if draw_count == 0:
        raise ValueError("CSV 中没有有效开奖记录。")
    return HistoryData(draw_count, red_counts, blue_counts, last_draw)


def parse_official_history(payload: str) -> HistoryData:
    try:
        response = json.loads(payload)
    except json.JSONDecodeError as error:
        raise ValueError("官网返回的数据不是有效 JSON。") from error
    if not isinstance(response, dict) or str(response.get("state")) != "0":
        message = response.get("message", "未知错误") if isinstance(response, dict) else "格式错误"
        raise ValueError("官网开奖接口返回失败：{}".format(message))

    records = response.get("result")
    if not isinstance(records, list) or not records:
        raise ValueError("官网暂未返回双色球开奖记录。")

    draws = []
    for row_number, record in enumerate(records, start=1):
        if not isinstance(record, dict) or record.get("name") != "双色球":
            raise ValueError("官网第 {} 条记录格式不正确。".format(row_number))
        issue = str(record.get("code", "")).strip()
        if not issue.isdigit():
            raise ValueError("官网第 {} 条记录缺少有效期号。".format(row_number))
        try:
            reds = [int(value.strip()) for value in record["red"].split(",")]
            blue = int(record["blue"])
        except (KeyError, AttributeError, TypeError, ValueError):
            raise ValueError("官网第 {} 条记录号码格式不正确。".format(row_number))

        draw = _validate_draw(reds, blue, "官网第 {} 条记录".format(row_number))
        draws.append((int(issue), issue, str(record.get("date", "")).strip(), draw))

    draws.sort(key=lambda item: item[0], reverse=True)
    red_counts = Counter({number: 0 for number in range(1, 34)})
    blue_counts = Counter({number: 0 for number in range(1, 17)})
    for _, _, _, (reds, blue) in draws:
        red_counts.update(reds)
        blue_counts.update([blue])

    _, latest_issue, latest_date, last_draw = draws[0]
    return HistoryData(
        len(draws), red_counts, blue_counts, last_draw, latest_issue, latest_date
    )


def fetch_official_history() -> HistoryData:
    request = Request(
        LOTTERY_HISTORY_URL,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; SsqHistoryTool/1.0)",
            "Referer": "https://www.cwl.gov.cn/",
        },
    )
    with urlopen(request, timeout=20) as response:
        payload = response.read(10 * 1024 * 1024 + 1)
    if len(payload) > 10 * 1024 * 1024:
        raise ValueError("官网返回的数据过大，已停止读取。")
    return parse_official_history(payload.decode("utf-8"))


class SsqApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.history_counts: Optional[Tuple[Counter, Counter]] = None
        self.last_draw: Optional[Ticket] = None
        self.sync_results = queue.Queue()
        self.root.title("双色球选号与历史统计")
        self.root.geometry("900x800")
        self.root.minsize(700, 620)
        self._build_ui()
        self.root.after(150, self._poll_sync_results)

    def _build_ui(self) -> None:
        main = ttk.Frame(self.root, padding=16)
        main.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main, text="双色球选号与历史统计", font=("", 18, "bold")).pack(anchor=tk.W)
        ttk.Label(
            main,
            text="可纯随机选号，或按同步/导入的历史频次加权选号；历史频次不能预测开奖结果或提高中奖概率。",
            wraplength=700,
        ).pack(anchor=tk.W, pady=(4, 8))
        ttk.Label(main, text="单注一等奖概率：1 / 17,721,088（按 6 红 + 1 蓝规则计算）").pack(
            anchor=tk.W, pady=(0, 12)
        )

        notebook = ttk.Notebook(main)
        notebook.pack(fill=tk.BOTH, expand=True)
        self.pick_tab = ttk.Frame(notebook, padding=12)
        self.stats_tab = ttk.Frame(notebook, padding=12)
        notebook.add(self.pick_tab, text="选号")
        notebook.add(self.stats_tab, text="历史统计")
        self._build_pick_tab()
        self._build_stats_tab()

    def _build_pick_tab(self) -> None:
        controls = ttk.Frame(self.pick_tab)
        controls.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(controls, text="生成注数：").pack(side=tk.LEFT)
        self.ticket_count = tk.IntVar(value=5)
        ttk.Spinbox(
            controls, from_=1, to=100, width=6, textvariable=self.ticket_count
        ).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(controls, text="纯随机生成", command=self._generate).pack(side=tk.LEFT)
        ttk.Button(
            controls, text="按历史频次生成", command=self._generate_by_history
        ).pack(side=tk.LEFT, padx=(8, 0))

        self.ticket_table = ttk.Treeview(
            self.pick_tab, columns=("index", "red", "blue"), show="headings", height=14
        )
        self.ticket_table.heading("index", text="注")
        self.ticket_table.heading("red", text="红球")
        self.ticket_table.heading("blue", text="蓝球")
        self.ticket_table.column("index", width=55, anchor=tk.CENTER)
        self.ticket_table.column("red", width=430, anchor=tk.CENTER)
        self.ticket_table.column("blue", width=100, anchor=tk.CENTER)
        self.ticket_table.pack(fill=tk.BOTH, expand=True)
        ttk.Label(self.pick_tab, text="本次号码的生成依据：").pack(anchor=tk.W, pady=(10, 2))
        self.explanation = scrolledtext.ScrolledText(
            self.pick_tab, height=7, wrap=tk.WORD, state=tk.DISABLED
        )
        self.explanation.pack(fill=tk.X)
        self._generate()

    def _generate(self, history_counts: Optional[Tuple[Counter, Counter]] = None) -> None:
        try:
            red_weights = history_counts[0] if history_counts is not None else None
            blue_weights = history_counts[1] if history_counts is not None else None
            tickets = generate_tickets(
                self.ticket_count.get(),
                red_weights=red_weights,
                blue_weights=blue_weights,
            )
        except (ValueError, tk.TclError) as error:
            messagebox.showerror("无法生成号码", str(error), parent=self.root)
            return

        self.ticket_table.delete(*self.ticket_table.get_children())
        for index, (reds, blue) in enumerate(tickets, start=1):
            red_text = "  ".join("{:02d}".format(number) for number in reds)
            self.ticket_table.insert(
                "", tk.END, values=(index, red_text, "{:02d}".format(blue))
            )
        self._show_explanations(tickets, history_counts is not None)

    def _show_explanations(self, tickets: List[Ticket], frequency_weighted: bool) -> None:
        lines = []
        for index, (reds, blue) in enumerate(tickets, start=1):
            if frequency_weighted:
                method = "按历史频次 + 1 加权抽取"
            else:
                method = "纯随机抽取，未使用历史频次"

            if self.history_counts is None:
                frequency_detail = "尚未载入历史数据，无法列出历史出现次数。"
            else:
                red_counts, blue_counts = self.history_counts
                red_detail = "、".join(
                    "{:02d}（{}期）".format(number, red_counts[number])
                    for number in reds
                )
                frequency_detail = "红球历史次数：{}；蓝球 {:02d} 历史次数：{} 期。".format(
                    red_detail, blue, blue_counts[blue]
                )

            lines.append(
                "第{}注：{}。{} 历史频次仅是当前数据的描述，不代表下期概率。".format(
                    index, method, frequency_detail
                )
            )

        self.explanation.configure(state=tk.NORMAL)
        self.explanation.delete("1.0", tk.END)
        self.explanation.insert(tk.END, "\n".join(lines))
        self.explanation.configure(state=tk.DISABLED)

    def _generate_by_history(self) -> None:
        if self.history_counts is None:
            messagebox.showinfo(
                "需要历史数据", "请先在“历史统计”页导入开奖 CSV。", parent=self.root
            )
            return
        self._generate(self.history_counts)

    def _build_stats_tab(self) -> None:
        controls = ttk.Frame(self.stats_tab)
        controls.pack(fill=tk.X, pady=(0, 8))
        self.sync_button = ttk.Button(
            controls, text="联网同步官网开奖", command=self._sync_official_data
        )
        self.sync_button.pack(side=tk.LEFT)
        ttk.Button(controls, text="导入开奖 CSV", command=self._load_csv).pack(side=tk.LEFT)
        self.stats_status = ttk.Label(controls, text="尚未载入数据")
        self.stats_status.pack(side=tk.LEFT, padx=10)

        ttk.Label(
            self.stats_tab,
            text="图表展示当前历史数据的号码出现次数；虚线为该号码类型的平均次数，不表示未来趋势。",
            wraplength=700,
        ).pack(anchor=tk.W, pady=(0, 8))

        latest_frame = ttk.LabelFrame(self.stats_tab, text="最近一期开奖", padding=8)
        latest_frame.pack(fill=tk.X, pady=(0, 8))
        self.latest_draw_label = ttk.Label(latest_frame, text="请联网同步，或导入按时间排列的开奖 CSV。")
        self.latest_draw_label.pack(anchor=tk.W)

        charts = ttk.Frame(self.stats_tab)
        charts.pack(fill=tk.X, pady=(0, 8))
        red_chart_frame = ttk.LabelFrame(charts, text="红球出现次数", padding=4)
        red_chart_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
        blue_chart_frame = ttk.LabelFrame(charts, text="蓝球出现次数", padding=4)
        blue_chart_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.red_chart = tk.Canvas(
            red_chart_frame, height=145, background="white", highlightthickness=0
        )
        self.red_chart.pack(fill=tk.BOTH, expand=True)
        self.blue_chart = tk.Canvas(
            blue_chart_frame, height=145, background="white", highlightthickness=0
        )
        self.blue_chart.pack(fill=tk.BOTH, expand=True)
        self.red_chart.bind("<Configure>", self._red_chart_resized)
        self.blue_chart.bind("<Configure>", self._blue_chart_resized)

        self.stats_table = ttk.Treeview(
            self.stats_tab, columns=("number", "red_count", "blue_count"), show="headings"
        )
        self.stats_table.heading("number", text="号码")
        self.stats_table.heading("red_count", text="红球出现期数")
        self.stats_table.heading("blue_count", text="蓝球出现期数")
        self.stats_table.column("number", width=100, anchor=tk.CENTER)
        self.stats_table.column("red_count", width=180, anchor=tk.CENTER)
        self.stats_table.column("blue_count", width=180, anchor=tk.CENTER)
        self.stats_table.pack(fill=tk.BOTH, expand=True)

    def _red_chart_resized(self, _event: tk.Event) -> None:
        if self.history_counts is not None:
            self._draw_frequency_chart(
                self.red_chart, self.history_counts[0], 6, 33, "#d94b4b"
            )

    def _blue_chart_resized(self, _event: tk.Event) -> None:
        if self.history_counts is not None:
            self._draw_frequency_chart(
                self.blue_chart, self.history_counts[1], 1, 16, "#3978c5"
            )

    @staticmethod
    def _draw_frequency_chart(
        canvas: tk.Canvas,
        counts: Counter,
        draws_per_issue: int,
        number_of_balls: int,
        color: str,
    ) -> None:
        canvas.delete("all")
        width = canvas.winfo_width()
        height = canvas.winfo_height()
        numbers = range(1, number_of_balls + 1)
        values = [counts[number] for number in numbers]
        if not values:
            return

        left, right, top, bottom = 32, 8, 24, 24
        plot_width = max(1, width - left - right)
        plot_height = max(1, height - top - bottom)
        maximum = max(values + [1])
        average = sum(values) / len(values)
        average_y = top + plot_height * (1 - average / maximum)

        canvas.create_line(left, average_y, width - right, average_y, fill="#666666", dash=(4, 3))
        canvas.create_text(
            left + 2, max(8, average_y - 8), text="均值 {:.1f}".format(average), anchor=tk.W
        )

        step = plot_width / number_of_balls
        bar_width = max(2, step * 0.62)
        label_interval = 1 if number_of_balls <= 16 else 3
        for index, number in enumerate(numbers):
            value = values[index]
            x_center = left + step * (index + 0.5)
            bar_height = plot_height * value / maximum
            canvas.create_rectangle(
                x_center - bar_width / 2,
                top + plot_height - bar_height,
                x_center + bar_width / 2,
                top + plot_height,
                fill=color,
                outline="",
            )
            if number % label_interval == 0 or number == 1:
                canvas.create_text(
                    x_center, height - bottom + 10, text="{:02d}".format(number)
                )

    def _load_csv(self) -> None:
        path = filedialog.askopenfilename(
            parent=self.root,
            title="选择历史开奖 CSV",
            filetypes=(("CSV 文件", "*.csv"), ("所有文件", "*.*")),
        )
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8-sig", newline="") as stream:
                history = read_history(stream)
        except (OSError, UnicodeError, ValueError, csv.Error) as error:
            messagebox.showerror("导入失败", str(error), parent=self.root)
            return

        self._apply_history(history, "CSV")

    def _sync_official_data(self) -> None:
        self.sync_button.configure(state=tk.DISABLED)
        self.stats_status.configure(text="正在连接中国福利彩票官网...")
        worker = threading.Thread(target=self._fetch_official_data_worker, daemon=True)
        worker.start()

    def _fetch_official_data_worker(self) -> None:
        try:
            history = fetch_official_history()
        except (URLError, TimeoutError, OSError, UnicodeError, ValueError) as error:
            self.sync_results.put((False, str(error)))
            return
        self.sync_results.put((True, history))

    def _poll_sync_results(self) -> None:
        while True:
            try:
                succeeded, result = self.sync_results.get_nowait()
            except queue.Empty:
                break

            self.sync_button.configure(state=tk.NORMAL)
            if succeeded:
                self._apply_history(result, "中国福利彩票官网")
            else:
                self.stats_status.configure(text="官网同步失败")
                messagebox.showerror(
                    "联网同步失败",
                    "{}\n\n可检查网络后重试，或改用 CSV 导入。".format(result),
                    parent=self.root,
                )
        self.root.after(150, self._poll_sync_results)

    def _apply_history(self, history: HistoryData, source: str) -> None:
        self.history_counts = (history.red_counts, history.blue_counts)
        self.last_draw = history.last_draw
        reds, blue = history.last_draw
        latest_info = []
        if history.latest_issue:
            latest_info.append("第 {} 期".format(history.latest_issue))
        if history.latest_date:
            latest_info.append(history.latest_date)
        prefix = "（{}）".format("，".join(latest_info)) if latest_info else ""
        self.latest_draw_label.configure(
            text="{}红球：{}    蓝球：{:02d}".format(
                prefix, "  ".join("{:02d}".format(number) for number in reds), blue
            )
        )
        self.stats_table.delete(*self.stats_table.get_children())
        for number in range(1, 34):
            self.stats_table.insert(
                "",
                tk.END,
                values=(
                    "{:02d}".format(number),
                    history.red_counts[number],
                    history.blue_counts[number] if number <= 16 else "-",
                ),
            )
        self.stats_status.configure(
            text="{}：已载入 {} 期".format(source, history.draw_count)
        )
        self._red_chart_resized(None)
        self._blue_chart_resized(None)


def main() -> None:
    root = tk.Tk()
    SsqApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
