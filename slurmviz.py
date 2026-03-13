#!/usr/bin/env python3
"""slurmviz - A terminal UI dashboard for Slurm cluster GPU status."""

import argparse
import asyncio
import os
import random
import sys
from dataclasses import dataclass, field

from textual.app import App
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.timer import Timer
from textual.widget import Widget
from textual.widgets import Footer, Header, Static


# ── Data Models ──────────────────────────────────────────────────────────────

@dataclass
class GpuInfo:
    """Single GPU on a node."""
    index: int
    utilization: int  # 0-100 percent
    allocated: bool
    job_id: str = ""
    user: str = ""


@dataclass
class NodeInfo:
    """A single Slurm compute node."""
    name: str
    state: str  # idle, mixed, allocated, down, drain
    total_gpus: int
    used_gpus: int
    total_cpus: int
    used_cpus: int
    mem_total_mb: int
    mem_used_mb: int
    gpus: list[GpuInfo] = field(default_factory=list)


@dataclass
class JobInfo:
    """A Slurm job."""
    job_id: str
    name: str
    user: str
    state: str  # R, PD, CG, etc.
    elapsed: str
    num_gpus: int
    node: str
    partition: str = ""


@dataclass
class ClusterData:
    """All cluster data in one snapshot."""
    nodes: list[NodeInfo]
    jobs: list[JobInfo]
    my_jobs: list[JobInfo]
    user: str


# ── Data Fetching ────────────────────────────────────────────────────────────

async def run_cmd(cmd: str) -> str:
    """Run a shell command and return stdout."""
    proc = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, _ = await proc.communicate()
    return stdout.decode().strip()


async def fetch_slurm_data() -> ClusterData:
    """Fetch real data from Slurm commands."""
    user = os.environ.get("USER", "unknown")

    # Run all commands in parallel
    node_raw, job_raw, my_job_raw, gpu_alloc_raw = await asyncio.gather(
        run_cmd('sinfo -N -o "%N %T %G %C %m" --noheader 2>/dev/null'),
        run_cmd('squeue -o "%i %j %u %t %M %b %N %P" --noheader 2>/dev/null'),
        run_cmd(f'squeue -u {user} -o "%i %j %u %t %M %b %N %P" --noheader 2>/dev/null'),
        run_cmd('squeue -o "%N %b %u %i" --noheader 2>/dev/null'),
    )

    # Build per-node GPU allocation map: {node: [{user, job_id, gpus}]}
    node_gpu_alloc: dict[str, list[dict]] = {}
    for line in gpu_alloc_raw.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        node, gres, alloc_user, job_id = parts[0], parts[1], parts[2], parts[3]
        gpu_count = 0
        if "gpu:" in gres:
            try:
                gpu_count = int(gres.split("gpu:")[-1].split(",")[0])
            except ValueError:
                pass
        if gpu_count > 0:
            node_gpu_alloc.setdefault(node, []).append(
                {"user": alloc_user, "job_id": job_id, "gpus": gpu_count}
            )

    # Parse nodes
    nodes = []
    seen = set()
    for line in node_raw.splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue
        name, state, gres, cpus_str, mem = parts[0], parts[1], parts[2], parts[3], parts[4]
        if name in seen:
            continue
        seen.add(name)

        total_gpus = 0
        if "gpu:" in gres:
            try:
                total_gpus = int(gres.split("gpu:")[-1].split("(")[0].split(",")[0])
            except ValueError:
                pass

        # Parse CPU A/I/O/T format
        cpu_parts = cpus_str.split("/")
        used_cpus = int(cpu_parts[0]) if len(cpu_parts) >= 4 else 0
        total_cpus = int(cpu_parts[3]) if len(cpu_parts) >= 4 else 0
        mem_total = int(mem) if mem.isdigit() else 0

        # Count used GPUs from allocation data
        allocs = node_gpu_alloc.get(name, [])
        used_gpus = sum(a["gpus"] for a in allocs)

        # Build per-GPU list
        gpus = []
        for i in range(total_gpus):
            gpus.append(GpuInfo(index=i, utilization=0, allocated=False))
        # Mark allocated GPUs
        gpu_idx = 0
        for a in allocs:
            for _ in range(a["gpus"]):
                if gpu_idx < len(gpus):
                    gpus[gpu_idx].allocated = True
                    gpus[gpu_idx].user = a["user"]
                    gpus[gpu_idx].job_id = a["job_id"]
                    gpus[gpu_idx].utilization = random.randint(60, 99)  # estimate
                    gpu_idx += 1

        nodes.append(NodeInfo(
            name=name, state=state.lower(), total_gpus=total_gpus,
            used_gpus=used_gpus, total_cpus=total_cpus, used_cpus=used_cpus,
            mem_total_mb=mem_total, mem_used_mb=0, gpus=gpus,
        ))

    # Parse jobs
    def parse_jobs(raw: str) -> list[JobInfo]:
        jobs = []
        for line in raw.splitlines():
            parts = line.split()
            if len(parts) < 7:
                continue
            jid, name, usr, state, elapsed, gres, node = parts[:7]
            partition = parts[7] if len(parts) > 7 else ""
            ngpu = 0
            if "gpu:" in gres:
                try:
                    ngpu = int(gres.split("gpu:")[-1].split(",")[0])
                except ValueError:
                    pass
            jobs.append(JobInfo(
                job_id=jid, name=name, user=usr, state=state,
                elapsed=elapsed, num_gpus=ngpu, node=node, partition=partition,
            ))
        return jobs

    return ClusterData(
        nodes=sorted(nodes, key=lambda n: n.name),
        jobs=parse_jobs(job_raw),
        my_jobs=parse_jobs(my_job_raw),
        user=user,
    )


