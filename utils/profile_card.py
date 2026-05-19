# =========================================================
#                    utils/profile_card.py
# =========================================================

from __future__ import annotations

from io import BytesIO
from typing import Optional, Tuple

from PIL import (
    Image,
    ImageDraw,
    ImageFont,
    ImageFilter,
    ImageOps,
)


# =========================================================
#                         HELPERS
# =========================================================

def _clamp(x):
    return max(0, min(255, int(x)))


def _mix(a, b, t):

    return tuple(
        _clamp(x * (1 - t) + y * t)
        for x, y in zip(a, b)
    )


def _light(rgb, amount=0.2):
    return _mix(rgb, (255, 255, 255), amount)


def _dark(rgb, amount=0.2):
    return _mix(rgb, (0, 0, 0), amount)


def _load_font(size, bold=False):

    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",

        "DejaVuSans-Bold.ttf"
        if bold
        else "DejaVuSans.ttf",
    ]

    for path in paths:

        try:
            return ImageFont.truetype(path, size=size)
        except Exception:
            pass

    return ImageFont.load_default()


def _gradient(size, top, bottom):

    w, h = size

    img = Image.new("RGBA", size)

    draw = ImageDraw.Draw(img)

    for y in range(h):

        t = y / h

        color = _mix(top, bottom, t)

        draw.line((0, y, w, y), fill=color)

    return img


def _avatar(avatar_bytes, size=240):

    avatar = Image.open(
        BytesIO(avatar_bytes)
    ).convert("RGBA")

    avatar = ImageOps.fit(
        avatar,
        (size, size),
        Image.LANCZOS,
    )

    mask = Image.new(
        "L",
        (size, size),
        0,
    )

    md = ImageDraw.Draw(mask)

    md.ellipse(
        (0, 0, size, size),
        fill=255,
    )

    out = Image.new(
        "RGBA",
        (size, size),
        (0, 0, 0, 0),
    )

    out.paste(avatar, (0, 0), mask)

    return out


def _progress(
    draw,
    x,
    y,
    w,
    h,
    value,
    color,
):

    value = max(0, min(1, value))

    # background
    draw.rounded_rectangle(
        (x, y, x + w, y + h),
        radius=h // 2,
        fill=(26, 30, 40),
    )

    pw = int(w * value)

    if pw > 0:

        glow = (
            min(255, color[0] + 40),
            min(255, color[1] + 40),
            min(255, color[2] + 40),
        )

        draw.rounded_rectangle(
            (x, y, x + pw, y + h),
            radius=h // 2,
            fill=glow,
        )

        draw.rounded_rectangle(
            (
                x + 2,
                y + 2,
                x + pw - 2,
                y + h - 2,
            ),
            radius=h // 2,
            fill=color,
        )


def _center_text(
    draw,
    text,
    font,
    x1,
    y1,
    x2,
    y2,
    fill,
):

    bbox = draw.textbbox(
        (0, 0),
        text,
        font=font,
    )

    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]

    tx = x1 + ((x2 - x1) - tw) / 2
    ty = y1 + ((y2 - y1) - th) / 2 - 1

    draw.text(
        (tx, ty),
        text,
        font=font,
        fill=fill,
    )


# =========================================================
#                    MAIN FUNCTION
# =========================================================

