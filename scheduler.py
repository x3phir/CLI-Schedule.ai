import time
from typing import Dict, List, Any
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, IntPrompt
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text
import pyfiglet

# Import dari file lokal
import data_manager # Asumsi file ini ada
from csp_solver import solve_csp, get_slot_index, get_time_from_index, CONSTANTS # Asumsi file ini ada dan sudah diupdate

# --- Konstanta & Inisialisasi ---
console = Console()
DAYS = CONSTANTS["DAYS"]
TIME_SLOTS = CONSTANTS["TIME_SLOTS"]
SLOT_DURATION = CONSTANTS["SLOT_DURATION"]

# Daftar Pilihan Constraint Global Default Waktu
GLOBAL_TIME_DEFAULTS = {
    'task_earliest_start': "Default Waktu Mulai Paling Awal (HH:MM)",
    'task_latest_end': "Default Waktu Selesai Paling Akhir (HH:MM)",
}

# Daftar Pilihan Constraint Global Lainnya (Berlaku untuk seluruh jadwal)
GLOBAL_CONSTRAINTS = {
    'global_max_unique_activities_per_day': "Maksimal Jenis Aktivitas Unik per Hari",
    'global_max_hours_per_day': "Maksimal Jam Total Aktivitas per Hari",
    'global_min_gap': "Jeda Minimum Antar Aktivitas (menit)",
    'global_max_low_priority_per_day': "Maksimal Aktivitas Prioritas Rendah (1/2) per Hari",
    'global_max_work_days': "Maksimal Hari Bekerja dalam Seminggu"
}

# --- Fungsi Utility Tampilan & Animasi ---

def show_welcome_screen():
    """Menampilkan layar selamat datang yang menarik dengan ASCII Art."""
    
    console.clear() 
    
    # --- 1. Teks ASCII Besar ---
    try:
        # Gunakan font 'slant' atau 'big' untuk tampilan tebal
        ascii_text = pyfiglet.figlet_format("SCHEDULE.AI", font="slant")
        console.print(f"[bold magenta]{ascii_text}[/bold magenta]", justify="center")
    except Exception:
        # Fallback jika pyfiglet gagal
        console.print(Text("SCHEDULE.AI", justify="center", style="bold huge red"))
        
    # 2. Judul Utama dalam Panel Besar
    welcome_panel = Panel(
        Text("🚀 SCHEDULER MAHASISWA 🚀", justify="center", style="bold white on #4CAF50"), # Hijau
        title="[bold yellow]✨ Selamat Datang di Schedule.ai[/bold yellow]",
        subtitle="[dim]CLI Scheduling Assistant untuk Work-Life Balance Anda[/dim]",
        border_style="cyan",
        width=80
    )
    console.print(welcome_panel, justify="center")
    
    console.print("\n" * 1) # Kurangi baris kosong agar tidak terlalu renggang
    
    # 3. Kotak Informasi Singkat
    info_text = Text()
    info_text.append("Sistem ini akan membantu Anda: ", style="bold")
    info_text.append("\n  ✅ Mengatur jadwal kuliah dan aktivitas (Fixed Schedule)")
    info_text.append("\n  🧠 Menyelesaikan penjadwalan menggunakan AI (CSP Backtracking)")
    info_text.append("\n  📊 Menganalisis Work-Life Balance Score Anda")
    info_text.append("\n\n")
    info_text.append("Siapkan Jadwal Fixed Anda dan Aktivitas yang Ingin Dicapai!", style="italic magenta")
    
    info_panel = Panel(
        info_text,
        title="[bold blue]📝 Bagaimana Ini Bekerja?[/bold blue]",
        border_style="blue",
        padding=(1, 4),
        width=80
    )
    console.print(info_panel, justify="center")

    # 4. Footer Animasi Ringan
    console.print("\n" * 1)
    console.print("[dim]Menginisialisasi modul...[/dim]")
    
    # Animasi Spinner Singkat
    with console.status(
        "[bold green]Memuat Data dari data.json...[/bold green]", 
        spinner="earth", 
        speed=1.5
    ) as status:
        time.sleep(1) 
        status.update("[bold yellow]Inisialisasi CSP Engine...[/bold yellow]")
        time.sleep(0.5)
        status.update("[bold cyan]Semua Sistem Siap! 🎯[/bold cyan]")
        time.sleep(0.5)

    console.print("\n[bold]Tekan [yellow]ENTER[/yellow] untuk menuju Menu Utama...[/bold]")
    Prompt.ask("") 
    clear_screen()

