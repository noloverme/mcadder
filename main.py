#!/usr/bin/env python3
"""
MC Adder
Добавляет или удаляет серверы Minecraft в servers.dat.
"""

import os
import shutil
import sys
from pathlib import Path
import nbtlib
from nbtlib import tag

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")
# ANSI escape codes for colors
class Color:
    WHITE = '\033[97m'
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    RESET = '\033[0m'

def print_color(text, color):
    """Prints text in a given color."""
    print(f"{color}{text}{Color.RESET}")

def clear_screen():
    """Clears the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')

def select_minecraft_directory():
    """Displays a menu to select the Minecraft directory."""
    if sys.platform == "win32":
        appdata_str = os.getenv("APPDATA")
        appdata = Path(appdata_str) if appdata_str else Path.home() / "AppData" / "Roaming"
        paths = {
            "1": appdata / ".minecraft",
            "2": appdata / ".tlauncher" / "legacy" / "Minecraft" / "game",
            "3": appdata / "CCBlueX" / "LiquidLauncher" / "data" / "gameDir" / "nextgen",
        }
    elif sys.platform == "darwin":
        home = Path.home()
        paths = {
            "1": home / "Library" / "Application Support" / "minecraft",
            "2": home / ".tlauncher" / "legacy" / "Minecraft" / "game",
            "3": home / "Library" / "Application Support" / "CCBlueX" / "LiquidLauncher" / "data" / "gameDir" / "nextgen",
        }
    else:  # Linux
        home = Path.home()
        paths = {
            "1": home / ".minecraft",
            "2": home / ".tlauncher" / "legacy" / "Minecraft" / "game",
            "3": home / ".config" / "CCBlueX" / "LiquidLauncher" / "data" / "gameDir" / "nextgen",
        }

    while True:
        clear_screen()
        print_color("Выберите директорию Minecraft:", Color.WHITE)
        print_color("[1] Minecraft (.minecraft)", Color.GREEN)
        print_color("[2] Legacy Launcher (.tlauncher/legacy/Minecraft/game)", Color.GREEN)
        print_color("[3] LiquidBounce (CCBlueX/LiquidLauncher/...)", Color.GREEN)
        print_color("[4] Своя (указать вручную)", Color.RED)
        
        try:
            choice = input(f"{Color.YELLOW}[] Ваш выбор: {Color.RESET}").strip()
            if choice in paths:
                return paths[choice]
            elif choice == "4":
                clear_screen()
                custom_path_str = input(f"{Color.YELLOW}Укажите путь к папке игры: {Color.RESET}").strip()
                custom_path = Path(custom_path_str)
                if custom_path.is_dir():
                    return custom_path
                else:
                    print_color("Ошибка: Указанный путь не существует или не является директорией.", Color.RED)
                    input("Нажмите Enter для продолжения...")
            else:
                print_color("Неверный выбор. Пожалуйста, выберите от 1 до 4.", Color.RED)
                input("Нажмите Enter для продолжения...")
        except (KeyboardInterrupt, EOFError):
            print_color("\nВыход.", Color.RED)
            sys.exit(0)

def get_server_lines():
    """Asks user for server list file and returns the lines."""
    default_path = Path("localips.txt")
    while True:
        clear_screen()
        print_color("Выбор файла со списком серверов:", Color.WHITE)
        print_color(f"[1] Использовать {default_path.name}", Color.GREEN)
        print_color("[2] Указать другой файл", Color.GREEN)
        try:
            choice = input(f"{Color.YELLOW}[] Ваш выбор [1]: {Color.RESET}").strip()
            if choice in ("1", ""):
                file_path = default_path
            elif choice == "2":
                custom_path_str = input(f"{Color.YELLOW}Укажите путь к файлу: {Color.RESET}").strip()
                file_path = Path(custom_path_str)
            else:
                print_color("Неверный выбор. Введите 1 или 2.", Color.RED)
                input("Нажмите Enter для продолжения...")
                continue

            if not file_path.is_file():
                print_color(f"[!] Файл '{file_path}' не найден.", Color.RED)
                input("Нажмите Enter для продолжения...")
                continue

            return file_path.read_text(encoding="utf-8").splitlines()
        except (KeyboardInterrupt, EOFError):
            print_color("\nВыход.", Color.RED)
            sys.exit(0)

def parse_line(line):
    s = line.strip()
    if not s or s.startswith("#"):
        return None
    if "|" in s:
        name, ip = s.split("|", 1)
        name, ip = name.strip(), ip.strip()
        if not ip:
            return None
        return (name if name else None, ip)
    return (None, s)

def load_or_create_servers_dat(path):
    if path.exists():
        try:
            nbt = nbtlib.load(path)
            if isinstance(nbt, nbtlib.File):
                data = nbt.root if hasattr(nbt, "root") else nbt
            else:
                data = nbt

            if "servers" not in data:
                data["servers"] = tag.List[tag.Compound]([])
            return nbt
        except Exception as e:
            raise RuntimeError(f"Ошибка при чтении {path}: {e}")
    else:
        root = tag.Compound()
        root["servers"] = tag.List[tag.Compound]([])
        return nbtlib.File(root)

def server_exists(servers_list, ip, name):
    ip_lower = ip.lower()
    for s in servers_list:
        s_ip = str(s.get("ip", "")).strip().lower()
        s_name = str(s.get("name", "")).strip()
        if s_ip == ip_lower or (name and s_name == name):
            return True
    return False

def make_entry(display_name, ip):
    comp = tag.Compound()
    comp["name"] = tag.String(display_name)
    comp["ip"] = tag.String(ip)
    return comp

def add_servers(minecraft_dir, servers_dat_path, lines):
    entries = [p for line in lines if (p := parse_line(line))]

    if not entries:
        print_color("[!] Нет строк для добавления.", Color.YELLOW)
        return

    minecraft_dir.mkdir(parents=True, exist_ok=True)

    if servers_dat_path.exists():
        backup_path = servers_dat_path.with_suffix(".dat.bak")
        try:
            shutil.copy2(servers_dat_path, backup_path)
            print_color(f"💾 Создан бэкап: {backup_path}", Color.WHITE)
        except Exception as e:
            print_color(f"⚠️ Не удалось создать бэкап: {e}", Color.YELLOW)

    nbt = load_or_create_servers_dat(servers_dat_path)
    data = nbt.root if hasattr(nbt, "root") else nbt
    servers = data["servers"]

    added = skipped = 0
    for name, ip in entries:
        display_name = name or ip
        if server_exists(servers, ip, display_name):
            skipped += 1
            continue
        servers.append(make_entry(display_name, ip))
        added += 1

    nbt.save(servers_dat_path)
    print_color(f"\n✅ Готово! Добавлено: {added}, пропущено: {skipped}", Color.GREEN)
    print_color(f"📁 Файл сохранён: {servers_dat_path}", Color.WHITE)

def remove_servers(servers_dat_path, lines):
    entries_to_remove = [p for line in lines if (p := parse_line(line))]

    if not entries_to_remove:
        print_color("[!] Нет серверов для удаления в файле.", Color.YELLOW)
        return

    if not servers_dat_path.exists():
        print_color(f"[!] Файл {servers_dat_path} не найден. Нечего удалять.", Color.RED)
        return

    backup_path = servers_dat_path.with_suffix(".dat.bak")
    try:
        shutil.copy2(servers_dat_path, backup_path)
        print_color(f"💾 Создан бэкап: {backup_path}", Color.WHITE)
    except Exception as e:
        print_color(f"⚠️ Не удалось создать бэкап: {e}", Color.YELLOW)

    nbt = load_or_create_servers_dat(servers_dat_path)
    data = nbt.root if hasattr(nbt, "root") else nbt
    servers = data["servers"]

    ips_to_remove = {ip.lower() for _, ip in entries_to_remove if ip}
    names_to_remove = {name.lower() for name, _ in entries_to_remove if name}

    initial_count = len(servers)
    servers_to_keep = []
    for s in servers:
        s_ip = str(s.get("ip", "")).strip().lower()
        s_name = str(s.get("name", "")).strip().lower()
        if s_ip in ips_to_remove or (s_name and s_name in names_to_remove):
            continue
        servers_to_keep.append(s)

    removed_count = initial_count - len(servers_to_keep)

    if removed_count > 0:
        data["servers"] = tag.List[tag.Compound](servers_to_keep)
        nbt.save(servers_dat_path)
        print_color(f"\n✅ Готово! Удалено: {removed_count}", Color.GREEN)
        print_color(f"📁 Файл сохранён: {servers_dat_path}", Color.WHITE)
    else:
        print_color("\n✅ Ничего не было удалено.", Color.YELLOW)

def clear_servers_dat(servers_dat_path):
    """Wipe servers.dat (with backup), keep empty list."""
    if servers_dat_path.exists():
        backup_path = servers_dat_path.with_suffix(".dat.bak")
        try:
            shutil.copy2(servers_dat_path, backup_path)
            print_color(f"💾 Создан бэкап: {backup_path}", Color.WHITE)
        except Exception as e:
            print_color(f"⚠️ Не удалось создать бэкап: {e}", Color.YELLOW)
    root = tag.Compound()
    root["servers"] = tag.List[tag.Compound]([])
    nbtlib.File(root).save(servers_dat_path)
    print_color("🧹 Список серверов очищен.", Color.YELLOW)


def run_scan_flow(minecraft_dir, servers_dat, lines):
    import asyncio
    import scanner as sc

    # --- range / concurrency settings ---
    clear_screen()
    print_color("Сканирование серверов (Java, порты 25000-26000):", Color.WHITE)
    print_color("Фаза 1: быстрый SLP-пинг всех host:port (жив ли)", Color.GREEN)
    print_color("Фаза 2: только живым -> пробный вход со случайным ником", Color.GREEN)
    print_color("   valid = зашли без кика | whitelist = кик 'not whitelisted' (отброс)", Color.WHITE)
    print_color("   warning = живой, но кик с другой причиной / online-mode", Color.WHITE)
    try:
        pr = input(f"{Color.YELLOW}[] Порты [25000-26000]: {Color.RESET}").strip()
        if pr:
            a, b = pr.replace(" ", "").split("-", 1)
            port_from, port_to = int(a), int(b)
        else:
            port_from, port_to = 25000, 26000
        conc_s = input(f"{Color.YELLOW}[] Параллельных пингов [1000]: {Color.RESET}").strip()
        concurrency = int(conc_s) if conc_s else 1000
        concurrency = max(50, min(concurrency, 3000))
        print_color("Прокси для подключений (пинг + вход):", Color.WHITE)
        print_color("[1] Без прокси (напрямую)", Color.GREEN)
        print_color("[2] Один прокси (http/socks4/socks5)", Color.GREEN)
        print_color("[3] Список прокси из файла", Color.GREEN)
        psel = (input(f"{Color.YELLOW}[] Прокси [1]: {Color.RESET}").strip() or "1")
        proxies = []
        if psel == "2":
            s = input(f"{Color.YELLOW}URL прокси (напр. socks5://127.0.0.1:1080, socks5://user:pass@host:1080, http://host:8080): {Color.RESET}").strip()
            try:
                proxies = [sc.parse_proxy(s)]
            except ValueError as e:
                print_color(f"[!] Bad proxy: {e}", Color.RED)
                input("Нажмите Enter для продолжения...")
                return
        elif psel == "3":
            ppath = input(f"{Color.YELLOW}Файл списка [proxies.txt]: {Color.RESET}").strip() or "proxies.txt"
            try:
                plines = Path(ppath).read_text(encoding="utf-8").splitlines()
            except Exception as e:
                print_color(f"[!] Не могу прочитать {ppath}: {e}", Color.RED)
                input("Нажмите Enter для продолжения...")
                return
            try:
                proxies = sc.load_proxies(plines)
            except ValueError as e:
                print_color(f"[!] Bad proxy в файле: {e}", Color.RED)
                input("Нажмите Enter для продолжения...")
                return
            if not proxies:
                print_color("[!] В файле нет прокси.", Color.RED)
                input("Нажмите Enter для продолжения...")
                return
        elif psel != "1":
            print_color("Неверный выбор прокси, иду напрямую.", Color.YELLOW)
    except (ValueError, KeyboardInterrupt, EOFError):
        print_color("\nВыход.", Color.RED)
        return

    targets = sc.build_targets_from_lines(lines, port_from, port_to)
    if not targets:
        print_color("[!] Нет целей для сканирования.", Color.YELLOW)
        input("Нажмите Enter для продолжения...")
        return

    # --- check proxies before the long scan (dead ones are dropped) ---
    pool = None
    if proxies:
        print_color(f"Проверка {len(proxies)} прокси (туннель до {targets[0][0]}:{targets[0][1]})...",
                    Color.WHITE)
        try:
            alive_proxies = asyncio.run(sc.filter_working_proxies(
                proxies, targets[0][0], targets[0][1], timeout=6.0))
        except KeyboardInterrupt:
            print_color("\nВыход.", Color.RED)
            return
        print_color(f"Живых прокси: {len(alive_proxies)}/{len(proxies)}",
                    Color.GREEN if alive_proxies else Color.RED)
        if not alive_proxies:
            print_color("Все прокси мертвы, сканировать нечего.", Color.RED)
            input("Нажмите Enter для продолжения...")
            return
        pool = sc.ProxyPool(alive_proxies)

    print_color(f"\nЦелей: {len(targets)} ({len(set(h for h, _, _ in targets))} хостов x {port_to - port_from + 1} портов)", Color.WHITE)
    print_color("Пинг идёт быстро (RST закрытых портов), вход — только по живым. Ctrl+C для отмены.", Color.YELLOW)
    try:
        go = input(f"{Color.YELLOW}[] Начать? [Y/n]: {Color.RESET}").strip().lower()
        if go in ("n", "no", "нет"):
            return
    except (KeyboardInterrupt, EOFError):
        print_color("\nВыход.", Color.RED)
        return

    print_color("\nСканирую...", Color.WHITE)

    state = {"valid": 0, "warning": 0, "wl": 0}

    def on_progress(done, total, r):
        cat = r.get("category")
        if cat == "valid":
            state["valid"] += 1
        elif cat == "warning":
            state["warning"] += 1
        elif cat == "whitelisted":
            state["wl"] += 1
        if cat in ("valid", "warning"):
            print(f"\n[+] {r['host']}:{r['port']} -> {cat}: {r.get('reason','')[:120]}")
        if done == total:
            print(f"\nLOGIN [{done}/{total}] valid={state['valid']} warn={state['warning']} white={state['wl']}")

    try:
        results = asyncio.run(sc.scan_targets(
            targets, concurrency=concurrency, login_concurrency=80,
            status_timeout=2.5, login_timeout=8.0, on_progress=on_progress,
            proxies=pool
        ))
    except KeyboardInterrupt:
        print_color("\n\nПрервано пользователем. Частичных результатов нет (повторите для полного скана).", Color.RED)
        input("Нажмите Enter для продолжения...")
        return

    print()  # newline after progress line
    valid, warning, whitelisted, _ = sc.split_results(results)
    offline_n = len(targets) - len(results)
    if pool is not None:
        pok, pfail, pdead = pool.summary()
        print_color(f"Прокси: запросов {pok}, ошибок {pfail}, мертвых {pdead}", Color.WHITE)
    print_color(f"\n=== Итог: всего {len(targets)} | alive {len(results)} ===", Color.WHITE)
    print_color(f"Валидные (без кика): {len(valid)}", Color.GREEN)
    print_color(f"С предупреждениями (кик с другой причиной/online-mode): {len(warning)}", Color.YELLOW)
    print_color(f"Whitelist (отброшены): {len(whitelisted)}", Color.RED)
    print_color(f"Оффлайн: {offline_n}", Color.WHITE)

    for r in (valid[:10] + warning[:10]):
        print(f"  {r['category']:7} {r['host']}:{r['port']} ({r.get('version_name','')}) :: {r.get('reason','')[:130]}")
    if len(valid) + len(warning) > 20:
        print(f"  ... показано 20 из {len(valid)+len(warning)}")

    # save txt for inspection / reuse
    try:
        Path("scan_valid.txt").write_text("\n".join(sc.results_to_lines(valid)), encoding="utf-8")
        Path("scan_warning.txt").write_text("\n".join(sc.results_to_lines(warning)), encoding="utf-8")
        print_color("📝 Сохранено: scan_valid.txt, scan_warning.txt", Color.WHITE)
    except Exception as e:
        print_color(f"⚠️ Не удалось сохранить txt: {e}", Color.YELLOW)

    if not valid and not warning:
        print_color("Нечего добавлять.", Color.YELLOW)
        input("Нажмите Enter для продолжения...")
        return

    print_color("\nЧто сделать с результатом?", Color.WHITE)
    print_color("[1] Очистить свой список и добавить только валидные", Color.GREEN)
    print_color("[2] Добавить только валидные (не очищая)", Color.GREEN)
    print_color("[3] Добавить валидные + с предупреждениями", Color.YELLOW)
    print_color("[4] Ничего не делать", Color.RED)
    try:
        sel = input(f"{Color.YELLOW}[] Ваш выбор: {Color.RESET}").strip()
    except (KeyboardInterrupt, EOFError):
        return

    if sel == "1":
        clear_servers_dat(servers_dat)
        add_servers(minecraft_dir, servers_dat, sc.results_to_lines(valid))
    elif sel == "2":
        add_servers(minecraft_dir, servers_dat, sc.results_to_lines(valid))
    elif sel == "3":
        add_servers(minecraft_dir, servers_dat,
                    sc.results_to_lines(valid) + sc.results_to_lines(warning))
    else:
        print_color("Без изменений в servers.dat.", Color.WHITE)
        input("Нажмите Enter для продолжения...")


def main():
    # On Windows, enable ANSI escape codes
    if sys.platform == "win32":
        os.system("")

    minecraft_dir = select_minecraft_directory()
    servers_dat = minecraft_dir / "servers.dat"

    while True:
        clear_screen()
        print_color("Что нужно сделать?", Color.WHITE)
        print_color("[1] Добавить", Color.GREEN)
        print_color("[2] Удалить", Color.RED)
        print_color("[3] Сканировать (пинг 25000-26000 + вход) и добавить", Color.GREEN)

        try:
            choice = input(f"{Color.YELLOW}[] Ваш выбор: {Color.RESET}").lower().strip()
            if choice in ["1", "2", "3"]:
                break
            print_color("Неверный выбор. Пожалуйста, введите '1', '2' или '3'.", Color.RED)
            input("Нажмите Enter для продолжения...")
        except (KeyboardInterrupt, EOFError):
            print_color("\nВыход.", Color.RED)
            sys.exit(0)

    lines = get_server_lines()

    if choice == "1":
        add_servers(minecraft_dir, servers_dat, lines)
    elif choice == "2":
        remove_servers(servers_dat, lines)
    elif choice == "3":
        run_scan_flow(minecraft_dir, servers_dat, lines)

if __name__ == "__main__":
    main()
