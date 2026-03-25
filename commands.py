import time
from abc import ABC, abstractmethod

from models import (
    CommandHistory,
    CommandRecord,
    ValveEmulator,
    ValveMode,
    ValveOrientation,
)


class ValveCommand(ABC):
    def __init__(self, valve: ValveEmulator, history: CommandHistory) -> None:
        self.valve = valve
        self.history = history

    @abstractmethod
    def execute(self) -> str:
        raise NotImplementedError

    def _log(self, command_name: str, details: str, result: str) -> None:
        self.history.add(
            CommandRecord(
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
                command_name=command_name,
                details=details,
                result=result,
            )
        )


class OpenCommand(ValveCommand):
    def execute(self) -> str:
        result = self.valve.move_to(100.0)
        self._log("OpenCommand", "Открыть на 100%", result)
        return result


class CloseCommand(ValveCommand):
    def execute(self) -> str:
        result = self.valve.move_to(0.0)
        self._log("CloseCommand", "Закрыть на 0%", result)
        return result


class StopCommand(ValveCommand):
    def execute(self) -> str:
        result = self.valve.stop_motion()
        self._log("StopCommand", "Остановить движение", result)
        return result


class SetPositionCommand(ValveCommand):
    def __init__(self, valve: ValveEmulator, history: CommandHistory, position: float) -> None:
        super().__init__(valve, history)
        self.position = position

    def execute(self) -> str:
        result = self.valve.move_to(self.position)
        self._log("SetPositionCommand", f"Установить {self.position:.1f}%", result)
        return result


class SetModeCommand(ValveCommand):
    def __init__(self, valve: ValveEmulator, history: CommandHistory, mode: ValveMode) -> None:
        super().__init__(valve, history)
        self.mode = mode

    def execute(self) -> str:
        result = self.valve.set_mode(self.mode)
        self._log("SetModeCommand", f"Режим: {self.mode.value}", result)
        return result


class SetOrientationCommand(ValveCommand):
    def __init__(self, valve: ValveEmulator, history: CommandHistory, orientation: ValveOrientation) -> None:
        super().__init__(valve, history)
        self.orientation = orientation

    def execute(self) -> str:
        result = self.valve.set_orientation(self.orientation)
        self._log("SetOrientationCommand", f"Ориентация: {self.orientation.value}", result)
        return result


class SetAmbientTemperatureCommand(ValveCommand):
    def __init__(self, valve: ValveEmulator, history: CommandHistory, ambient: float) -> None:
        super().__init__(valve, history)
        self.ambient = ambient

    def execute(self) -> str:
        result = self.valve.set_ambient_temperature(self.ambient)
        self._log("SetAmbientTemperatureCommand", f"ambient={self.ambient:.1f}", result)
        return result


class SyncSensorCommand(ValveCommand):
    def execute(self) -> str:
        result = self.valve.reset_sensor_to_actual()
        self._log("SyncSensorCommand", "Синхронизация датчика с фактическим положением", result)
        return result


class CommandInvoker:
    def execute_command(self, command: ValveCommand) -> str:
        return command.execute()