def show_spinner(text="Sedang memproses..."):
    """Menampilkan spinner Rich untuk animasi loading."""
    with console.status(f"[bold cyan]{text}[/cyan]", spinner="dots", speed=1.5):
        time.sleep(1.5) # Durasi minimum untuk animasi

def clear_screen():
    """Membersihkan layar terminal."""
    console.print("\n" * 5) # Cukup untuk simulasi clear di banyak terminal

# --- Fungsi Input Interaktif ---

def input_fixed_schedule(data: Dict):
    """Input Jadwal Kuliah/Fixed."""
    clear_screen()
    console.rule("[bold yellow] INPUT JADWAL TETAP (KULIAH/FIXED) [/bold yellow]")
    
    name = Prompt.ask("Nama Jadwal Tetap (cth: Kalkulus I)", default="Kuliah")
    day = Prompt.ask("Hari", choices=DAYS, default="Senin")
    start_time = Prompt.ask("Waktu Mulai (HH:MM, cth: 08:00)", default="08:00")
    end_time = Prompt.ask("Waktu Selesai (HH:MM, cth: 09:30)", default="09:30")
    
    try:
        start_slot = get_slot_index(start_time)
        end_slot = get_slot_index(end_time)
        if start_slot >= end_slot:
            raise ValueError
    except:
        console.print("[bold red]Waktu tidak valid! Pastikan format HH:MM dan Mulai < Selesai.[/bold red]")
        time.sleep(2)
        return
        
    data['fixed_schedule'].append({
        'name': name,
        'day': day,
        'start_time': start_time,
        'end_time': end_time,
        'is_locked': True # Jadwal fixed selalu terkunci
    })
    data_manager.save_data(data)
    console.print(f"[bold green]✅ Jadwal '{name}' berhasil ditambahkan.[/bold green]")
    Prompt.ask("Tekan [bold]ENTER[/bold] untuk melanjutkan...")

def input_activities(data: Dict):
    """Input Daftar Aktivitas yang Perlu Dijadwalkan."""
    clear_screen()
    console.rule("[bold yellow] INPUT AKTIVITAS (Kerkom, Olahraga, dll) [/bold yellow]")
    
    name = Prompt.ask("Nama Aktivitas (cth: Kerkom Alpro)", default="Kerkom")
    duration = IntPrompt.ask("Durasi (Jam)", default=2)
    
    # 1 (terendah) - 5 (tertinggi)
    priority = IntPrompt.ask("Prioritas (1=Rendah, 5=Tinggi)", choices=['1', '2', '3', '4', '5'], default=3)
    
    # Jumlah pengulangan per minggu (diasumsikan)
    count_per_week = IntPrompt.ask("Berapa kali per minggu aktivitas ini dilakukan?", default=1)
    
    for i in range(count_per_week):
        # Tambahkan ID unik untuk setiap instance
        data['activities'].append({
            'id': f"{name}_{i+1}_{int(time.time())}",
            'name': name,
            'duration': duration,
            'priority': priority
        })
        
    data_manager.save_data(data)
    console.print(f"[bold green]✅ Aktivitas '{name}' ({count_per_week}x) berhasil ditambahkan.[/bold green]")
    Prompt.ask("Tekan [bold]ENTER[/bold] untuk melanjutkan...")

