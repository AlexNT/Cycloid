"""Выгрузка деталей циклоидального редуктора в SOLIDWORKS через COM API (pywin32).

Детали: звёздочка (диск), корпус с канавками под ролики, эксцентрик, ролик.
SOLIDWORKS должен быть установлен (запускается сам, если закрыт). Все размеры - в мм.
Каждая деталь строится в своей системе координат, ось детали = нормаль плоскости "Спереди".
"""
import math
import os

import pythoncom
import win32com.client
from win32com.client import VARIANT

SW_DEFAULT_TEMPLATE_PART = 8     # swDefaultTemplatePart
SW_END_MID_PLANE = 6             # swEndCondMidPlane
SW_REF_PLANE_DISTANCE = 8        # swRefPlaneReferenceConstraint_Distance
SW_REF_PLANE_FLIP = 256          # swRefPlaneReferenceConstraint_OptionFlip
M = 0.001                        # API работает в метрах


def _arr(values):
    return VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [float(v) for v in values])


def _null():
    return VARIANT(pythoncom.VT_DISPATCH, None)


def _connect():
    try:
        app = win32com.client.GetActiveObject("SldWorks.Application")
    except pythoncom.com_error:
        app = win32com.client.Dispatch("SldWorks.Application")
    app.Visible = True
    return app


class _Part:
    """Новая деталь SOLIDWORKS и набор операций эскиз / вытяжка."""

    def __init__(self):
        self.app = _connect()
        template = self.app.GetUserPreferenceStringValue(SW_DEFAULT_TEMPLATE_PART)
        self.model = self.app.NewDocument(template, 0, 0, 0)
        if self.model is None:
            raise RuntimeError("не удалось создать деталь (нет шаблона детали по умолчанию?)")
        self.sk = self.model.SketchManager
        self.front = self._front_plane()

    def _front_plane(self):
        """Первая плоскость в дереве = 'Спереди' (имя зависит от языка интерфейса)."""
        feat = self.model.FirstFeature
        while feat is not None:
            if feat.GetTypeName2 == "RefPlane":
                return feat
            feat = feat.GetNextFeature
        raise RuntimeError("не найдена плоскость 'Спереди'")

    def plane(self, offset_mm=0.0):
        """Плоскость, параллельная 'Спереди', со смещением по оси детали."""
        if abs(offset_mm) < 1e-9:
            return self.front
        self.front.Select2(False, 0)
        flag = SW_REF_PLANE_DISTANCE | (SW_REF_PLANE_FLIP if offset_mm < 0 else 0)
        feat = self.model.FeatureManager.InsertRefPlane(flag, abs(offset_mm) * M, 0, 0, 0, 0)
        if feat is None:
            raise RuntimeError("не удалось создать вспомогательную плоскость")
        return feat

    def begin(self, plane):
        plane.Select2(False, 0)
        self.sk.InsertSketch(True)
        self.sk.AddToDB = True          # без авто-привязок: точки ставятся ровно как заданы

    def circle(self, x, y, r):
        self.sk.CreateCircleByRadius(x * M, y * M, 0.0, r * M)

    def spline_closed(self, pts):
        flat = []
        for x, y in pts:
            flat += [x * M, y * M, 0.0]
        flat += [pts[0][0] * M, pts[0][1] * M, 0.0]
        if self.sk.CreateSpline2(_arr(flat), True) is None:
            raise RuntimeError("не удалось построить сплайн профиля")

    def arc(self, center, p1, p2):
        """Дуга против часовой стрелки от p1 до p2 вокруг center."""
        s = self.sk.CreateArc(center[0] * M, center[1] * M, 0.0, p1[0] * M, p1[1] * M, 0.0,
                              p2[0] * M, p2[1] * M, 0.0, 1)
        if s is None:
            raise RuntimeError("не удалось построить дугу")

    def extrude_mid(self, depth_mm, merge=False):
        self.sk.AddToDB = False
        feat = self.model.FeatureManager.FeatureExtrusion2(
            True, False, False, SW_END_MID_PLANE, 0, depth_mm * M, 0.0,
            False, False, False, False, 0.0174532925199433, 0.0174532925199433,
            False, False, False, False, merge, True, True, 0, 0, False)
        if feat is None:
            raise RuntimeError("не удалось выполнить вытяжку")

    def finish(self, save_path):
        self.model.ViewZoomtofit2()
        if not save_path:
            return None
        save_path = os.path.abspath(save_path)
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        err = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        warn = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        if not self.model.Extension.SaveAs(save_path, 0, 1, _null(), err, warn):
            raise RuntimeError(f"не удалось сохранить {save_path} (код {err.value})")
        return save_path


# ---------------------------------------------------------------- детали
def export_disc(profile, holes, thickness, save_path=None, decimate=3):
    """Звёздочка: profile [(x, y)] - замкнутый контур, holes [(x, y, r)]."""
    p = _Part()
    p.begin(p.front)
    p.spline_closed(profile[::decimate])
    for x, y, r in holes:
        p.circle(x, y, r)
    p.extrude_mid(thickness)
    return p.finish(save_path)


def export_housing(n, R, rp, r_out, height, save_path=None):
    """Корпус: внешний круг r_out, внутри - контур из дуг радиуса R и полуканавок под ролики."""
    p = _Part()
    p.begin(p.front)
    p.circle(0, 0, r_out)
    d = 2 * math.asin(rp / (2 * R))                # угол пересечения канавки с окружностью R
    step = 2 * math.pi / n

    def pt(a):
        return (R * math.cos(a), R * math.sin(a))
    for i in range(n):
        a = i * step
        c = pt(a)
        p.arc(c, pt(a - d), pt(a + d))              # канавка (выпуклая наружу)
        p.arc((0, 0), pt(a + d), pt(a + step - d))  # стенка между канавками
    p.extrude_mid(height)
    return p.finish(save_path)


def export_eccentric(e, r_cam, r_shaft, r_hole, discs, thickness, pitch, journal, save_path=None):
    """Эксцентрик: вал r_shaft с центральным отверстием r_hole и шейками r_cam под диски.
    Шейка k смещена на e * (cos(k*180°), sin(k*180°)) и стоит на высоте (k - (discs-1)/2) * pitch."""
    p = _Part()
    total = discs * pitch + 2 * journal
    p.begin(p.front)
    p.circle(0, 0, r_shaft)
    p.circle(0, 0, r_hole)
    p.extrude_mid(total)
    for k in range(discs):
        z = (k - (discs - 1) / 2) * pitch
        a = k * math.pi
        plane = p.plane(z)
        p.begin(plane)
        p.circle(e * math.cos(a), e * math.sin(a), r_cam)
        p.circle(0, 0, r_hole)
        p.extrude_mid(thickness, merge=True)
    return p.finish(save_path)


def export_roller(rp, length, save_path=None):
    """Ролик корпуса - цилиндр радиуса rp."""
    p = _Part()
    p.begin(p.front)
    p.circle(0, 0, rp)
    p.extrude_mid(length)
    return p.finish(save_path)
