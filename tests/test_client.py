import unittest

from podme_api.client import PodMeClient

podme_client = PodMeClient("example@example.com", "example")


class TestPodMeClient(unittest.TestCase):
    def test_login(self):
        self.assertEqual(1, 1)


if __name__ == '__main__':
    unittest.main()
