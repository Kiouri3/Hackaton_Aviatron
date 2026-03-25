import threading
import time
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class ValveMode(Enum):
    NORMAL = "нормальный"
    JAMMED = "клин задвижки"
    DRIVE_FAILURE = "отказ привода"


class ValveState(Enum):
    OPEN = "открыто"
    CLOSED = "закрыто"
    INTERMEDIATE = "промежуточное"


class ValveOrientation(Enum):
    HORIZONTAL = "горизонтальный"
    VERTICAL = "вертикальный"


@dataclass
class CommandRecord:
    timestamp: str
    command_name: str
    details: str
    result: str


@dataclass
class AlarmRecord:
    timestamp: str
    level: str
    text: str


class CommandHistory:
    def __init__(self) -> None:
        self._records: List[CommandRecord] = []
        self._lock = threading.Lock()

    def add(self, record: CommandRecord) -> None:
        with self._lock:
            self._records.append(record)

    def all(self) -> List[CommandRecord]:
        with self._lock:
            return list(self._records)


class AlarmJournal:
    def __init__(self) -> None:
        self._records: List[AlarmRecord] = []
        self._lock = threading.Lock()

    def add(self, level: str, text: str) -> None:
        with self._lock:
            self._records.append(
                AlarmRecord(
                    timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
                    level=level,
                    text=text,
                )
            )

    def all(self) -> List[AlarmRecord]:
        with self._lock:
            return list(self._records)


class PositionSensor:
    """
    Плавный датчик положения с инерцией и квантованием.
    """

    def __init__(
        self,
        update_rate: float = 0.22,
        quantization: float = 0.1,
        bias: float = 0.0,
    ) -> None:
        self.update_rate = update_rate
        self.quantization = quantization
        self.bias = bias
        self._measured_position = 0.0
        self._frozen = False

    def freeze(self, value: bool) -> None:
        self._frozen = value

    def reset(self, value: float = 0.0) -> None:
        self._measured_position = max(0.0, min(100.0, value))

    def update(self, actual_position: float) -> None:
        if self._frozen:
            return

        target = actual_position + self.bias
        delta = target - self._measured_position
        self._measured_position += delta * self.update_rate

        if self.quantization > 0:
            self._measured_position = round(self._measured_position / self.quantization) * self.quantization

        self._measured_position = max(0.0, min(100.0, self._measured_position))

    def read(self) -> float:
        return round(self._measured_position, 2)


class TemperatureModel:
    """
    Температура привода/механического узла.
    """

    def __init__(self, ambient_temp: float = 25.0) -> None:
        self.ambient_temp = ambient_temp
        self.temperature = ambient_temp + 2.0

    def set_ambient(self, value: float) -> None:
        self.ambient_temp = value

    def update(
        self,
        dt: float,
        moving: bool,
        mode: ValveMode,
        actual_position: float,
        target_position: float,
        orientation: ValveOrientation,
    ) -> None:
        heating = 0.0

        if moving:
            heating += 1.4
            if 1.0 < actual_position < 99.0:
                heating += 0.2

        if mode == ValveMode.JAMMED:
            if abs(target_position - actual_position) > 0.5:
                heating += 3.5
            else:
                heating += 1.5

        if mode == ValveMode.DRIVE_FAILURE:
            heating += 0.1
            if orientation == ValveOrientation.VERTICAL and actual_position > 0.0:
                heating += 0.25

        cooling_coeff = 0.075
        self.temperature += heating * dt
        self.temperature -= (self.temperature - self.ambient_temp) * cooling_coeff * dt

        if self.temperature < self.ambient_temp:
            self.temperature += (self.ambient_temp - self.temperature) * 0.05

        self.temperature = round(self.temperature, 2)

    def read(self) -> float:
        return round(self.temperature, 2)


