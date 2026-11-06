import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('notification_qa', ROOT / 'tools/notification_qa.py')
qa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qa)


class NotificationQATests(unittest.TestCase):
    def test_blank_body_is_followed_by_another_message(self):
        cases = list(qa.CASES)
        empty = next(i for i, row in enumerate(cases) if not row[2])
        self.assertGreater(empty, 0)
        self.assertGreater(len(cases[empty - 1][2]), 120)
        self.assertTrue(cases[empty + 1][2])

    def test_ci_only_fixture_is_not_installed(self):
        build = (ROOT / 'tools/build_skin.py').read_text()
        install = (ROOT / 'install.sh').read_text()
        self.assertNotIn('notification_qa', build)
        self.assertNotIn('notification_qa', install)


if __name__ == '__main__':
    unittest.main()
