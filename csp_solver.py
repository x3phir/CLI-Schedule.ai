from typing import List, Dict, Tuple, Any, Optional
import math

# --- Constants ---
DAYS = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat"]
START_HOUR = 6  # 06:00
END_HOUR = 24  # 24:00
SLOT_DURATION = 30  # minutes per slot
SLOTS_PER_DAY = ((END_HOUR - START_HOUR) * 60) // SLOT_DURATION
TIME_SLOTS = [f"{h:02d}:{m:02d}" for h in range(START_HOUR, END_HOUR) for m in range(0, 60, SLOT_DURATION)]

# --- Helpers ---
def get_slot_index(time_str: str) -> int:
    """
    Konversi 'HH:MM' ke indeks slot (berbasis 0).
    Waktu di luar START_HOUR..END_HOUR dapat menghasilkan indeks negatif atau >SLOTS_PER_DAY.
    """
    try:
        h, m = map(int, time_str.split(':'))
        minutes_from_start = (h * 60 + m) - (START_HOUR * 60)
        return minutes_from_start // SLOT_DURATION
    except:
        return -100 # Default safe index

def get_time_from_index(index: int) -> str:
    """Konversi indeks slot kembali ke format waktu 'HH:MM'."""
    minutes_from_start = index * SLOT_DURATION
    total_minutes = (START_HOUR * 60) + minutes_from_start
    h = (total_minutes // 60) % 24
    m = total_minutes % 60
    return f"{h:02d}:{m:02d}"

# --- Normalization utilities ---
def normalize_generated_schedule(raw: Any) -> Dict[str, Dict[str, Dict]]:
    """
    Memastikan generated_schedule adalah dict yang di-key oleh nama hari dan key dalam adalah str(slot)->activity dict.
    Mengembalikan dict yang dinormalisasi dengan setiap hari yang ada.
    """
    normalized = {day: {} for day in DAYS}
    if not raw:
        return normalized

    if isinstance(raw, dict):
        for day in DAYS:
            day_slots = raw.get(day, {})
            if isinstance(day_slots, dict):
                for k, v in day_slots.items():
                    # Pastikan key slot adalah string
                    if str(k).isdigit():
                        normalized[day][str(k)] = v
            # Jika ada struktur lain yang tidak terduga, ini akan mengabaikannya

    # Juga menangani kasus di mana raw adalah daftar datar entri dengan bidang hari
    elif isinstance(raw, list):
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            day = entry.get('day')
            slot = entry.get('slot')
            act = entry.get('activity') or entry.get('act') or entry
            if day in normalized and slot is not None:
                normalized[day][str(int(slot))] = act

    return normalized

def get_current_day_stats(schedule: Dict[str, Dict[int, Any]], day: str) -> Tuple[int, Dict[str, float]]:
    """
    Menghitung jumlah aktivitas unik dan total jam per kategori untuk hari tertentu.
    Hanya menghitung aktivitas NON-FIXED.
    """
    unique_activities = set()
    category_hours = {}

    for slot, act in schedule[day].items():
        if not act or act.get('is_fixed'): # Abaikan fixed tasks
            continue
        
        name = act.get('name')
        category = act.get('category')
        
        # Hitung unik (asumsi semua slot dari satu aktivitas memiliki nama yang sama)
        if name:
            unique_activities.add(name)
        
        # Hitung jam per kategori (hanya hitung sekali per slot)
        if category:
            # Menggunakan duration_slots jika tersedia, jika tidak, hitung 1 slot
            duration = act.get('duration_slots', 1) * SLOT_DURATION / 60.0
            # Untuk menghindari penghitungan berulang per slot untuk durasi penuh,
            # hanya tambahkan durasi satu slot (0.5 jam)
            if act.get('is_first_slot') or not act.get('is_first_slot') and not act.get('duration_slots'):
                 category_hours[category] = category_hours.get(category, 0.0) + (SLOT_DURATION / 60.0)

    return len(unique_activities), category_hours

# --- Constraint checking ---
def is_valid(
    schedule: Dict[str, Dict[int, Any]],
    day: str,
    start_slot: int,
    activity: Dict,
    constraints: Dict,
    activities_indexed_by_name: Dict[str, Dict],
) -> bool:
    """
    Memeriksa apakah penempatan activity pada day dimulai di start_slot valid,
    mempertimbangkan batasan per-task, global, dan yang baru direfaktor.
    """
    duration_slots = max(1, int(activity['duration'] * 60) // SLOT_DURATION)
    end_slot = start_slot + duration_slots
    
    # 0. Batasan Durasi (Waktu)
    if end_slot > SLOTS_PER_DAY or start_slot < 0:
        return False

    # 1. Batasan Hari Bebas Wajib (Pilihan Baru 5)
    mandatory_day_off = constraints.get('global_mandatory_day_off')
    if mandatory_day_off and day == mandatory_day_off:
        # Jika bukan fixed task, tidak boleh dijadwalkan pada hari ini
        if not activity.get('is_fixed'):
            return False

    # 2. Tidak tumpang tindih dengan jadwal yang sudah ada
    for s in range(start_slot, end_slot):
        if s in schedule[day]:
            return False

    # 3. Time Blocking Global (Blok Waktu Terlarang) (Pilihan Baru 1)
    # Aktivitas (kecuali fixed) tidak boleh dijadwalkan jika tumpang tindih dengan blok terlarang
    forbidden_blocks = constraints.get('global_no_activity_blocks', [])
    for start_time, end_time in forbidden_blocks:
        block_start_slot = get_slot_index(start_time)
        block_end_slot = get_slot_index(end_time)
        
        # Cek jika ada tumpang tindih antara [start_slot, end_slot) dan [block_start_slot, block_end_slot)
        if start_slot < block_end_slot and end_slot > block_start_slot:
            return False # Aktivitas tumpang tindih dengan blok terlarang

    # 4. Global Min Gap (Jeda/Gap Minimum) (Pilihan Baru 3)
    # Memastikan ada gap minimum antara aktivitas yang baru dan aktivitas yang sudah ada (fixed/non-fixed)
    if constraints.get('global_min_gap') is not None:
        min_gap_minutes = int(constraints['global_min_gap'])
        min_gap_slots = max(1, math.ceil(min_gap_minutes / SLOT_DURATION))
        
        # Cek gap SEBELUM aktivitas dimulai
        for gap_i in range(1, min_gap_slots + 1):
            prev_slot = start_slot - gap_i
            # Jika ada slot yang ditempati (baik fixed atau terjadwal)
            if prev_slot in schedule[day] and schedule[day][prev_slot] is not None:
                return False

        # Cek gap SETELAH aktivitas berakhir (jika ada aktivitas segera setelahnya)
        for gap_i in range(0, min_gap_slots):
            next_slot = end_slot + gap_i
            if next_slot in schedule[day] and schedule[day][next_slot] is not None:
                return False

    # Dapatkan statistik hari ini (hanya hitungan aktivitas non-fixed)
    current_task_count, current_category_hours = get_current_day_stats(schedule, day)
    
    # 5. Global Max Tasks per Day (Pilihan Baru 2)
    # Maksimal jumlah aktivitas unik (non-fixed) yang dijadwalkan per hari
    if constraints.get('global_max_tasks_per_day') is not None:
        max_tasks = int(constraints['global_max_tasks_per_day'])
        
        # Jika aktivitas ini BELUM ada di jadwal hari ini, hitungannya bertambah 1
        is_new_task_for_day = activity['name'] not in [
            act.get('name') for slot, act in schedule[day].items() if act and not act.get('is_fixed')
        ]
        
        current_count_plus_one = current_task_count + (1 if is_new_task_for_day else 0)
        
        if current_count_plus_one > max_tasks:
            return False

    # 6. Global Max Hours per Category per Day (Pilihan Baru 4)
    # Batasan total jam per kategori (e.g., Belajar: max 4 jam)
    max_category_hours = constraints.get('global_max_hours_per_category_per_day', {})
    category = activity.get('category')
    
    if category and category in max_category_hours:
        max_limit = float(max_category_hours[category])
        activity_duration_hours = duration_slots * SLOT_DURATION / 60.0
        
        # Hitung total jam saat ini (current_category_hours dihitung per slot 0.5 jam)
        current_category_hours_for_cat = current_category_hours.get(category, 0.0)
        
        # Total baru = jam saat ini + durasi aktivitas baru
        new_total_hours = current_category_hours_for_cat + activity_duration_hours
        
        if new_total_hours > max_limit:
            return False

    # --- Sisa Batasan Lama (Task-based) ---
    # Logika diperbarui untuk memprioritaskan batasan per-task (keyed by name)
    act_name = activity.get('name')
    act_constraints = constraints.get(act_name, {}) if act_name else {}

    # Task-based earliest (Prioritas: Properti Aktivitas > Batasan Per-Task > Global Default)
    task_earliest = (
        activity.get('earliest_start') or 
        act_constraints.get('earliest_start') or 
        constraints.get('task_earliest_start')
    )
    if task_earliest:
        if start_slot < get_slot_index(task_earliest):
            return False

    # Task-based latest end (Prioritas: Properti Aktivitas > Batasan Per-Task > Global Default)
    task_latest_end = (
        activity.get('latest_end') or 
        act_constraints.get('latest_end') or 
        constraints.get('task_latest_end')
    )
    if task_latest_end:
        if end_slot > get_slot_index(task_latest_end):
            return False

    # Task 'after' constraints: activity must be after listed activities
    # (Logika ini tetap dipertahankan seperti sebelumnya, memeriksa di hari yang sama)
    after_list = activity.get('after') or []
    for prev_name in after_list:
        found_earlier = False
        for s, act in schedule[day].items():
            if isinstance(act, dict) and act.get('name') == prev_name:
                # Temukan akhir blok aktivitas sebelumnya
                block_end = s + 1
                while block_end in schedule[day] and schedule[day][block_end].get('name') == prev_name:
                    block_end += 1
                
                # Memastikan blok sebelumnya berakhir sebelum aktivitas ini dimulai
                if block_end <= start_slot:
                    found_earlier = True
                    break
        
        # Jika prev_name ada dalam daftar aktivitas, tapi tidak ditemukan lebih awal hari ini,
        # maka batasan 'after' dilanggar.
        if prev_name in activities_indexed_by_name and not found_earlier:
            return False

    return True

# --- Backtracking solver (Tidak Diubah) ---
def csp_backtracking(
    activities: List[Dict],
    initial_schedule: Dict[str, Dict[int, Any]],
    constraints: Dict,
    activities_indexed_by_name: Dict[str, Dict],
    activity_index: int = 0,
) -> Tuple[Dict[str, Dict[int, Any]], bool]:
    """Logika backtracking inti (menggunakan is_valid yang baru direfaktor)"""
    # shallow copy schedule map
    current_schedule = {d: s.copy() for d, s in initial_schedule.items()}

    # base case
    if activity_index >= len(activities):
        return current_schedule, True

    activity = activities[activity_index]
    duration_slots = max(1, int(activity['duration'] * 60) // SLOT_DURATION)

    # Cek apakah aktivitas ini sudah ditempatkan di jadwal awal (misalnya dari generated_schedule yang dikunci)
    is_already_placed = False
    for day in DAYS:
        for slot, act in current_schedule[day].items():
            if isinstance(act, dict) and act.get('name') == activity['name']:
                is_already_placed = True
                break
        if is_already_placed:
            break
            
    if is_already_placed and activity.get('is_locked', False):
         # Jika aktivitas sudah terkunci di jadwal awal, lanjutkan ke aktivitas berikutnya tanpa mencoba menjadwalkannya
        return csp_backtracking(activities, current_schedule, constraints, activities_indexed_by_name, activity_index + 1)


    # Coba setiap hari dan setiap slot mulai
    for day in DAYS:
        # Cek apakah hari ini adalah hari bebas wajib (untuk efisiensi)
        if constraints.get('global_mandatory_day_off') == day and not activity.get('is_fixed'):
            continue # Langsung lewati hari ini

        for start_slot in range(0, SLOTS_PER_DAY - duration_slots + 1):
            if is_valid(current_schedule, day, start_slot, activity, constraints, activities_indexed_by_name):
                # assign
                new_schedule = {d: s.copy() for d, s in current_schedule.items()}
                for s in range(start_slot, start_slot + duration_slots):
                    new_schedule[day][s] = {
                        'name': activity['name'],
                        'priority': activity.get('priority', 0),
                        'duration_slots': duration_slots,
                        'category': activity.get('category'),
                        'is_first_slot': s == start_slot,
                    }
                
                # recursion
                result_schedule, success = csp_backtracking(
                    activities, new_schedule, constraints, activities_indexed_by_name, activity_index + 1
                )
                if success:
                    return result_schedule, True
                # otherwise continue searching

    # Jika tidak bisa menempatkan aktivitas ini, lewati jika diizinkan
    if constraints.get('allow_skip_unplaceable', True):
        # Coba melewati aktivitas ini dan lanjutkan
        return csp_backtracking(
            activities, current_schedule, constraints, activities_indexed_by_name, activity_index + 1
        )

    return current_schedule, False

# --- Main solve function (Sedikit Diubah untuk Memasukkan is_fixed) ---
def solve_csp(data: Dict[str, Any], constraints: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
    """
    Fungsi utama. Mengembalikan (final_schedule, status) di mana final_schedule adalah dict: day -> {slot_str: act_dict}.
    """
    if 'activities' not in data:
        return {}, 'NO_ACTIVITIES'

    # Normalisasi generated_schedule
    data['generated_schedule'] = normalize_generated_schedule(data.get('generated_schedule'))

    # Build initial schedule and index activities by name
    initial_schedule: Dict[str, Dict[int, Any]] = {day: {} for day in DAYS}

    # 1. Masukkan Jadwal Tetap (Fixed Schedule)
    for fixed_act in data.get('fixed_schedule', []) or []:
        day = fixed_act.get('day')
        if day not in initial_schedule: continue
        
        start_slot = get_slot_index(fixed_act.get('start_time', '00:00'))
        end_slot = get_slot_index(fixed_act.get('end_time', '00:00'))
        
        start_slot = max(0, start_slot)
        end_slot = min(SLOTS_PER_DAY, end_slot)

        for s in range(start_slot, end_slot):
            initial_schedule[day][s] = {
                'name': fixed_act.get('name', 'FIXED'),
                'is_fixed': True,
                'category': fixed_act.get('category'),
                'is_first_slot': s == start_slot,
            }

    # 2. Masukkan Slot Generated yang Dikunci (Locked Generated Slots)
    for day, slots in (data.get('generated_schedule') or {}).items():
        if day not in initial_schedule: continue
        if not isinstance(slots, dict): continue

        for slot_str, act in slots.items():
            try:
                slot_int = int(slot_str)
            except Exception:
                continue

            if act and isinstance(act, dict) and act.get('is_locked'):
                # Pastikan slot yang dikunci tidak menimpa fixed
                if slot_int not in initial_schedule[day]:
                    initial_schedule[day][slot_int] = {**act, 'is_locked': True} # Tambahkan is_locked untuk consistency

    # Activities list and index
    activities_all: List[Dict] = data.get('activities', [])
    activities_indexed_by_name = {a['name']: a for a in activities_all}

    # Hapus aktivitas yang sudah terkunci dari daftar activities_to_schedule
    locked_activity_names = set()
    for day in DAYS:
        for slot, act in initial_schedule[day].items():
            if act and act.get('is_locked') and not act.get('is_fixed'):
                locked_activity_names.add(act.get('name'))

    activities_to_be_scheduled = [
        act for act in activities_all if act['name'] not in locked_activity_names
    ]

    # Tentukan max tasks to schedule
    max_tasks = constraints.get('max_tasks_to_schedule') or constraints.get('max_tasks')
    if max_tasks is None: max_tasks = len(activities_to_be_scheduled)
    try: max_tasks = int(max_tasks)
    except: max_tasks = len(activities_to_be_scheduled)

    # Urutkan aktivitas berdasarkan prioritas (desc)
    activities_sorted = sorted(
        activities_to_be_scheduled,
        key=lambda x: (x.get('priority', 0), -x.get('duration', 0)), # priority, then shorter duration first
        reverse=True,
    )

    # Batasi ke top-k
    activities_to_schedule = activities_sorted[:max_tasks]

    # Tambahkan kembali aktivitas yang terkunci ke awal list untuk memastikan mereka dipertimbangkan
    # Namun, karena logika csp_backtracking sudah mengabaikan yang terkunci, kita biarkan saja listnya
    # hanya berisi yang harus dijadwalkan.

    # Panggil backtracking
    final_schedule, success = csp_backtracking(
        activities_to_schedule, 
        initial_schedule, 
        constraints, 
        activities_indexed_by_name
    )

    # Konversi kunci slot ke str untuk output
    output = {day: {str(slot): act for slot, act in final_schedule[day].items()} for day in DAYS}
    
    if success:
        # Gabungkan dengan struktur generated_schedule asli untuk entri non-locked
        data['generated_schedule'] = data.get('generated_schedule') or {day: {} for day in DAYS}
        for day in DAYS:
            merged = {**data['generated_schedule'].get(day, {})}
            for slot, act in output[day].items():
                merged[str(slot)] = act
            output[day] = merged
        return output, 'SUCCESS'
    else:
        # Kembalikan initial_schedule jika gagal
        output_fail = {day: {str(slot): act for slot, act in initial_schedule[day].items()} for day in DAYS}
        return output_fail, 'FAILURE'

# --- Export (Updated for consistency) ---
CONSTANTS = {
    'DAYS': DAYS,
    'TIME_SLOTS': TIME_SLOTS,
    'SLOTS_PER_DAY': SLOTS_PER_DAY,
    'SLOT_DURATION': SLOT_DURATION,
    'get_time_from_index': get_time_from_index,
}