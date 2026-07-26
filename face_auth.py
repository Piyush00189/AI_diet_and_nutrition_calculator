"""
face_auth.py
--------------
AI Diet Chart & Nutrition Calculator — Face Recognition Helpers

Core, UI-free helpers shared by:
  - face_login_page.py      — biometric login (identifies WHO is in
    front of the camera by comparing against every enrolled user).
  - face_capture_window.py  — the capture popup used by Settings'
    "Enable Biometric" flow to register a face for the logged-in user.

Uses OpenCV to talk to the webcam, and InsightFace (running on ONNX
Runtime) to detect a face and turn it into a 512-dimension embedding
that can be stored (as raw bytes, in the users.face_encoding column)
and compared later with cosine similarity.

Why InsightFace: it ships pretrained SCRFD (detection) + ArcFace
(recognition) ONNX models as a single pip-installable package with no
C++ toolchain required to build anything — just OpenCV, onnxruntime,
and insightface itself.

SETUP:
    pip install opencv-python onnxruntime insightface

    The first time get_face_app() runs, InsightFace downloads its
    "buffalo_l" model pack (~330 MB) to ~/.insightface/models — that
    requires an internet connection once; after that it's cached
    locally and works offline.

    If you have an NVIDIA GPU and want faster inference, you can
    additionally `pip install onnxruntime-gpu` (instead of the CPU
    onnxruntime package) and change PROVIDERS below to
    ["CUDAExecutionProvider", "CPUExecutionProvider"].

All three dependencies are optional at import time — every page that
uses this module checks dependencies_available() first and shows a
plain "install these packages" message instead of crashing if they're
missing, the same way diet_planner.py handles a missing
google-generativeai install.
"""

import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None

try:
    import onnxruntime
except ImportError:
    onnxruntime = None

try:
    from insightface.app import FaceAnalysis
except ImportError:
    FaceAnalysis = None

# "buffalo_l" is InsightFace's standard general-purpose model pack:
# SCRFD for detection, ArcFace (ResNet, 512-d embeddings) for
# recognition. Swap to "buffalo_s" for a smaller/faster (less
# accurate) pack if CPU inference speed becomes an issue.
MODEL_NAME = "buffalo_l"
PROVIDERS = ["CPUExecutionProvider"]
DETECTION_SIZE = (320, 320)  # smaller = faster on CPU, still plenty for a single face at webcam range

# Cosine similarity threshold for a match. Embeddings are L2-normalized
# (face.normed_embedding), so this is a plain dot product in [-1, 1];
# higher = more similar. 0.5 is a reasonable starting point for
# buffalo_l — tighten it (e.g. 0.6) if you see false accepts, loosen
# it (e.g. 0.4) if a legitimate user keeps failing to match.
DEFAULT_SIMILARITY_THRESHOLD = 0.5

_face_app = None  # lazily-initialized singleton — model load is slow, do it once


def dependencies_available() -> bool:
    return cv2 is not None and onnxruntime is not None and FaceAnalysis is not None


def dependencies_error_message() -> str:
    missing = []
    if cv2 is None:
        missing.append("opencv-python")
    if onnxruntime is None:
        missing.append("onnxruntime")
    if FaceAnalysis is None:
        missing.append("insightface")
    return (
        "Biometric login needs a couple of packages that aren't installed yet: "
        f"{', '.join(missing)}. Run: pip install {' '.join(missing)}"
    )


def get_face_app():
    """Returns the shared InsightFace FaceAnalysis instance, creating
    and preparing it on first use (this is what triggers the one-time
    model download). Raises RuntimeError on failure — e.g. no internet
    the first time, or a broken onnxruntime install."""
    global _face_app
    if not dependencies_available():
        raise RuntimeError(dependencies_error_message())

    if _face_app is None:
        try:
            app = FaceAnalysis(name=MODEL_NAME, providers=PROVIDERS)
            app.prepare(ctx_id=0, det_size=DETECTION_SIZE)
        except Exception as e:
            raise RuntimeError(
                "Couldn't load the InsightFace face model. If this is the "
                "first run, it needs an internet connection to download the "
                f"'{MODEL_NAME}' model pack (~330 MB) to ~/.insightface/models. "
                f"Underlying error: {e}"
            )
        _face_app = app
    return _face_app


def open_camera(index: int = 0):
    """Opens the default webcam. Returns a cv2.VideoCapture.
    Raises RuntimeError if dependencies are missing or the camera
    can't be opened."""
    if cv2 is None:
        raise RuntimeError(dependencies_error_message())
    cap = cv2.VideoCapture(index)
    if not cap.isOpened():
        cap.release()
        raise RuntimeError(
            "Couldn't access a webcam. Make sure one is connected and isn't "
            "already in use by another application."
        )
    return cap


def release_camera(cap) -> None:
    if cap is not None:
        cap.release()


def frame_to_rgb(frame):
    """cv2 frames are BGR; PIL (used for the on-screen preview) expects RGB."""
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)


def encode_face(frame) -> np.ndarray:
    """
    Detects a face in `frame` (a BGR OpenCV frame — InsightFace expects
    the same BGR layout cv2.VideoCapture/cv2.imread produce, so no
    color conversion is needed here) and returns its 512-dimension,
    L2-normalized ArcFace embedding as a float32 numpy array.

    Raises RuntimeError if dependencies/model are unavailable, if no
    face was found, or if more than one face was found — multiple
    faces make it ambiguous whose face is being registered or matched,
    so we ask for a clean single-person frame instead of guessing.
    """
    app = get_face_app()  # raises RuntimeError itself if unavailable

    faces = app.get(frame)

    if len(faces) == 0:
        raise RuntimeError(
            "No face detected. Face the camera directly in good lighting and try again."
        )
    if len(faces) > 1:
        raise RuntimeError("More than one face detected. Make sure only you are in frame.")

    return np.asarray(faces[0].normed_embedding, dtype=np.float32)


def encoding_to_bytes(encoding: np.ndarray) -> bytes:
    """Serializes a face embedding for storage in the database
    (users.face_encoding, a LONGBLOB)."""
    return np.asarray(encoding, dtype=np.float32).tobytes()


def bytes_to_encoding(data: bytes) -> np.ndarray:
    """Reverses encoding_to_bytes()."""
    return np.frombuffer(data, dtype=np.float32)


def best_match(encoding: np.ndarray, candidates: list, threshold: float = DEFAULT_SIMILARITY_THRESHOLD):
    """
    `candidates` is a list of dicts, each with at least 'email' and
    'face_encoding' (raw bytes, as returned by database.get_biometric_users()).

    Both `encoding` and every stored encoding are L2-normalized ArcFace
    embeddings, so cosine similarity is just their dot product. Returns
    the email of the closest match whose similarity is >= `threshold`,
    or None if nobody matches closely enough (or there are no
    candidates, or dependencies are missing).
    """
    if not dependencies_available() or not candidates:
        return None

    query = np.asarray(encoding, dtype=np.float32)

    best_email = None
    best_score = -1.0
    for candidate in candidates:
        known = bytes_to_encoding(candidate["face_encoding"])
        score = float(np.dot(query, known))
        if score > best_score:
            best_score = score
            best_email = candidate["email"]

    if best_score >= threshold:
        return best_email
    return None