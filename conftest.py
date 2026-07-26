"""Kök conftest — pytest'in proje kökünü sys.path'e ekleyip `mio_core`'u bulmasını garanti eder."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
