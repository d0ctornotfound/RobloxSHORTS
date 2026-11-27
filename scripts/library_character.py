"""New named character recipes on the unchanged source R6 rig."""
from pathlib import Path
from r6_variant_character import VariantCharacter, ROOT, SKINS, EXPRESSIONS, apply_garments, hair_style
from r6_character import R6Character, ROLE_COLORS, face_material

# name is instance ID; role is reusable identity, not the instance name.
RECIPES={"librarian":{"skin":"honey","shirt":"cardigan","pants":"blue_denim","face":"librarian","hair":"teacher"}}
class RecipeCharacter(R6Character):
    def __init__(self,name,role):
        self.recipe=RECIPES[role]
        r=self.recipe
        ROLE_COLORS.setdefault(role,(SKINS[r["skin"]],(.3,.1,.2),(.1,.2,.4)))
        super().__init__(name,role,skin=SKINS[r["skin"]],face_dir=ROOT/r["face"])
        self.face_materials.update({e:face_material(e,ROOT/r["face"]) for e in EXPRESSIONS if e not in self.face_materials})
        self.variant_garment=apply_garments(self,r["shirt"],r["pants"])
    def _accessories(self):
        hair_style(self,self.recipe["hair"])

def character(name,role="lead"):
    return RecipeCharacter(name,role) if role in RECIPES else VariantCharacter(name,role)
