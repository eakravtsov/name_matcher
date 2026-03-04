import torch
import torch.nn.functional as F
import joblib
from siamese_model import SiameseBiLSTM, string_to_tensor
from router_l1 import check_level_1, levenshtein_distance

# QWERTY distances mapping for analytical explanations
# Using a staggered geometric layout approximation
QWERTY_KEYBOARD = [
    "1234567890-=",
    "qwertyuiop[]",
    "asdfghjkl;'",
    "zxcvbnm,./"
]
KEY_COORDS = {}
for y, row in enumerate(QWERTY_KEYBOARD):
    for x, char in enumerate(row):
        offset = y * 0.5
        KEY_COORDS[char] = (x + offset, y)

def qwerty_distance(char1, char2):
    """Calculates geographical Euclidean distance between two characters on a QWERTY keyboard."""
    c1 = char1.lower()
    c2 = char2.lower()
    if c1 not in KEY_COORDS or c2 not in KEY_COORDS:
        return 5.0 # default penalty
    x1, y1 = KEY_COORDS[c1]
    x2, y2 = KEY_COORDS[c2]
    return ((x1-x2)**2 + (y1-y2)**2)**0.5

class NameMatcherWrapper:
    def __init__(self, model_path='best_siamese_model.pt', calibrator_path='calibrator.pkl'):
        """Initializes the multi-tier resolution pipeline mapping L1, L2, and L3."""
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        print(f"Initializing NameMatcher on {self.device}...")
        
        self.model = SiameseBiLSTM().to(self.device)
        try:
            self.model.load_state_dict(torch.load(model_path, map_location=self.device, weights_only=True))
            self.model.eval()
            self.calibrator = joblib.load(calibrator_path)
            self.ready = True
        except FileNotFoundError:
            print("WARNING: Could not find Level 2/3 assets. Only Level 1 will be active.")
            self.ready = False
            
    def check_qwerty_typo(self, n1, n2):
        """Analytical heuristic to explain L2 responses with keyboard ergonomics."""
        if len(n1) == len(n2) and levenshtein_distance(n1.lower(), n2.lower()) == 1:
            for c1, c2 in zip(n1.lower(), n2.lower()):
                if c1 != c2:
                    dist = qwerty_distance(c1, c2)
                    if dist <= 1.5:
                        return f"Strong likelihood of adjacent QWERTY typo ('{c1}' vs '{c2}')"
        return "Complex misspelling or structural deviation"
        
    def evaluate(self, name1, name2, use_carlton=True, use_wikidata=True, use_jrc=True, use_l2=True,
                 strict_unknowns=False):
        # Level 1 API Intercept
        l1_res = check_level_1(name1, name2, use_carlton, use_wikidata, use_jrc)
        
        # --- Phase 9: Gender Mismatch Veto ---
        g1, g2 = l1_res.get("gender1", "Unknown"), l1_res.get("gender2", "Unknown")
        if (g1 == 'M' and g2 == 'F') or (g1 == 'F' and g2 == 'M'):
            return {
                "name1": name1, "name2": name2,
                "match": False,
                "confidence": 0.0,
                "explanation": f"Structural Gender Mismatch: '{name1}' ({g1}) and '{name2}' ({g2}) are contrasting categorical genders. Instant rejection applied to prevent transitive false positives."
            }

        if l1_res["match"]:
            return {
                "name1": name1, "name2": name2,
                "match": True,
                "confidence": l1_res["confidence"],
                "explanation": l1_res['explanation']
            }
            
        # --- Phase 15: Strict Unknowns Logic ---
        # If a name is not in the dictionary, it's considered 'Unknown'.
        # If strict_unknowns is enabled, we bypass L2 entirely for unknown names.
        is_known = (g1 != "Unknown" and g2 != "Unknown")
        if strict_unknowns and not is_known:
            return {
                "name1": name1, "name2": name2,
                "match": False,
                "confidence": 0.0,
                "explanation": f"Strict Unknown Violation: One or both entities are not in the Knowledge Base. Strict spelling required (Exact match failed at L1)."
            }

        if not use_l2:
            return {
                "name1": name1, "name2": name2,
                "match": False,
                "confidence": 0.0,
                "explanation": f"L1 Router found no match. Level 2 Neural Model is disabled."
            }
            
        if not self.ready:
            return {
                "name1": name1, "name2": name2,
                "match": False,
                "confidence": 0.0,
                "explanation": "L1 Router deferred, but Level 2 Model unavailable."
            }
            
        # Level 2 Neural Prop // Level 3 Calibration
        t1 = string_to_tensor(name1).unsqueeze(0).to(self.device)
        t2 = string_to_tensor(name2).unsqueeze(0).to(self.device)
        
        with torch.no_grad():
            out1, out2 = self.model(t1, t2)
            dist = F.pairwise_distance(out1, out2).item()
            
        prob = self.calibrator.predict_proba([[dist]])[0][1]
        
        is_match = bool(prob >= 0.8)
        
        reasoning = ""
        if is_match:
            typo_hint = self.check_qwerty_typo(name1, name2)
            reasoning = f"Level 2 Neural Model detected high semantic proximity ({prob*100:.1f}% confidence). {typo_hint}."
        elif prob > 0.2:
            reasoning = f"Level 2 Neural Model considered the topological similarity dubious ({prob*100:.1f}% confidence)."
        else:
            reasoning = f"Level 2 Neural Model found these character sequences to be divergent ({prob*100:.1f}% confidence)."
            
        return {
            "name1": name1, "name2": name2,
            "match": is_match,
            "confidence": float(round(prob, 4)),
            "explanation": reasoning
        }