class ValveEmulator:
    def __init__(
        self,
        movement_speed_percent_per_sec: float = 14.0,
        gravity_fall_speed_percent_per_sec: float = 30.0,
        ambient_temp: float = 25.0,
        orientation: ValveOrientation = ValveOrientation.HORIZONTAL,
    ) -> None:
        self.target_position: float = 0.0
        self.actual_position: float = 0.0
        self.mode: ValveMode = ValveMode.NORMAL
        self.orientation: ValveOrientation = orientation

        self.movement_speed_percent_per_sec = movement_speed_percent_per_sec
        self.gravity_fall_speed_percent_per_sec = gravity_fall_speed_percent_per_sec

        self.position_sensor = PositionSensor(update_rate=0.22, quantization=0.1, bias=0.0)
        self.temperature_model = TemperatureModel(ambient_temp=ambient_temp)

        self.is_moving: bool = False
        self.drive_active: bool = False
        self.last_info: str = "Система готова"
        self.last_alarm: str = ""
        self._lock = threading.Lock()
        self._stop = False
        self._worker_thread: Optional[threading.Thread] = None

        self.start_time = time.time()
        self.position_trace = deque(maxlen=600)
        self.sensor_trace = deque(maxlen=600)
        self.temperature_trace = deque(maxlen=600)

        self.command_history = CommandHistory()
        self.alarm_journal = AlarmJournal()

        self._worker_thread = threading.Thread(target=self._worker, daemon=True)
        self._worker_thread.start()

    @property
    def state(self) -> ValveState:
        if self.actual_position <= 0.1:
            return ValveState.CLOSED
        if self.actual_position >= 99.9:
            return ValveState.OPEN
        return ValveState.INTERMEDIATE

    def shutdown(self) -> None:
        self._stop = True
        if self._worker_thread:
            self._worker_thread.join(timeout=1.0)

    def _add_alarm(self, level: str, text: str) -> None:
        self.last_alarm = text
        self.alarm_journal.add(level, text)

    def set_mode(self, mode: ValveMode) -> str:
        with self._lock:
            old_mode = self.mode
            self.mode = mode

            if mode == ValveMode.DRIVE_FAILURE:
                self.drive_active = False
                if self.orientation == ValveOrientation.VERTICAL and self.actual_position > 0.0:
                    info = "Отказ привода: вертикальная задвижка переходит в падение к 0%"
                    self.last_info = info
                    self._add_alarm("ALARM", "Отказ привода")
                    return info
                info = "Отказ привода: дальнейшее приводное движение невозможно"
                self.last_info = info
                self._add_alarm("ALARM", "Отказ привода")
                return info

            if mode == ValveMode.JAMMED:
                self.drive_active = False
                info = "Заклинивание: механика заблокирована"
                self.last_info = info
                self._add_alarm("ALARM", "Заклинивание задвижки")
                return info

            if old_mode != ValveMode.NORMAL and mode == ValveMode.NORMAL:
                info = "Режим normal восстановлен"
                self.last_info = info
                self._add_alarm("INFO", "Переход в нормальный режим")
                return info

            info = f"Режим изменен на {mode.value}"
            self.last_info = info
            return info

    def set_orientation(self, orientation: ValveOrientation) -> str:
        with self._lock:
            self.orientation = orientation
            info = f"Ориентация изменена на {orientation.value}"
            self.last_info = info
            return info

    def set_ambient_temperature(self, value: float) -> str:
        with self._lock:
            self.temperature_model.set_ambient(value)
            info = f"Температура окружающей среды установлена: {value:.1f} °C"
            self.last_info = info
            return info

    def move_to(self, target_position: float) -> str:
        with self._lock:
            target_position = max(0.0, min(100.0, target_position))
            self.target_position = target_position

            if self.mode == ValveMode.DRIVE_FAILURE:
                if self.orientation == ValveOrientation.VERTICAL:
                    info = "Команда принята, но привод отказал: вертикальная задвижка падает к 0%"
                else:
                    info = "Команда не выполнена: отказ привода"
                self.last_info = info
                return info

            if self.mode == ValveMode.JAMMED:
                info = "Команда не выполнена: задвижка заклинена"
                self.last_info = info
                return info

            self.drive_active = True
            info = f"Новое задание: {target_position:.1f}%"
            self.last_info = info
            return info

    def stop_motion(self) -> str:
        with self._lock:
            self.target_position = self.actual_position
            self.drive_active = False
            info = "Команда стоп: движение остановлено"
            self.last_info = info
            return info

    def reset_sensor_to_actual(self) -> str:
        with self._lock:
            self.position_sensor.reset(self.actual_position)
            info = "Датчик положения синхронизирован с фактическим положением"
            self.last_info = info
            return info

    def _worker(self) -> None:
        dt = 0.1

        while not self._stop:
            with self._lock:
                self.is_moving = False

                if self.mode == ValveMode.NORMAL:
                    delta = self.target_position - self.actual_position
                    if abs(delta) > 0.05 and self.drive_active:
                        self.is_moving = True
                        step = self.movement_speed_percent_per_sec * dt
                        if delta > 0:
                            self.actual_position = min(self.actual_position + step, self.target_position)
                        else:
                            self.actual_position = max(self.actual_position - step, self.target_position)

                        if abs(self.target_position - self.actual_position) <= 0.05:
                            self.actual_position = self.target_position
                            self.drive_active = False
                    else:
                        self.drive_active = False

                elif self.mode == ValveMode.JAMMED:
                    self.drive_active = False
                    self.is_moving = False

                elif self.mode == ValveMode.DRIVE_FAILURE:
                    self.drive_active = False

                    if self.orientation == ValveOrientation.VERTICAL and self.actual_position > 0.0:
                        self.is_moving = True
                        step = self.gravity_fall_speed_percent_per_sec * dt
                        self.actual_position = max(0.0, self.actual_position - step)
                        self.target_position = 0.0
                    else:
                        self.is_moving = False

                self.position_sensor.update(self.actual_position)
                self.temperature_model.update(
                    dt=dt,
                    moving=self.is_moving,
                    mode=self.mode,
                    actual_position=self.actual_position,
                    target_position=self.target_position,
                    orientation=self.orientation,
                )

                t = time.time() - self.start_time
                self.position_trace.append((t, round(self.actual_position, 2)))
                self.sensor_trace.append((t, self.position_sensor.read()))
                self.temperature_trace.append((t, self.temperature_model.read()))

            time.sleep(dt)

    def get_status(self) -> dict:
        with self._lock:
            measured = self.position_sensor.read()
            actual = round(self.actual_position, 2)
            diff = round(abs(actual - measured), 2)

            return {
                "target_position": round(self.target_position, 2),
                "actual_position": actual,
                "measured_position": measured,
                "sensor_delta": diff,
                "temperature": self.temperature_model.read(),
                "ambient_temp": self.temperature_model.ambient_temp,
                "mode": self.mode.value,
                "orientation": self.orientation.value,
                "state": self.state.value,
                "is_moving": self.is_moving,
                "drive_active": self.drive_active,
                "last_info": self.last_info,
                "last_alarm": self.last_alarm,
            }
