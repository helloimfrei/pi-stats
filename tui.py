import sys
from collections import deque

import httpx
from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Footer, Sparkline, Static, TabbedContent, TabPane

SERVER_URL = sys.argv[1] if len(sys.argv) > 1 else "http://bazzite.local:8000"

MAX_HISTORY = 300  # 5 min at 1s intervals

# palette — terra jade
BG      = "#f7f0d8"  # warm off-white yellow cream
FG      = "#2d5c44"  # dark jade green
ACCENT  = "#7a4a28"  # mid-dark wood brown
MUTED   = "#9a8a70"  # warm muted tone
EMPTY   = "#ddd0b8"  # empty bar
HOT     = "#c03020"  # warm red
WARM    = "#a07820"  # amber


class StatsApp(App):
    CSS = f"""
    Screen {{
        background: {BG};
    }}
    Footer {{
        background: {ACCENT};
        color: {BG};
    }}
    TabbedContent {{
        margin: 1 1;
        height: 1fr;
    }}
    Tabs {{
        dock: top;
        height: 3;
        background: {BG};
    }}
    Tab {{
        color: {ACCENT};
        background: {BG};
        padding: 0 2;
    }}
    Tab:hover {{
        color: {FG};
    }}
    Tab.-active {{
        color: {FG};
        text-style: bold;
    }}
    Underline > .underline--bar {{
        color: {ACCENT};
        background: {EMPTY};
    }}
    ContentSwitcher {{
        height: 1fr;
    }}
    TabPane {{
        padding: 1 2;
        border: solid {ACCENT};
        color: {FG};
        background: {BG};
        text-style: bold;
    }}
    Static {{
        width: 1fr;
        color: {FG};
        background: {BG};
        text-style: bold;
    }}
    Sparkline {{
        height: 3;
        margin: 0 2;
        background: {BG};
    }}
    Sparkline > .sparkline--max-color {{
        color: #2d5c44;
    }}
    Sparkline > .sparkline--min-color {{
        color: #7aaa8a;
    }}
    .graph-label {{
        height: 1;
        margin: 1 2 0 2;
        color: {ACCENT};
        background: {BG};
    }}
    VerticalScroll {{
        background: {BG};
    }}
    """

    TITLE = "pi-stats"
    BINDINGS = [("q", "quit", "Quit")]

    def __init__(self) -> None:
        super().__init__()
        self.cpu_history: deque[float] = deque(maxlen=MAX_HISTORY)
        self.mem_history: deque[float] = deque(maxlen=MAX_HISTORY)
        self.gpu_history: deque[float] = deque(maxlen=MAX_HISTORY)
        self.gpu_temp_history: deque[float] = deque(maxlen=MAX_HISTORY)

    def compose(self) -> ComposeResult:
        with TabbedContent():
            with TabPane("Overview", id="tab-overview"):
                with VerticalScroll():
                    yield Static("waiting...", id="ov-cpu")
                    yield Sparkline([], id="ov-cpu-spark")
                    yield Static("waiting...", id="ov-gpu")
                    yield Sparkline([], id="ov-gpu-spark")
                    yield Static("waiting...", id="ov-ram")
                    yield Sparkline([], id="ov-ram-spark")
                    yield Static("", id="ov-temps")
            with TabPane("CPU"):
                yield Static("waiting...", id="cpu")
                yield Static("CPU %  (5 min)", classes="graph-label")
                yield Sparkline([], id="cpu-spark")
            with TabPane("GPU"):
                yield Static("waiting...", id="gpu")
                yield Static("GPU Util %  (5 min)", classes="graph-label")
                yield Sparkline([], id="gpu-spark")
                yield Static("GPU Temp °C  (5 min)", classes="graph-label")
                yield Sparkline([], id="gpu-temp-spark")
            with TabPane("Memory"):
                yield Static("waiting...", id="memory")
                yield Static("Memory %  (5 min)", classes="graph-label")
                yield Sparkline([], id="mem-spark")
        yield Footer()

    def on_mount(self) -> None:
        self.poll_stats()
        self.set_interval(1, self.poll_stats)

    async def poll_stats(self) -> None:
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(f"{SERVER_URL}/stats", timeout=5)
            data = r.json()
        except Exception as e:
            self.query_one("#ov-cpu", Static).update(f"[{HOT}]connection error: {e}[/]")
            return

        cpu = data["cpu"]
        mem = data["memory"]
        gpu = data.get("gpu", {})
        temps = data.get("temps", {})

        # --- history ---
        self.cpu_history.append(cpu["percent"])
        self.mem_history.append(mem["percent"])
        if gpu:
            self.gpu_history.append(gpu["util_percent"])
            self.gpu_temp_history.append(gpu["temp_c"])
        cpu_temp = _extract_cpu_temp(temps)

        # --- Overview tab ---
        freq = f"{cpu['freq_mhz']:.0f} MHz" if cpu["freq_mhz"] else "n/a"
        nvme_temp = _extract_nvme_temp(temps)
        cpu_temp_str = f"  [{MUTED}]{cpu_temp:.0f}°C[/]" if cpu_temp is not None else ""

        self.query_one("#ov-cpu", Static).update(
            f"\n  [{ACCENT}]CPU[/]    [bold {FG}]{cpu['percent']:>5.1f}%[/]"
            f"   [{MUTED}]{freq}  {cpu['cores']}c/{cpu['threads']}t[/]{cpu_temp_str}\n"
        )
        self.query_one("#ov-cpu-spark", Sparkline).data = list(self.cpu_history)

        self.query_one("#ov-ram", Static).update(
            f"\n  [{ACCENT}]RAM[/]    [bold {FG}]{mem['percent']:>5.1f}%[/]"
            f"   [{MUTED}]{mem['used_gb']} / {mem['total_gb']} GB[/]\n"
        )
        self.query_one("#ov-ram-spark", Sparkline).data = list(self.mem_history)

        if gpu:
            self.query_one("#ov-gpu", Static).update(
                f"\n  [{ACCENT}]GPU[/]    [bold {FG}]{gpu['util_percent']:>5.1f}%[/]"
                f"   [{MUTED}]{gpu['temp_c']}°C  {gpu['name']}[/]\n"
            )
            self.query_one("#ov-gpu-spark", Sparkline).data = list(self.gpu_history)
        else:
            self.query_one("#ov-gpu", Static).update(f"\n  [{ACCENT}]GPU[/]    [{MUTED}]not detected[/]\n")

        temps_parts = []
        if nvme_temp is not None:
            c = _temp_color(nvme_temp)
            temps_parts.append(f"[{ACCENT}]NVMe[/]  [{c}]{nvme_temp:.0f}°C[/]")
        ram_temp = _extract_ram_temp(temps)
        if ram_temp is not None:
            c = _temp_color(ram_temp)
            temps_parts.append(f"[{ACCENT}]RAM[/]   [{c}]{ram_temp:.0f}°C[/]")
        self.query_one("#ov-temps", Static).update(
            "\n  " + "   ".join(temps_parts) + "\n" if temps_parts else ""
        )

        # --- CPU tab ---
        cores = cpu["per_core"]
        per_core = "\n".join(
            "  " + "  ".join(
                f"[{ACCENT}]C{i:<2}[/] {_mini_bar(cores[i])}"
                for i in range(row, min(row + 8, len(cores)))
            )
            for row in range(0, len(cores), 8)
        )
        self.query_one("#cpu", Static).update(
            f"\n"
            f"  [{ACCENT}]Usage[/]    {_bar(cpu['percent'])}\n"
            f"  [{ACCENT}]Freq[/]     [{FG}]{freq}[/]\n"
            f"  [{ACCENT}]Cores[/]    [{FG}]{cpu['cores']}[/]  "
            f"[{ACCENT}]Threads[/]  [{FG}]{cpu['threads']}[/]\n"
            f"\n{per_core}\n"
        )
        self.query_one("#cpu-spark", Sparkline).data = list(self.cpu_history)

        # --- Memory tab ---
        self.query_one("#memory", Static).update(
            f"\n"
            f"  [{ACCENT}]Used[/]     [{FG}]{mem['used_gb']} GB[/]  /  "
            f"[{FG}]{mem['total_gb']} GB[/]\n"
            f"  [{ACCENT}]Usage[/]    {_bar(mem['percent'], width=30)}\n"
        )
        self.query_one("#mem-spark", Sparkline).data = list(self.mem_history)

        # --- GPU tab ---
        if gpu:
            vram_pct = gpu["memory_used_mb"] / gpu["memory_total_mb"] * 100
            self.query_one("#gpu", Static).update(
                f"\n"
                f"  [{ACCENT}]Name[/]     [{FG}]{gpu['name']}[/]\n"
                f"  [{ACCENT}]Util[/]     {_bar(gpu['util_percent'])}\n"
                f"  [{ACCENT}]Temp[/]     [{FG}]{gpu['temp_c']}°C[/]\n"
                f"  [{ACCENT}]VRAM[/]     {_bar(vram_pct)}"
                f"  [{MUTED}]{gpu['memory_used_mb']} / {gpu['memory_total_mb']} MB[/]\n"
            )
            self.query_one("#gpu-spark", Sparkline).data = list(self.gpu_history)
            self.query_one("#gpu-temp-spark", Sparkline).data = list(self.gpu_temp_history)
        else:
            self.query_one("#gpu", Static).update(f"\n  [{MUTED}]no GPU detected[/]\n")



