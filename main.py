import tkinter as tk

from gui import ValveScadaApp


def main() -> None:
    root = tk.Tk()
    app = ValveScadaApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
