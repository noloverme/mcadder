<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=12,24,35,42&height=240&section=header&text=MC%20Adder%20%26%20Scanner&fontSize=52&fontColor=ffffff&animation=fadeIn&desc=Высокоскоростной%20SLP-сканер%20и%20инжектор%20серверов%20в%20Minecraft%20servers.dat&descSize=19&descAlignY=72" width="100%" alt="MC Adder Header"/>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.8+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.8+"/>
  <img src="https://img.shields.io/badge/Minecraft-Java_Edition-5B8731?style=for-the-badge&logo=minecraft&logoColor=white" alt="Minecraft Java"/>
  <img src="https://img.shields.io/badge/AsyncIO-High_Speed-00ADD8?style=for-the-badge&logo=fastapi&logoColor=white" alt="AsyncIO Scanner"/>
  <img src="https://img.shields.io/badge/Proxy-HTTP_|_SOCKS4_|_SOCKS5-7C3AED?style=for-the-badge&logo=pfsense&logoColor=white" alt="Proxy Support"/>
  <img src="https://img.shields.io/badge/License-MIT-F59E0B?style=for-the-badge&logo=open-source-initiative&logoColor=white" alt="MIT License"/>
</p>

<p align="center">
  <b>Ультимативная консольная утилита для массового сканирования портов Minecraft (25000–26000), проверки авторизации игроков и моментального внедрения серверов в клиент игры.</b>
</p>

---