def input_constraints(data: Dict) -> Dict:
    """Input Pilihan Constraints, dengan alur baru yang fokus pada pemilihan tugas."""
    clear_screen()
    console.rule("[bold magenta] PENGATURAN CONSTRAINTS (KENDALA) [/bold magenta]")
    
    current_constraints = {}
    
    # 1. BATASAN SPESIFIK PER-TUGAS (NEW FLOW)
    unique_activities = sorted(list(set(act['name'] for act in data.get('activities', []) or [])))

    if unique_activities:
        console.print("\n[bold cyan]1. BATASAN SPESIFIK PER-TUGAS[/bold cyan] (Earliest Start/Latest End)")
        
        while True:
            # Tampilkan daftar tugas untuk dipilih
            task_options = [f"{i+1}. {name}" for i, name in enumerate(unique_activities)]
            task_options.append(f"{len(unique_activities)+1}. Selesai Input Batasan Tugas")
            
            console.print(Panel("\n".join(task_options), title="[bold yellow]Pilih Tugas yang Ingin Diatur[/bold yellow]", border_style="yellow"))
            
            try:
                choice_index = IntPrompt.ask("Pilih nomor tugas atau 'Selesai'", choices=[str(i+1) for i in range(len(task_options))])
                
                if choice_index == len(unique_activities) + 1:
                    break # Selesai
                
                selected_task_name = unique_activities[choice_index - 1]
                
                # Inisialisasi entri batasan untuk tugas ini
                if selected_task_name not in current_constraints:
                    current_constraints[selected_task_name] = {}
                
                console.print(f"\n[bold magenta]Mengatur Batasan untuk: {selected_task_name}[/bold magenta]")
                
                constraint_type = Prompt.ask(
                    "Pilih Batasan", 
                    choices=['earliest_start', 'latest_end', 'kembali'], 
                    default='earliest_start'
                )

                if constraint_type == 'kembali':
                    continue

                desc = "Waktu Mulai Paling Awal (HH:MM)" if constraint_type == 'earliest_start' else "Waktu Selesai Paling Akhir (HH:MM)"
                
                # Dapatkan nilai sebelumnya jika ada
                current_val = current_constraints[selected_task_name].get(constraint_type, "08:00" if constraint_type == 'earliest_start' else "22:00")
                
                val = Prompt.ask(f" > Masukkan Waktu {desc} (Saat ini: {current_val})", default=current_val)
                
                current_constraints[selected_task_name][constraint_type] = val
                console.print(f"[bold green]✅ Batasan {constraint_type} '{val}' diterapkan pada {selected_task_name}.[/bold green]")
                
            except IndexError:
                console.print("[bold red]Pilihan tidak valid. Coba lagi.[/bold red]")
                time.sleep(1)
            except ValueError:
                console.print("[bold red]Input harus berupa angka.[/bold red]")
                time.sleep(1)
                
    else:
        console.print("[dim]Tidak ada aktivitas yang terdaftar. Lewati Batasan Per-Tugas.[/dim]")


    # 2. GLOBAL DEFAULT CONSTRAINTS (Menggunakan daftar baru GLOBAL_TIME_DEFAULTS)
    console.print("\n" * 2)
    console.print("[bold cyan]2. BATASAN GLOBAL DEFAULT WAKTU[/bold cyan] (Berlaku untuk tugas yang belum memiliki batasan spesifik)")
    for key, desc in GLOBAL_TIME_DEFAULTS.items():
        if Prompt.ask(f"Aktifkan: {desc}? [y/n]", choices=['y', 'n'], default='n') == 'y':
            val = Prompt.ask(f"  > Masukkan Waktu ({desc}) (HH:MM)", default="08:00" if 'start' in key else "22:00")
            current_constraints[key] = val


    # 3. GLOBAL CONSTRAINTS LAINNYA
    console.print("\n[bold cyan]3. BATASAN GLOBAL LAINNYA[/bold cyan] (Berlaku untuk seluruh jadwal)")
    for key, desc in GLOBAL_CONSTRAINTS.items():
        if Prompt.ask(f"Aktifkan: {desc}? [y/n]", choices=['y', 'n'], default='n') == 'y':
            # Logika Global Constraints yang sudah cukup baik (mengambil float/int)
            if 'jam' in desc.lower():
                 val = float(Prompt.ask(f"  > Masukkan Nilai ({desc}) (Jam/Angka)", default=8))
            elif 'menit' in desc.lower():
                 val = int(Prompt.ask(f"  > Masukkan Nilai ({desc}) (Menit/Angka)", default=30))
            else:
                 val = IntPrompt.ask(f"  > Masukkan Nilai ({desc}) (Angka)", default=1)
                 
            current_constraints[key] = val
            
    return current_constraints

# --- Fungsi Tampilan Output ---

