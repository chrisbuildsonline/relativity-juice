import os
import shutil
import tempfile
import unittest

from src.status import wait


class WaitTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.log = os.path.join(self.dir, "render.log")
        self.pid = os.path.join(self.dir, "render.pid")

    def frames(self, n):
        for f in range(1, n + 1):
            open(os.path.join(self.dir, "%04d.png" % f), "w").close()

    def pidfile(self, pid):
        with open(self.pid, "w") as fh:
            fh.write(str(pid))

    def no_sleep(self, s):
        raise AssertionError("should not have slept")

    def test_complete_exits_0_without_sleeping(self):
        self.frames(360)
        self.pidfile(os.getpid())
        code, text = wait(self.dir, self.log, self.pid, sleep=self.no_sleep)
        self.assertEqual(code, 0)
        self.assertIn("360/360", text)

    def test_dead_process_and_incomplete_exits_1(self):
        self.frames(5)
        self.pidfile(999999999)
        code, text = wait(self.dir, self.log, self.pid, sleep=self.no_sleep)
        self.assertEqual(code, 1)
        self.assertIn("5/360", text)
        self.assertIn("not running", text)

    def test_polls_every_30s_until_frames_complete(self):
        self.frames(358)
        self.pidfile(os.getpid())
        naps = []

        def sleep(s):
            naps.append(s)
            if len(naps) == 2:
                self.frames(360)

        code, _ = wait(self.dir, self.log, self.pid, sleep=sleep)
        self.assertEqual((code, naps), (0, [30, 30]))

    def test_gives_up_after_max_minutes_with_exit_2(self):
        self.frames(5)
        self.pidfile(os.getpid())
        now = [0.0]

        def sleep(s):
            now[0] += s

        code, text = wait(self.dir, self.log, self.pid, max_min=2, sleep=sleep, clock=lambda: now[0])
        self.assertEqual(code, 2)
        self.assertIn("5/360", text)
        self.assertGreaterEqual(now[0], 120)
        self.assertLess(now[0], 180)