[⚡ Быстрый старт](#-быстрый-старт) • [✨ Возможности](#-ключевые-возможности) • [📡 Архитектура сканера](#-архитектура-сканера) • [🛡️ Прокси](#%EF%B8%8F-прокси-система) • [🎮 Поддерживаемые лаунчеры](#-поддерживаемые-лаунчеры) • [📋 Форматы файлов](#-форматы-файлов)

</div>

<br/>

## 🎯 О проекте

**MC Adder** решает сразу две ключевые задачи:
1. **Сверхбыстрое асинхронное сканирование**: сканирует диапазоны портов (`25000-26000` и любые кастомные) на тысячах хостов, выполняет двухфазную фильтрацию (SLP Status Ping + тестовый Login Handshake со случайным валидным ником) и определяет тип доступности (Valid / Whitelist / Warning / Offline).
2. **Менеджмент `servers.dat`**: пакетное добавление или удаление найденных узлов прямо в файл серверов Minecraft любого установленного лаунчера (Vanilla, TLauncher / Legacy Launcher, LiquidBounce или произвольный каталог) с автоматическим созданием резервных копий (`.dat.bak`).

---

## ✨ Ключевые возможности

<table>
  <tr>
    <td width="50%" valign="top">
      <h3 align="left">⚡ Высокопроизводительный сканер</h3>
      <ul>
        <li><b>Двухфазная архитектура</b>: быстрый SLP-пинг с конкарренси 1000+ потоков, затем детальный логин только по живым узлам.</li>
        <li><b>Тестовый Login Handshake</b>: эмуляция подключения клиента с генерацией валидного ника <code>PlayerXXXXXX</code>.</li>
        <li><b>Интеллектуальная фильтрация</b>: автоматическое распознавание и отсеивание Whitelist, определение Online-Mode и открытых серверов.</li>
        <li><b>Чистый Standard Library</b>: движок сканера и сетевых протоколов написан на чистом <code>asyncio</code> + <code>struct</code> без тяжелых зависимостей.</li>
      </ul>
    </td>
    <td width="50%" valign="top">
      <h3 align="left">🎮 Интеграция с Minecraft</h3>
      <ul>
        <li><b>Прямая запись в NBT</b>: безопасная работа с NBT-файлом <code>servers.dat</code> через библиотеку <code>nbtlib</code>.</li>
        <li><b>Автоопределение лаунчеров</b>: автоматический поиск путей под Windows, Linux и macOS.</li>
        <li><b>Защита от сбоев</b>: создание зеркального бэкапа <code>servers.dat.bak</code> перед любыми операциями записи.</li>
        <li><b>Анти-дубликаты</b>: автоматическая дедупликация серверов по IP и названию с регистронезависимым сравнением.</li>
      </ul>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <h3 align="left">🛡️ Прокси-пул (Rotator)</h3>
      <ul>
        <li><b>Все протоколы</b>: поддержка <code>socks5://</code>, <code>socks4://</code>, <code>socks4a://</code>, <code>http://</code> и <code>https://</code>.</li>
        <li><b>Авторизация</b>: поддержка приватных прокси с аутентификацией (<code>user:pass@host:port</code>).</li>
        <li><b>Пре-чек валидности</b>: параллельная проверка доступности туннелей перед запуском скана.</li>
        <li><b>Авто-ротация и ретраи</b>: round-robin балансировка и автоматический вывод из пула мертвых прокси после 30 ошибок.</li>
      </ul>
    </td>
    <td width="50%" valign="top">
      <h3 align="left">📋 Предустановленные базы</h3>
      <ul>
        <li><b>181 проверенный узел</b>: в репозитории уже сформирован готовый <code>localips.txt</code> со всеми активными серверами хостинга (серии <code>D</code>, <code>F</code>, <code>M</code>, <code>N</code>, <code>S</code>, <code>Z</code> и др.).</li>
        <li><b>Экспорт результатов</b>: сохранение рабочих целей в <code>scan_valid.txt</code> и <code>scan_warning.txt</code> для повторного использования.</li>
      </ul>
    </td>
  </tr>
</table>

---

## 📡 Архитектура сканера

Процесс сканирования разделен на два независимых конвейера для обеспечения максимальной скорости и минимальной нагрузки на сеть:

```mermaid
flowchart TD
    A["📄 localips.txt / Хосты"] --> B["🌐 Пул прокси (HTTP / SOCKS4 / SOCKS5)"]
    B --> C["⚡ Фаза 1: SLP Ping (25000-26000)"]
    C -- "RST / Timeout" --> D["💀 Offline (Отброшено)"]
    C -- "Ответ SLP (MOTD / Protocol)" --> E["Живой сервер"]
    E --> F["🔑 Фаза 2: Login Handshake (PlayerXXXXXX)"]
    F -- "Login Success" --> G["🟢 VALID (Готов к игре)"]
    F -- "Kick: whitelist" --> H["🔴 WHITELIST (Отброшено)"]
    F -- "Online-Mode / Custom Kick" --> I["🟡 WARNING (С предупреждением)"]
    G --> J["💾 Запись в servers.dat Minecraft"]
    I --> J
```

### 🏷️ Классификация результатов:
* <kbd>🟢 VALID</kbd> — сервер полностью доступен (Offline-mode / без кика), возвращает `Login Success`.
* <kbd>🟡 WARNING</kbd> — сервер отвечает на SLP, но кикает при входе (требует лицензию `online-mode: true`, бан-лист, кастомный антибот или специфичный протокол версии).
* <kbd>🔴 WHITELISTED</kbd> — сервер находится под белым списком (`You are not whitelisted`, `multiplayer.disconnect.not_whitelisted`). Автоматически отсеивается.
* <kbd>⚪ OFFLINE</kbd> — порт закрыт либо не отвечает на SLP-пакет.

---

## ⚡ Быстрый старт

### 1. Клонирование и установка зависимостей

```bash
# Клонируйте репозиторий
git clone https://github.com/noloverme/mcadder.git
cd mcadder

# Установите зависимости
pip install -r requirements.txt
```

### 2. Запуск программы

```bash
python main.py
```

---

## 🖥️ Интерактивное меню

При запуске скрипт проведет вас через удобный пошаговый мастер:

```text
==================================================
  Выберите директорию Minecraft:
  [1] Minecraft (.minecraft)
  [2] Legacy Launcher (.tlauncher/legacy/Minecraft/game)
  [3] LiquidBounce (CCBlueX/LiquidLauncher/...)
  [4] Своя (указать вручную)
==================================================

  Что нужно сделать?
  [1] Добавить серверы из файла
  [2] Удалить серверы из файла
  [3] Сканировать (пинг 25000-26000 + вход) и добавить

==================================================
```

---

## 🛡️ Прокси-система

Сканер может работать напрямую или через пул прокси с распределением нагрузки (round-robin) как для фазы SLP-пинга, так и для фазы авторизации.

### Поддерживаемые форматы:
Создайте файл `proxies.txt` рядом со скриптом:

```ini
# SOCKS5 без авторизации
socks5://127.0.0.1:9050

# SOCKS5 с логином и паролем
socks5://username:password@198.51.100.25:1080

# HTTP / HTTPS прокси
http://10.0.0.1:8080
http://admin:secret@10.0.0.2:3128

# SOCKS4 / SOCKS4a (с удаленным DNS)
socks4://192.168.1.50:1080
socks4a://192.168.1.51:1080

# Простой IP:PORT (автоматически определяется как SOCKS5)
185.220.101.5:1080
```

> [!TIP]
> Перед стартом сканирования утилита производит параллельный пре-чек всех прокси. Мертвые исключаются из ротации, а во время работы ведется телеметрия: `Прокси: запросов N, ошибок M, мертвых K`.

---

## 📋 Форматы файлов

### `localips.txt` (Список серверов/нод)
Каждая запись на новой строке. Строки с `#` игнорируются:

```text
# Имя сервера|IP/домен:порт
Hypixel|mc.hypixel.net
Local Test|127.0.0.1:25565

# Без указания порта (для пункта [3] сканер переберет 25000-26000)
D1|d1.joinserver.ru
F12|f12.joinserver.ru
M5|m5.joinserver.ru
```

### Экспорт сканирования:
По завершении сканирования создаются готовые списки:
* `scan_valid.txt` — только гарантированно открытые серверы;
* `scan_warning.txt` — серверы, ответившие на SLP, но требующие лицензию/спец-клиент.

---

## 🎮 Поддерживаемые лаунчеры

Утилита автоматически кросс-платформенно находит каталоги Minecraft:

| Платформа | Vanilla Client | Legacy / TLauncher | LiquidBounce |
|:---:|:---:|:---:|:---:|
| **Windows** | `%APPDATA%\.minecraft` | `%APPDATA%\.tlauncher\legacy\...` | `%APPDATA%\CCBlueX\LiquidLauncher\...` |
| **Linux** | `~/.minecraft` | `~/.tlauncher/legacy/...` | `~/.config/CCBlueX/LiquidLauncher/...` |
| **macOS** | `~/Library/Application Support/minecraft` | `~/.tlauncher/legacy/...` | `~/Library/Application Support/CCBlueX/...` |

---

## ⚙️ Структура проекта

```text
mcadder/
├── main.py              # Точка входа, CLI-интерфейс и NBT-модификатор
├── scanner.py           # Высокоскоростной асинхронный SLP & Login сканер
├── localips.txt         # База из 181 валидного узла joinserver.ru
├── requirements.txt     # Зависимости проекта (только nbtlib)
├── .gitignore           # Игнорирование кэша и бэкапов
├── README.md            # Документация проекта
└── LICENSE              # Лицензия MIT
```

---

<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=12,24,35,42&height=100&section=footer" width="100%" alt="Footer"/>

<sub>Разработано с ❤️ для Minecraft сообщества • MIT License</sub>

</div>
