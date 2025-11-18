#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Система автоматичного керування зарядкою Feyree EV на основі стану батареї Deye інвертора.

Логіка роботи:
- Увімкнення зарядки (16A): якщо SOC >= пороговому значенню і немає помітного імпорту з мережі
- Вимикання зарядки: в усіх інших випадках
"""

import logging
import os
import sys
import time
from typing import Dict, Optional

import tinytuya
from dotenv import load_dotenv
from pysolarmanv5 import PySolarmanV5, V5FrameError, NoSocketAvailableError

# Завантаження конфігурації з .env файлу
load_dotenv()

# ============================================================
# Налаштування логування
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# ============================================================
# Завантаження конфігурації з ENV
# ============================================================

# Deye інвертор
LOGGER_IP = os.getenv("LOGGER_IP", "")
LOGGER_SN = int(os.getenv("LOGGER_SN", ""))
MB_SLAVE_ID = int(os.getenv("MB_SLAVE_ID", "1"))
LOGGER_PORT = int(os.getenv("LOGGER_PORT", "8899"))

# Feyree зарядка
FEYREE_IP = os.getenv("FEYREE_IP", "")
FEYREE_DEVICE_ID = os.getenv("FEYREE_DEVICE_ID", "")
FEYREE_LOCAL_KEY = os.getenv("FEYREE_LOCAL_KEY", "")
FEYREE_VERSION = os.getenv("FEYREE_VERSION", "3.3")

# Feyree DPS коди (Data Point System)
FEYREE_SWITCH_DPS = int(os.getenv("FEYREE_SWITCH_DPS", "18"))  # DPS для ВВІМК/ВИМК
FEYREE_MODE_DPS = int(os.getenv("FEYREE_MODE_DPS", "14"))  # DPS для режиму роботи
FEYREE_CHARGE_NOW_MODE = os.getenv(
    "FEYREE_CHARGE_NOW_MODE", "charge_now"
)  # Режим "заряджати зараз"
# DPS 123 - це ключова команда для старту зарядки (True = start, False = stop)
# DPS 101 - статус зарядки ("finish", "charing" [з опечаткою від Tuya])
# DPS 124 - статус режиму ("CloseCharging", тощо)

# Логіка керування
SOC_THRESHOLD = float(os.getenv("SOC_THRESHOLD", "90"))
GRID_IMPORT_THRESHOLD = float(os.getenv("GRID_IMPORT_THRESHOLD", "250"))
CHECK_INTERVAL_SEC = int(os.getenv("CHECK_INTERVAL_SEC", "120"))
CHARGING_CURRENT_A = int(os.getenv("CHARGING_CURRENT_A", "16"))

# Налаштування повторів та timeout
MAX_ATTEMPTS = int(os.getenv("MAX_ATTEMPTS", "5"))
RETRY_DELAY_SEC = float(os.getenv("RETRY_DELAY_SEC", "1.0"))
CONNECTION_TIMEOUT_SEC = int(os.getenv("CONNECTION_TIMEOUT_SEC", "15"))


# ============================================================
# Клас для роботи з Deye інвертором
# ============================================================


class DeyeInverter:
    """Клас для читання даних з Deye інвертора через Modbus."""

    def __init__(self):
        """Ініціалізація клієнта Deye інвертора."""
        self.client = None
        self._connect()
        logger.info(
            f"Deye інвертор: підключення до {LOGGER_IP}:{LOGGER_PORT} (SN: {LOGGER_SN})"
        )

    def _connect(self):
        """Створює нове з'єднання з інвертором."""
        self.client = PySolarmanV5(
            address=LOGGER_IP,
            serial=LOGGER_SN,
            port=LOGGER_PORT,
            mb_slave_id=MB_SLAVE_ID,
            socket_timeout=CONNECTION_TIMEOUT_SEC,
            verbose=False,
        )

    def reconnect(self):
        """Перепідключається до інвертора."""
        logger.warning("Спроба перепідключення до Deye інвертора...")
        try:
            if self.client:
                self.disconnect()
        except Exception:
            pass  # Ігноруємо помилки при закритті
        self._connect()
        logger.info("Перепідключення успішне")

    def read_registers(self, start: int, quantity: int) -> list[int]:
        """
        Зчитує діапазон Modbus-регістрів з повторними спробами.

        Args:
            start: Початкова адреса регістру
            quantity: Кількість регістрів для читання

        Returns:
            Список значень регістрів

        Raises:
            V5FrameError: Якщо всі спроби не вдалися
        """
        last_exc = None

        for attempt in range(MAX_ATTEMPTS):
            try:
                values = self.client.read_holding_registers(
                    register_addr=start, quantity=quantity
                )
                if len(values) != quantity:
                    raise V5FrameError(
                        f"Неочікувана довжина відповіді для регістрів {start}-{start+quantity-1}: "
                        f"{len(values)} != {quantity}"
                    )
                return values
            except NoSocketAvailableError as exc:
                # З'єднання закрите - намагаємося перепідключитись
                last_exc = exc
                if attempt < MAX_ATTEMPTS - 1:
                    logger.warning(
                        f"З'єднання закрите. Спроба {attempt + 1}/{MAX_ATTEMPTS} перепідключення..."
                    )
                    try:
                        self.reconnect()
                        time.sleep(RETRY_DELAY_SEC)
                    except Exception as reconnect_exc:
                        logger.error(f"Помилка перепідключення: {reconnect_exc}")
                        time.sleep(RETRY_DELAY_SEC)
            except V5FrameError as exc:
                last_exc = exc
                if attempt < MAX_ATTEMPTS - 1:
                    logger.warning(
                        f"Спроба {attempt + 1}/{MAX_ATTEMPTS} не вдалася: {exc}"
                    )
                    time.sleep(RETRY_DELAY_SEC)

        # Якщо всі спроби не вдалися
        logger.error(f"Не вдалося зчитати регістри після {MAX_ATTEMPTS} спроб")
        if last_exc:
            raise last_exc
        raise V5FrameError("Не вдалося зчитати регістри")

    @staticmethod
    def as_signed16(value: int) -> int:
        """Перетворює 16-бітне беззнакове значення у signed (для потужностей)."""
        return value - 0x10000 if value >= 0x8000 else value

    def get_battery_and_grid_state(self) -> Dict[str, float | str]:
        """
        Зчитує необхідні дані про батарею та мережу.

        Returns:
            Словник з ключами:
            - battery_soc_pct: Рівень заряду батареї (%)
            - grid_power_w: Потужність з/в мережі (W, позитивне = імпорт)
            - grid_direction: Напрямок потоку ("import", "export", "idle")
        """
        # Читаємо регістри 169-190 (169=grid power, 184=SOC)
        # Регістр 169: активна потужність мережі (W, signed)
        # Регістр 184: рівень заряду батареї (%)
        regs = self.read_registers(start=169, quantity=22)  # 169 to 190

        # Регістр 169: потужність мережі
        grid_power_w = float(self.as_signed16(regs[0]))

        # Регістр 184: SOC батареї (офсет 15 від початку 169)
        battery_soc_pct = float(regs[15])

        # Визначення напрямку потоку енергії мережі
        if grid_power_w > 10:
            grid_direction = "import"  # імпорт з мережі
        elif grid_power_w < -10:
            grid_direction = "export"  # експорт в мережу
        else:
            grid_direction = "idle"  # баланс

        return {
            "battery_soc_pct": battery_soc_pct,
            "grid_power_w": grid_power_w,
            "grid_direction": grid_direction,
        }

    def disconnect(self):
        """Закриває з'єднання з інвертором."""
        if hasattr(self.client, "disconnect"):
            self.client.disconnect()


