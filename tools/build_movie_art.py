"""Generate original abstract movie fallback assets; no image inputs or downloads."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter
import numpy as np
import xml.etree.ElementTree as E
root=Path(__file__).resolve().parents[1]; media=root/'skin/media/aperture/movies'; media.mkdir(parents=True,exist_ok=True)
w,h=1920,1080
y,x=np.mgrid[0:h,0:w]; g=np.exp(-(((x-1430)/530)**2+((y-360)/430)**2)); a=np.exp(-(((x-1770)/350)**2+((y-700)/270)**2))
rgb=np.stack([8+18*g+42*a,18+55*g+10*a,25+61*g],axis=-1).clip(0,255).astype('uint8'); im=Image.fromarray(rgb,'RGB').convert('RGBA'); d=ImageDraw.Draw(im)
# Original orbital horizon, atmospheric arcs and luminous amber sun.
for rad in [270,310,390,505,650]:
 d.ellipse((1400-rad,270-rad,1400+rad,270+rad),outline=(111,199,205,50 if rad%2 else 75),width=2)
glow=Image.new('RGBA',(w,h)); gd=ImageDraw.Draw(glow); gd.ellipse((1320,190,1480,350),fill=(255,175,83,175)); glow=glow.filter(ImageFilter.GaussianBlur(45)); im=Image.alpha_composite(im,glow); d=ImageDraw.Draw(im); d.ellipse((1348,218,1452,322),fill=(255,218,153,255))
for i in range(15):
 yy=570+i*24; d.line([(0,yy+150),(700,yy+50),(1350,yy-30),(1920,yy+10)],fill=(59,122,141,max(10,65-i*3)),width=2)
im.convert('RGB').save(media/'horizon.jpg',quality=94)
# Readability scrim keeps supplied art cinematic and readable.
a=np.maximum((1-np.clip(x/1500,0,1))*235,np.clip((y-390)/580,0,1)*250).astype('uint8'); s=np.zeros((h,w,4),dtype='uint8'); s[:,:,:3]=[5,12,19]; s[:,:,3]=a; Image.fromarray(s).save(media/'scrim.png')
# Original abstract poster, no copyrighted movie artwork.
p=Image.new('RGB',(400,600),(15,36,47)); pd=ImageDraw.Draw(p)
for yy in range(600):
 pd.line((0,yy,400,yy),fill=(int(14+yy*.025),int(37+yy*.045),int(50+yy*.035)))
for r in [75,100,138,183,235,300]: pd.ellipse((200-r,210-r,200+r,210+r),outline=(87,149,156),width=2)
pd.ellipse((164,174,236,246),fill=(244,205,145))
for yy in range(355,600,19): pd.line((0,yy+80,400,yy-25),fill=(36,83,101),width=2)
p.save(media/'poster.jpg',quality=95)
Image.new('RGBA',(8,8),(5,12,19,235)).save(media/'plate.png')
Image.new('RGBA',(8,8),(127,232,218,255)).save(media/'accent.png')
Image.new('RGBA',(8,8),(231,242,243,255)).save(media/'white.png')
