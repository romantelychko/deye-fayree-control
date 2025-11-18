# Інструкція з налаштування Tuya для Feyree зарядки

Для керування зарядкою Feyree через локальну мережу потрібно отримати `DEVICE_ID` та `LOCAL_KEY` з платформи Tuya.

## Зміст

- [Важливо: Smart Life ≠ Tuya IoT Platform](#важливо-smart-life--tuya-iot-platform)
- [Крок 1: Налаштування Tuya IoT Platform](#крок-1-налаштування-tuya-iot-platform)
- [Крок 2: Створення тимчасового віртуального оточення](#крок-2-створення-тимчасового-віртуального-оточення)
- [Крок 3: Встановлення tinytuya](#крок-3-встановлення-tinytuya)
- [Крок 4: Запуск майстра налаштування](#крок-4-запуск-майстра-налаштування)
- [Крок 5: Знайти Device ID та Local Key](#крок-5-знайти-device-id-та-local-key)
  - [Розуміння DPS кодів](#розуміння-dps-кодів)
- [Крок 6: Очищення тимчасового оточення](#крок-6-очищення-тимчасового-оточення)
- [Налаштування .env файлу](#налаштування-env-файлу)
- [Перевірка налаштування](#перевірка-налаштування)
- [Усунення проблем](#усунення-проблем)
- [Додаткові ресурси](#додаткові-ресурси)
- [Альтернатива: Використання розумної розетки](#альтернатива-використання-розумної-розетки)

---

## Важливо: Smart Life ≠ Tuya IoT Platform

**Якщо ви використовуєте додаток Smart Life:**
- Ваш акаунт в **Smart Life** (споживацький додаток) - це **ОКРЕМИЙ** акаунт
- **Tuya IoT Platform** (https://iot.tuya.com/) - це платформа для розробників з **ІНШИМ** акаунтом
- Вам потрібно **створити новий акаунт** на Tuya IoT Platform
- Потім **прив'язати** ваш Smart Life акаунт до Cloud Project через QR код
- Після прив'язки всі пристрої зі Smart Life будуть доступні в Cloud Project

### Крок 1: Налаштування Tuya IoT Platform

1. **Створити обліковий запис на Tuya IoT Platform**
   - Перейдіть на https://iot.tuya.com/
   - Натисніть "Sign Up" і створіть **новий акаунт** (це НЕ той самий акаунт що в Smart Life!)
   - Або увійдіть через Google/GitHub

2. **Створити Cloud Project**
   - Виберіть "Cloud" → "Development"
   - Натисніть "Create Cloud Project"
   - Назва: наприклад "Home Automation"
   - Industry: "Smart Home" або "Charging Station"
   - Development Method: "Smart Home"
   - Data Center: "Central Europe Data Center"

3. **Обрати API сервіси**
   - Активуйте наступні API:
     - IoT Core
     - Authorization Token Management
   - Натиснути "Authorize"

4. **Отримати API ключі**
   - Перейдіть на вкладку "Overview"
   - Скопіюйте:
     - **Access ID/Client ID**
     - **Access Secret/Client Secret**

5. **Переконатись що Feyree вже в Smart Life**
   - Ваша зарядка Feyree вже має бути додана в додаток **Smart Life**
   - Перевірте що вона працює через додаток
   - Ви використовуєте існуючий акаунт Smart Life

6. **Прив'язати Smart Life акаунт до Cloud Project**
   - На IoT Platform: "Cloud" → "Development" → ваш проєкт
   - "Devices" → "Link App Account" → "Tuya App Account Authorization"
   - З'явиться **QR код**
   - Відкрийте **Smart Life** → "Me" (або "Профіль") → "Scan" (або іконка сканування)
   - Відскануйте QR код
   - Після цього всі ваші пристрої зі Smart Life з'являться в Cloud Project!

7. Скопіюйте **Device ID** пристрою Feyree

### Крок 2: Створення тимчасового віртуального оточення

Оскільки tinytuya потрібен тільки для одноразового отримання ключів, краще створити тимчасове віртуальне оточення:

```bash
# Створення тимчасового віртуального оточення
python3 -m venv /tmp/deye-fayree-control-venv

# Активація віртуального оточення
source /tmp/deye-fayree-control-venv/bin/activate
```

### Крок 3: Встановлення tinytuya

```bash
pip install tinytuya
```

### Крок 4: Запуск майстра налаштування

```bash
python -m tinytuya wizard
```

Введіть:
- API Key (**Access ID/Client ID**)
- API Secret (**Access Secret/Client Secret**)
- **Device ID** з вашого додатку (або wizard знайде автоматично)
- Region (наприклад: **eu** для Європи)

На запит **Download DP Name mappings** введіть Y (або Enter)
На запит **Poll local devices?** введіть **n**.

Wizard створить файл `devices.json` з усіма пристроями.

### Крок 5: Знайти Device ID та Local Key

У файлі `snapshot.json` (або `devices.json`) знайдіть ваш Feyree пристрій:

```json
{
  "devices": [
    {
      "name": "Feyree Charger",
      "id": "0000000000000000000000",
      "key": "a1b2c3d4e5f67890",
      "ip": "172.16.32.48",
      ...
    }
  ]
}
```

- `id` - це ваш **DEVICE_ID**
- `key` - це ваш **LOCAL_KEY**

### Розуміння DPS кодів

**DPS (Data Point System)** - це коди керування пристроєм Tuya. У файлі `devices.json` ви побачите секцію `mapping`:

```json
"mapping": {
  "18": {"code": "switch", "type": "Boolean"},
  "14": {"code": "work_mode", "type": "Enum"},
  "101": {"code": "charge_status", "type": "Enum"},
  "114": {"code": "current", "type": "Integer"},
  "123": {"code": "charge_start", "type": "Boolean"}
}
```

**Основні DPS коди для Feyree:**
- **DPS 18** (`switch`) - Головний перемикач ВВІМК/ВИМК
- **DPS 14** (`work_mode`) - Режим роботи (`charge_now`, `charge_pct`, тощо)
- **DPS 101** (`charge_status`) - Статус зарядки (`charing`, `finish`)
- **DPS 114** (`current`) - Поточна сила струму (A)
- **DPS 123** (`charge_start`) - Команда старту/зупинки зарядки
- **DPS 124** (`mode_status`) - Статус режиму (`CloseCharging`, тощо)

Ці значення вже налаштовані за замовчуванням у `.env.example`:
```env
FEYREE_SWITCH_DPS=18
FEYREE_MODE_DPS=14
FEYREE_CHARGE_NOW_MODE=charge_now
```

⚠️ **Важливо:** Якщо ваш пристрій має інші DPS коди, змініть їх у `.env` файлі відповідно до вашого `devices.json`.

### Крок 6: Очищення тимчасового оточення

Після отримання ключів, можна видалити тимчасове віртуальне оточення:

```bash
# Вийти з віртуального оточення
deactivate

# Видалити тимчасове оточення (опціонально)
rm -rf /tmp/deye-fayree-control-venv
```

Ключі вже отримані, tinytuya більше не потрібен для роботи системи.

## Налаштування .env файлу

Після отримання ключів, створіть `.env` файл з `.env.example` та оновіть:

```bash
# В директорії проекту
cp .env.example .env
nano .env  # або vim, gedit, тощо
```

Оновіть отримані параметри:

```env
# Параметри отримані через tinytuya wizard
FEYREE_IP=172.16.32.48                      # IP з devices.json або ваша IP
FEYREE_DEVICE_ID=0000000000000000000000    # "id" з devices.json
FEYREE_LOCAL_KEY=a1b2c3d4e5f67890          # "key" з devices.json
FEYREE_VERSION=3.3                          # "version" з devices.json (зазвичай 3.3)
```

Також не забудьте налаштувати параметри Deye інвертора:

```env
LOGGER_IP=172.16.32.50    # IP вашого Data Logger
LOGGER_SN=0000000000      # Серійний номер (10 цифр)
```

## Перевірка налаштування

Після налаштування `.env` файлу, запустіть систему:

```bash
# Через Makefile (рекомендовано)
make build
make up
make logs

# Або через Docker Compose
docker compose up -d
docker compose logs -f
```

Якщо все правильно налаштовано, ви побачите в логах:

```
INFO - Deye інвертор: Підключення УСПІШНЕ
INFO - Feyree зарядка: Підключення УСПІШНЕ
INFO - Всі пристрої підключені успішно. Запуск основного циклу...
```

Якщо є помилки підключення до Feyree:
- Перевірте що IP адреса правильна: `ping <FEYREE_IP>`
- Перевірте що DEVICE_ID та LOCAL_KEY правильні (отримані через wizard)
- Спробуйте іншу версію протоколу в `.env`: `FEYREE_VERSION=3.1` або `3.4`
- Переконайтесь що зарядка в тій самій локальній мережі
- Перевірте що зарядка увімкнена та підключена до WiFi

## Усунення проблем

### Помилка: "Device not found"

- Перевірте що пристрій увімкнено та підключено до WiFi
- Перевірте IP адресу: `ping 172.16.32.48`
- Перевірте що MAC адреса відповідає: `arp -a | grep 172.16.32.48`

### Помилка: "Decryption failed"

- Local Key неправильний - отримайте його знову через wizard
- Версія протоколу неправильна - спробуйте 3.1, 3.3 або 3.4

### Помилка: "Connection timeout"

- Пристрій може бути в сплячому режимі - спробуйте керувати через додаток спочатку
- Firewall блокує з'єднання - перевірте налаштування мережі
- Пристрій може бути в іншій підмережі

### Пристрій з'являється через wizard але не підключається

- Деякі пристрої Tuya не підтримують локальне керування (тільки через хмару)
- В такому випадку потрібно використовувати Cloud API (складніше)

## Додаткові ресурси

- **Офіційна документація Tuya:** https://developer.tuya.com/
- **tinytuya GitHub:** https://github.com/jasonacox/tinytuya
  - Детальна документація про роботу з Tuya пристроями
  - Приклади коду та troubleshooting
- **Tuya IoT Platform:** https://iot.tuya.com/
  - Керування Cloud Projects
  - Перегляд пристроїв та їх DPS кодів
- **Smart Life додаток:** (iOS/Android)
  - Первинне налаштування пристроїв
  - Перевірка підключення до WiFi

## Альтернатива: Використання розумної розетки

Якщо локальне керування Feyree не працює, можна:

1. Підключити Feyree через розумну розетку (яка підтримує Tuya)
2. Керувати розеткою замість зарядки
3. Змінити в коді керування розеткою

Це простіший варіант, але менш гнучкий (не можна регулювати силу струму).

