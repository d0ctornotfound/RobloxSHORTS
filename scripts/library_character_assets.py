"""Generate the worked custom role, in addition to the regular variant atlas."""
from pathlib import Path
from PIL import Image,ImageDraw
from r6_variant_textures import character_face,EXPRESSIONS,cloth,srgb,SKINS,generate
def main():
    out=Path("assets/r6_variants");generate(out)
    dest=out/"librarian";dest.mkdir(exist_ok=True)
    for e in EXPRESSIONS:
        im=character_face(e,"teacher")
        # Small freckles create a distinct repeatable identity across every expression.
        d=ImageDraw.Draw(im)
        for x,y in ((.25,.51),(.28,.535),(.31,.50),(.69,.51),(.72,.535),(.75,.50)):
            d.ellipse((x*1024-5,y*1024-5,x*1024+5,y*1024+5),fill=(100,55,31,160))
        im.save(dest/(e+".png"))
    cloth("cardigan_sleeve",srgb(SKINS["honey"])).save(out/"librarian_sleeve.png")
if __name__=="__main__":main()
