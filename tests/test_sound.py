import os
import struct
import tempfile
import unittest
import wave

import numpy as np

from src.relativity import beta_at
from src.sound import RATE, beta, write_wav

TITLE, FLIGHT, END = 2.0, 15.0, 2.5


class SoundTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory()
        cls.path = os.path.join(cls.dir.name, "bed.wav")
        write_wav(cls.path, TITLE, FLIGHT, END)
        with wave.open(cls.path, "rb") as w:
            cls.fmt = (w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getnframes())
            raw = w.readframes(w.getnframes())
        cls.x = np.array(struct.unpack("<%dh" % (len(raw) // 2), raw)) / 32768.0

    @classmethod
    def tearDownClass(cls):
        cls.dir.cleanup()

    def test_format_and_length(self):
        rate, channels, width, n = self.fmt
        self.assertEqual((rate, channels, width), (48000, 1, 2))
        self.assertAlmostEqual(n / rate, TITLE + FLIGHT + END, delta=0.001)

    def test_level_no_clipping_no_dc(self):
        self.assertLessEqual(np.abs(self.x).max(), 0.89)
        self.assertGreater(np.abs(self.x).max(), 0.3)
        self.assertLess(abs(self.x.mean()), 0.005)

    def test_rises_with_the_flight(self):
        a = int(TITLE * RATE)
        first = np.sqrt(np.mean(self.x[a:a + RATE] ** 2))
        b = int((TITLE + FLIGHT) * RATE)
        last = np.sqrt(np.mean(self.x[b - RATE:b] ** 2))
        self.assertGreater(last, first)

    def test_fades_in_and_out(self):
        n = int(0.05 * RATE)
        self.assertLess(np.abs(self.x[:n]).max(), 0.02)
        self.assertLess(np.abs(self.x[-n:]).max(), 0.02)

    def test_beta_matches_the_numpy_curve(self):
        for t in (-1.0, 0.0, 0.4, 3.3, 7.5, 12.0, 14.96, 15.0, 20.0):
            self.assertAlmostEqual(beta(t), float(beta_at(t)), delta=1e-9)


if __name__ == "__main__":
    unittest.main()
