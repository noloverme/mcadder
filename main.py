#!/usr/bin/env python3
"""
add_mc_servers_liquid.py
Добавляет или удаляет серверы из targets.txt в servers.dat.
"""

import os
import shutil
from pathlib import Path
import nbtlib
from nbtlib import tag
import sys
import requests

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
        appdata = Path(os.getenv("APPDATA"))
        paths = {
            "1": appdata / ".minecraft",
            "2": appdata / ".tlauncher" / "legacy" / "Minecraft" / "game",
            "3": appdata / "CCBlueX" / "LiquidLauncher" / "data" / "gameDir" / "nextgen",
        }
    else: # Assuming Linux/macOS
        home = Path.home()
        paths = {
            "1": home / ".minecraft",
            "2": home / ".tlauncher" / "legacy" / "Minecraft" / "game",
            "3": home / ".config" / "CCBlueX" / "LiquidLauncher" / "data" / "gameDir" / "nextgen",
        }


    while True:
        clear_screen()
        print_color("Выберите директорию Minecraft:", Color.WHITE)
        print_color("[1] Minecraft (%appdata%/.minecraft)", Color.GREEN)
        print_color("[2] Legacy Launcher (%appdata%/.tlauncher\\legacy\\Minecraft\\game)", Color.GREEN)
        print_color("[3] LiquidBounce (%appdata%/CCBlueX/LiquidLauncher/data/gameDir/nextgen)", Color.GREEN)
        print_color("[4] Своя (указать)", Color.RED)
        
        try:
            choice = input(f"{Color.YELLOW}[] Ваш выбор: {Color.RESET}").strip()
            if choice in paths:
                return paths[choice]
            elif choice == "4":
                clear_screen()
                custom_path_str = input(f"{Color.YELLOW}Укажите путь: {Color.RESET}").strip()
                custom_path = Path(custom_path_str)
                if custom_path.is_dir():
                    return custom_path
                else:
                    print_color("Ошибка: Указанный путь не существует или не является директорией.", Color.RED)
            else:
                print_color("Неверный выбор. Пожалуйста, выберите от 1 до 4.", Color.RED)
        except (KeyboardInterrupt, EOFError):
            print_color("\nВыход.", Color.RED)
            sys.exit(0)

def get_server_lines():
    """Asks user for server list source and returns the lines."""
    while True:
        clear_screen()
        print_color("Откуда брать список серверов?", Color.WHITE)
        print_color("[1] Локальный файл (localips.txt)", Color.GREEN)
        print_color("[2] Скачать актуальные данные", Color.GREEN)
        try:
            source_choice = input(f"{Color.YELLOW}[] Ваш выбор: {Color.RESET}").strip()
            if source_choice == "1":
                targets_path = Path("localips.txt")
                if not targets_path.exists():
                    print_color(f"[!] Не найден файл {targets_path}. Создай его рядом со скриптом.", Color.RED)
                    input("Нажмите Enter для продолжения...")
                    continue
                return targets_path.read_text(encoding="utf-8").splitlines()
            elif source_choice == "2":
                TARGETS_URL = "http://hm.aquatime.life/targets.txt"
                try:
                    print_color("Скачивание актуальных данных...", Color.YELLOW)
                    response = requests.get(TARGETS_URL, timeout=10)
                    response.raise_for_status()
                    return response.text.splitlines()
                except requests.exceptions.RequestException as e:
                    print_color(f"Не удалось скачать список серверов: {e}", Color.RED)
                    input("Нажмите Enter для продолжения...")
                    continue
            else:
                print_color("Неверный выбор. Пожалуйста, введите '1' или '2'.", Color.RED)
                input("Нажмите Enter для продолжения...")
        except (KeyboardInterrupt, EOFError):
            print_color("\nВыход.", Color.RED)
            sys.exit(0)

def parse_line(line):
    s = line.strip()
    if not s or s.startswith("#"):
        return None
    if "|" in s:
        name, ip = s.split("|", 1)
        return (name.strip(), ip.strip())
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
                data["servers"] = tag.List([], tag.Compound)
            return nbt
        except Exception as e:
            raise RuntimeError(f"Ошибка при чтении {path}: {e}")
    else:
        root = tag.Compound()
        root["servers"] = tag.List([], tag.Compound)
        return nbtlib.File(root)

def server_exists(servers_list, ip, name):
    for s in servers_list:
        if s.get("ip") == ip or (name and s.get("name") == name):
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
        servers_dat_path.with_suffix(".dat.bak")

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

    servers_dat_path.with_suffix(".dat.bak")

    nbt = load_or_create_servers_dat(servers_dat_path)
    data = nbt.root if hasattr(nbt, "root") else nbt
    servers = data["servers"]

    ips_to_remove = {ip for _, ip in entries_to_remove}
    
    initial_count = len(servers)
    servers_to_keep = [s for s in servers if str(s.get("ip", "")) not in ips_to_remove]
    
    removed_count = initial_count - len(servers_to_keep)

    if removed_count > 0:
        data["servers"] = tag.List[tag.Compound](servers_to_keep)
        nbt.save(servers_dat_path)
        print_color(f"\n✅ Готово! Удалено: {removed_count}", Color.GREEN)
        print_color(f"📁 Файл сохранён: {servers_dat_path}", Color.WHITE)
    else:
        print_color("\n✅ Ничего не было удалено.", Color.YELLOW)

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
        
        try:
            choice = input(f"{Color.YELLOW}[] Ваш выбор: {Color.RESET}").lower().strip()
            if choice in ["1", "2"]:
                break
            print_color("Неверный выбор. Пожалуйста, введите '1' или '2'.", Color.RED)
        except (KeyboardInterrupt, EOFError):
            print_color("\nВыход.", Color.RED)
            sys.exit(0)

    lines = get_server_lines()

    if choice == "1":
        add_servers(minecraft_dir, servers_dat, lines)
    elif choice == "2":
        remove_servers(servers_dat, lines)

if __name__ == "__main__":
    main()