# ============================================================
# Клас для керування зарядкою Feyree EV
# ============================================================


class FeyreeCharger:
    """Клас для керування зарядкою Feyree EV через Tuya протокол."""

    def __init__(self):
        """
        Ініціалізація зарядки Feyree.

        Raises:
            ValueError: Якщо не вказані DEVICE_ID або LOCAL_KEY
        """
        if not FEYREE_DEVICE_ID or FEYREE_DEVICE_ID == "your_device_id_here":
            raise ValueError(
                "FEYREE_DEVICE_ID не налаштовано! "
                "Встановіть Device ID в .env файлі. "
                "Використайте 'python -m tinytuya wizard' для отримання ключів."
            )

        if not FEYREE_LOCAL_KEY or FEYREE_LOCAL_KEY == "your_local_key_here":
            raise ValueError(
                "FEYREE_LOCAL_KEY не налаштовано! "
                "Встановіть Local Key в .env файлі. "
                "Використайте 'python -m tinytuya wizard' для отримання ключів."
            )

        # Ініціалізація Tuya пристрою
        self.device = tinytuya.OutletDevice(
            dev_id=FEYREE_DEVICE_ID,
            address=FEYREE_IP,
            local_key=FEYREE_LOCAL_KEY,
            version=FEYREE_VERSION,
        )
        self.device.set_socketTimeout(CONNECTION_TIMEOUT_SEC)

        self.current_state = None  # Кешуємо стан для уникнення зайвих перемикань

        logger.info(
            f"Feyree зарядка: підключення до {FEYREE_IP} (ID: {FEYREE_DEVICE_ID})"
        )

    def get_status(self) -> Optional[Dict]:
        """
        Отримує поточний стан зарядки.

        Returns:
            Словник зі станом пристрою або None у випадку помилки
        """
        try:
            status = self.device.status()
            return status
        except Exception as e:
            logger.error(f"Помилка отримання статусу Feyree: {e}")
            return None

    def turn_on(self, current_a: int = CHARGING_CURRENT_A) -> bool:
        """
        Увімкнює зарядку з заданим струмом.

        Args:
            current_a: Сила струму зарядки (Ампери)

        Returns:
            True якщо команда виконана успішно, False інакше
        """
        try:
            logger.info(f"Спроба увімкнути зарядку Feyree на {current_a}A")

            # Увімкнення перемикача
            switch_result = self.device.set_value(FEYREE_SWITCH_DPS, True)
            if not switch_result:
                logger.warning(
                    f"Не вдалося увімкнути перемикач (DPS {FEYREE_SWITCH_DPS})"
                )
                return False

            time.sleep(0.5)

            # Встановлення режиму charge_now (DPS 14 - це Enum: "charge_now", "charge_pct", etc.)
            self.device.set_value(FEYREE_MODE_DPS, FEYREE_CHARGE_NOW_MODE)  # type: ignore[arg-type]
            time.sleep(0.5)

            # Активація зарядки (DPS 123 = True - ключова команда для старту)
            self.device.set_value(123, True)
            time.sleep(0.5)

            # DPS 10 (додатковий параметр)
            self.device.set_value(10, 1)

            logger.info(f"Зарядка Feyree УВІМКНЕНА ({current_a}A)")
            self.current_state = True
            return True

        except Exception as e:
            logger.error(f"Помилка увімкнення зарядки Feyree: {e}")
            return False

    def turn_off(self) -> bool:
        """
        Вимикає зарядку.

        Returns:
            True якщо команда виконана успішно, False інакше
        """
        try:
            logger.info("Спроба вимкнути зарядку Feyree")

            # Зупинка зарядки (DPS 123 = False - ключова команда для зупинки)
            self.device.set_value(123, False)
            time.sleep(0.5)

            # Вимкнення головного перемикача (DPS 18 = switch)
            result = self.device.set_value(FEYREE_SWITCH_DPS, False)

            if result:
                logger.info("Зарядка Feyree ВИМКНЕНА")
                self.current_state = False
                return True
            else:
                logger.warning(f"Не вдалося вимкнути зарядку (DPS {FEYREE_SWITCH_DPS})")
                return False

        except Exception as e:
            logger.error(f"Помилка вимкнення зарядки Feyree: {e}")
            return False

    def display_device_status(self, status: Optional[Dict], prefix: str = ""):
        """
        Відображає детальну інформацію про стан пристрою.

        Args:
            status: Словник зі станом пристрою
            prefix: Префікс для логування (напр. "ДО" або "ПІСЛЯ")
        """
        if not status or "dps" not in status:
            logger.warning(f"{prefix} Статус недоступний")
            return

        dps = status.get("dps", {})

        logger.info(f"{prefix} Стан пристрою Feyree:")

        # Основні DPS коди
        switch_state = dps.get(str(FEYREE_SWITCH_DPS), None)
        work_mode = dps.get(str(FEYREE_MODE_DPS), None)
        work_state = dps.get("3", None)  # ВАЖЛИВО: це реальний стан зарядки!

        # Додаткові важливі коди зі snapshot.json
        charge_status = dps.get("101", None)  # finish/charging/тощо
        energy_kwh = dps.get("102", None)  # енергія в Втг
        current_a = dps.get("114", None)  # струм
        max_current = dps.get("115", None)  # макс струм
        charging_time = dps.get("120", None)  # час зарядки
        charge_mode_status = dps.get("124", None)  # статус режиму зарядки

        # Виводимо основну інформацію
        if work_state is not None:
            logger.info(f"  └─ DPS 3 (work_state): {work_state}")

        if switch_state is not None:
            logger.info(
                f"  └─ DPS {FEYREE_SWITCH_DPS} (switch): {'ВВІМК' if switch_state else 'ВИМК'}"
            )

        if work_mode is not None:
            logger.info(f"  └─ DPS {FEYREE_MODE_DPS} (work_mode): {work_mode}")

        if charge_status is not None:
            logger.info(f"  └─ DPS 101 (charge_status): {charge_status}")

        if charge_mode_status is not None:
            logger.info(f"  └─ DPS 124 (mode_status): {charge_mode_status}")

        if current_a is not None:
            logger.info(f"  └─ DPS 114 (current): {current_a}A")

        if max_current is not None:
            logger.info(f"  └─ DPS 115 (max_current): {max_current}A")

        if energy_kwh is not None:
            # Згідно з devices.json, scale=3, тому ділимо на 1000
            # DPS 102 повертає integer, конвертуємо в float
            energy_display: float = float(energy_kwh) / 1000.0
            logger.info(f"  └─ DPS 102 (energy): {energy_display:.3f} kWh")

        if charging_time is not None:
            logger.info(f"  └─ DPS 120 (time): {charging_time}")

    def should_charge(
        self, battery_soc: float, grid_power: float, grid_direction: str
    ) -> bool:
        """
        Визначає чи потрібно вмикати зарядку на основі поточного стану.

        Логіка: Зарядка увімкнена якщо:
        - Батарея заряджена >= SOC_THRESHOLD (за замовчуванням 90%)
        - ТА немає помітного імпорту з мережі:
          - АБО напрямок != "import"
          - АБО потужність імпорту < GRID_IMPORT_THRESHOLD (за замовчуванням 250W)

        Args:
            battery_soc: Рівень заряду батареї (%)
            grid_power: Потужність мережі (W)
            grid_direction: Напрямок потоку енергії

        Returns:
            True якщо потрібно заряджати, False інакше
        """
        # Умова 1: Батарея достатньо заряджена
        soc_ok = battery_soc >= SOC_THRESHOLD

        # Умова 2: Немає помітного імпорту з мережі
        grid_ok = (grid_direction != "import") or (grid_power < GRID_IMPORT_THRESHOLD)

        return soc_ok and grid_ok