def _extract_cpu_temp(temps: dict) -> float | None:
    for key in ("k10temp", "coretemp"):
        if key in temps:
            for r in temps[key]:
                if r["label"] in ("Tctl", "Package id 0"):
                    return r["current"]
            if temps[key]:
                return temps[key][0]["current"]
    return None


def _extract_nvme_temp(temps: dict) -> float | None:
    if "nvme" not in temps:
        return None
    composites = [r["current"] for r in temps["nvme"] if r["label"] == "Composite"]
    return max(composites) if composites else None


def _extract_ram_temp(temps: dict) -> float | None:
    if "jc42" not in temps:
        return None
    readings = [r["current"] for r in temps["jc42"]]
    return max(readings) if readings else None


def _temp_color(temp: float) -> str:
    if temp >= 80:
        return HOT
    if temp >= 60:
        return WARM
    return FG


def _mini_bar(percent: float, width: int = 6) -> str:
    filled = int(width * percent / 100)
    empty = width - filled
    return f"[{FG}]{'█' * filled}[/][{EMPTY}]{'░' * empty}[/] [{ACCENT}]{percent:>3.0f}%[/]"


def _bar(percent: float, width: int = 20) -> str:
    filled = int(width * percent / 100)
    empty = width - filled
    return f"[{FG}]{'█' * filled}[/][{EMPTY}]{'░' * empty}[/] [{ACCENT}]{percent:.1f}%[/]"


if __name__ == "__main__":
    StatsApp().run()
