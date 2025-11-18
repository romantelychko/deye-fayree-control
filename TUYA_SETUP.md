# Інструкція з налаштування Tuya для Feyree зарядки

Для керування зарядкою Feyree через локальну мережу потрібно отримати `DEVICE_ID` та `LOCAL_KEY` з платформи Tuya.

⚠️ Важливо: Smart Life ≠ Tuya IoT Platform

**Якщо ви використовуєте додаток Smart Life:**
- Ваш акаунт в **Smart Life** (споживацький додаток) - це **ОКРЕМИЙ** акаунт
- **Tuya IoT Platform** (https://iot.tuya.com/) - це платформа для розробників з **ІНШИМ** акаунтом
- Вам потрібно **створити новий акаунт** на Tuya IoT Platform
- Потім **прив'язати** ваш Smart Life акаунт до Cloud Project через QR код
- Після прив'язки всі пристрої зі Smart Life будуть доступні в Cloud Project

### Крок 1: Налаштування Tuya IoT Platform

Потрібно

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

**Також зверніть увагу на `mapping`** - це DPS коди вашого пристрою:
- Якщо ви бачите `"18": {"code": "switch", "type": "Boolean"}` - це DPS для вмикання/вимикання
- Якщо ви бачите `"14": {"code": "work_mode", "type": "Enum"}` - це DPS для режиму роботи

Ці значення вже налаштовані за замовчуванням у `.env` файлі як:
```env
FEYREE_SWITCH_DPS=18
FEYREE_MODE_DPS=14
```

Якщо ваш пристрій має інші DPS коди, змініть їх у `.env` файлі.

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

Після отримання ключів, відкрийте `.env` файл і оновіть:

```env
FEYREE_DEVICE_ID=0000000000000000000000
FEYREE_LOCAL_KEY=a1b2c3d4e5f67890
FEYREE_VERSION=3.3
```

## Перевірка налаштування

Після налаштування, запустіть:

```bash
# Створення тимчасового віртуального оточення
python3 -m venv /tmp/deye-fayree-control-venv

# Активація віртуального оточення
source /tmp/deye-fayree-control-venv/bin/activate

# Встановлення пакетів
pip install -r requirements.txt

# Запустити скрипт
python main.py
```

Якщо все правильно, ви побачите:

```
2024-01-15 12:30:00 - INFO - Feyree зарядка: підключення до 172.16.32.48 (ID: 0000000000000000000000)
```

Якщо є помилки:
- Перевірте що IP адреса правильна
- Перевірте що DEVICE_ID та LOCAL_KEY правильні
- Спробуйте іншу версію протоколу (3.1, 3.3, 3.4)
- Переконайтесь що зарядка в тій самій мережі

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

- Офіційна документація Tuya: https://developer.tuya.com/
- tinytuya GitHub: https://github.com/jasonacox/tinytuya
- Спільнота Home Assistant Tuya: https://www.home-assistant.io/integrations/tuya/

## Альтернатива: Використання розумної розетки

Якщо локальне керування Feyree не працює, можна:

1. Підключити Feyree через розумну розетку (яка підтримує Tuya)
2. Керувати розеткою замість зарядки
3. Змінити в коді керування розеткою

Це простіший варіант, але менш гнучкий (не можна регулювати силу струму).