# ============================================================
# Основна логіка керування
# ============================================================


def control_loop() -> None:
    """
    Основний цикл керування зарядкою EV.

    Безкінечний цикл, що:
    1. Зчитує стан батареї та мережі з Deye інвертора
    2. Приймає рішення про увімкнення/вимкнення зарядки
    3. Отримує поточний стан Feyree перед виконанням команди
    4. Виконує відповідні команди (якщо потрібно)
    5. Отримує стан Feyree після виконання команди
    6. Чекає CHECK_INTERVAL_SEC перед наступною перевіркою
    """
    logger.info("=" * 60)
    logger.info("Запуск системи керування зарядкою Feyree EV")
    logger.info("=" * 60)
    logger.info("Порогові значення:")
    logger.info(f"  - Мінімальний SOC для зарядки: {SOC_THRESHOLD}%")
    logger.info(f"  - Максимальний імпорт з мережі: {GRID_IMPORT_THRESHOLD}W")
    logger.info(f"  - Інтервал перевірки: {CHECK_INTERVAL_SEC} сек")
    logger.info(f"  - Сила струму зарядки: {CHARGING_CURRENT_A}A")
    logger.info("=" * 60)

    # Ініціалізація компонентів
    try:
        inverter = DeyeInverter()
        charger = FeyreeCharger()
    except ValueError as e:
        logger.error(f"Помилка ініціалізації: {e}")
        logger.error("Припинення роботи програми")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Неочікувана помилка ініціалізації: {e}")
        sys.exit(1)

    # Перевірка підключення до пристроїв
    logger.info("-" * 60)
    logger.info("Перевірка підключення до пристроїв...")
    logger.info("-" * 60)

    # Тест підключення до Deye інвертора
    try:
        logger.info("Тестове підключення до Deye інвертора...")
        test_state = inverter.get_battery_and_grid_state()
        logger.info("Deye інвертор: Підключення УСПІШНЕ")
        logger.info(f"  Поточний SOC: {test_state['battery_soc_pct']:.1f}%")
        logger.info(
            f"  Потужність мережі: {test_state['grid_power_w']:.0f}W ({test_state['grid_direction']})"
        )
    except Exception as e:
        logger.error(f"Deye інвертор: Підключення НЕВДАЛЕ - {e}")
        logger.error("Неможливо продовжити роботу без доступу до інвертора")
        sys.exit(1)

    # Тест підключення до Feyree зарядки
    try:
        logger.info("Тестове підключення до Feyree зарядки...")
        test_status = charger.get_status()
        if test_status:
            logger.info("Feyree зарядка: Підключення УСПІШНЕ")
            if "dps" in test_status:
                # Показуємо поточний стан головного перемикача (якщо доступний)
                switch_state = test_status["dps"].get(
                    str(FEYREE_SWITCH_DPS), "невідомо"
                )
                work_mode = test_status["dps"].get(str(FEYREE_MODE_DPS), "невідомо")
                logger.info(f"  Стан: {'ВВІМК' if switch_state else 'ВИМК'}")
                logger.info(f"  Режим: {work_mode}")
        else:
            logger.warning(
                "Feyree зарядка: Підключення встановлено, але не отримано статус"
            )
            logger.warning("Продовжуємо роботу, але можливі проблеми з керуванням")
    except Exception as e:
        logger.error(f"Feyree зарядка: Підключення НЕВДАЛЕ - {e}")
        logger.error("Неможливо продовжити роботу без доступу до зарядки")
        sys.exit(1)

    logger.info("Всі пристрої підключені успішно. Запуск основного циклу...")

    # Основний цикл
    iteration = 0
    try:
        while True:
            iteration += 1
            logger.info("-" * 60)
            logger.info(f"Ітерація #{iteration} - {time.strftime('%Y-%m-%d %H:%M:%S')}")

            try:
                # Крок 1: Отримання даних з інвертора
                logger.info("Читання даних з Deye інвертора...")
                state = inverter.get_battery_and_grid_state()

                battery_soc: float = float(state["battery_soc_pct"])
                grid_power: float = float(state["grid_power_w"])
                grid_direction: str = str(state["grid_direction"])

                logger.info("Стан системи:")
                logger.info(f"  - Батарея: {battery_soc:.1f}%")
                logger.info(f"  - Мережа: {grid_power:.0f}W ({grid_direction})")

                # Крок 2: Прийняття рішення
                should_charge = charger.should_charge(
                    battery_soc, grid_power, grid_direction
                )

                logger.info("Аналіз умов зарядки:")
                logger.info(
                    f"  - SOC >= {SOC_THRESHOLD}%: {'ТАК' if battery_soc >= SOC_THRESHOLD else 'НІ'}"
                )
                logger.info(
                    f"  - Імпорт < {GRID_IMPORT_THRESHOLD}W або експорт: {'ТАК' if (grid_direction != 'import' or grid_power < GRID_IMPORT_THRESHOLD) else 'НІ'}"
                )
                logger.info(
                    f"Рішення: {'УВІМКНУТИ зарядку' if should_charge else 'ВИМКНУТИ зарядку'}"
                )

                # Крок 3: Отримання поточного стану перед виконанням команди
                logger.info("Отримання стану пристрою...")
                status_before = charger.get_status()
                charge_status = None
                if status_before and "dps" in status_before:
                    charger.display_device_status(status_before, prefix="[ДО]")
                    # Оновлюємо current_state з реального стану пристрою
                    actual_state = status_before.get("dps", {}).get(
                        str(FEYREE_SWITCH_DPS), None
                    )
                    charge_status = status_before.get("dps", {}).get(
                        "101", None
                    )  # Реальний статус зарядки
                    if actual_state is not None:
                        charger.current_state = actual_state

                # Крок 4: Виконання команди
                command_executed = False

                # Визначаємо чи зарядка вже відбувається (DPS 101 = "charing")
                is_already_charging = (
                    charge_status and "char" in str(charge_status).lower()
                )

                # Визначаємо чи потрібно виконати команду
                if should_charge and not is_already_charging:
                    # Потрібно увімкнути зарядку (тільки якщо вона ще не заряджається)
                    command_executed = charger.turn_on(CHARGING_CURRENT_A)
                elif not should_charge and is_already_charging:
                    # Потрібно вимкнути зарядку (тільки якщо вона заряджається)
                    command_executed = charger.turn_off()
                else:
                    # Стан не змінився
                    if should_charge and is_already_charging:
                        logger.info(
                            f"Зарядка вже відбувається (DPS 101 = {charge_status})"
                        )
                    else:
                        logger.info(
                            f"Стан зарядки не змінився (залишається: {'ВВІМК' if charger.current_state else 'ВИМК'})"
                        )

                # Крок 5: Отримання стану після виконання команди
                if command_executed:
                    # Невелика затримка для застосування команди
                    time.sleep(2)
                    logger.info("Перевірка стану після виконання команди...")
                    status_after = charger.get_status()
                    if status_after:
                        charger.display_device_status(status_after, prefix="[ПІСЛЯ]")

            except NoSocketAvailableError as e:
                logger.error(f"З'єднання з інвертором закрите: {e}")
                logger.info("Спроба перепідключення в наступній ітерації...")
            except V5FrameError as e:
                logger.error(f"Помилка зв'язку з інвертором: {e}")
            except Exception as e:
                logger.error(f"Неочікувана помилка в циклі: {e}", exc_info=True)

            # Крок 4: Очікування до наступної перевірки
            logger.info(
                f"Очікування {CHECK_INTERVAL_SEC} секунд до наступної перевірки..."
            )
            time.sleep(CHECK_INTERVAL_SEC)

    except KeyboardInterrupt:
        logger.info("\n" + "=" * 60)
        logger.info("Отримано сигнал зупинки (Ctrl+C)")
        logger.info("Завершення роботи програми...")
        logger.info("=" * 60)
    finally:
        # Закриття з'єднань
        inverter.disconnect()


# ============================================================
# Точка входу
# ============================================================


def main() -> None:
    """Основна точка входу програми."""
    try:
        control_loop()
    except Exception as e:
        logger.critical(f"Критична помилка: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
