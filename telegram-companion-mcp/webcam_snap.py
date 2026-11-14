import time
import tempfile
from pathlib import Path
from typing import Tuple, Optional

def take_webcam_photo() -> Tuple[bool, Optional[Path], str]:
    """
    Captures a single photo from the laptop's front webcam.
    Returns: (success, photo_path, message)
    """
    try:
        import cv2

        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(0)

        if not cap.isOpened():
            return False, None, "❌ Laptop webcam is not available or is currently in use by another app (Zoom, Teams, etc.)."

        # Allow camera auto-exposure to adjust
        time.sleep(0.3)
        ret, frame = cap.read()
        cap.release()

        if not ret or frame is None:
            return False, None, "❌ Could not grab image frame from camera."

        out_path = Path(tempfile.gettempdir()) / f"webcam_{int(time.time())}.jpg"
        cv2.imwrite(str(out_path), frame)

        if out_path.exists() and out_path.stat().st_size > 1000:
            return True, out_path, "📷 *Desk / Webcam Photo Captured!*"
        else:
            return False, None, "❌ Saved webcam photo was empty."

    except ImportError:
        return False, None, "❌ opencv-python is not installed."
    except Exception as e:
        return False, None, f"❌ Webcam capture error: {e}"