def build_profile_card_png(
    *,
    username: str,
    avatar_bytes: Optional[bytes],

    accent_rgb=(88, 101, 242),

    points=0,

    wins=0,
    losses=0,

    zxc_5=1000,
    rank_5="UNRANKED",
    calib_5=0,

    zxc_1=1000,
    rank_1="UNRANKED",
    calib_1=0,

    kda_ratio=0.0,

    clan_tag="",
    clan_name="",
):

    # =====================================================
    #                         BASE
    # =====================================================

    W = 1900
    H = 720

    accent = accent_rgb

    base = _gradient(
        (W, H),
        _dark(accent, 0.72),
        (5, 7, 12),
    )

    # =====================================================
    #                         GLOW
    # =====================================================

    glow = Image.new(
        "RGBA",
        (W, H),
        (0, 0, 0, 0),
    )

    gd = ImageDraw.Draw(glow)

    gd.ellipse(
        (-250, -100, 650, 780),
        fill=(*accent, 90),
    )

    gd.ellipse(
        (1300, 50, 2100, 900),
        fill=(*_light(accent, 0.2), 60),
    )

    glow = glow.filter(
        ImageFilter.GaussianBlur(140)
    )

    base.alpha_composite(glow)

    # =====================================================
    #                      MAIN PANEL
    # =====================================================

    panel = Image.new(
        "RGBA",
        (W, H),
        (0, 0, 0, 0),
    )

    pd = ImageDraw.Draw(panel)

    pd.rounded_rectangle(
        (45, 45, W - 45, H - 45),
        radius=48,
        fill=(14, 16, 24, 225),
        outline=(*_light(accent, 0.12), 80),
        width=2,
    )

    # glossy top
    pd.rounded_rectangle(
        (
            48,
            48,
            W - 48,
            125,
        ),
        radius=48,
        fill=(255, 255, 255, 8),
    )

    panel = panel.filter(
        ImageFilter.GaussianBlur(0.3)
    )

    base.alpha_composite(panel)

    draw = ImageDraw.Draw(base)

    # =====================================================
    #                         FONTS
    # =====================================================

    username_font = _load_font(70, True)

    clan_font = _load_font(30)

    stat_font = _load_font(42, True)

    small_font = _load_font(24)

    label_font = _load_font(22)

    rank_font = _load_font(52, True)

    rank_small = _load_font(40, True)

    # =====================================================
    #                        AVATAR
    # =====================================================

    AV_SIZE = 250

    AV_X = 90
    AV_Y = 225

    if avatar_bytes:

        avatar = _avatar(
            avatar_bytes,
            AV_SIZE,
        )

        aglow = Image.new(
            "RGBA",
            (W, H),
            (0, 0, 0, 0),
        )

        ad = ImageDraw.Draw(aglow)

        ad.ellipse(
            (
                AV_X - 25,
                AV_Y - 25,
                AV_X + AV_SIZE + 25,
                AV_Y + AV_SIZE + 25,
            ),
            fill=(*accent, 150),
        )

        aglow = aglow.filter(
            ImageFilter.GaussianBlur(45)
        )

        base.alpha_composite(aglow)

        base.paste(
            avatar,
            (AV_X, AV_Y),
            avatar,
        )

        draw.ellipse(
            (
                AV_X - 5,
                AV_Y - 5,
                AV_X + AV_SIZE + 5,
                AV_Y + AV_SIZE + 5,
            ),
            outline=_light(accent, 0.22),
            width=5,
        )

    # =====================================================
    #                       USER INFO
    # =====================================================

    draw.text(
        (400, 135),
        username[:20],
        font=username_font,
        fill=(255, 255, 255),
    )

    clan = f"[{clan_tag}] {clan_name}".strip()

    draw.text(
        (405, 225),
        clan[:38],
        font=clan_font,
        fill=(180, 190, 210),
    )

    draw.line(
        (400, 295, 1020, 295),
        fill=(255, 255, 255, 22),
        width=2,
    )

    # =====================================================
    #                         STATS
    # =====================================================

    matches = wins + losses

    winrate = int(
        (wins / max(1, matches)) * 100
    )

    stats = [
        ("POINTS", str(points)),
        ("MATCHES", str(matches)),
        ("WINRATE", f"{winrate}%"),
        ("KDA", f"{kda_ratio:.2f}"),
    ]

    sx = 400
    sy = 355

    card_w = 280
    card_h = 115

    gap_x = 30
    gap_y = 30

    for i, (title, value) in enumerate(stats):

        x = sx + (i % 2) * (card_w + gap_x)

        y = sy + (i // 2) * (card_h + gap_y)

        draw.rounded_rectangle(
            (
                x,
                y,
                x + card_w,
                y + card_h,
            ),
            radius=28,
            fill=(24, 28, 38, 210),
            outline=(255, 255, 255, 18),
        )

        draw.text(
            (x + 24, y + 16),
            title,
            font=label_font,
            fill=(155, 165, 185),
        )

        draw.text(
            (x + 24, y + 52),
            value,
            font=stat_font,
            fill=(255, 255, 255),
        )

    # =====================================================
    #                    RIGHT PANEL
    # =====================================================

    rx = 1130
    ry = 85

    rw = 690
    rh = 550

    draw.rounded_rectangle(
        (
            rx,
            ry,
            rx + rw,
            ry + rh,
        ),
        radius=42,
        fill=(20, 23, 34, 225),
        outline=(255, 255, 255, 18),
    )

    draw.text(
        (rx + 45, ry + 35),
        "COMPETITIVE",
        font=small_font,
        fill=(165, 175, 195),
    )

    # =====================================================
    #                         5X5
    # =====================================================

    y1 = ry + 95

    draw.text(
        (rx + 45, y1),
        "5x5",
        font=rank_font,
        fill=_light(accent, 0.2),
    )

    draw.text(
        (rx + 45, y1 + 72),
        rank_5[:16],
        font=rank_font,
        fill=(255, 255, 255),
    )

    draw.text(
        (rx + 45, y1 + 150),
        f"ZXC {zxc_5}",
        font=stat_font,
        fill=(220, 225, 240),
    )

    # calibration box
    box1_y = y1 + 230

    draw.rounded_rectangle(
        (
            rx + 40,
            box1_y,
            rx + rw - 40,
            box1_y + 92,
        ),
        radius=24,
        fill=(18, 20, 30),
    )

    draw.text(
        (rx + 65, box1_y + 16),
        "Calibration Progress",
        font=small_font,
        fill=(170, 180, 200),
    )

    _progress(
        draw,
        rx + 65,
        box1_y + 50,
        470,
        22,
        calib_5 / 5,
        accent,
    )

    _center_text(
        draw,
        f"{calib_5}/5",
        label_font,
        rx + 550,
        box1_y + 40,
        rx + 620,
        box1_y + 72,
        (255, 255, 255),
    )

    # divider
    divider_y = box1_y + 140

    draw.line(
        (
            rx + 45,
            divider_y,
            rx + rw - 45,
            divider_y,
        ),
        fill=(255, 255, 255, 18),
        width=2,
    )

    # =====================================================
    #                         1X1
    # =====================================================

    y2 = divider_y + 38

    draw.text(
        (rx + 45, y2),
        "1x1",
        font=rank_font,
        fill=_light(accent, 0.2),
    )

    draw.text(
        (rx + 165, y2 + 10),
        rank_1[:18],
        font=rank_small,
        fill=(255, 255, 255),
    )

    draw.text(
        (rx + 45, y2 + 82),
        f"ZXC {zxc_1}",
        font=stat_font,
        fill=(220, 225, 240),
    )

    box2_y = y2 + 165

    draw.rounded_rectangle(
        (
            rx + 40,
            box2_y,
            rx + rw - 40,
            box2_y + 92,
        ),
        radius=24,
        fill=(18, 20, 30),
    )

    draw.text(
        (rx + 65, box2_y + 16),
        "Calibration Progress",
        font=small_font,
        fill=(170, 180, 200),
    )

    _progress(
        draw,
        rx + 65,
        box2_y + 50,
        470,
        22,
        calib_1 / 5,
        _light(accent, 0.12),
    )

    _center_text(
        draw,
        f"{calib_1}/5",
        label_font,
        rx + 550,
        box2_y + 40,
        rx + 620,
        box2_y + 72,
        (255, 255, 255),
    )

    # =====================================================
    #                         EXPORT
    # =====================================================

    out = BytesIO()

    base.save(
        out,
        format="PNG",
        quality=100,
    )

    out.seek(0)

    return out


# =========================================================
#                   BANNER (NO TEXT)
# =========================================================

def build_profile_banner_png(
    *,
    username: str,
    avatar_bytes: Optional[bytes],
    accent_rgb=(88, 101, 242),
    points=0,
    wins=0,
    losses=0,
    zxc_5=1000,
    rank_5="UNRANKED",
    calib_5=0,
    zxc_1=1000,
    rank_1="UNRANKED",
    calib_1=0,
    kda_ratio=0.0,
    clan_tag="",
    clan_name="",
):
    """
    Большой “премиум” баннер без текста на самой картинке.
    Всё текстовое (ник/ранги/статы) показывайте в embed полях — тогда ничего не “прыгает”.
    """

    # Длиннее по X, но не слишком по Y (чтобы Discord выглядело как баннер)
    W = 1800
    H = 420
    accent = accent_rgb

    # --- фон ---
    base = _gradient((W, H), _dark(accent, 0.72), (5, 7, 12))

    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((-260, -180, 780, 660), fill=(*accent, 85))
    gd.ellipse((W - 760, -240, W + 260, 720), fill=(*_light(accent, 0.22), 70))
    glow = glow.filter(ImageFilter.GaussianBlur(120))
    base.alpha_composite(glow)

    # мягкий паттерн слэшей
    pat = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    pd = ImageDraw.Draw(pat)
    for x in range(-H, W, 42):
        pd.line((x, 0, x + H, H), fill=(*_light(accent, 0.32), 14), width=12)
    base.alpha_composite(pat)

    # --- панель ---
    panel = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    pdraw = ImageDraw.Draw(panel)
    m = 22
    pdraw.rounded_rectangle(
        (m, m, W - m, H - m),
        radius=34,
        fill=(14, 16, 24, 220),
        outline=(*_light(accent, 0.12), 80),
        width=2,
    )
    # glossy top
    pdraw.rounded_rectangle((m + 3, m + 3, W - m - 3, m + 70), radius=34, fill=(255, 255, 255, 9))
    panel = panel.filter(ImageFilter.GaussianBlur(0.3))
    base.alpha_composite(panel)

    draw = ImageDraw.Draw(base)

    # --- аватар (фиксированные координаты) ---
    AV_SIZE = 160
    AV_X = 62
    AV_Y = (H - AV_SIZE) // 2

    # glow под аватаром
    aglow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ad = ImageDraw.Draw(aglow)
    ad.ellipse((AV_X - 26, AV_Y - 26, AV_X + AV_SIZE + 26, AV_Y + AV_SIZE + 26), fill=(*accent, 140))
    aglow = aglow.filter(ImageFilter.GaussianBlur(42))
    base.alpha_composite(aglow)

    if avatar_bytes:
        try:
            avatar = _avatar(avatar_bytes, AV_SIZE)
            base.paste(avatar, (AV_X, AV_Y), avatar)
        except Exception:
            pass
    draw.ellipse((AV_X - 4, AV_Y - 4, AV_X + AV_SIZE + 4, AV_Y + AV_SIZE + 4), outline=_light(accent, 0.22), width=5)

    # --- правый блок (2 режима) без текста ---
    rx = W - 680
    ry = m + 34
    rw = 610
    rh = H - (m + 34) * 2

    draw.rounded_rectangle((rx, ry, rx + rw, ry + rh), radius=32, fill=(20, 23, 34, 225), outline=(255, 255, 255, 18))

    # две одинаковые зоны: сверху 5x5, снизу 1x1
    inner_pad = 26
    zone_h = (rh - inner_pad * 3) // 2
    zone_w = rw - inner_pad * 2
    z1 = (rx + inner_pad, ry + inner_pad, zone_w, zone_h)
    z2 = (rx + inner_pad, ry + inner_pad * 2 + zone_h, zone_w, zone_h)

    def _zone(x, y, w, h, *, col, calib):
        draw.rounded_rectangle((x, y, x + w, y + h), radius=26, fill=(18, 20, 30, 200), outline=(*_light(col, 0.10), 60))
        # “иконка” круга слева
        cx, cy = x + 62, y + h // 2
        draw.ellipse((cx - 30, cy - 30, cx + 30, cy + 30), fill=(*_dark(col, 0.15), 230))
        draw.ellipse((cx - 20, cy - 20, cx + 20, cy + 20), fill=(*col, 235))
        # progress bar (калибровка)
        bar_x = x + 120
        bar_y = y + (h // 2) - 10
        _progress(draw, bar_x, bar_y, w - 160, 20, (calib / 5), col)

    _zone(*z1, col=accent, calib=int(calib_5 or 0))
    _zone(*z2, col=_light(accent, 0.12), calib=int(calib_1 or 0))

    out = BytesIO()
    base.save(out, format="PNG", quality=100)
    out.seek(0)
    return out
