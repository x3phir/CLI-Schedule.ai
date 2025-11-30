import json
from rich.console import Console

FILE_PATH = "data.json"
console = Console()

def load_data():
    """Memuat data jadwal dari file JSON."""
    try:
        with open(FILE_PATH, 'r') as f:
            data = json.load(f)
            # Pastikan kunci utama ada
            if "fixed_schedule" not in data:
                data["fixed_schedule"] = []
            if "activities" not in data:
                data["activities"] = []
            if "generated_schedule" not in data:
                data["generated_schedule"] = []
            return data
    except FileNotFoundError:
        return {
            "fixed_schedule": [],
            "activities": [],
            "generated_schedule": []
        }
    except json.JSONDecodeError:
        console.print("[bold red]ERROR:[/bold red] File data.json rusak. Memuat data kosong.")
        return {
            "fixed_schedule": [],
            "activities": [],
            "generated_schedule": []
        }

def save_data(data):
    """Menyimpan data jadwal ke file JSON."""
    try:
        with open(FILE_PATH, 'w') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        console.print(f"[bold red]ERROR:[/bold red] Gagal menyimpan data: {e}")

# Inisialisasi file saat program pertama kali dijalankan
if __name__ == '__main__':
    data = load_data()
    save_data(data)