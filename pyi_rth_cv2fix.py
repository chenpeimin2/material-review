import sys
import importlib
try:
    m = importlib.import_module('cv2.cv2')
    sys.modules['cv2'] = m
except Exception:
    pass
