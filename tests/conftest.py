import sys
from pathlib import Path

# Testlerin proje kökündeki modülleri bulabilmesi için.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
