from pathlib import Path
import sys,tempfile,unittest,xml.etree.ElementTree as E
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from style_dialogs import apply
class MenuStyle(unittest.TestCase):
 def test_home_brand_removed_only(self):
  home=E.parse(ROOT/'skin/xml/Home.xml');self.assertFalse(home.findall('.//label[.="Aperture"]'))
  for i in ('100','101','102','103','104','105','106'):self.assertIsNotNone(home.find('.//control[@id="'+i+'"]'))
 def test_power_actions_preserved_and_focus_not_destructive(self):
  p=E.parse(ROOT/'skin/xml/DialogButtonMenu.xml');actions=[x.text for x in p.findall('.//content/item/onclick')]
  self.assertEqual(actions,['Quit()','Powerdown()','AlarmClock(shutdowntimer,Shutdown())','CancelAlarm(shutdowntimer)','Suspend()','Hibernate()','Reset()','dialog.close(all,true)','System.LogOff','mastermode','InhibitIdleShutdown(true)','InhibitIdleShutdown(false)'])
  self.assertFalse(p.findall('.//onfocus'));self.assertEqual(p.findtext('defaultcontrol'),'9000')
 def test_shared_style_is_idempotent_preserves_actions(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);(p/'xml').mkdir();(p/'colors').mkdir();(p/'addon.xml').write_text('<addon id="skin.aperture"/>')
   (p/'colors/defaults.xml').write_text('<colors><color name="button_focus">FF12A0C7</color></colors>')
   (p/'xml/Includes.xml').write_text('<includes><include name="DialogBackgroundCommons"><control type="image"><height>70</height><texture colordiffuse="button_focus">old.png</texture></control><control type="label" id="$PARAM[header_id]"><font>font32_title</font></control><control type="button"><onclick>Action(close)</onclick><texturenofocus>special://xbmc/media/vendor_icon.png</texturenofocus></control></include></includes>')
   for n in ['Includes_Buttons.xml','Includes_DialogSelect.xml']:(p/'xml'/n).write_text('<includes/>')
   apply(p);first=(p/'xml/Includes.xml').read_bytes();apply(p);self.assertEqual(first,(p/'xml/Includes.xml').read_bytes())
   t=E.parse(p/'xml/Includes.xml');self.assertEqual(t.findtext('.//onclick'),'Action(close)');self.assertEqual(t.findtext('.//height'),'2');self.assertNotIn('vendor_icon',first.decode())
 def test_rejects_system_skin(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);(p/'addon.xml').write_text('<addon id="skin.estuary"/>')
   with self.assertRaises(ValueError):apply(p)
