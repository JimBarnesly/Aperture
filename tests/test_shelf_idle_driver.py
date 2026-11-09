import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock

spec = importlib.util.spec_from_file_location('ci_shelf_idle', Path(__file__).resolve().parents[1] / 'tools/ci_shelf_idle.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class IdleDriverTests(unittest.TestCase):
    def exercise(self, changed_queue=False, paused=False, premature=False):
        now = [0]
        queue = ['a', 'b']
        player = {'properties': {'speed': 1}}
        states = [dict(sequence=2, window=10502, dialog=9999, shelf_visible=True, player=player, queue=queue),
                  dict(sequence=3, window=10502, dialog=9999, shelf_visible=True, player=player, queue=queue),
                  dict(sequence=4, window=12006, dialog=9999, player={'properties': {'speed': 0 if paused else 1}},
                       queue=['c'] if changed_queue else queue)]
        def wait(description, predicate, **kwargs):
            state = states.pop(0)
            if state['window'] == 12006 and not premature: now[0] += 25
            self.assertTrue(predicate(state))
            return state
        def sleep(seconds): now[0] += seconds
        press, screenshot, checks = Mock(), Mock(), []
        result = module.exercise_idle_return(press, wait, lambda: dict(sequence=1, queue=queue),
                                            screenshot, checks, sleep, lambda: now[0])
        self.assertEqual([c.args[0] for c in press.call_args_list], ['BackSpace', 'Right'])
        self.assertEqual(checks[0]['seconds_since_input'], 60)
        self.assertEqual(checks[0]['seconds_since_entry'], 90)
        self.assertEqual(result['window'], 12006)

    def test_waits_real_minute_after_input_and_preserves_audio(self): self.exercise()
    def test_rejects_queue_change(self):
        with self.assertRaisesRegex(AssertionError, 'replaced'): self.exercise(changed_queue=True)
    def test_rejects_paused_audio(self):
        with self.assertRaisesRegex(AssertionError, 'paused'): self.exercise(paused=True)
    def test_rejects_early_return(self):
        with self.assertRaisesRegex(AssertionError, 'before one minute'): self.exercise(premature=True)