def display_calendar(schedule: Dict):
    """Menampilkan jadwal dalam bentuk grid kalender mingguan."""
    clear_screen()
    console.rule("[bold green] 📅 JADWAL MINGGUAN TER-EFEKTIF [/bold green]")

    # Hitung total jam
    total_hours_per_activity: Dict[str, float] = {}
    total_slots_filled = 0
    
    for day_slots in schedule.values():
        for slot_data in day_slots.values():
            if slot_data:
                name = slot_data['name']
                is_fixed = slot_data.get('is_fixed', False)
                # Hanya hitung slot pertama jika durasi lebih dari 30 menit,
                # atau jika itu adalah jadwal fixed/locked yang mungkin sudah terdaftar.
                if slot_data.get('is_first_slot') or is_fixed or slot_data.get('is_locked'):
                    # Asumsi durasi untuk non-fixed/non-locked/non-first-slot adalah 30 menit
                    duration_minutes = SLOT_DURATION 
                    if slot_data.get('duration_slots'):
                         duration_minutes = slot_data['duration_slots'] * SLOT_DURATION
                    elif is_fixed or slot_data.get('is_locked'):
                         # Sulit mendapatkan durasi fixed/locked dari sini, tapi anggap 30 menit per slot
                         duration_minutes = SLOT_DURATION
                         
                    total_hours_per_activity[name] = total_hours_per_activity.get(name, 0.0) + (duration_minutes / 60)
                total_slots_filled += 1

    # Inisialisasi Tabel
    table = Table(title="Jadwal Mingguan (06:00 - 00:00)", show_lines=True, header_style="bold blue")
    table.add_column("Waktu")
    for day in DAYS:
        table.add_column(day, justify="center")

    # Isi Tabel per 30 Menit
    current_time_slots = TIME_SLOTS[::2] # Ambil per jam
    
    for i in range(0, len(TIME_SLOTS), 2):
        start_time = TIME_SLOTS[i]
        
        row_content = [f"[bold]{start_time}[/bold]"]
        
        # Periksa slot 30 menit (i dan i+1) untuk setiap hari
        for day in DAYS:
            slot_i = schedule[day].get(str(i))
            slot_i_plus_1 = schedule[day].get(str(i + 1))
            
            cell_content = ""
            
            # Jika ada aktivitas di jam penuh (slot i)
            if slot_i and slot_i.get("is_first_slot"):
                name = slot_i['name']
                style = "bold green" if not slot_i.get("is_fixed") else "bold yellow"
                lock_icon = " 🔒" if slot_i.get("is_locked") else ""
                
                # Cek durasi untuk merge cell (hanya visual, Rich tidak punya merge cell vertikal)
                # Kita hanya menampilkan nama di slot pertama.
                cell_content = f"[{style}]{name}{lock_icon}[/{style}]"
            
            # Jika ada aktivitas di menit ke-30 (slot i+1)
            elif slot_i_plus_1 and slot_i_plus_1.get("is_first_slot"):
                name = slot_i_plus_1['name']
                style = "bold green" if not slot_i_plus_1.get("is_fixed") else "bold yellow"
                lock_icon = " 🔒" if slot_i_plus_1.get("is_locked") else ""
                cell_content = f"[{style}]{name}{lock_icon}[/{style}] (30 menit)"

            row_content.append(cell_content)
            
        table.add_row(*row_content)

    console.print(table)
    display_stats(total_hours_per_activity, total_slots_filled)

def calculate_work_life_score(total_hours_per_activity: Dict[str, float]) -> float:
    """Menghitung Work-Life Balance Score (skor 0-100)."""
    
    # Asumsi Kategori
    # Work/Produktif: Kerkom, Kuliah (Fixed)
    # Life/Non-Produktif: Olahraga, Aktivitas Lain
    
    work_hours = sum(hours for name, hours in total_hours_per_activity.items() if 'kuliah' in name.lower() or 'kerkom' in name.lower() or 'belajar' in name.lower())
    life_hours = sum(hours for name, hours in total_hours_per_activity.items() if 'olahraga' in name.lower() or 'lain' in name.lower())

    total_scheduled_hours = work_hours + life_hours
    
    if total_scheduled_hours == 0:
        return 0.0
        
    # Rasio Ideal 60% Work, 40% Life (atau 1.5:1)
    # Skor 100 jika rasio Work/Life mendekati 1.5.
    
    if work_hours == 0 or life_hours == 0:
        # Jika salah satu 0, skor sangat rendah
        score = 20.0 * (work_hours > 0) * (life_hours > 0)
    else:
        # Semakin mendekati 1.5, semakin baik
        ratio = work_hours / life_hours
        distance_from_ideal = abs(ratio - 1.5)
        
        # Normalisasi ke skor 0-100
        # Batasi agar jarak 1.5 tetap mendapat skor tinggi
        score = max(0, 100 - (distance_from_ideal * 30))
        
    return min(100.0, max(0.0, score))


