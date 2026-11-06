#!/usr/bin/env python3
"""Apply Aperture's quiet dialog palette to a staged official Estuary copy.
Never alters system files or actions; repeatable across supported Omega sources.
"""
from pathlib import Path
import xml.etree.ElementTree as ET

PALETTE={'primary_background':'FF14252C','secondary_background':'332A444B','dialog_tint':'F014252C','button_focus':'FF35535C','button_alt_focus':'8035535C','selected':'FFB3E3E5','blue':'FFB3E3E5','grey':'FFB9CBCF'}
def apply(skin):
    skin=Path(skin)
    if not (skin/'addon.xml').is_file() or ET.parse(skin/'addon.xml').getroot().get('id')!='skin.aperture':
        raise ValueError('Only an assembled Aperture skin may be styled')
    for p in (skin/'colors').glob('*.xml'):
        tree=ET.parse(p)
        for node in tree.findall('color'):
            if node.get('name') in PALETTE: node.text=PALETTE[node.get('name')]
        ET.indent(tree);tree.write(p,encoding='utf-8',xml_declaration=True)
    p=skin/'xml/Includes.xml'; tree=ET.parse(p)
    inc=tree.find('./include[@name="DialogBackgroundCommons"]')
    if inc is None: raise ValueError('Unsupported Estuary dialog foundation')
    # Retain all close controls/IDs/navigation; replace only header decoration.
    for control in inc.iter('control'):
        if control.get('type')=='image':
            texture=control.find('texture')
            if texture is not None and texture.get('colordiffuse')=='button_focus':
                texture.text='colors/white.png';texture.set('colordiffuse','FF6B959C')
                height=control.find('height')
                if height is not None and height.text=='70':height.text='2'
        if control.get('id')=='$PARAM[header_id]':
            control.find('font').text='font32'
            shadow=control.find('shadowcolor')
            if shadow is not None:shadow.text='00000000'
    for node in inc.iter():
        if node.text=='special://xbmc/media/vendor_icon.png':node.text='dialogs/close.png'
    ET.indent(tree);tree.write(p,encoding='utf-8',xml_declaration=True)
    # Flatten glossy cyan focus textures on shared menu/select buttons.
    for name in ('Includes_Buttons.xml','Includes_DialogSelect.xml'):
        p=skin/'xml'/name
        tree=ET.parse(p)
        for node in tree.iter():
            if node.get('colordiffuse')=='button_focus' and node.tag.startswith(('texture','alttexture')) and 'border' not in node.attrib:
                node.text='colors/white.png'
        ET.indent(tree);tree.write(p,encoding='utf-8',xml_declaration=True)
if __name__=='__main__':
    import sys
    apply(sys.argv[1])
