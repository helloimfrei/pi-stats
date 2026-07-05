# pi-stats

A terminal dashboard for monitoring a remote Linux PC from a Raspberry Pi. Displays CPU, RAM, GPU, and temperature stats with rolling 5-minute sparklines.

## Layout

- **server** — FastAPI app that exposes `/stats`, runs on the machine being monitored
- **tui** — Textual TUI that runs on the Pi (or any machine), polls the server every second

## Setup

### On the monitored machine (Linux PC)

Install server dependencies only:

```bash
uv sync --only-group server
uvicorn server:app --host 0.0.0.0 --port 8000
```

To run as a systemd user service:

```ini
# ~/.config/systemd/user/pi-stats.service
[Unit]
Description=pi-stats server
After=network.target

[Service]
WorkingDirectory=/path/to/pi-stats
ExecStart=/path/to/pi-stats/.venv/bin/python -m uvicorn server:app --host 0.0.0.0 --port 8000
Restart=on-failure

[Install]
WantedBy=default.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now pi-stats
loginctl enable-linger $USER
```

> **Note (Bazzite/immutable Fedora):** Use a user service (not system), and use the full real path `/var/home/user/...` rather than `/home/user/...`. Also allow mDNS through the firewall if you want `hostname.local` to resolve:
> ```bash
> sudo firewall-cmd --add-service=mdns --permanent && sudo firewall-cmd --reload
> ```

### On the Pi (TUI client)

```bash
uv sync
python tui.py http://<server-ip>:8000
```

The default URL is `http://bazzite.local:8000` — edit `SERVER_URL` in `tui.py` to change it.

## Stats

- CPU usage, frequency, core/thread count
- Per-core usage bars
- RAM usage
- GPU utilization and VRAM (via `nvidia-smi`)
- Temperatures: CPU (k10temp/coretemp), GPU, NVMe (highest composite), RAM (jc42)
- 5-minute rolling sparklines for CPU, RAM, GPU

## Requirements

- Python 3.12+
- [uv](https://github.com/astral-sh/uv)
