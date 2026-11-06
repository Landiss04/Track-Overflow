import sys
import unittest

from utils.process_speed import keep_full_speed


class KeepFullSpeedTest(unittest.TestCase):
    def test_accepted_on_windows_and_a_no_op_elsewhere(self) -> None:
        self.assertEqual(keep_full_speed(), sys.platform == "win32")


if __name__ == "__main__":
    unittest.main()
