# slurmviz

A terminal UI dashboard for monitoring Slurm GPU cluster status, built with [Textual](https://github.com/Textualize/textual).

## Features

- **Node map** — per-node GPU utilization bars with state indicators
- **GPU summary** — cluster-wide totals and per-user GPU/job breakdown
- **All GPUs** — per-GPU utilization bars with user/job info for every GPU in the cluster
- **My jobs** — your running and pending jobs at a glance
- **Auto-refresh** — configurable polling interval (default: 5s)
- **Demo mode** — realistic fake data when Slurm isn't available

## Example Dashboard

```
┌─────────────────────────── slurmviz ──────────────────────────── 12:34:56 ┐
│                                                                           │
├── NODES ──────────────────────┬── GPU SUMMARY ────────────────────────────┤
│                               │                                           │
│ ● node01   █████░░░  5/8 mixed│   GPU CLUSTER                             │
│ ● node02   ████████  8/8 alloc│                                           │
│ ● node03   ░░░░░░░░  0/8  idle│   Total  128   Used   87   Free   33      │
│ ◐ node04   ██░░░░░░  2/8 mixed│   ██████████████████░░░░░░░░░░░░  26% free│
│ ● node05   ████████  8/8 alloc│                                           │
│ ✗ node06   --------  0/4  down│   ⚠ 8 GPUs offline (down/drain)           │
│ ● node07   ██████░░  6/8 mixed│                                           │
│ ● node08   ████████  8/8 alloc│   PER-USER GPU USAGE                      │
│ ● node09   ░░░░░░░░  0/4  idle│   USER         GPUs JOBS                  │
│ ◐ node10   ██░░░░░░  2/8 mixed│  ►you            16    3  ████░░░░  13%   │
│ ● node11   ████████  4/4 alloc│   alice          12    2  ███░░░░░  10%   │
│ ● node12   ██████░░  6/8 mixed│   bob            24    4  ██████░░  20%   │
│ ● node13   ████████  8/8 alloc│   charlie         8    2  ██░░░░░░   6%   │
│ ● node14   ████░░░░  4/8 mixed│   diana          16    3  ████░░░░  13%   │
│ ✗ node15   --------  0/4 drain│   eve             8    1  ██░░░░░░   6%   │
│ ● node16   ██████░░  6/8 mixed│   frank           3    1  █░░░░░░░   2%   │
│                               │                                           │
├── ALL GPUs ───────────────────┴───────────────────────────────────────────┤
│                                                                           │
│  node01   ██████░░ 82%  █████░░░ 70%  ███████░ 91%  ██████░░ 78%    5/8   │
│  node02   ████████ 95%  ███████░ 88%  ████████ 92%  ████████ 97%    8/8   │
│  node03   ░░░░░░░░  1%  ░░░░░░░░  0%  ░░░░░░░░  2%  ░░░░░░░░  0%    0/8   │
│  ...                                                                      │
│                                                                           │
├── MY JOBS ────────────────────────────────────────────────────────────────┤
│                                                                           │
│ ◈ MY JOBS  jobs:3  gpus:16                                                │
│ ID         NAME                  ST       TIME GPU NODE         PART       │
│ 1000042    train-llama          RUN   12:34:56   8 node02      batch       │
│ 1000051    finetune-vit         RUN    3:21:00   4 node14      short       │
│ 1000067    eval-bert            RUN    0:45:12   4 node11      batch       │
│                                                                           │
├───────────────────────────────────────────────────────────────────────────┤
│  q Quit   r Refresh   d Demo                                              │
└───────────────────────────────────────────────────────────────────────────┘
```

## Installation

```bash
source .venv/bin/activate
uv sync
```

## Usage

```bash
uv pip install -e .
```

Then run:

```bash
# Live mode (connects to Slurm)
slurmviz

# Demo mode (fake data, no Slurm required)
slurmviz --demo

# Custom refresh interval (seconds)
slurmviz -r 10
```

### Keyboard Shortcuts

| Key | Action              |
|-----|---------------------|
| `q` | Quit                |
| `r` | Refresh immediately |
| `d` | Toggle demo mode    |

## Requirements

- Python 3.10+
- [uv](https://docs.astral.sh/uv/)
- Slurm commands (`sinfo`, `squeue`) for live data — falls back to demo mode automatically if unavailable
