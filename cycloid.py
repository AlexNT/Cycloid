"""Тестовая отрисовка циклоидального редуктора (диск-"звёздочка", ролики, выход).

Только стандартная библиотека (tkinter + math). Запуск:  python cycloid.py

Профиль диска (эквидистанта к укороченной эпициклоиде на радиус ролика):
    x = R*cos t - rp*cos(t+psi) - e*cos(N t)
    y = -R*sin t + rp*sin(t+psi) + e*sin(N t)
    psi = atan( sin((1-N) t) / (R/(e N) - cos((1-N) t)) )
где N - число роликов корпуса, R - радиус окружности роликов,
rp - радиус ролика, e - эксцентриситет. Зубцов диска N-1, передаточное N-1.
"""
import math
import tkinter as tk
from tkinter import ttk


# ---------------------------------------------------------------- геометрия
def disc_profile(n_pins, R, rp, e, steps=1440):
    """Точки профиля диска относительно его центра (диск на фазе 0)."""
    pts = []
    k = R / (e * n_pins)
    for i in range(steps):
        t = 2 * math.pi * i / steps
        a = (1 - n_pins) * t
        psi = math.atan2(math.sin(a), k - math.cos(a))
        x = R * math.cos(t) - rp * math.cos(t + psi) - e * math.cos(n_pins * t)
        y = -R * math.sin(t) + rp * math.sin(t + psi) + e * math.sin(n_pins * t)
        pts.append((x, y))
    return pts


def rotate(pts, ang, cx=0.0, cy=0.0):
    c, s = math.cos(ang), math.sin(ang)
    return [(cx + x * c - y * s, cy + x * s + y * c) for x, y in pts]


def pin_centers(n_pins, R):
    return [(R * math.cos(2 * math.pi * i / n_pins),
             R * math.sin(2 * math.pi * i / n_pins)) for i in range(n_pins)]


def min_clearance(disc_pts, pins, rp):
    """Минимальный зазор диск-ролик (0 = касание, <0 = врезание)."""
    best = 1e9
    for px, py in pins:
        for x, y in disc_pts[::4]:
            d = math.hypot(x - px, y - py) - rp
            if d < best:
                best = d
    return best


# ---------------------------------------------------------------- интерфейс
HOUSING_K = 1.3     # внешний радиус корпуса = HOUSING_K * R


