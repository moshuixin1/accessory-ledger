import os
import struct
from io import BytesIO
from PIL import Image, ImageStat
import numpy as np

THUMB_SIZE = (300, 300)
PHASH_SIZE = (16, 16)
HIST_BINS = 64

# ---------------------------------------------------------------------------
#  Perceptual hash (pHash)
# ---------------------------------------------------------------------------
def _calculate_phash(img: Image.Image) -> list[int]:
    """Compute a simplified perceptual hash (pHash) as a list of bits."""
    img = img.convert("L").resize(PHASH_SIZE, Image.LANCZOS)
    pixels = np.array(img, dtype=np.float64)
    avg = pixels.mean()
    return [int(p > avg) for p in pixels.flatten()]


def _hamming(bits_a: list[int], bits_b: list[int]) -> int:
    return sum(1 for a, b in zip(bits_a, bits_b) if a != b)


# ---------------------------------------------------------------------------
#  Colour histogram (HSV)
# ---------------------------------------------------------------------------
def _calculate_histogram(img: Image.Image) -> np.ndarray:
    img = img.convert("HSV").resize((128, 128), Image.LANCZOS)
    h, s, v = img.split()
    hist_h = h.histogram() if hasattr(h, "histogram") else h.getdata()
    hist_s = s.histogram() if hasattr(s, "histogram") else s.getdata()
    hist_v = v.histogram() if hasattr(v, "histogram") else v.getdata()

    if isinstance(hist_h, np.ndarray):
        hist_h = hist_h.tolist()
        hist_s = hist_s.tolist()
        hist_v = hist_v.tolist()

    bins = HIST_BINS
    h_binned = _bin_histogram(hist_h, 256, bins)
    s_binned = _bin_histogram(hist_s, 256, bins)
    v_binned = _bin_histogram(hist_v, 256, bins)
    return np.array(h_binned + s_binned + v_binned, dtype=np.float64)


def _bin_histogram(raw: list[int], src_bins: int, dst_bins: int) -> list[float]:
    """Downsample a histogram from src_bins to dst_bins."""
    result = [0.0] * dst_bins
    group = src_bins // dst_bins
    for i in range(dst_bins):
        start = i * group
        end = start + group if i < dst_bins - 1 else src_bins
        result[i] = sum(raw[start:end])
    total = sum(result)
    return [v / total for v in result] if total > 0 else result


def _histogram_cosine(a: np.ndarray, b: np.ndarray) -> float:
    dot = float(np.dot(a, b))
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    return dot / (na * nb) if na * nb > 0 else 0.0


# ---------------------------------------------------------------------------
#  Public API
# ---------------------------------------------------------------------------

class ImageMatcher:
    """Stores pre-computed hashes for all catalog items and ranks matches."""

    def __init__(self):
        self._items: dict[int, tuple[list[int], np.ndarray]] = {}

    def add(self, item_id: int, img_path: str) -> None:
        ph, hist = self._compute(img_path)
        self._items[item_id] = (ph, hist)

    def remove(self, item_id: int) -> None:
        self._items.pop(item_id, None)

    def update(self, item_id: int, img_path: str) -> None:
        self.remove(item_id)
        self.add(item_id, img_path)

    def rebuild(self, items: list[tuple[int, str]]) -> None:
        """Rebuild the index from a list of (item_id, img_path) tuples."""
        self._items.clear()
        for item_id, path in items:
            try:
                self.add(item_id, path)
            except Exception:
                continue  # skip missing / corrupted files

    def match(self, img_path: str, top_k: int = 5) -> list[tuple[int, float]]:
        ph, hist = self._compute(img_path)
        if ph is None:
            return []

        results: list[tuple[int, float]] = []
        for item_id, (cand_ph, cand_hist) in self._items.items():
            dist = _hamming(ph, cand_ph)
            sim_ph = max(0.0, 1.0 - dist / len(ph))
            sim_hist = _histogram_cosine(hist, cand_hist)
            score = 0.55 * sim_ph + 0.45 * sim_hist
            results.append((item_id, round(score, 4)))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    @staticmethod
    def _compute(img_path: str) -> tuple[list[int] | None, np.ndarray | None]:
        try:
            img = Image.open(img_path).convert("RGB")
            ph = _calculate_phash(img)
            hist = _calculate_histogram(img)
            return ph, hist
        except Exception:
            return None, None


# ---------------------------------------------------------------------------
#  Thumbnail helpers
# ---------------------------------------------------------------------------

def make_thumbnail(src_path: str, dest_path: str, size: tuple[int, int] = THUMB_SIZE) -> str:
    """Create a thumbnail and return the destination path."""
    img = Image.open(src_path).convert("RGB")
    img.thumbnail(size, Image.LANCZOS)
    img.save(dest_path, "JPEG", quality=85)
    return dest_path