def display_stats(total_hours_per_activity: Dict[str, float], total_slots_filled: int):
    """Menampilkan statistik dan Work-Life Balance Score."""
    
    console.rule("[bold cyan] 📊 STATISTIK JADWAL & WORK-LIFE BALANCE [/bold cyan]")
    
    # Statistik Total Jam per Aktivitas
    stat_table = Table(show_header=True, header_style="bold magenta")
    stat_table.add_column("Aktivitas")
    stat_table.add_column("Total Jam", justify="right")
    
    for name, hours in sorted(total_hours_per_activity.items(), key=lambda item: item[1], reverse=True):
        stat_table.add_row(name, f"{hours:.1f} jam")
        
    console.print(stat_table)
    
    # Work-Life Balance Score
    score = calculate_work_life_score(total_hours_per_activity)
    score_text = f"[bold white on blue] {score:.1f} / 100 [/bold white on blue]"
    
    # Saran berdasarkan skor
    if score >= 80:
        advice = "[green]Balance score SANGAT BAIK! Jadwal Anda efisien dan seimbang.[/green]"
    elif score >= 50:
        advice = "[yellow]Balance score CUKUP. Pertimbangkan menambah waktu rekreasi atau mengurangi beban kerja.[/yellow]"
    else:
        advice = "[red]Balance score RENDAH. Anda mungkin terlalu fokus pada Work atau Life. Coba longgarkan constraints![/red]"
        
    console.print(Panel(
        f"[bold]WORK-LIFE BALANCE SCORE:[/bold] {score_text}\n\n{advice}",
        title="HASIL ANALISIS",
        border_style="cyan"
    ))
    
    console.print(f"\n[dim]Total Slot Terisi: {total_slots_filled * SLOT_DURATION / 60:.1f} jam dari {len(DAYS) * 18} jam potensial.[/dim]")

# --- Fungsi Penjadwalan & Edit Manual ---

def generate_schedule(data: Dict):
    """Mengumpulkan constraints dan memanggil CSP Solver."""
    
    if not data['fixed_schedule'] and not data['activities']:
        console.print("[bold red]❌ Gagal:[/bold red] Input jadwal fixed atau aktivitas terlebih dahulu!")
        Prompt.ask("Tekan [bold]ENTER[/bold] untuk kembali...")
        return
        
    constraints = input_constraints(data)
    
    show_spinner("Memecahkan Penjadwalan dengan CSP Backtracking...")
    
    # Catatan: Batasan per-tugas sudah tersimpan dalam `constraints` di bawah nama tugas
    new_schedule, status = solve_csp(data, constraints)
    
    if status == "SUCCESS":
        data['generated_schedule'] = new_schedule
        data_manager.save_data(data)
        display_calendar(new_schedule)
        Prompt.ask("Tekan [bold]ENTER[/bold] untuk kembali ke Menu Utama...")
    else:
        console.print(Panel(
            "[bold white on red] 💥 SOLUSI TIDAK DITEMUKAN 💥 [/bold white on red]",
            subtitle="Jadwal terlalu padat atau constraints terlalu ketat.",
            border_style="red"
        ))
        console.print("\n[yellow]Saran:[/yellow] Coba hilangkan beberapa constraint, kurangi durasi, atau tingkatkan prioritas aktivitas yang paling penting.")
        Prompt.ask("Tekan [bold]ENTER[/bold] untuk kembali ke Menu Utama...")

