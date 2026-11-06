"""Execute the QA readiness helper without importing Kodi or running its service."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

class MenuBarReadiness(unittest.TestCase):
 def run_helper(self, blocked=lambda t:False, moves=True, focus_delay=0):
  source=Path(__file__).resolve().parents[1]/'tools/menus_qa_service.py'
  tree=ast.parse(source.read_text())
  helper=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='focus_home_bar')
  state={'time':0.0,'focus':100,'target':None,'keys':[],'checks':[]}
  def focus():
   if state['target'] is not None and state['time']>=focus_delay:
    state['focus']=state.pop('target');state['target']=None
   return state['focus']
  def set_focus(ident):state['target']=ident
  def rpc(method):
   state['keys'].append((method,state['time'],focus()))
   if moves:state['focus']=120
  def until(label,pred):
   for _ in range(300):
    if pred():return
    state['time']+=.1
   raise RuntimeError(label)
  ns={'time':SimpleNamespace(monotonic=lambda:state['time']),
      'xbmcgui':SimpleNamespace(getCurrentWindowId=lambda:10000),
      'xbmc':SimpleNamespace(getCondVisibility=lambda _:blocked(state['time'])),
      'until':until,'rpc':rpc,'checks':state['checks']}
  exec(compile(ast.Module(body=[helper],type_ignores=[]),str(source),'exec'),ns)
  home=SimpleNamespace(setFocusId=set_focus,getFocusId=focus)
  return state,lambda:ns['focus_home_bar'](home,lambda:True)
 def test_waits_for_observed_source_focus_then_sends_one_right(self):
  state,run=self.run_helper(focus_delay=.5);run()
  self.assertEqual(len(state['keys']),1)
  key,when,focus=state['keys'][0]
  self.assertEqual((key,focus),('Input.Right',103));self.assertGreaterEqual(when,1.5)
 def test_modal_interruption_restarts_stability_interval(self):
  state,run=self.run_helper(blocked=lambda t:.4<=t<1.0);run()
  self.assertGreaterEqual(state['keys'][0][1],2.0)
 def test_does_not_retry_or_force_destination_on_navigation_failure(self):
  state,run=self.run_helper(moves=False)
  with self.assertRaisesRegex(RuntimeError,'bar focus after one Right'):run()
  self.assertEqual(len(state['keys']),1);self.assertEqual(state['focus'],103)
 def test_unready_home_never_sends_key(self):
  state,run=self.run_helper(blocked=lambda _:True)
  with self.assertRaisesRegex(RuntimeError,'settled Home Music focus'):run()
  self.assertEqual(state['keys'],[])
