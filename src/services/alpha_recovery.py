"""Recover RGBA pixels from aligned black/white composites, independent of capture."""
from PySide6.QtGui import QImage


def recover_alpha(black: QImage, white: QImage) -> QImage:
    """Recover foreground color and alpha from two opaque composite images.

    Inputs must have the same pixel bounds and unchanged foreground content,
    captured over pure black and pure white backgrounds, respectively.
    The returned image uses premultiplied RGBA and can be saved directly as PNG.
    This module does not acquire frames or manipulate windows.
    """
    if black.isNull() or white.isNull():
        raise ValueError("Alpha recovery requires two non-empty images.")
    if black.size() != white.size():
        raise ValueError("Alpha recovery requires matching image dimensions.")

    # Convert to a predictable byte order, independent of the source format.
    black = black.convertToFormat(QImage.Format.Format_RGBX8888)
    white = white.convertToFormat(QImage.Format.Format_RGBX8888)
    output = QImage(black.size(), QImage.Format.Format_RGBA8888_Premultiplied)
    if output.isNull():
        raise MemoryError("Could not allocate the alpha recovery image.")

    b, w, rgba = black.constBits(), white.constBits(), output.bits()
    b_stride = black.bytesPerLine()
    w_stride = white.bytesPerLine()
    out_stride = output.bytesPerLine()

    for y in range(black.height()):
        b_row, w_row, out_row = y * b_stride, y * w_stride, y * out_stride
        for x in range(0, black.width() * 4, 4):
            bi, wi, oi = b_row + x, w_row + x, out_row + x
            red, green, blue = b[bi], b[bi + 1], b[bi + 2]
            dr, dg, db = w[wi] - red, w[wi + 1] - green, w[wi + 2] - blue
            # W - B = 255 * (1 - alpha). Median tolerates small RGB rounding differences.
            delta = dr + dg + db - min(dr, dg, db) - max(dr, dg, db)
            alpha = max(0, min(255, 255 - delta))

            # The black composite already contains premultiplied foreground RGB.
            rgba[oi] = min(red, alpha)
            rgba[oi + 1] = min(green, alpha)
            rgba[oi + 2] = min(blue, alpha)
            rgba[oi + 3] = alpha

    output.setDevicePixelRatio(black.devicePixelRatio())
    return output