# ── Demo Data ────────────────────────────────────────────────────────────────

_DEMO_USERS = ["alice", "bob", "charlie", "diana", "eve", "frank"]
_DEMO_JOBNAMES = [
    "train-llama", "eval-bert", "finetune-vit", "preprocess", "inference-gpt",
    "train-diffusion", "rl-ppo-run", "data-augment", "tokenize-xl", "distill-t5",
]


def generate_demo_data() -> ClusterData:
    """Generate realistic fake cluster data."""
    user = os.environ.get("USER", "you")
    nodes = []
    all_jobs = []
    my_jobs = []
    job_counter = 1000000

    for i in range(1, 17):
        name = f"gpu{i:02d}"
        total_gpus = random.choice([4, 4, 8, 8, 8])
        total_cpus = total_gpus * 16

        # Weighted state selection
        r = random.random()
        if r < 0.05:
            state = "down"
            used_gpus = 0
        elif r < 0.10:
            state = "drain"
            used_gpus = 0
        elif r < 0.30:
            state = "idle"
            used_gpus = 0
        elif r < 0.70:
            state = "mixed"
            used_gpus = random.randint(1, total_gpus - 1)
        else:
            state = "allocated"
            used_gpus = total_gpus

        gpus = []
        for gi in range(total_gpus):
            allocated = gi < used_gpus
            util = random.randint(40, 99) if allocated else random.randint(0, 5)
            gpu_user = ""
            gpu_job = ""
            if allocated:
                gpu_user = random.choice(_DEMO_USERS + [user, user])  # bias towards user
                gpu_job = str(job_counter)
            gpus.append(GpuInfo(
                index=gi, utilization=util, allocated=allocated,
                user=gpu_user, job_id=gpu_job,
            ))

        used_cpus = int(total_cpus * (used_gpus / total_gpus)) if total_gpus > 0 else 0
        mem_total = total_cpus * 4000

        nodes.append(NodeInfo(
            name=name, state=state, total_gpus=total_gpus,
            used_gpus=used_gpus, total_cpus=total_cpus, used_cpus=used_cpus,
            mem_total_mb=mem_total, mem_used_mb=int(mem_total * used_gpus / max(total_gpus, 1)),
            gpus=gpus,
        ))

        # Create jobs for allocated GPUs
        if used_gpus > 0:
            # Group consecutive GPUs by user
            current_user = None
            gpu_count = 0
            for g in gpus:
                if g.allocated:
                    if g.user != current_user:
                        if current_user is not None:
                            job_counter += 1
                            j = JobInfo(
                                job_id=str(job_counter), name=random.choice(_DEMO_JOBNAMES),
                                user=current_user,
                                state=random.choice(["R", "R", "R", "R", "CG"]),
                                elapsed=f"{random.randint(0,72)}:{random.randint(0,59):02d}:{random.randint(0,59):02d}",
                                num_gpus=gpu_count, node=name,
                            )
                            all_jobs.append(j)
                            if current_user == user:
                                my_jobs.append(j)
                        current_user = g.user
                        gpu_count = 1
                    else:
                        gpu_count += 1
            if current_user is not None:
                job_counter += 1
                j = JobInfo(
                    job_id=str(job_counter), name=random.choice(_DEMO_JOBNAMES),
                    user=current_user,
                    state=random.choice(["R", "R", "R", "R", "CG"]),
                    elapsed=f"{random.randint(0,72)}:{random.randint(0,59):02d}:{random.randint(0,59):02d}",
                    num_gpus=gpu_count, node=name,
                )
                all_jobs.append(j)
                if current_user == user:
                    my_jobs.append(j)

    # Add some pending jobs
    for _ in range(random.randint(1, 4)):
        job_counter += 1
        u = random.choice(_DEMO_USERS + [user])
        j = JobInfo(
            job_id=str(job_counter), name=random.choice(_DEMO_JOBNAMES),
            user=u, state="PD", elapsed="0:00:00",
            num_gpus=random.choice([1, 2, 4, 8]), node="(Priority)",
        )
        all_jobs.append(j)
        if u == user:
            my_jobs.append(j)

    return ClusterData(nodes=nodes, jobs=all_jobs, my_jobs=my_jobs, user=user)


