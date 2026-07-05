import psutil
from fastapi import FastAPI

app = FastAPI()


@app.get("/stats")
def stats():
    cpu_freq = psutil.cpu_freq()
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    temps = {}
    thermal = psutil.sensors_temperatures() if hasattr(psutil, "sensors_temperatures") else {}
    for name, entries in thermal.items():
        temps[name] = [{"label": e.label, "current": e.current} for e in entries]

    gpu = {}
    try:
        import subprocess

        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            parts = [p.strip() for p in result.stdout.strip().split(",")]
            gpu = {
                "name": parts[0],
                "temp_c": int(parts[1]),
                "util_percent": int(parts[2]),
                "memory_used_mb": int(parts[3]),
                "memory_total_mb": int(parts[4]),
            }
    except FileNotFoundError:
        pass

    return {
        "cpu": {
            "percent": psutil.cpu_percent(interval=1),
            "per_core": psutil.cpu_percent(interval=0, percpu=True),
            "cores": psutil.cpu_count(logical=False),
            "threads": psutil.cpu_count(logical=True),
            "freq_mhz": cpu_freq.current if cpu_freq else None,
        },
        "memory": {
            "total_gb": round(mem.total / 1e9, 1),
            "used_gb": round(mem.used / 1e9, 1),
            "percent": mem.percent,
        },
        "disk": {
            "total_gb": round(disk.total / 1e9, 1),
            "used_gb": round(disk.used / 1e9, 1),
            "percent": disk.percent,
        },
        "temps": temps,
        "gpu": gpu,
    }