class App(tk.Tk):
    AUTO_KEYS = ("Rh", "ro", "bore")

    def __init__(self):
        super().__init__()
        self.title("Циклоидальный редуктор - тестовая отрисовка диска")
        self.geometry("1100x760")
        try:
            self.state("zoomed")            # Windows: развернуть на весь экран
        except tk.TclError:
            self.attributes("-zoomed", True)
        self.phi = 0.0
        self.running = False
        self.vars = {}
        self._cache_key = None
        self._cache = None

        panel = ttk.Frame(self, padding=8)
        panel.pack(side=tk.LEFT, fill=tk.Y)
        self.canvas = tk.Canvas(self, bg="white", highlightthickness=0)
        self.canvas.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self.canvas.bind("<Configure>", lambda _e: self.redraw())

        self._slider(panel, "N  - число роликов", "n", 27, 3, 60, 1, int)
        self._slider(panel, "R  - радиус окружности роликов, мм", "R", 70.0, 10, 150, 0.5)
        self._slider(panel, "rp - радиус ролика, мм", "rp", 6.0, 0.5, 15, 0.1)
        self._slider(panel, "e  - эксцентриситет, мм", "e", 1.5, 0.1, 10, 0.05)
        self._slider(panel, "Дисков (1 или 2, сдвиг 180°)", "discs", 2, 1, 2, 1, int)
        self._slider(panel, "Выходных пальцев", "nh", 6, 3, 16, 1, int)
        self.vars["auto"] = tk.BooleanVar(value=True)
        ttk.Checkbutton(panel, text="Авто-размеры Rh, ro, отверстия (ввод вручную фиксирует)",
                        variable=self.vars["auto"], command=self._on_auto).pack(anchor="w", pady=(6, 0))
        self._slider(panel, "Rh - радиус окружности пальцев, мм", "Rh", 30.0, 3, 100, 0.1)
        self._slider(panel, "ro - радиус выходного пальца, мм", "ro", 2.7, 0.3, 10, 0.1)
        self._slider(panel, "Радиус центрального отверстия, мм", "bore", 12.0, 0.5, 40, 0.1)
        self._slider(panel, "Толщина диска (для SolidWorks), мм", "thick", 8.0, 1, 40, 0.5, lock=False)
        self._slider(panel, "Угол входного вала, °", "phi", 0, 0, 360, 1, float, self._on_phi, lock=False)
        self._slider(panel, "Скорость анимации, °/кадр", "speed", 2.0, 0.2, 10, 0.1, lock=False)

        for key, text, val in (("show_pins", "Ролики корпуса", True),
                               ("show_disc", "Диск", True),
                               ("show_fill", "Заливка диска", True),
                               ("show_out", "Выходные пальцы", True),
                               ("show_hub", "Выходная ступица (6 закладных)", True),
                               ("show_housing", "Корпус", True),
                               ("show_orbit", "Эксцентрик / орбита", True),
                               ("show_base", "Делительные окружности", True),
                               ("show_dev", "Профиль в фазе 0 (контроль)", False)):
            v = tk.BooleanVar(value=val)
            self.vars[key] = v
            ttk.Checkbutton(panel, text=text, variable=v, command=self.redraw).pack(anchor="w")

        ttk.Button(panel, text="Пресет 26:1 (N=27)", command=self.preset_26).pack(fill=tk.X, pady=(8, 0))
        ttk.Button(panel, text="Экспорт DXF (диск, фаза 0)", command=self.export_dxf).pack(fill=tk.X)
        sw = ttk.LabelFrame(panel, text="Выгрузка в SolidWorks", padding=4)
        sw.pack(fill=tk.X, pady=(6, 0))
        for text, what in (("Звёздочка", "disc"), ("Корпус", "housing"),
                           ("Эксцентрик", "eccentric"), ("Ролик", "roller"), ("Все детали", "all")):
            ttk.Button(sw, text=text, command=lambda w=what: self.export_sw(w)).pack(
                side=tk.LEFT, expand=True, fill=tk.X)
        self.btn = ttk.Button(panel, text="Старт анимации", command=self.toggle)
        self.btn.pack(fill=tk.X, pady=(10, 2))
        ttk.Button(panel, text="Сбросить угол", command=self.reset_phi).pack(fill=tk.X)

        self.info = tk.StringVar()
        ttk.Label(panel, textvariable=self.info, justify=tk.LEFT,
                  wraplength=300).pack(anchor="w", pady=10)
        self.redraw()

    # ---- виджеты
    def _slider(self, parent, text, key, init, lo, hi, step, typ=float, cmd=None, lock=True):
        var = tk.DoubleVar(value=init)
        self.vars[key] = var
        ttk.Label(parent, text=text).pack(anchor="w", pady=(6, 0))
        row = ttk.Frame(parent)
        row.pack(fill=tk.X)
        txt = tk.StringVar(value=f"{init:g}")
        var._txt = txt

        def touched():
            # ручная правка авто-параметра сразу фиксирует его
            if key in self.AUTO_KEYS and self.vars["auto"].get():
                self.vars[key + "_lock"].set(True)
            (cmd or self.redraw)()

        def on_scale(_v=None):
            val = round(var.get() / step) * step
            if typ is int:
                val = int(round(val))
            var.set(val)
            txt.set(f"{val:g}")
            touched()

        def on_entry(_e=None):
            try:
                val = float(txt.get().replace(",", "."))
            except ValueError:
                txt.set(f"{var.get():g}")
                return
            if typ is int:
                val = int(round(val))
            val = max(val, 0.0)
            if val == var.get():
                txt.set(f"{val:g}")
                return
            var.set(val)
            txt.set(f"{val:g}")
            touched()

        ttk.Scale(row, from_=lo, to=hi, variable=var, command=on_scale).pack(
            side=tk.LEFT, fill=tk.X, expand=True)
        ent = ttk.Entry(row, textvariable=txt, width=7, justify="right")
        ent.pack(side=tk.LEFT, padx=(4, 0))
        ent.bind("<Return>", on_entry)
        ent.bind("<FocusOut>", on_entry)
        if lock:
            lv = tk.BooleanVar(value=False)
            self.vars[key + "_lock"] = lv
            ttk.Checkbutton(row, text="фикс", variable=lv, command=self.redraw).pack(
                side=tk.LEFT, padx=(4, 0))

    def _set(self, key, val):
        self.vars[key].set(val)
        self.vars[key]._txt.set(f"{val:g}")

    def locked(self, key):
        return self.vars[key + "_lock"].get()

    def _on_auto(self):
        if not self.vars["auto"].get():
            return
        # включили авто: снимаем фиксацию с авто-параметров
        for k in self.AUTO_KEYS:
            self.vars[k + "_lock"].set(False)
        self.redraw()

    def preset_26(self):
        for k, v in (("n", 27), ("R", 70.0), ("rp", 6.0), ("e", 1.5), ("discs", 2), ("nh", 6)):
            self._set(k, v)
            self.vars[k + "_lock"].set(False)
        self.vars["auto"].set(True)
        self._on_auto()

    def export_dxf(self):
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(defaultextension=".dxf", initialfile="disc.dxf",
                                            filetypes=[("DXF", "*.dxf")])
        if not path:
            return
        lay = self.constrain()
        n, R, rp, e = self.params()
        if e * n >= R:
            return
        out = ["0", "SECTION", "2", "ENTITIES", "0", "POLYLINE", "8", "DISC", "66", "1", "70", "1"]
        for x, y in self.profile(n, R, rp, e):
            out += ["0", "VERTEX", "8", "DISC", "10", f"{x:.5f}", "20", f"{y:.5f}"]
        out += ["0", "SEQEND", "8", "DISC"]

        def circ(x, y, r, layer):
            return ["0", "CIRCLE", "8", layer, "10", f"{x:.5f}", "20", f"{y:.5f}", "40", f"{r:.5f}"]
        for i in range(lay["nh"]):
            a = 2 * math.pi * i / lay["nh"]
            out += circ(lay["Rh"] * math.cos(a), lay["Rh"] * math.sin(a), lay["ro"] + e, "HOLES")
        out += circ(0, 0, lay["bore"], "BORE")
        out += ["0", "ENDSEC", "0", "EOF"]
        with open(path, "w") as f:
            f.write("\n".join(out) + "\n")

    def export_sw(self, what):
        """what: 'disc' | 'housing' | 'eccentric' | 'roller' | 'all'"""
        import os
        from tkinter import messagebox
        try:
            import sw_export
        except ImportError as ex:
            messagebox.showerror("SolidWorks", f"Нужен pywin32 (pip install pywin32):\n{ex}")
            return
        lay = self.constrain()
        n, R, rp, e = self.params()
        if e * n >= R:
            messagebox.showerror("SolidWorks", "Профиль вырожден (e*N >= R).")
            return
        bore, thick = lay["bore"], self.vars["thick"].get()
        nd = int(self.vars["discs"].get())
        pitch = thick + 1.0                     # шаг дисков вдоль оси
        height = nd * pitch + 2.0               # толщина корпуса и длина роликов
        if bore - e <= 0.5:
            messagebox.showerror("SolidWorks", "Радиус отверстия диска слишком мал для эксцентрика (bore - e <= 0.5).")
            return
        out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sw_out")
        tag = f"N{n}_R{R:g}_rp{rp:g}_e{e:g}"
        holes = []
        for i in range(lay["nh"]):
            a = 2 * math.pi * i / lay["nh"]
            holes.append((lay["Rh"] * math.cos(a), lay["Rh"] * math.sin(a), lay["ro"] + e))
        holes.append((0.0, 0.0, bore))
        r_shaft = bore - e

        def disc():
            return sw_export.export_disc(self.profile(n, R, rp, e), holes, thick,
                                         os.path.join(out, f"disc_{tag}.SLDPRT"))

        def housing():
            return sw_export.export_housing(n, R, rp, HOUSING_K * R, height,
                                            os.path.join(out, f"housing_{tag}.SLDPRT"))

        def eccentric():
            return sw_export.export_eccentric(e, bore, r_shaft, 0.5 * r_shaft, nd, thick, pitch, 10.0,
                                              os.path.join(out, f"eccentric_{tag}.SLDPRT"))

        def roller():
            return sw_export.export_roller(rp, height, os.path.join(out, f"roller_{tag}.SLDPRT"))

        jobs = {"disc": disc, "housing": housing, "eccentric": eccentric, "roller": roller}
        todo = list(jobs) if what == "all" else [what]
        self.config(cursor="watch")
        self.update_idletasks()
        done = []
        try:
            for name in todo:
                done.append(jobs[name]())
        except Exception as ex:
            messagebox.showerror("SolidWorks", f"Не удалось выгрузить:\n{ex}")
        else:
            messagebox.showinfo("SolidWorks", "Созданы и сохранены:\n" + "\n".join(done))
        finally:
            self.config(cursor="")

    def _on_phi(self):
        self.phi = math.radians(self.vars["phi"].get())
        self.redraw()

    def reset_phi(self):
        self._set("phi", 0)
        self.phi = 0.0
        self.redraw()

    def toggle(self):
        self.running = not self.running
        self.btn.config(text="Стоп" if self.running else "Старт анимации")
        if self.running:
            self.tick()

    def tick(self):
        if not self.running:
            return
        self.phi = (self.phi + math.radians(self.vars["speed"].get())) % (2 * math.pi)
        self._set("phi", round(math.degrees(self.phi), 1))
        self.redraw()
        self.after(16, self.tick)

    # ---- расчёт согласованных размеров
    def params(self):
        return (int(self.vars["n"].get()), self.vars["R"].get(),
                self.vars["rp"].get(), self.vars["e"].get())

    def profile(self, n, R, rp, e):
        key = (n, R, rp, e)
        if self._cache_key != key:
            self._cache = disc_profile(n, R, rp, e)
            self._cache_key = key
        return self._cache

    def constrain(self):
        """Согласует параметры, чтобы детали не налезали друг на друга.
        Зафиксированные параметры не меняются - подстраиваются остальные."""
        v = self.vars
        L = self.locked
        n, R, rp, e = self.params()
        nh = int(v["nh"].get())
        warn = []

        # зафиксированные rp / e имеют приоритет: подгоняем R (или уменьшаем N)
        def r_min(nn):
            need = max(rp * 1.25 / math.sin(math.pi / nn), e * nn / 0.9, 5 * rp)
            return math.ceil(need * 10) / 10
        if (L("rp") or L("e")) and R < r_min(n):
            if not L("R"):
                R = r_min(n)
                self._set("R", R)
            elif not L("n"):
                while n > 3 and R < r_min(n):
                    n -= 1
                self._set("n", n)
        # незафиксированные rp / e урезаем: ролики не касаются, профиль не вырождается
        if not L("e"):
            e2 = min(e, 0.9 * R / n)
            if e2 != e:
                e = round(e2, 2)
                self._set("e", e)
        if not L("rp"):
            rp2 = min(rp, R * math.sin(math.pi / n) / 1.25, 0.2 * R)
            if rp2 != rp:
                rp = round(rp2, 1)
                self._set("rp", rp)
        if e * n >= R:
            warn.append("e*N >= R: профиль вырожден")
            e = 0.99 * R / n          # только для расчёта
        if rp > R * math.sin(math.pi / n):
            warn.append("ролики корпуса пересекаются")

        # радиус впадины диска
        root = min(math.hypot(x, y) for x, y in self.profile(n, R, rp, e)[::4])
        wall = max(0.8, 0.03 * R)
        Rh, ro, bore = v["Rh"].get(), v["ro"].get(), v["bore"].get()
        if v["auto"].get():
            if not L("Rh"):
                Rh = 0.72 * root
            if not L("ro"):
                ro = 0.06 * R
            if not L("bore"):
                bore = 0.28 * root
        for _ in range(4):
            if not L("ro"):
                ro = max(0.3, min(ro, Rh * math.sin(math.pi / nh) - e - wall / 2))
            if not L("Rh"):
                Rh = min(max(Rh, ro + e + wall + 2.0), root - wall - ro - e)
            # отверстия не помещаются рядом друг с другом - уменьшаем их число
            while not L("nh") and nh > 3 and Rh * math.sin(math.pi / nh) < e + 0.3 + wall / 2:
                nh -= 1
        free = Rh - ro - e - wall                 # от оси до отверстий под пальцы
        if not L("bore"):
            bore = max(0.5, min(bore, 0.8 * free))
        for k, val in (("Rh", Rh), ("ro", ro), ("bore", bore)):
            if not L(k):
                self._set(k, round(val, 1))
        Rh, ro, bore = v["Rh"].get(), v["ro"].get(), v["bore"].get()
        if nh != int(v["nh"].get()):
            self._set("nh", nh)

        free = Rh - ro - e - wall
        if Rh + ro + e > root - wall / 2:
            warn.append("пальцы выходят за впадины диска")
        if Rh * math.sin(math.pi / nh) < e + ro:
            warn.append("отверстия под пальцы пересекаются")
        if bore > free:
            warn.append("центральное отверстие задевает отверстия под пальцы")
        hub = bore + 0.9 * (free - bore) if free > bore else bore * 1.2
        return {"nh": nh, "Rh": Rh, "ro": ro, "bore": bore, "root": root,
                "hub": hub, "warn": warn}

    # ---- отрисовка
    def redraw(self):
        c = self.canvas
        c.delete("all")
        w, h = max(c.winfo_width(), 50), max(c.winfo_height(), 50)

        lay = self.constrain()
        n, R, rp, e = self.params()
        base = self.profile(n, R, rp, e)

        phi = self.phi
        nd = int(self.vars["discs"].get())
        nh, Rh, ro, bore = lay["nh"], lay["Rh"], lay["ro"], lay["bore"]
        # диск k: эксцентрик на угле phi + k*180°, поворот -(угол эксцентрика)/(N-1)
        discs = []
        for k in range(nd):
            ph = phi + k * math.pi
            th = -ph / (n - 1)
            discs.append((e * math.cos(ph), e * math.sin(ph), th,
                          rotate(base, th, e * math.cos(ph), e * math.sin(ph))))
        theta = -phi / (n - 1)          # поворот выходного звена
        pins = pin_centers(n, R)

        housing = self.vars["show_housing"].get()
        scale = 0.46 * min(w, h) / ((HOUSING_K * R) if housing else (R + rp + e))
        ox, oy = w / 2, h / 2

        def P(x, y):
            return ox + x * scale, oy - y * scale

        def circle(x, y, r, **kw):
            X, Y = P(x, y)
            c.create_oval(X - r * scale, Y - r * scale, X + r * scale, Y + r * scale, **kw)

        # корпус и ролики - под диском
        if housing:
            circle(0, 0, HOUSING_K * R, outline="#888888", fill="#d9d9d9", width=2)
            circle(0, 0, R + rp + 0.5, outline="#888888", fill="#ffffff")

        if self.vars["show_pins"].get():
            for px, py in pins:
                circle(px, py, rp, outline="#444444", fill="#e07070", width=1)

        if self.vars["show_base"].get():
            circle(0, 0, R, outline="#bbbbbb", dash=(4, 4))
            circle(0, 0, R * (n - 1) / n, outline="#dddddd", dash=(2, 4))
            c.create_line(*P(-R - rp, 0), *P(R + rp, 0), fill="#eeeeee")
            c.create_line(*P(0, -R - rp), *P(0, R + rp), fill="#eeeeee")

        if self.vars["show_dev"].get():
            flat = [v for p in base for v in P(*p)]
            c.create_polygon(flat, outline="#d08000", fill="", dash=(3, 3))

        if self.vars["show_disc"].get():
            fill = "#cfe3ff" if self.vars["show_fill"].get() else ""
            for k, (cx, cy, th, disc) in enumerate(reversed(discs)):
                flat = [v for p in disc for v in P(*p)]
                col = "#1f5fbf" if k == len(discs) - 1 else "#b0701f"
                c.create_polygon(flat, outline=col, fill=fill, width=2)
                for i in range(nh):
                    a = 2 * math.pi * i / nh + th
                    circle(cx + Rh * math.cos(a), cy + Rh * math.sin(a), ro + e, outline=col)
                circle(cx, cy, bore, outline=col)

        if self.vars["show_out"].get():
            for i in range(nh):
                a = 2 * math.pi * i / nh + theta
                circle(Rh * math.cos(a), Rh * math.sin(a), ro, outline="#222222", fill="#777777")

        if self.vars["show_hub"].get():
            hub = lay["hub"]
            mid = (bore + hub) / 2
            circle(0, 0, hub, outline="#1f3f9f", fill="#2f6fe0", width=2)
            for i in range(6):
                a = 2 * math.pi * i / 6 + theta
                circle(mid * math.cos(a), mid * math.sin(a),
                       0.2 * (hub - bore), outline="#8a6a10", fill="#d8a52a")
            circle(0, 0, bore, outline="#555555", fill="#ffffff")

        if self.vars["show_orbit"].get():
            cx, cy = discs[0][0], discs[0][1]
            circle(0, 0, e, outline="#2a9d2a")
            circle(cx, cy, 0.25 * max(rp, 1), outline="#2a9d2a", fill="#2a9d2a")
            c.create_line(*P(0, 0), *P(cx, cy), fill="#2a9d2a", width=2)
            circle(0, 0, 0.2 * max(rp, 1), outline="black", fill="black")

        clr = min(min_clearance(d[3], pins, rp) for d in discs)
        warn = "".join(f"\n! {t}" for t in lay["warn"])
        self.info.set(
            f"Зубцов диска: {n - 1}\n"
            f"Передаточное число: {n - 1}\n"
            f"Макс. e для профиля: {R / n:.2f} мм\n"
            f"Диаметр по вершинам: {2 * (R - rp + e):.2f} мм\n"
            f"Мин. зазор диск-ролик: {clr:+.3f} мм\n"
            f"Угол вала: {math.degrees(phi):.0f}°  "
            f"выход: {math.degrees(theta):.1f}°" + warn)


if __name__ == "__main__":
    App().mainloop()