# ── Widgets ──────────────────────────────────────────────────────────────────

STATE_COLORS = {
    "idle": "green",
    "mixed": "yellow",
    "allocated": "magenta",
    "down": "red",
    "drain": "red",
    "drained": "red",
    "draining": "dark_orange",
}


def gpu_bar_char(util: int, allocated: bool) -> tuple[str, str]:
    """Return a block character and color for a GPU utilization level."""
    if not allocated:
        return "░", "dim"
    if util >= 80:
        return "█", "green"
    if util >= 50:
        return "▓", "yellow"
    if util >= 20:
        return "▒", "dark_orange"
    return "▒", "red"


class NodeMapWidget(Widget):
    """Shows all nodes with per-node GPU utilization bars."""

    DEFAULT_CSS = """
    NodeMapWidget {
        height: 100%;
        padding: 0 1;
    }
    """

    data: reactive[ClusterData | None] = reactive(None)

    def render(self) -> str:
        if self.data is None:
            return "[dim]Loading...[/]"

        lines = []
        for n in self.data.nodes:
            color = STATE_COLORS.get(n.state, "white")
            # State indicator
            if n.state in ("down", "drain", "drained"):
                dot = f"[{color}]✗[/]"
            elif n.state == "idle":
                dot = f"[{color}]●[/]"
            elif n.state == "mixed":
                dot = f"[{color}]◐[/]"
            else:
                dot = f"[{color}]●[/]"

            # Per-GPU mini bar
            bar = ""
            if n.gpus:
                for g in n.gpus:
                    ch, c = gpu_bar_char(g.utilization, g.allocated)
                    bar += f"[{c}]{ch}[/]"
            else:
                bar = "[dim]--[/]"

            gpu_label = f"{n.used_gpus}/{n.total_gpus}"
            state_label = f"[{color}]{n.state[:5]:>5}[/]"
            lines.append(
                f" {dot} [bold]{n.name:<8}[/] {bar} [bold]{gpu_label:>5}[/] {state_label}"
            )

        return "\n".join(lines) if lines else "[dim]No nodes[/]"