def edit_manual_schedule(data: Dict):
    """Memungkinkan user untuk mengedit dan mengunci slot jadwal."""
    
    if not data.get('generated_schedule'):
        console.print("[bold red]❌ Gagal:[/bold red] Jadwal belum pernah di-generate!")
        Prompt.ask("Tekan [bold]ENTER[/bold] untuk kembali...")
        return

    clear_screen()
    console.rule("[bold yellow] ✏️ EDIT MANUAL JADWAL [/bold yellow]")
    
    display_calendar(data['generated_schedule'])

    day = Prompt.ask("Pilih Hari yang ingin diedit", choices=DAYS, default="Senin")
    start_time = Prompt.ask("Waktu Mulai Slot (HH:MM, cth: 10:00)", default="10:00")
    
    try:
        start_slot_index = get_slot_index(start_time)
        if str(start_slot_index) not in data['generated_schedule'][day]:
            raise ValueError
    except:
        console.print("[bold red]Slot waktu tidak valid atau kosong.[/bold red]")
        Prompt.ask("Tekan [bold]ENTER[/bold] untuk kembali...")
        return
        
    slot_data = data['generated_schedule'][day][str(start_slot_index)]
    
    console.print(f"\n[bold]Aktivitas pada {day} {start_time}:[/bold] [cyan]{slot_data['name']}[/cyan]")
    
    action = Prompt.ask("Pilih Aksi", choices=['lock', 'unlock', 'remove', 'ganti_nama'], default='lock')
    
    if action == 'lock':
        slot_data['is_locked'] = True
        console.print("[bold green]✅ Slot berhasil DIKUNCI! Tidak akan diubah saat generate CSP berikutnya.[/bold green]")
    elif action == 'unlock':
        slot_data['is_locked'] = False
        console.print("[bold green]✅ Slot berhasil DIBUKA! Bisa diubah saat generate CSP berikutnya.[/bold green]")
    elif action == 'remove':
        # Menghapus slot aktivitas yang generated
        if not slot_data.get('is_fixed'):
            del data['generated_schedule'][day][str(start_slot_index)]
            console.print("[bold green]✅ Slot berhasil DIHAPUS.[/bold green]")
        else:
             console.print("[bold red]❌ Tidak bisa menghapus jadwal fixed (kuliah) dari sini.[/bold red]")
    elif action == 'ganti_nama':
         new_name = Prompt.ask("Nama Aktivitas Baru", default=slot_data['name'])
         slot_data['name'] = new_name
         console.print("[bold green]✅ Nama aktivitas berhasil diubah.[/bold green]")
         
    data_manager.save_data(data)
    Prompt.ask("Tekan [bold]ENTER[/bold] untuk melanjutkan...")

# --- Main Program ---

def main_menu():
    """Tampilan Menu Utama."""
    show_welcome_screen()
    # Asumsi data_manager.load_data() mengembalikan struktur data yang diperlukan
    data = data_manager.load_data() 
    
    while True:
        clear_screen()
        console.print(Panel(
            Text("SCHEDULER MAHASISWA AJAIB", justify="center", style="bold white on blue"),
            title="✨ SCHEDULE.AI ",
            border_style="yellow"
        ))
        
        menu_table = Table(title="Menu Utama", show_header=False)
        menu_table.add_column()
        menu_table.add_row("[bold]1.[/bold] Input Jadwal Tetap (Kuliah, dll) 📅")
        menu_table.add_row("[bold]2.[/bold] Input Aktivitas (Kerkom, Olahraga, dll) 📝")
        menu_table.add_row("[bold]3.[/bold] [green]GENERATE JADWAL (CSP)[/green] 🚀")
        menu_table.add_row("[bold]4.[/bold] Lihat Jadwal Terakhir 👀")
        menu_table.add_row("[bold]5.[/bold] Edit/Kunci Manual Jadwal 🔒")
        menu_table.add_row("[bold]6.[/bold] Reset Semua Data 🗑️")
        menu_table.add_row("[bold]7.[/bold] Keluar 🚪")
        
        console.print(menu_table)
        
        choice = Prompt.ask("Pilih Menu", choices=['1', '2', '3', '4', '5', '6', '7'], default='3')
        
        if choice == '1':
            input_fixed_schedule(data)
        elif choice == '2':
            input_activities(data)
        elif choice == '3':
            generate_schedule(data)
        elif choice == '4':
            if data.get('generated_schedule'):
                display_calendar(data['generated_schedule'])
            else:
                console.print("[bold red]❌ Jadwal belum pernah di-generate![/bold red]")
            Prompt.ask("Tekan [bold]ENTER[/bold] untuk kembali...")
        elif choice == '5':
            edit_manual_schedule(data)
        elif choice == '6':
            if Prompt.ask("❗❗ Yakin ingin mereset semua data?", choices=['ya', 'tidak'], default='tidak') == 'ya':
                data = data_manager.load_data() # Memuat ulang kosong
                data_manager.save_data(data)
                console.print("[bold green]✅ Semua data berhasil di-reset.[/bold green]")
            Prompt.ask("Tekan [bold]ENTER[/bold] untuk melanjutkan...")
        elif choice == '7':
            console.print(Panel(Text("Sampai jumpa! Semoga jadwalmu efektif. 🎉", justify="center"), border_style="red"))
            break

if __name__ == "__main__":
    main_menu()