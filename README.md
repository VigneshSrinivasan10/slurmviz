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
│ ● gpu01    █████░░░  5/8 mixed│   GPU CLUSTER                             │
│ ● gpu02    ████████  8/8 alloc│                                           │
│ ● gpu03    ░░░░░░░░  0/8  idle│   Total  128   Used   87   Free   33      │
│ ◐ gpu04    ██░░░░░░  2/8 mixed│   ██████████████████░░░░░░░░░░░░  26% free│
│ ● gpu05    ████████  8/8 alloc│                                           │
│ ✗ gpu06    --------  0/4  down│   ⚠ 8 GPUs offline (down/drain)           │
│ ● gpu07    ██████░░  6/8 mixed│                                           │
│ ● gpu08    ████████  8/8 alloc│   PER-USER GPU USAGE                      │
│ ● gpu09    ░░░░░░░░  0/4  idle│   USER         GPUs JOBS                  │
│ ◐ gpu10    ██░░░░░░  2/8 mixed│  ►you            16    3  ████░░░░  13%   │
│ ● gpu11    ████████  4/4 alloc│   alice          12    2  ███░░░░░  10%   │
│ ● gpu12    ██████░░  6/8 mixed│   bob            24    4  ██████░░  20%   │
│ ● gpu13    ████████  8/8 alloc│   charlie         8    2  ██░░░░░░   6%   │
│ ● gpu14    ████░░░░  4/8 mixed│   diana          16    3  ████░░░░  13%   │
│ ✗ gpu15    --------  0/4 drain│   eve             8    1  ██░░░░░░   6%   │
│ ● gpu16    ██████░░  6/8 mixed│   frank           3    1  █░░░░░░░   2%   │
│                               │                                           │
├── ALL GPUs ───────────────────┴───────────────────────────────────────────┤
│                                                                           │
│  gpu01    ██████░░ 82%  █████░░░ 70%  ███████░ 91%  ██████░░ 78%    5/8   │
│  gpu02    ████████ 95%  ███████░ 88%  ████████ 92%  ████████ 97%    8/8   │
│  gpu03    ░░░░░░░░  1%  ░░░░░░░░  0%  ░░░░░░░░  2%  ░░░░░░░░  0%    0/8   │
│  ...                                                                      │
│                                                                           │
├── MY JOBS ────────────────────────────────────────────────────────────────┤
│                                                                           │
│ ◈ MY JOBS  jobs:3  gpus:16                                                │
│ ID         NAME                  ST       TIME GPU NODE         PART       │
│ 1000042    train-llama          RUN   12:34:56   8 gpu02       batch       │
│ 1000051    finetune-vit         RUN    3:21:00   4 gpu14       short       │
│ 1000067    eval-bert            RUN    0:45:12   4 gpu11       batch       │
│                                                                           │
├───────────────────────────────────────────────────────────────────────────┤
│  q Quit   r Refresh   d Demo                                              │
└───────────────────────────────────────────────────────────────────────────┘
```

## Installation

```bash
uv sync
```

## Usage

First, install the package:

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
