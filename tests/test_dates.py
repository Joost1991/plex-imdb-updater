import unittest
from datetime import datetime, timedelta

from utils.util import is_short_treshold


class MyTestCase(unittest.TestCase):
    def test_is_short_threshold(self):
        self.assertTrue(is_short_treshold(datetime.now()))
        self.assertTrue(is_short_treshold(datetime.now() + timedelta(days=5)))
        self.assertFalse(is_short_treshold(datetime.now() - timedelta(days=-15)))


if __name__ == '__main__':
    unittest.main()