class GpuSummaryWidget(Widget):
    """Shows cluster-wide GPU summary and per-user breakdown."""

    DEFAULT_CSS = """
    GpuSummaryWidget {
        height: 100%;
        padding: 0 1;
    }
    """

    data: reactive[ClusterData | None] = reactive(None)

    def render(self) -> str:
        if self.data is None:
            return "[dim]Loading...[/]"

        nodes = self.data.nodes
        total = sum(n.total_gpus for n in nodes)
        down_gpus = sum(
            n.total_gpus for n in nodes if n.state in ("down", "drain", "drained")
        )
        used = sum(n.used_gpus for n in nodes)
        free = total - down_gpus - used
        usable = total - down_gpus
        pct = (free * 100 // usable) if usable > 0 else 0

        # Big bar
        bar_len = 30
        filled = pct * bar_len // 100
        bar = f"[green]{'█' * filled}[/][dim]{'░' * (bar_len - filled)}[/]"

        # Color for percentage
        if pct >= 50:
            pct_color = "green"
        elif pct >= 20:
            pct_color = "yellow"
        else:
            pct_color = "red"

        lines = [
            f"[bold]  GPU CLUSTER[/]",
            f"",
            f"  [dim]Total[/] [bold]{total:>4}[/]   [dim]Used[/] [bold]{used:>4}[/]   [dim]Free[/] [bold green]{free:>4}[/]",
            f"  {bar} [{pct_color} bold]{pct:>3}%[/] [dim]free[/]",
            f"",
        ]

        if down_gpus > 0:
            lines.append(f"  [red]⚠ {down_gpus} GPUs offline (down/drain)[/]")
            lines.append("")

        # Per-user breakdown
        user_gpus: dict[str, int] = {}
        user_jobs: dict[str, int] = {}
        for j in self.data.jobs:
            user_jobs[j.user] = user_jobs.get(j.user, 0) + 1
            if j.state in ("R", "CG"):
                user_gpus[j.user] = user_gpus.get(j.user, 0) + j.num_gpus

        sorted_users = sorted(user_gpus.items(), key=lambda x: -x[1])

        lines.append(f"  [bold]PER-USER GPU USAGE[/]")
        lines.append(f"  [dim]{'USER':<12} {'GPUs':>4} {'JOBS':>4}  {'':20}[/]")

        for u, g in sorted_users[:10]:
            j = user_jobs.get(u, 0)
            u_pct = (g * 100 // usable) if usable > 0 else 0
            u_bar_len = 16
            u_filled = u_pct * u_bar_len // 100
            u_bar = f"[yellow]{'█' * u_filled}[/][dim]{'░' * (u_bar_len - u_filled)}[/]"

            marker = "►" if u == self.data.user else " "
            u_color = "green bold" if u == self.data.user else "white"

            lines.append(
                f"  [{u_color}]{marker}{u:<11}[/] [cyan]{g:>4}[/] [dim]{j:>4}[/]  {u_bar} [bold]{u_pct:>2}%[/]"
            )

        return "\n".join(lines)


class MyJobsWidget(Widget):
    """Shows current user's jobs."""

    DEFAULT_CSS = """
    MyJobsWidget {
        height: 100%;
        padding: 0 1;
    }
    """

    data: reactive[ClusterData | None] = reactive(None)

    def render(self) -> str:
        if self.data is None:
            return "[dim]Loading...[/]"

        jobs = self.data.my_jobs
        total_gpus = sum(j.num_gpus for j in jobs if j.state in ("R", "CG"))

        lines = [
            f"  [bold cyan]◈ MY JOBS[/]  [dim]jobs:[/][bold]{len(jobs)}[/]  [dim]gpus:[/][bold green]{total_gpus}[/]",
            f"  [dim]{'ID':<10} {'NAME':<20} {'ST':>3} {'TIME':>10} {'GPU':>3} {'NODE':<12} {'PART':<10}[/]",
        ]

        if not jobs:
            lines.append(f"  [dim]No jobs running[/]")
        else:
            for j in jobs:
                state_color = {"R": "green", "PD": "yellow", "CG": "magenta"}.get(j.state, "red")
                state_label = {"R": "RUN", "PD": "PND", "CG": "CMP"}.get(j.state, j.state)
                name = j.name[:18] + ".." if len(j.name) > 20 else j.name
                lines.append(
                    f"  [white]{j.job_id:<10}[/] [bold]{name:<20}[/] [{state_color}]{state_label:>3}[/] "
                    f"[dim]{j.elapsed:>10}[/] [cyan]{j.num_gpus:>3}[/] [green]{j.node:<12}[/] [dim]{j.partition:<10}[/]"
                )

        return "\n".join(lines)


class GpuGridWidget(Widget):
    """Per-GPU visualization — a thin vertical bar for every GPU in the cluster."""

    DEFAULT_CSS = """
    GpuGridWidget {
        height: 100%;
        padding: 0 1;
    }
    """

    data: reactive[ClusterData | None] = reactive(None)

    def _gpu_bar(self, util: int, allocated: bool, is_mine: bool, is_down: bool, bar_width: int = 12) -> str:
        """Render a thin horizontal bar for a single GPU."""
        if is_down:
            return f"[red]{'✗' * bar_width}[/]"
        if not allocated:
            return f"[dim green]{'░' * bar_width}[/]"

        filled = max(1, util * bar_width // 100)
        empty = bar_width - filled

        if is_mine:
            c = "bright_green"
        elif util >= 90:
            c = "bright_red"
        elif util >= 70:
            c = "yellow"
        elif util >= 40:
            c = "cyan"
        else:
            c = "green"

        return f"[{c}]{'█' * filled}[/][dim]{'░' * empty}[/]"

    def render(self) -> str:
        if self.data is None:
            return "[dim]Loading...[/]"

        # Count totals
        total_gpus = sum(len(n.gpus) for n in self.data.nodes)
        alloc_gpus = sum(1 for n in self.data.nodes for g in n.gpus if g.allocated)
        free_gpus = total_gpus - alloc_gpus

        lines = [
            f"  [bold cyan]⬡ ALL GPUs[/]  "
            f"[dim]total:[/][bold]{total_gpus}[/]  "
            f"[dim]alloc:[/][bold]{alloc_gpus}[/]  "
            f"[dim]free:[/][bold green]{free_gpus}[/]  "
            f"[dim](bar = utilization per GPU)[/]",
            "",
        ]

        # Render per-node: node name then a thin bar for each GPU
        for n in self.data.nodes:
            if not n.gpus:
                continue

            node_color = STATE_COLORS.get(n.state, "white")
            is_down = n.state in ("down", "drain", "drained")

            # Header line: node name + GPU index labels
            gpu_indices = "  ".join(f"[dim]{g.index:<12}[/]" for g in n.gpus[:4])
            # Build GPU bars - 2 per row if >4 GPUs, or all on one row
            bar_width = 10
            gpu_rows = []
            row_gpus = []
            for g in n.gpus:
                is_mine = g.user == self.data.user
                bar = self._gpu_bar(g.utilization, g.allocated, is_mine, is_down, bar_width)

                # Label: util% and user
                if is_down:
                    label = f"[red]DOWN[/]"
                elif not g.allocated:
                    label = f"[dim green]free[/]"
                else:
                    c = "bright_green" if is_mine else "white"
                    label = f"[{c}]{g.utilization:>3}%[/]"

                row_gpus.append(f"{bar} {label}")
                if len(row_gpus) == 4:
                    gpu_rows.append(row_gpus)
                    row_gpus = []
            if row_gpus:
                gpu_rows.append(row_gpus)

            # First row gets the node name
            for ri, row in enumerate(gpu_rows):
                prefix = f"  [{node_color}]{n.name:<8}[/] " if ri == 0 else "             "
                lines.append(prefix + "  ".join(row))

        # Legend
        lines.append("")
        lines.append(
            f"  [dim green]░░[/][dim]=free[/]  "
            f"[green]██[/][dim]=<40%[/]  "
            f"[cyan]██[/][dim]=40-69%[/]  "
            f"[yellow]██[/][dim]=70-89%[/]  "
            f"[bright_red]██[/][dim]=90%+[/]  "
            f"[bright_green]██[/][dim]=yours[/]  "
            f"[red]✗✗[/][dim]=down[/]"
        )

        return "\n".join(lines)


# ── Main App ─────────────────────────────────────────────────────────────────

TCSS = """
#top-row {
    height: 2fr;
    layout: horizontal;
}

#node-panel {
    width: 1fr;
    border: solid $accent-darken-2;
    border-title-color: $text;
    overflow-y: auto;
}

#summary-panel {
    width: 1fr;
    border: solid $accent-darken-2;
    border-title-color: $text;
    overflow-y: auto;
}

#jobs-panel {
    height: auto;
    max-height: 12;
    border: solid $accent-darken-2;
    border-title-color: $text;
    overflow-y: auto;
}

#gpu-panel {
    height: 1fr;
    border: solid $accent-darken-2;
    border-title-color: $text;
    overflow-y: auto;
}
"""


class SlurmViz(App):
    """Slurm GPU cluster dashboard."""

    CSS = TCSS
    TITLE = "slurmviz"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
        ("d", "toggle_demo", "Demo"),
    ]

    demo_mode: reactive[bool] = reactive(False)
    refresh_interval: int = 5

    def __init__(self, demo: bool = False, refresh: int = 5) -> None:
        super().__init__()
        self.demo_mode = demo
        self.refresh_interval = refresh
        self._refresh_timer: Timer | None = None

    def compose(self):
        yield Header(show_clock=True)
        with Horizontal(id="top-row"):
            yield VerticalScroll(NodeMapWidget(id="node-map"), id="node-panel")
            yield VerticalScroll(GpuSummaryWidget(id="gpu-summary"), id="summary-panel")
        yield VerticalScroll(MyJobsWidget(id="my-jobs"), id="jobs-panel")
        yield VerticalScroll(GpuGridWidget(id="gpu-grid"), id="gpu-panel")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#node-panel").border_title = "NODES"
        self.query_one("#summary-panel").border_title = "GPU SUMMARY"
        self.query_one("#jobs-panel").border_title = "MY JOBS"
        self.query_one("#gpu-panel").border_title = "ALL GPUs"
        self._refresh_timer = self.set_interval(self.refresh_interval, self._do_refresh)
        self.call_after_refresh(self._do_refresh)

    async def _do_refresh(self) -> None:
        if self.demo_mode:
            data = generate_demo_data()
        else:
            try:
                data = await fetch_slurm_data()
                if not data.nodes:
                    # No Slurm available, fall back to demo
                    data = generate_demo_data()
                    self.demo_mode = True
                    self.sub_title = "DEMO MODE (Slurm not found)"
            except Exception:
                data = generate_demo_data()
                self.demo_mode = True
                self.sub_title = "DEMO MODE (error)"

        self.query_one("#node-map", NodeMapWidget).data = data
        self.query_one("#gpu-summary", GpuSummaryWidget).data = data
        self.query_one("#my-jobs", MyJobsWidget).data = data
        self.query_one("#gpu-grid", GpuGridWidget).data = data

    def watch_demo_mode(self, value: bool) -> None:
        if value:
            self.sub_title = "DEMO MODE"
        else:
            self.sub_title = ""

    def action_refresh(self) -> None:
        self.call_after_refresh(self._do_refresh)

    def action_toggle_demo(self) -> None:
        self.demo_mode = not self.demo_mode
        self.call_after_refresh(self._do_refresh)


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Slurm GPU cluster TUI dashboard")
    parser.add_argument("--demo", action="store_true", help="Use demo/fake data")
    parser.add_argument("-r", "--refresh", type=int, default=5, help="Refresh interval in seconds (default: 5)")
    args = parser.parse_args()

    app = SlurmViz(demo=args.demo, refresh=args.refresh)
    app.run()


if __name__ == "__main__":
    main()
