import math
import tkinter as tk
from tkinter import messagebox, ttk

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from commands import (
    CloseCommand,
    CommandInvoker,
    OpenCommand,
    SetAmbientTemperatureCommand,
    SetModeCommand,
    SetOrientationCommand,
    SetPositionCommand,
    StopCommand,
    SyncSensorCommand,
)
from models import ValveEmulator, ValveMode, ValveOrientation


class ValveScadaApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("SCADA Эмулятор задвижки НПС")
        self.root.geometry("1600x950")
        self.root.configure(bg="#20252b")

        self.style = ttk.Style()
        self.style.theme_use("clam")
        self._configure_style()

        self.valve = ValveEmulator(
            movement_speed_percent_per_sec=14.0,
            gravity_fall_speed_percent_per_sec=32.0,
            ambient_temp=25.0,
            orientation=ValveOrientation.HORIZONTAL,
        )
        self.history = self.valve.command_history
        self.invoker = CommandInvoker()

        self._build_ui()
        self._update_ui()

    def _configure_style(self) -> None:
        self.style.configure(".", background="#20252b", foreground="#d7dde5", fieldbackground="#2a3138")
        self.style.configure("TFrame", background="#20252b")
        self.style.configure("TLabelframe", background="#20252b", foreground="#d7dde5")
        self.style.configure("TLabelframe.Label", background="#20252b", foreground="#f0f3f6")
        self.style.configure("TLabel", background="#20252b", foreground="#d7dde5")
        self.style.configure("Header.TLabel", font=("Segoe UI", 12, "bold"), foreground="#ffffff")
        self.style.configure("Value.TLabel", font=("Consolas", 12, "bold"), foreground="#7fe3ff")
        self.style.configure("Alarm.TLabel", font=("Segoe UI", 11, "bold"), foreground="#ff6b6b")
        self.style.configure("Info.TLabel", font=("Segoe UI", 10), foreground="#ffd166")
        self.style.configure("TButton", background="#2d3842", foreground="#ffffff", padding=6)
        self.style.map("TButton", background=[("active", "#3a4753")])
        self.style.configure("TRadiobutton", background="#20252b", foreground="#d7dde5")
        self.style.configure("TCombobox", fieldbackground="#2a3138", foreground="#ffffff")
        self.style.configure("TEntry", fieldbackground="#2a3138", foreground="#ffffff")

    def _build_ui(self) -> None:
        self.main = ttk.Frame(self.root, padding=10)
        self.main.pack(fill=tk.BOTH, expand=True)

        self.main.columnconfigure(0, weight=0)
        self.main.columnconfigure(1, weight=1)
        self.main.rowconfigure(1, weight=1)

        self._build_top_bar()
        self._build_left_panel()
        self._build_center_panel()
        self._build_bottom_panel()

    def _build_top_bar(self) -> None:
        top = ttk.LabelFrame(self.main, text="Состояние системы", padding=10)
        top.grid(row=0, column=0, columnspan=2, sticky="nsew", pady=(0, 10))

        top.columnconfigure(0, weight=1)
        top.columnconfigure(1, weight=1)
        top.columnconfigure(2, weight=1)
        top.columnconfigure(3, weight=2)

        self.lbl_top_state = ttk.Label(top, text="Состояние: -", style="Header.TLabel")
        self.lbl_top_state.grid(row=0, column=0, sticky="w", padx=5, pady=2)

        self.lbl_top_mode = ttk.Label(top, text="Режим: -", style="Header.TLabel")
        self.lbl_top_mode.grid(row=0, column=1, sticky="w", padx=5, pady=2)

        self.lbl_top_orientation = ttk.Label(top, text="Ориентация: -", style="Header.TLabel")
        self.lbl_top_orientation.grid(row=0, column=2, sticky="w", padx=5, pady=2)

        self.lbl_top_motion = ttk.Label(top, text="Движение: -", style="Header.TLabel")
        self.lbl_top_motion.grid(row=1, column=0, sticky="w", padx=5, pady=2)

        self.lbl_top_drive = ttk.Label(top, text="Привод: -", style="Header.TLabel")
        self.lbl_top_drive.grid(row=1, column=1, sticky="w", padx=5, pady=2)

        self.lbl_top_alarm = ttk.Label(top, text="Авария: нет", style="Alarm.TLabel")
        self.lbl_top_alarm.grid(row=1, column=2, sticky="w", padx=5, pady=2)

        self.lbl_top_info = ttk.Label(top, text="Инфо: -", style="Info.TLabel")
        self.lbl_top_info.grid(row=0, column=3, rowspan=2, sticky="ew", padx=5, pady=2)

    def _build_left_panel(self) -> None:
        left = ttk.Frame(self.main)
        left.grid(row=1, column=0, sticky="nsw", padx=(0, 10))
        left.rowconfigure(4, weight=1)

        params = ttk.LabelFrame(left, text="Технологические параметры", padding=10)
        params.pack(fill=tk.X, pady=(0, 10))

        self.lbl_target = ttk.Label(params, text="Задание: -", style="Value.TLabel")
        self.lbl_target.pack(anchor="w", pady=2)
        self.lbl_actual = ttk.Label(params, text="Фактическое положение: -", style="Value.TLabel")
        self.lbl_actual.pack(anchor="w", pady=2)
        self.lbl_sensor = ttk.Label(params, text="Положение по датчику: -", style="Value.TLabel")
        self.lbl_sensor.pack(anchor="w", pady=2)
        self.lbl_delta = ttk.Label(params, text="Разница факт/датчик: -", style="Value.TLabel")
        self.lbl_delta.pack(anchor="w", pady=2)
        self.lbl_temp = ttk.Label(params, text="Температура узла: -", style="Value.TLabel")
        self.lbl_temp.pack(anchor="w", pady=2)
        self.lbl_ambient = ttk.Label(params, text="Температура среды: -", style="Value.TLabel")
        self.lbl_ambient.pack(anchor="w", pady=2)

        control = ttk.LabelFrame(left, text="Управление", padding=10)
        control.pack(fill=tk.X, pady=(0, 10))

        buttons_frame = ttk.Frame(control)
        buttons_frame.pack(fill=tk.X, pady=(0, 8))
        ttk.Button(buttons_frame, text="Открыть", command=self.open_valve).grid(row=0, column=0, sticky="ew", padx=2, pady=2)
        ttk.Button(buttons_frame, text="Закрыть", command=self.close_valve).grid(row=0, column=1, sticky="ew", padx=2, pady=2)
        ttk.Button(buttons_frame, text="Стоп", command=self.stop_valve).grid(row=0, column=2, sticky="ew", padx=2, pady=2)
        buttons_frame.columnconfigure(0, weight=1)
        buttons_frame.columnconfigure(1, weight=1)
        buttons_frame.columnconfigure(2, weight=1)

        pos_frame = ttk.Frame(control)
        pos_frame.pack(fill=tk.X, pady=4)
        ttk.Label(pos_frame, text="Положение, %").grid(row=0, column=0, sticky="w")
        self.position_entry = ttk.Entry(pos_frame, width=12)
        self.position_entry.insert(0, "50")
        self.position_entry.grid(row=0, column=1, padx=5)
        ttk.Button(pos_frame, text="Установить", command=self.set_position).grid(row=0, column=2, padx=2)

        amb_frame = ttk.Frame(control)
        amb_frame.pack(fill=tk.X, pady=4)
        ttk.Label(amb_frame, text="Среда, °C").grid(row=0, column=0, sticky="w")
        self.ambient_entry = ttk.Entry(amb_frame, width=12)
        self.ambient_entry.insert(0, "25")
        self.ambient_entry.grid(row=0, column=1, padx=5)
        ttk.Button(amb_frame, text="Применить", command=self.set_ambient).grid(row=0, column=2, padx=2)

        ttk.Button(control, text="Синхронизировать датчик с фактом", command=self.sync_sensor).pack(fill=tk.X, pady=6)

        modes = ttk.LabelFrame(left, text="Режимы", padding=10)
        modes.pack(fill=tk.X, pady=(0, 10))
        self.mode_var = tk.StringVar(value=ValveMode.NORMAL.value)
        for mode in ValveMode:
            ttk.Radiobutton(modes, text=mode.value, value=mode.value, variable=self.mode_var, command=self.change_mode).pack(anchor="w", pady=2)

        orient = ttk.LabelFrame(left, text="Ориентация задвижки", padding=10)
        orient.pack(fill=tk.X, pady=(0, 10))
        self.orientation_var = tk.StringVar(value=ValveOrientation.HORIZONTAL.value)
        for orientation in ValveOrientation:
            ttk.Radiobutton(
                orient,
                text=orientation.value,
                value=orientation.value,
                variable=self.orientation_var,
                command=self.change_orientation,
            ).pack(anchor="w", pady=2)

        explanation = ttk.LabelFrame(left, text="Пояснение по температуре", padding=10)
        explanation.pack(fill=tk.BOTH, expand=True)

        text = (
            "Температура в модели — это температура привода/механического узла.\n\n"
            "Она формируется из:\n"
            "• температуры окружающей среды;\n"
            "• нагрева при движении;\n"
            "• дополнительного нагрева под нагрузкой;\n"
            "• сильного нагрева при заклинивании;\n"
            "• последующего охлаждения после остановки.\n\n"
            "При отказе привода собственного нагрева почти нет, "
            "но для вертикальной задвижки при падении остаётся небольшой нагрев от трения."
        )

        self.temp_explain = tk.Text(
            explanation,
            height=13,
            wrap="word",
            bg="#11161b",
            fg="#d7dde5",
            insertbackground="#ffffff",
            relief="flat",
        )
        self.temp_explain.pack(fill=tk.BOTH, expand=True)
        self.temp_explain.insert("1.0", text)
        self.temp_explain.configure(state="disabled")

    def _build_center_panel(self) -> None:
        center = ttk.Frame(self.main)
        center.grid(row=1, column=1, sticky="nsew")
        center.rowconfigure(0, weight=0)
        center.rowconfigure(1, weight=1)
        center.columnconfigure(0, weight=1)

        mimic_frame = ttk.LabelFrame(center, text="SCADA-мнемосхема", padding=10)
        mimic_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        self.canvas = tk.Canvas(
            mimic_frame,
            width=980,
            height=260,
            bg="#11161b",
            highlightthickness=1,
            highlightbackground="#3a4550",
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        charts_frame = ttk.LabelFrame(center, text="Графики", padding=10)
        charts_frame.grid(row=1, column=0, sticky="nsew")
        charts_frame.rowconfigure(0, weight=1)
        charts_frame.rowconfigure(1, weight=1)
        charts_frame.columnconfigure(0, weight=1)

        self.fig_position = Figure(figsize=(8, 3.2), dpi=100)
        self.ax_position = self.fig_position.add_subplot(111)
        self.ax_position.set_title("Положение задвижки")
        self.ax_position.set_xlabel("Время, сек")
        self.ax_position.set_ylabel("Положение, %")
        self.ax_position.set_ylim(-5, 105)
        self.ax_position.grid(True)
        self.position_line_actual, = self.ax_position.plot([], [], label="Фактическое")
        self.position_line_sensor, = self.ax_position.plot([], [], label="Датчик")
        self.ax_position.legend(loc="upper right")
        self.canvas_position = FigureCanvasTkAgg(self.fig_position, master=charts_frame)
        self.canvas_position.get_tk_widget().grid(row=0, column=0, sticky="nsew", pady=(0, 8))

        self.fig_temp = Figure(figsize=(8, 3.2), dpi=100)
        self.ax_temp = self.fig_temp.add_subplot(111)
        self.ax_temp.set_title("Температура узла")
        self.ax_temp.set_xlabel("Время, сек")
        self.ax_temp.set_ylabel("Температура, °C")
        self.ax_temp.grid(True)
        self.temperature_line, = self.ax_temp.plot([], [], label="Температура")
        self.ax_temp.legend(loc="upper right")
        self.canvas_temp = FigureCanvasTkAgg(self.fig_temp, master=charts_frame)
        self.canvas_temp.get_tk_widget().grid(row=1, column=0, sticky="nsew")

    def _build_bottom_panel(self) -> None:
        bottom = ttk.Frame(self.root, padding=(10, 0, 10, 10))
        bottom.pack(fill=tk.BOTH, expand=False)
        bottom.columnconfigure(0, weight=1)
        bottom.columnconfigure(1, weight=1)

        history_frame = ttk.LabelFrame(bottom, text="История команд", padding=10)
        history_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        self.history_list = tk.Listbox(
            history_frame,
            height=12,
            bg="#11161b",
            fg="#d7dde5",
            selectbackground="#335c67",
            relief="flat",
        )
        self.history_list.pack(fill=tk.BOTH, expand=True)

        alarm_frame = ttk.LabelFrame(bottom, text="Журнал событий / аварий", padding=10)
        alarm_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        self.alarm_list = tk.Listbox(
            alarm_frame,
            height=12,
            bg="#11161b",
            fg="#ffd6a5",
            selectbackground="#8338ec",
            relief="flat",
        )
        self.alarm_list.pack(fill=tk.BOTH, expand=True)

    def _append_last_history(self) -> None:
        records = self.history.all()
        if not records:
            return
        last = records[-1]
        text = f"{last.timestamp} | {last.command_name} | {last.details} | {last.result}"
        self.history_list.insert(tk.END, text)
        self.history_list.yview_moveto(1)

    def _refresh_alarm_list(self) -> None:
        self.alarm_list.delete(0, tk.END)
        for item in self.valve.alarm_journal.all():
            self.alarm_list.insert(tk.END, f"{item.timestamp} | {item.level} | {item.text}")
        self.alarm_list.yview_moveto(1)

    def open_valve(self) -> None:
        result = self.invoker.execute_command(OpenCommand(self.valve, self.history))
        self._append_last_history()
        self._refresh_alarm_list()
        self.root.title(f"SCADA Эмулятор задвижки НПС — {result}")

    def close_valve(self) -> None:
        result = self.invoker.execute_command(CloseCommand(self.valve, self.history))
        self._append_last_history()
        self._refresh_alarm_list()
        self.root.title(f"SCADA Эмулятор задвижки НПС — {result}")

    def stop_valve(self) -> None:
        result = self.invoker.execute_command(StopCommand(self.valve, self.history))
        self._append_last_history()
        self._refresh_alarm_list()
        self.root.title(f"SCADA Эмулятор задвижки НПС — {result}")

    def set_position(self) -> None:
        raw = self.position_entry.get().strip().replace(",", ".")
        try:
            pos = float(raw)
        except ValueError:
            messagebox.showerror("Ошибка", "Введите корректное положение в диапазоне 0..100")
            return

        if not 0.0 <= pos <= 100.0:
            messagebox.showerror("Ошибка", "Положение должно быть в диапазоне 0..100")
            return

        result = self.invoker.execute_command(SetPositionCommand(self.valve, self.history, pos))
        self._append_last_history()
        self._refresh_alarm_list()
        self.root.title(f"SCADA Эмулятор задвижки НПС — {result}")

    def set_ambient(self) -> None:
        raw = self.ambient_entry.get().strip().replace(",", ".")
        try:
            temp = float(raw)
        except ValueError:
            messagebox.showerror("Ошибка", "Введите корректную температуру среды")
            return

        result = self.invoker.execute_command(SetAmbientTemperatureCommand(self.valve, self.history, temp))
        self._append_last_history()
        self._refresh_alarm_list()
        self.root.title(f"SCADA Эмулятор задвижки НПС — {result}")

    def sync_sensor(self) -> None:
        result = self.invoker.execute_command(SyncSensorCommand(self.valve, self.history))
        self._append_last_history()
        self._refresh_alarm_list()
        self.root.title(f"SCADA Эмулятор задвижки НПС — {result}")

    def change_mode(self) -> None:
        mode = ValveMode(self.mode_var.get())
        result = self.invoker.execute_command(SetModeCommand(self.valve, self.history, mode))
        self._append_last_history()
        self._refresh_alarm_list()
        self.root.title(f"SCADA Эмулятор задвижки НПС — {result}")

    def change_orientation(self) -> None:
        orientation = ValveOrientation(self.orientation_var.get())
        result = self.invoker.execute_command(SetOrientationCommand(self.valve, self.history, orientation))
        self._append_last_history()
        self._refresh_alarm_list()
        self.root.title(f"SCADA Эмулятор задвижки НПС — {result}")

    def _update_ui(self) -> None:
        status = self.valve.get_status()

        self.lbl_top_state.config(text=f"Состояние: {status['state']}")
        self.lbl_top_mode.config(text=f"Режим: {status['mode']}")
        self.lbl_top_orientation.config(text=f"Ориентация: {status['orientation']}")
        self.lbl_top_motion.config(text=f"Движение: {'да' if status['is_moving'] else 'нет'}")
        self.lbl_top_drive.config(text=f"Привод активен: {'да' if status['drive_active'] else 'нет'}")
        self.lbl_top_alarm.config(text=f"Авария: {status['last_alarm'] if status['last_alarm'] else 'нет'}")
        self.lbl_top_info.config(text=f"Инфо: {status['last_info']}")

        self.lbl_target.config(text=f"Задание: {status['target_position']:.1f}%")
        self.lbl_actual.config(text=f"Фактическое положение: {status['actual_position']:.1f}%")
        self.lbl_sensor.config(text=f"Положение по датчику: {status['measured_position']:.1f}%")
        self.lbl_delta.config(text=f"Разница факт/датчик: {status['sensor_delta']:.2f}%")
        self.lbl_temp.config(text=f"Температура узла: {status['temperature']:.2f} °C")
        self.lbl_ambient.config(text=f"Температура среды: {status['ambient_temp']:.1f} °C")

        self._draw_mimic(status)
        self._update_plots()
        self._refresh_alarm_list()

        self.root.after(200, self._update_ui)

    def _draw_mimic(self, status: dict) -> None:
        c = self.canvas
        c.delete("all")

        width = max(980, c.winfo_width())
        height = max(260, c.winfo_height())

        c.create_text(20, 15, text="Мнемосхема задвижки", anchor="w", fill="#d7dde5", font=("Segoe UI", 12, "bold"))

        pipe_color = "#4cc9f0"
        line_color = "#91a7b7"
        moving_color = "#ffd166"
        alarm_color = "#ef476f"
        ok_color = "#06d6a0"
        closed_color = "#e63946"
        body_color = "#495057"

        pipe_y = height // 2 + 8
        valve_x = width // 2
        valve_body_w = 92
        valve_body_h = 64

        # Укороченная труба: теперь она не заходит под текст справа и меньше конфликтует с мнемосхемой.
        left_panel_margin = 70
        right_info_start = width - 410
        pipe_left_end = valve_x - valve_body_w // 2 - 22
        pipe_right_start = valve_x + valve_body_w // 2 + 22
        pipe_left = left_panel_margin
        pipe_right = right_info_start - 45

        c.create_line(pipe_left, pipe_y, pipe_left_end, pipe_y, fill=pipe_color, width=16)
        c.create_line(pipe_right_start, pipe_y, pipe_right, pipe_y, fill=pipe_color, width=16)
        c.create_line(pipe_left, pipe_y - 8, pipe_left_end, pipe_y - 8, fill="#6fd3f5", width=2)
        c.create_line(pipe_left, pipe_y + 8, pipe_left_end, pipe_y + 8, fill="#1f7a8c", width=2)
        c.create_line(pipe_right_start, pipe_y - 8, pipe_right, pipe_y - 8, fill="#6fd3f5", width=2)
        c.create_line(pipe_right_start, pipe_y + 8, pipe_right, pipe_y + 8, fill="#1f7a8c", width=2)

        # Корпус уменьшен и сдвинут так, чтобы не загораживать подписи.
        c.create_rectangle(
            valve_x - valve_body_w // 2,
            pipe_y - valve_body_h // 2,
            valve_x + valve_body_w // 2,
            pipe_y + valve_body_h // 2,
            fill=body_color,
            outline=line_color,
            width=2,
        )
        c.create_text(valve_x + 88, pipe_y - 66, text="Задвижка", fill="#ffffff", font=("Segoe UI", 14, "bold"))

        orientation = status["orientation"]
        actual = status["actual_position"]
        mode = status["mode"]
        is_moving = status["is_moving"]

        if mode in (ValveMode.JAMMED.value, ValveMode.DRIVE_FAILURE.value):
            state_color = alarm_color
        elif is_moving:
            state_color = moving_color
        elif actual <= 0.1:
            state_color = closed_color
        elif actual >= 99.9:
            state_color = ok_color
        else:
            state_color = moving_color

        if orientation == ValveOrientation.HORIZONTAL.value:
            top = pipe_y - valve_body_h // 2 + 5
            bottom = pipe_y + valve_body_h // 2 - 5
            slot_left = valve_x - 14
            slot_right = valve_x + 14

            c.create_rectangle(slot_left, top, slot_right, bottom, fill="#2b2d42", outline="#8d99ae")
            travel = bottom - top - 24
            plate_y = bottom - 12 - (actual / 100.0) * travel

            c.create_rectangle(
                valve_x - 24,
                plate_y - 8,
                valve_x + 24,
                plate_y + 8,
                fill=state_color,
                outline="#ffffff",
            )
            c.create_line(valve_x, top - 28, valve_x, plate_y - 8, fill="#dee2e6", width=4)
            c.create_oval(valve_x - 14, top - 46, valve_x + 14, top - 18, fill="#6c757d", outline="#f8f9fa")
            # c.create_text(valve_x + 90, pipe_y - 58, text="Тип: horizontal", fill="#d7dde5", anchor="w")
        else:
            tower_top = pipe_y - 72
            tower_bottom = pipe_y + 72
            c.create_rectangle(
                valve_x - 24,
                tower_top,
                valve_x + 24,
                tower_bottom,
                fill="#2b2d42",
                outline="#8d99ae",
                width=2,
            )

            travel = tower_bottom - tower_top - 20
            gate_y = tower_bottom - 10 - (actual / 100.0) * travel
            c.create_rectangle(
                valve_x - 20,
                gate_y - 10,
                valve_x + 20,
                gate_y + 10,
                fill=state_color,
                outline="#ffffff",
            )
            c.create_line(valve_x, tower_top - 30, valve_x, gate_y - 10, fill="#dee2e6", width=4)
            c.create_oval(valve_x - 18, tower_top - 50, valve_x + 18, tower_top - 20, fill="#6c757d", outline="#f8f9fa")
            # c.create_text(valve_x + 90, pipe_y - 58, text="Тип: vertical", fill="#d7dde5", anchor="w")

            if mode == ValveMode.DRIVE_FAILURE.value and actual > 0.0:
                c.create_text(
                    valve_x + 90,
                    pipe_y - 34,
                    text="При отказе привода вертикальная задвижка падает вниз",
                    fill="#ffb703",
                    anchor="w",
                )

        opening = actual / 100.0
        opening_bar_w = 210
        bar_x1 = 80
        bar_y1 = 44
        c.create_text(bar_x1, bar_y1 - 12, text="Открытие потока", anchor="w", fill="#d7dde5")
        c.create_rectangle(bar_x1, bar_y1, bar_x1 + opening_bar_w, bar_y1 + 18, outline="#adb5bd", width=1)
        c.create_rectangle(bar_x1, bar_y1, bar_x1 + opening_bar_w * opening, bar_y1 + 18, fill=state_color, outline="")

        info_x = width - 360
        info_y0 = 34
        info_gap = 23
        c.create_text(info_x, info_y0 + info_gap * 0, text=f"Задание: {status['target_position']:.1f} %", anchor="w", fill="#7fe3ff", font=("Consolas", 12, "bold"))
        c.create_text(info_x, info_y0 + info_gap * 1, text=f"Факт: {status['actual_position']:.1f} %", anchor="w", fill="#7fe3ff", font=("Consolas", 12, "bold"))
        c.create_text(info_x, info_y0 + info_gap * 2, text=f"Датчик: {status['measured_position']:.1f} %", anchor="w", fill="#7fe3ff", font=("Consolas", 12, "bold"))
        c.create_text(info_x, info_y0 + info_gap * 3, text=f"Δ факт/датчик: {status['sensor_delta']:.2f} %", anchor="w", fill="#ffd166", font=("Consolas", 12, "bold"))
        c.create_text(info_x, info_y0 + info_gap * 4, text=f"Температура: {status['temperature']:.2f} °C", anchor="w", fill="#ff9f1c", font=("Consolas", 12, "bold"))
        c.create_text(info_x, info_y0 + info_gap * 5, text=f"Среда: {status['ambient_temp']:.1f} °C", anchor="w", fill="#ffd6a5", font=("Consolas", 12, "bold"))

        box_y = height - 55
        self._draw_status_box(c, 80, box_y, 170, 36, "STATE", status["state"], state_color)
        self._draw_status_box(c, 270, box_y, 170, 36, "MODE", status["mode"], "#6c757d" if mode == "normal" else alarm_color)
        self._draw_status_box(c, 460, box_y, 170, 36, "MOVE", "YES" if is_moving else "NO", moving_color if is_moving else "#495057")
        self._draw_status_box(c, 650, box_y, 240, 36, "ALARM", status["last_alarm"] if status["last_alarm"] else "none", alarm_color if status["last_alarm"] else "#495057")

    def _draw_status_box(self, c: tk.Canvas, x: int, y: int, w: int, h: int, title: str, value: str, fill: str) -> None:
        c.create_rectangle(x, y, x + w, y + h, fill="#1f242a", outline="#6c757d")
        c.create_text(x + 8, y + h // 2, text=title, anchor="w", fill="#adb5bd", font=("Segoe UI", 9, "bold"))
        c.create_rectangle(x + 70, y + 4, x + w - 4, y + h - 4, fill=fill, outline="")
        c.create_text(x + 78, y + h // 2, text=value, anchor="w", fill="#11161b", font=("Segoe UI", 9, "bold"))

    def _update_plots(self) -> None:
        p_trace = list(self.valve.position_trace)
        s_trace = list(self.valve.sensor_trace)
        t_trace = list(self.valve.temperature_trace)

        if p_trace:
            px = [i[0] for i in p_trace]
            py = [i[1] for i in p_trace]
            self.position_line_actual.set_data(px, py)

        if s_trace:
            sx = [i[0] for i in s_trace]
            sy = [i[1] for i in s_trace]
            self.position_line_sensor.set_data(sx, sy)

        if t_trace:
            tx = [i[0] for i in t_trace]
            ty = [i[1] for i in t_trace]
            self.temperature_line.set_data(tx, ty)

        if p_trace or s_trace:
            all_x = []
            if p_trace:
                all_x.extend([i[0] for i in p_trace])
            if s_trace:
                all_x.extend([i[0] for i in s_trace])
            if all_x:
                xmax = max(all_x)
                xmin = max(0.0, xmax - 60.0)
                self.ax_position.set_xlim(xmin, max(60.0, xmax + 1.0))

        if t_trace:
            tx = [i[0] for i in t_trace]
            ty = [i[1] for i in t_trace]
            xmax = max(tx)
            xmin = max(0.0, xmax - 60.0)
            self.ax_temp.set_xlim(xmin, max(60.0, xmax + 1.0))
            ymin = min(ty) - 2.0
            ymax = max(ty) + 2.0
            if math.isclose(ymin, ymax):
                ymax += 1.0
            self.ax_temp.set_ylim(ymin, ymax)

        self.canvas_position.draw_idle()
        self.canvas_temp.draw_idle()

    def on_close(self) -> None:
        self.valve.shutdown()
        self.root.destroy()
