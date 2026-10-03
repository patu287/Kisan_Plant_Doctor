# ══════════════════════════════════════════════════════════════════
#  KISAN PLANT DOCTOR — APP UI SIMULATOR  (v2 · green theme)
#  Paste this WHOLE file into ONE Colab cell (after model + db load)
#  Then run:   run_app_ui('hindi')
# ══════════════════════════════════════════════════════════════════
#
#  v2 CHANGES
#  ----------
#   • Layered green palette (9 shades, deep forest → mint) + small
#     teal / amber / red / blue accents per section so nothing is
#     flat green-on-green
#   • Wallpaper support: drop any image in and it becomes the app
#     background (3 auto-variants: page / header / body). Ships with
#     a CSS-only fallback so it still looks good with no image.
#   • Dark gradient hero card + header with wallpaper overlay
#   • Colour-coded treatment cards (teal=what it is, green=organic,
#     red=chemical, blue=prevention)
#   • Pill-style bottom nav, pulsing offline dot, lime camera brackets
#
#  EXPECTS THESE GLOBALS FROM EARLIER CELLS:
#      interpreter, input_details, output_details   (TFLite model)
#      class_names   (dict: "0" -> {plant, disease, ...})
#      disease_db    (dict: name -> {english|hindi|marathi: {...}})
#  disease_db is optional — generic fallback advice is built in.
# ══════════════════════════════════════════════════════════════════

import json, base64, io, os, re
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
from IPython.display import HTML, display

try:
    from google.colab import files          # only exists in Colab
except Exception:
    files = None

# ── CONFIG ────────────────────────────────────────────────────────
IMG_SIZE       = 160      # must match training
LOW_CONF       = 55.0     # below this -> "retake photo" state
NORMALIZE_255  = False    # True ONLY if you trained on 0..1 inputs.
                          # Your working Colab code feeds raw 0..255,
                          # so keep this False.
WALLPAPER      = None     # path to a background image, or None for
                          # the CSS-only gradient theme. If None, the
                          # file "wallpaper.jpg" is used when present.
FONT_CSS       = None     # embedded @font-face CSS, or None. If None,
                          # "inter_var.css" is used when present.
# ──────────────────────────────────────────────────────────────────


# ══════════════════════════════════════════════════════════════════
#  1. UI TRANSLATIONS (static chrome of the app)
# ══════════════════════════════════════════════════════════════════
UI_STRINGS = {
    "english": {
        "appName": "Kisan Plant Doctor", "tagline": "Photo lo, bimari jano",
        "offline": "100% Offline — No Internet Needed",
        "heroTitle": "Is your crop sick?",
        "heroSub": "Take a photo of the leaf. Get the disease name and treatment in your language.",
        "scanBtn": "Scan Leaf", "galleryBtn": "Choose from Gallery",
        "tipsTitle": "How to take a good photo",
        "tips": ["Hold phone 15–20 cm from the leaf",
                 "Avoid direct sunlight — use shade",
                 "Fill the frame with the leaf",
                 "Hold steady, tap to focus",
                 "Wipe the camera lens"],
        "navHome": "Home", "navCamera": "Camera", "navResult": "Result",
        "navCare": "Care", "navAbout": "About",
        "camTitle": "Point at the leaf",
        "camHint": "Fit the leaf inside the box",
        "captureBtn": "Capture & Diagnose",
        "analyzing": "Reading the leaf…",
        "resultTitle": "Diagnosis Result",
        "top3Title": "Top 3 possibilities",
        "tapHint": "Tap any row to see its treatment",
        "viewCare": "View Treatment",
        "lowTitle": "Not sure about this photo",
        "lowBody": "The photo may be blurry, dark or too far. Take another one — 20 cm away, good light, plain background.",
        "retake": "Retake Photo", "match": "match",
        "careTitle": "Treatment & Care",
        "desc": "What is it", "organic": "Organic remedy",
        "chemical": "Chemical remedy", "prevention": "Prevention",
        "severity": "Severity", "listen": "Listen",
        "readAll": "Read everything aloud",
        "expert": "This is a well-informed guess, not a doctor. Confirm with your local agriculture expert before spraying.",
        "aboutTitle": "About this app",
        "aboutBody": "The app runs a MobileNetV2 model directly on your phone. Nothing is uploaded anywhere. It works with the internet switched off.",
        "howTitle": "How it works",
        "how": ["Photo is cleaned (contrast + sharpen) inside the phone",
                "Model looks at the leaf 5 different ways and averages them",
                "Top 3 matches are shown with confidence",
                "Treatment is read from an offline database"],
        "limitsTitle": "Honest limitations",
        "limits": ["Trained mostly on lab photos — field photos are harder",
                   "About 5–6 out of 100 diagnoses can be wrong",
                   "Low light and blur reduce accuracy",
                   "Always confirm with an agriculture expert"],
        "modelTitle": "Model",
        "statDiseases": "Diseases", "statCrops": "Crops",
        "statLangs": "Languages",
        "verdict": "Best match", "of": "of 38",
    },
    "hindi": {
        "appName": "किसान प्लांट डॉक्टर", "tagline": "फोटो लें, बीमारी जानें",
        "offline": "100% ऑफलाइन — इंटरनेट की ज़रूरत नहीं",
        "heroTitle": "क्या आपकी फ़सल बीमार है?",
        "heroSub": "पत्ती की फोटो लें। बीमारी का नाम और इलाज अपनी भाषा में पाएं।",
        "scanBtn": "पत्ती स्कैन करें", "galleryBtn": "गैलरी से चुनें",
        "tipsTitle": "अच्छी फोटो कैसे लें",
        "tips": ["फोन पत्ती से 15–20 सेमी दूर रखें",
                 "सीधी धूप से बचें — छाया में फोटो लें",
                 "पत्ती से पूरा फ्रेम भरें",
                 "हाथ स्थिर रखें, टैप करके फोकस करें",
                 "कैमरा लेंस साफ कर लें"],
        "navHome": "होम", "navCamera": "कैमरा", "navResult": "परिणाम",
        "navCare": "इलाज", "navAbout": "जानकारी",
        "camTitle": "पत्ती की ओर करें",
        "camHint": "पत्ती को बॉक्स में फिट करें",
        "captureBtn": "फोटो लें और जांचें",
        "analyzing": "पत्ती देखी जा रही है…",
        "resultTitle": "जांच का परिणाम",
        "top3Title": "तीन सबसे संभव बीमारियां",
        "tapHint": "इलाज देखने के लिए किसी भी पंक्ति पर टैप करें",
        "viewCare": "इलाज देखें",
        "lowTitle": "इस फोटो से पक्का पता नहीं चला",
        "lowBody": "फोटो धुंधली, अंधेरी या बहुत दूर की हो सकती है। दोबारा फोटो लें — 20 सेमी दूर, अच्छी रोशनी, सादा बैकग्राउंड।",
        "retake": "दूसरी फोटो लें", "match": "मेल",
        "careTitle": "इलाज और देखभाल",
        "desc": "यह क्या है", "organic": "जैविक उपाय",
        "chemical": "रासायनिक उपाय", "prevention": "बचाव",
        "severity": "गंभीरता", "listen": "सुनें",
        "readAll": "सब कुछ सुनें",
        "expert": "यह एक अनुमान है, डॉक्टर की सलाह नहीं। छिड़काव से पहले अपने कृषि-विशेषज्ञ से ज़रूर पूछें।",
        "aboutTitle": "ऐप के बारे में",
        "aboutBody": "यह ऐप MobileNetV2 मॉडल को सीधे आपके फोन में चलाता है। कोई भी फोटो कहीं अपलोड नहीं होती। इंटरनेट बंद होने पर भी चलता है।",
        "howTitle": "यह कैसे काम करता है",
        "how": ["फोन के अंदर फोटो साफ की जाती है (रंग + तेज़)",
                "मॉडल पत्ती को 5 तरीकों से देखकर औसत निकालता है",
                "तीन सबसे संभव बीमारियां उनके दम के साथ दिखती हैं",
                "इलाज ऑफलाइन डेटाबेस से पढ़ा जाता है"],
        "limitsTitle": "सीमाएं — साफ़-साफ़",
        "limits": ["ज़्यादातर लैब फोटो पर ट्रेनिंग — खेत की फोटो कठिन",
                   "हर 100 में से 5–6 जांच गलत हो सकती हैं",
                   "कम रोशनी और धुंधली फोटो में सटीकता घटती है",
                   "हमेशा कृषि-विशेषज्ञ से पुष्टि करें"],
        "modelTitle": "मॉडल",
        "statDiseases": "बीमारियां", "statCrops": "फ़सलें",
        "statLangs": "भाषाएं",
        "verdict": "सबसे संभव", "of": "38 में से",
    },
    "marathi": {
        "appName": "किसान प्लांट डॉक्टर", "tagline": "फोटो काढा, रोग ओळखा",
        "offline": "100% ऑफलाइन — इंटरनेटची गरज नाही",
        "heroTitle": "तुमचे पीक आजारी आहे का?",
        "heroSub": "पानाचा फोटो काढा. रोगाचे नाव आणि उपाय तुमच्या भाषेत मिळवा.",
        "scanBtn": "पान स्कॅन करा", "galleryBtn": "गॅलरीमधून निवडा",
        "tipsTitle": "चांगला फोटो कसा काढायचा",
        "tips": ["फोन पानापासून 15–20 सेमी दूर ठेवा",
                 "थेट उन्हात नाही — सावलीत फोटो काढा",
                 "पानाने संपूर्ण चौकट भरा",
                 "हात स्थिर ठेवा, टॅप करून फोकस करा",
                 "कॅमेरा लेन्स पुसा"],
        "navHome": "होम", "navCamera": "कॅमेरा", "navResult": "निकाल",
        "navCare": "उपाय", "navAbout": "माहिती",
        "camTitle": "पानाकडे धरा",
        "camHint": "पान चौकटीत बसवा",
        "captureBtn": "फोटो काढा व तपासा",
        "analyzing": "पान तपासले जात आहे…",
        "resultTitle": "तपासणीचा निकाल",
        "top3Title": "सर्वाधिक संभाव्य तीन रोग",
        "tapHint": "उपाय पाहण्यासाठी कोणत्याही ओळीवर टॅप करा",
        "viewCare": "उपाय पाहा",
        "lowTitle": "या फोटोवरून नक्की सांगता येत नाही",
        "lowBody": "फोटो अस्पष्ट, अंधारातला किंवा खूप दूरचा असू शकतो. पुन्हा फोटो काढा — 20 सेमी अंतर, चांगला प्रकाश, साधी पार्श्वभूमी.",
        "retake": "पुन्हा फोटो काढा", "match": "जुळणी",
        "careTitle": "उपाय व काळजी",
        "desc": "हे काय आहे", "organic": "सेंद्रिय उपाय",
        "chemical": "रासायनिक उपाय", "prevention": "प्रतिबंध",
        "severity": "तीव्रता", "listen": "ऐका",
        "readAll": "सर्व काही ऐका",
        "expert": "ही एक अंदाजपूर्वक माहिती आहे, डॉक्टरांचा सल्ला नाही. फवारणीपूर्वी कृषी-तज्ज्ञांची खात्री करा.",
        "aboutTitle": "अ‍ॅप बद्दल",
        "aboutBody": "हा अ‍ॅप MobileNetV2 मॉडेल थेट तुमच्या फोनमध्ये चालवतो. कोणताही फोटो कुठे अपलोड होत नाही. इंटरनेट बंद असतानाही चालतो.",
        "howTitle": "हे कसे कार्य करते",
        "how": ["फोनमध्येच फोटो स्वच्छ केला जातो (रंग + स्पष्टता)",
                "मॉडेल पानाकडे 5 प्रकारे पाहून सरासरी काढतो",
                "सर्वाधिक संभाव्य तीन रोग खात्रीसह दाखवले जातात",
                "उपाय ऑफलाइन डेटाबेसमधून वाचला जातो"],
        "limitsTitle": "मर्यादा — स्पष्टपणे",
        "limits": ["बहुतेक लॅब फोटोंवर प्रशिक्षण — शेतातील फोटो अवघड",
                   "प्रत्येक 100 पैकी 5–6 निदान चुकीचे असू शकते",
                   "कमी प्रकाश व अस्पष्ट फोटोमुळे अचूकता कमी होते",
                   "नेहमी कृषी-तज्ज्ञांची पुष्टी करा"],
        "modelTitle": "मॉडेल",
        "statDiseases": "रोग", "statCrops": "पिके",
        "statLangs": "भाषा",
        "verdict": "सर्वाधिक संभव", "of": "38 पैकी",
    },
}

# severity key -> [pill bg, pill text colour, {lang: label}]
SEV_META = {
    "healthy":  ("#E8F5E9", "#1B5E20", {"english": "Healthy",  "hindi": "स्वस्थ", "marathi": "निरोगी"}),
    "low":      ("#F1F8E9", "#33691E", {"english": "Low",      "hindi": "कम",    "marathi": "कमी"}),
    "medium":   ("#FFF8E1", "#EF6C00", {"english": "Medium",   "hindi": "मध्यम", "marathi": "मध्यम"}),
    "high":     ("#FFF3E0", "#E65100", {"english": "High",     "hindi": "ज्यादा","marathi": "जास्त"}),
    "critical": ("#FFEBEE", "#C62828", {"english": "Critical", "hindi": "गंभीर", "marathi": "गंभीर"}),
}


# ══════════════════════════════════════════════════════════════════
#  2. WALLPAPER — one image in, three tuned variants out
# ══════════════════════════════════════════════════════════════════
def _sync_globals():
    """Pull model objects out of the notebook's namespace into this module.

    Needed when the file is imported (`import plant_doctor_ui as ui`) instead
    of pasted into a cell — module code cannot see notebook variables.
    Harmless when the code was pasted in: it just re-reads the same names.
    """
    try:
        ns = get_ipython().user_ns          # Colab / Jupyter
    except Exception:
        try:
            ns = __import__("__main__").__dict__
        except Exception:
            ns = {}
    for k in ("interpreter", "input_details", "output_details",
              "class_names", "disease_db"):
        if k in ns:
            globals()[k] = ns[k]
    return globals()


_REQUIRED = ("interpreter", "input_details", "output_details", "class_names")


def _require():
    """Sync + hard-fail with a readable message instead of a bare NameError."""
    g = _sync_globals()
    miss = [k for k in _REQUIRED if k not in g]
    if miss:
        raise RuntimeError(
            "This cell cannot see: %s\n"
            "  -> Run your model-loading and class_names cells first, in the SAME\n"
            "     session (Colab wipes memory on disconnect).\n"
            "  -> Then run  check_setup()  to see exactly what is missing."
            % ", ".join(miss))
    return g


def check_setup():
    """Print what this UI can and cannot see. Run it first if things break."""
    g = _sync_globals()
    print("── setup check ─────────────────────────────")
    for k, desc in [("interpreter",     "TFLite interpreter (the model)"),
                    ("input_details",   "model input tensor info"),
                    ("output_details",  "model output tensor info"),
                    ("class_names",     "38 class names"),
                    ("disease_db",      "treatment database")]:
        mark = "✅" if k in g else "❌"
        print("  %s  %-15s %s" % (mark, k, desc))
    try:
        n = len(g.get("class_names", {}))
        print("  ℹ️  class_names has %d entries" % n)
    except Exception:
        pass
    try:
        n = len(g.get("disease_db", {}) or {})
        print("  ℹ️  disease_db has %d entries" % n)
    except Exception:
        pass
    wp = WALLPAPER or ("wallpaper.jpg" if os.path.exists("wallpaper.jpg") else None)
    print("  %s  wallpaper      %s" % ("✅" if wp and os.path.exists(wp) else "➖", wp or "CSS gradient fallback"))
    fc = FONT_CSS
    if fc is None and os.path.exists("inter_var.css"):
        fc = io.open("inter_var.css", encoding="utf-8").read()
    print("  %s  inter_var.css  %s" % ("✅" if fc else "➖",
                                       "embedded Inter" if fc else "system fonts only"))
    print("────────────────────────────────────────────")
    missing = [k for k in ("interpreter", "input_details",
                           "output_details", "class_names") if k not in g]
    if missing:
        print("❌ Re-run your model cells — missing:", ", ".join(missing))
        return False
    print("✅ Ready. Run:  ui.run_app_ui('hindi')")
    return True


def _cover(im, w, h):
    """Center-crop to w:h then resize."""
    tw, th = im.size
    s = max(w / tw, h / th)
    nw, nh = int(tw * s) + 1, int(th * s) + 1
    im = im.resize((nw, nh), Image.LANCZOS)
    return im.crop(((nw - w) // 2, (nh - h) // 2,
                    (nw - w) // 2 + w, (nh - h) // 2 + h))


def _uri(im, q):
    b = io.BytesIO()
    im.save(b, format="JPEG", quality=q, optimize=True)
    return "url(data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode() + ")"


def prepare_wallpapers(path):
    """Return (page, hero, app) CSS url() strings from any image."""
    src = Image.open(path).convert("RGB")

    # page backdrop — blurred, deep forest
    p = _cover(src, 560, 820).filter(ImageFilter.GaussianBlur(3.2))
    p = Image.blend(p, Image.new("RGB", p.size, (8, 38, 20)), 0.44)

    # header / hero — darker, richer green
    h = _cover(src, 420, 300)
    h = Image.blend(h, Image.new("RGB", h.size, (10, 46, 23)), 0.40)
    h = ImageEnhance.Color(h).enhance(1.15)

    # scrolling body — lightened so dark text stays readable
    a = _cover(src, 440, 900)
    a = Image.blend(a, Image.new("RGB", a.size, (255, 255, 255)), 0.62)
    a = ImageEnhance.Color(a).enhance(0.75)

    return _uri(p, 58), _uri(h, 68), _uri(a, 66)


# ══════════════════════════════════════════════════════════════════
#  3. MODEL SIDE — TTA PIPELINE (Fix A + Fix B, self-contained)
# ══════════════════════════════════════════════════════════════════
def ui_preprocess(img):
    """Fix A: contrast 1.5, sharpen 2.0, colour 1.3, centre-crop 10%."""
    w, h = img.size
    c = img.crop((int(w * .10), int(h * .10), int(w * .90), int(h * .90)))
    c = ImageEnhance.Contrast(c).enhance(1.5)
    c = ImageEnhance.Sharpness(c).enhance(2.0)
    c = ImageEnhance.Color(c).enhance(1.3)
    return c.resize((IMG_SIZE, IMG_SIZE))


def ui_make_variants(img):
    base = img.resize((IMG_SIZE, IMG_SIZE))
    return [
        ui_preprocess(img),                                                 # 1 cleaned
        base,                                                               # 2 plain
        img.transpose(Image.FLIP_LEFT_RIGHT).resize((IMG_SIZE, IMG_SIZE)),  # 3 flip
        ImageEnhance.Brightness(base).enhance(1.3),                         # 4 brighter
        ImageEnhance.Brightness(base).enhance(0.7),                         # 5 darker
    ]


def _to_input(arr, detail):
    if detail["dtype"] == np.uint8:
        return np.asarray(arr, dtype=np.uint8)
    scale, zero = detail.get("quantization", (0.0, 0))
    arr = np.asarray(arr, dtype=np.float32)
    if NORMALIZE_255:
        arr = arr / 255.0
    if scale and scale > 0:
        arr = arr / scale + zero
    return arr.astype(np.float32)


def _from_output(out, detail):
    scale, zero = detail.get("quantization", (0.0, 0))
    out = np.asarray(out, dtype=np.float32)
    if scale and scale > 0:
        out = (out.astype(np.float32) - zero) * scale
    return out


def ui_predict_tta(photo_path, topk=3):
    """Fix B: 5-angle averaged prediction. Returns list of dicts."""
    _require()
    img = Image.open(photo_path).convert("RGB")
    probs = []
    for v in ui_make_variants(img):
        arr = np.expand_dims(_to_input(v, input_details[0]), 0)
        interpreter.set_tensor(input_details[0]["index"], arr)
        interpreter.invoke()
        p = _from_output(interpreter.get_tensor(output_details[0]["index"])[0],
                         output_details[0]).astype(np.float64)
        s = p.sum()
        if s > 0 and abs(s - 1.0) > 1e-3:            # not already softmax
            e = np.exp(p - p.max()); p = e / e.sum()
        probs.append(p)

    avg = np.mean(probs, axis=0)
    out = []
    for i in avg.argsort()[::-1][:topk]:
        meta = class_names[str(int(i))]
        plant, disease = meta.get("plant", "?"), meta.get("disease", "?")
        out.append({
            "plant": plant, "disease": disease,
            "conf": round(float(avg[i]) * 100, 1),
            "treat": {L: ui_treatment(plant, disease, L)
                      for L in ("english", "hindi", "marathi")},
        })
    return out


# ── treatment lookup ─────────────────────────────────────────────
_FIELD_ALIASES = {
    "name": ("name",), "desc": ("desc", "description"),
    "org":  ("org", "organic"), "chem": ("chem", "chemical"),
    "prev": ("prev", "prevention"), "sev": ("sev", "severity"),
}

def _norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def _extract(block):
    if not isinstance(block, dict):
        return {}
    out = {}
    for key, aliases in _FIELD_ALIASES.items():
        for a in aliases:
            if block.get(a):
                out[key] = str(block[a]); break
        out.setdefault(key, "")
    return out


def ui_treatment(plant, disease, lang):
    """Fuzzy lookup in disease_db, then generic fallback."""
    db = _sync_globals().get("disease_db", {}) or {}
    dn, pn = _norm(disease), _norm(plant)
    healthy = "healthy" in disease.lower()

    best, best_score = None, 0
    for key, val in db.items():
        if not isinstance(val, dict):
            continue
        kn, score = _norm(key), 0
        if dn and dn in kn: score += 3
        if pn and pn in kn: score += 2
        if kn and kn in dn: score += 1
        if score > best_score:
            best, best_score = val, score

    if best:
        src = best.get(lang) or best.get("english")
        if src:
            t = _extract(src)
            if t.get("desc") or t.get("org"):
                t.setdefault("name", "%s — %s" % (plant, disease))
                t["sev"] = t.get("sev") or ("Healthy" if healthy else "Medium")
                return t

    F = {
        "english": dict(
            name=("Healthy " + plant) if healthy else "%s — %s" % (plant, disease),
            desc=(f"Your {plant} plant looks healthy. No disease signs found."
                  if healthy else
                  f"{plant} leaves show symptoms commonly associated with {disease}."),
            org=("Keep regular compost and watering. Inspect the crop weekly."
                 if healthy else
                 "Spray neem oil (5 ml per litre of water) with a few drops of liquid soap. Remove and burn badly infected leaves."),
            chem=("No spray needed." if healthy else
                  "Apply Mancozeb 75% WP or Copper Oxychloride at 2 g per litre of water. Repeat after 10–12 days if needed."),
            prev=("Inspect the field every week and keep the area weed free."
                  if healthy else
                  "Keep spacing between plants for airflow, avoid overhead watering, and do not work in the field when leaves are wet."),
            sev="Healthy" if healthy else "Medium"),
        "hindi": dict(
            name=("स्वस्थ " + plant) if healthy else "%s — %s" % (plant, disease),
            desc=(f"आपका {plant} पौधा स्वस्थ है, बीमारी के कोई लक्षण नहीं।"
                  if healthy else
                  f"{plant} की पत्तियों पर {disease} के लक्षण दिख रहे हैं।"),
            org=("नियमित खाद और पानी दें। हर हफ़्ते खेत की जांच करें।"
                 if healthy else
                 "नीम का तेल (5 मिली प्रति लीटर पानी) में थोड़ा साबुन मिलाकर छिड़कें। बुरी तरह संक्रमित पत्तियां तोड़कर जला दें।"),
            chem=("किसी दवा की ज़रूरत नहीं।" if healthy else
                  "Mancozeb 75% WP या Copper Oxychloride 2 ग्राम प्रति लीटर पानी में घोलकर छिड़कें। ज़रूरत पड़े तो 10–12 दिन बाद दोहराएं।"),
            prev=("हर हफ्ते खेत देखें और खरपतवार साफ रखें।" if healthy else
                  "पौधों के बीच जगह रखें ताकि हवा लगे, ऊपर से पानी न दें, और गीली पत्तियों वाले खेत में काम न करें।"),
            sev="Healthy" if healthy else "Medium"),
        "marathi": dict(
            name=("निरोगी " + plant) if healthy else "%s — %s" % (plant, disease),
            desc=(f"तुमचे {plant} झाड निरोगी आहे, रोगाची लक्षणे नाहीत."
                  if healthy else
                  f"{plant} च्या पानांवर {disease} शी मिळतीजुळती लक्षणे आहेत."),
            org=("नियमित खत व पाणी द्या. दर आठवड्याला शेत तपासा."
                 if healthy else
                 "कडुनिंब तेल (5 मिली प्रति लीटर पाणी) थोड्या साबणासह फवारा. जास्त रोगट पाने काढून जाळा."),
            chem=("फवारणीची गरज नाही." if healthy else
                  "Mancozeb 75% WP किंवा Copper Oxychloride 2 ग्रॅम प्रति लीटर पाण्यात फवारा. गरज भासल्यास 10–12 दिवसांनी पुन्हा फवारा."),
            prev=("दर आठवड्याला शेत तपासा व तण स्वच्छ ठेवा." if healthy else
                  "झाडांमध्ये अंतर ठेवा जेणेकरून हवा खेळेल, वरून पाणी देऊ नका, ओल्या पानांवर काम करू नका."),
            sev="Healthy" if healthy else "Medium"),
    }[lang]
    return F


def _sev_key(sev_text, healthy):
    s = str(sev_text or "").strip().lower()
    if "healthy" in s or "none" in s:
        return "healthy"
    for k in ("critical", "high", "medium", "low"):
        if k in s:
            return k
    return "healthy" if healthy else "medium"


# ══════════════════════════════════════════════════════════════════
#  4. THE HTML / CSS / JS TEMPLATE
# ══════════════════════════════════════════════════════════════════
HTML_TEMPLATE = r"""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=Noto+Sans+Devanagari:wght@400;600;700&display=swap">
__FONTCSS__
<svg class="pd-sprite" aria-hidden="true" xmlns="http://www.w3.org/2000/svg"><defs>
<symbol id="pd-i-home" viewBox="0 0 24 24"><path d="M3 10.6 12 3.4l9 7.2"/><path d="M5.6 9.6V20h12.8V9.6"/><path d="M9.6 20v-6.2h4.8V20"/></symbol>
<symbol id="pd-i-camera" viewBox="0 0 24 24"><path d="M3 8.6A2.2 2.2 0 0 1 5.2 6.4h1.6l1.2-2.2h8l1.2 2.2h1.6A2.2 2.2 0 0 1 21 8.6v8.8a2.2 2.2 0 0 1-2.2 2.2H5.2A2.2 2.2 0 0 1 3 17.4z"/><circle cx="12" cy="12.9" r="3.6"/></symbol>
<symbol id="pd-i-chart" viewBox="0 0 24 24"><path d="M4.5 20.5v-8M12 20.5v-15M19.5 20.5v-11"/></symbol>
<symbol id="pd-i-leaf" viewBox="0 0 24 24"><path d="M4.2 20.2C4.2 11.4 11 4.2 20.2 4.2c0 8.8-7.2 16-16 16Z"/><path d="M4.2 20.2c4.4-6 8.6-9.4 13.4-11.6"/></symbol>
<symbol id="pd-i-info" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 11v5.4M12 7.9h.01"/></symbol>
<symbol id="pd-i-bulb" viewBox="0 0 24 24"><path d="M9.4 18.2h5.2M10.4 21h3.2"/><path d="M12 3.2a6 6 0 0 0-3.6 10.8c.6.5 1 1.2 1 1.9v.3h5.2v-.3c0-.7.4-1.4 1-1.9A6 6 0 0 0 12 3.2Z"/></symbol>
<symbol id="pd-i-clip" viewBox="0 0 24 24"><path d="M9.4 4.6h5.2v2.6H9.4z"/><path d="M15.6 6.2h1.8a1.6 1.6 0 0 1 1.6 1.6v11.2a1.6 1.6 0 0 1-1.6 1.6H6.6a1.6 1.6 0 0 1-1.6-1.6V7.8a1.6 1.6 0 0 1 1.6-1.6h1.8"/><path d="M8.6 12h6.8M8.6 15.8h4.6"/></symbol>
<symbol id="pd-i-sprout" viewBox="0 0 24 24"><path d="M12 20.8v-7.4"/><path d="M12 13.4c0-4 3.2-7.2 8-7.2 0 4-3.2 7.2-8 7.2Z"/><path d="M12 13.4c0-3.2-2.4-6-6.4-6 0 3.2 2.4 6 6.4 6Z"/></symbol>
<symbol id="pd-i-pill" viewBox="0 0 24 24"><path d="M10.6 4.1 4.1 10.6a3.6 3.6 0 0 0 0 5.1l4.2 4.2a3.6 3.6 0 0 0 5.1 0l6.5-6.5a3.6 3.6 0 0 0 0-5.1l-4.2-4.2a3.6 3.6 0 0 0-5.1 0Z"/><path d="M8.9 15.1 15 9"/></symbol>
<symbol id="pd-i-shield" viewBox="0 0 24 24"><path d="M12 3.2 19 6v6.2c0 4.6-3 7.7-7 9.2-4-1.5-7-4.6-7-9.2V6Z"/><path d="M9.2 12.1 11.3 14l3.6-3.8"/></symbol>
<symbol id="pd-i-warn" viewBox="0 0 24 24"><path d="M12 4.2 21 19.8H3Z"/><path d="M12 10v4.2M12 17.2h.01"/></symbol>
<symbol id="pd-i-list" viewBox="0 0 24 24"><path d="M9 6.5h11M9 12h11M9 17.5h11"/><path d="M4.6 6.5h.01M4.6 12h.01M4.6 17.5h.01"/></symbol>
<symbol id="pd-i-sound" viewBox="0 0 24 24"><path d="M11 4.8 6.2 8.8H3.4v6.4h2.8L11 19.2z"/><path d="M15.4 8.8a4.6 4.6 0 0 1 0 6.4"/><path d="M18.2 6a8.4 8.4 0 0 1 0 12"/></symbol>
<symbol id="pd-i-aperture" viewBox="0 0 24 24"><circle cx="12" cy="12" r="8.6"/><path d="M12 3.4v3.2M12 17.4v3.2M3.4 12h3.2M17.4 12h3.2"/><circle cx="12" cy="12" r="2.6"/></symbol>
<symbol id="pd-i-cpu" viewBox="0 0 24 24"><rect x="6.4" y="6.4" width="11.2" height="11.2" rx="2"/><path d="M9.8 9.8h4.4v4.4H9.8z"/><path d="M10 3.4v3M14 3.4v3M10 17.6v3M14 17.6v3M3.4 10h3M3.4 14h3M17.6 10h3M17.6 14h3"/></symbol>
<symbol id="pd-i-refresh" viewBox="0 0 24 24"><path d="M20.2 11.2a8.2 8.2 0 0 0-14.4-4.4L3.4 9"/><path d="M3.8 12.8a8.2 8.2 0 0 0 14.4 4.4l2.4-2.2"/><path d="M3.4 4.6V9h4.4M20.6 19.4V15h-4.4"/></symbol>
<symbol id="pd-i-image" viewBox="0 0 24 24"><rect x="3.4" y="4.8" width="17.2" height="14.4" rx="2.2"/><circle cx="8.6" cy="9.8" r="1.6"/><path d="M4.2 17.4 9.4 12l3.4 3.4 3-2.6 4.4 4.2"/></symbol>
</defs></svg>
<div class="pd-wrap">
  <div class="pd-phone">
    <div class="pd-notch"></div>

    <header class="pd-header">
      <div class="pd-hd-bg"></div>
      <div class="pd-brand">
        <div class="pd-logo">🌿</div>
        <div>
          <div class="pd-appname" data-i18n="appName"></div>
          <div class="pd-tagline" data-i18n="tagline"></div>
        </div>
      </div>
      <div class="pd-langs" id="pd-langs">
        <button data-lang="english">EN</button>
        <button data-lang="hindi">हिं</button>
        <button data-lang="marathi">मर</button>
      </div>
    </header>

    <div class="pd-offline"><i class="pd-dot"></i><span data-i18n="offline"></span></div>

    <main class="pd-body" id="pd-body">

      <!-- ─────────── HOME ─────────── -->
      <section class="pd-screen active" id="s-home">
        <div class="pd-hero">
          <div class="pd-hero-t" data-i18n="heroTitle"></div>
          <div class="pd-hero-s" data-i18n="heroSub"></div>
          <button class="pd-scan" data-go="camera">
            <span class="pd-scan-ico"><svg class="pd-ico-svg" style="width:17px;height:17px"><use href="#pd-i-camera"></use></svg></span>
            <span data-i18n="scanBtn"></span>
          </button>
          <button class="pd-ghost light" data-go="camera">
            <svg class="pd-ico-svg" style="width:15px;height:15px"><use href="#pd-i-image"></use></svg> <span data-i18n="galleryBtn"></span>
          </button>
        </div>

        <div class="pd-chips">
          <div class="pd-chip"><b>38</b><span data-i18n="statDiseases"></span></div>
          <div class="pd-chip"><b>14</b><span data-i18n="statCrops"></span></div>
          <div class="pd-chip"><b>3</b><span data-i18n="statLangs"></span></div>
        </div>

        <div class="pd-card k-lime">
          <div class="pd-card-t c-lime">
            <span class="pd-icobox"><svg class="pd-ico-svg"><use href="#pd-i-bulb"></use></svg></span><span class="st" data-i18n="tipsTitle"></span>
          </div>
          <ul class="pd-tips" id="pd-tips"></ul>
        </div>

        <div class="pd-mini">
          <b><svg class="pd-ico-svg" style="width:13px;height:13px"><use href="#pd-i-cpu"></use></svg> <span data-i18n="modelTitle"></span></b><br>
          <span id="pd-modelinfo"></span>
        </div>
      </section>

      <!-- ─────────── CAMERA ─────────── -->
      <section class="pd-screen" id="s-camera">
        <div class="pd-view">
          <img id="pd-viewimg" alt="leaf">
          <div class="pd-frame">
            <i class="c tl"></i><i class="c tr"></i><i class="c bl"></i><i class="c br"></i>
            <div class="pd-frame-hint" data-i18n="camHint"></div>
          </div>
          <div class="pd-view-title" data-i18n="camTitle"></div>
        </div>
        <div class="pd-card k-lime" style="margin-top:10px">
          <div class="pd-card-t c-lime">
            <span class="pd-icobox"><svg class="pd-ico-svg"><use href="#pd-i-bulb"></use></svg></span><span class="st" data-i18n="tipsTitle"></span>
          </div>
          <ul class="pd-tips compact" id="pd-tips2"></ul>
        </div>
        <button class="pd-scan wide" id="pd-capture">
          <span class="pd-scan-ico"><svg class="pd-ico-svg" style="width:17px;height:17px"><use href="#pd-i-aperture"></use></svg></span>
          <span data-i18n="captureBtn"></span>
        </button>
      </section>

      <!-- ─────────── RESULT ─────────── -->
      <section class="pd-screen" id="s-result">
        <div class="pd-scanline" id="pd-loading">
          <div class="pd-spin"></div>
          <div data-i18n="analyzing"></div>
        </div>

        <div id="pd-resultbody" style="display:none">
          <div class="pd-shot">
            <img id="pd-thumb" alt="leaf">
          </div>

          <div class="pd-verdict">
            <div class="pd-ring" id="pd-ring"><div class="pd-ringin">
              <b id="pd-badgepct">0%</b><small data-i18n="match"></small>
            </div></div>
            <div class="pd-verdict-t">
              <small data-i18n="verdict"></small>
              <div class="nm" id="pd-verdictname">—</div>
              <span class="pd-sev" id="pd-badgesev">—</span>
            </div>
          </div>

          <div class="pd-card k-amber" id="pd-lowbox" style="display:none;background:#FFFDF7">
            <div class="pd-card-t c-amber">
              <span class="pd-icobox"><svg class="pd-ico-svg"><use href="#pd-i-warn"></use></svg></span><span class="st" data-i18n="lowTitle"></span>
            </div>
            <p class="pd-p" data-i18n="lowBody"></p>
            <button class="pd-ghost small" data-go="camera"><svg class="pd-ico-svg" style="width:14px;height:14px"><use href="#pd-i-refresh"></use></svg> <span data-i18n="retake"></span></button>
          </div>

          <div class="pd-card k-green">
            <div class="pd-card-t c-green">
              <span class="pd-ico">📊</span><span class="st" data-i18n="top3Title"></span>
            </div>
            <div id="pd-top3"></div>
            <div class="pd-taphint" data-i18n="tapHint"></div>
          </div>

          <button class="pd-scan wide" data-go="care">
            <svg class="pd-ico-svg" style="width:16px;height:16px"><use href="#pd-i-leaf"></use></svg> <span data-i18n="viewCare"></span>
          </button>
        </div>
      </section>

      <!-- ─────────── TREATMENT ─────────── -->
      <section class="pd-screen" id="s-care">
        <div class="pd-illhead">
          <div class="pd-illname" id="pd-tname">—</div>
          <div class="pd-sevrow">
            <span class="pd-sev" id="pd-sev">—</span>
            <span class="pd-sevpct" id="pd-sevpct"></span>
          </div>
        </div>

        <div class="pd-card k-teal">
          <div class="pd-card-t c-teal">
            <span class="pd-icobox"><svg class="pd-ico-svg"><use href="#pd-i-clip"></use></svg></span><span class="st" data-i18n="desc"></span>
            <button class="pd-spk" data-say="desc"><svg class="pd-ico-svg"><use href="#pd-i-sound"></use></svg></button>
          </div>
          <p class="pd-p" id="pd-desc"></p>
        </div>

        <div class="pd-card k-green">
          <div class="pd-card-t c-green">
            <span class="pd-icobox"><svg class="pd-ico-svg"><use href="#pd-i-sprout"></use></svg></span><span class="st" data-i18n="organic"></span>
            <button class="pd-spk" data-say="org"><svg class="pd-ico-svg"><use href="#pd-i-sound"></use></svg></button>
          </div>
          <p class="pd-p" id="pd-org"></p>
        </div>

        <div class="pd-card k-red">
          <div class="pd-card-t c-red">
            <span class="pd-icobox"><svg class="pd-ico-svg"><use href="#pd-i-pill"></use></svg></span><span class="st" data-i18n="chemical"></span>
            <button class="pd-spk" data-say="chem"><svg class="pd-ico-svg"><use href="#pd-i-sound"></use></svg></button>
          </div>
          <p class="pd-p" id="pd-chem"></p>
        </div>

        <div class="pd-card k-blue">
          <div class="pd-card-t c-blue">
            <span class="pd-icobox"><svg class="pd-ico-svg"><use href="#pd-i-shield"></use></svg></span><span class="st" data-i18n="prevention"></span>
            <button class="pd-spk" data-say="prev"><svg class="pd-ico-svg"><use href="#pd-i-sound"></use></svg></button>
          </div>
          <p class="pd-p" id="pd-prev"></p>
        </div>

        <button class="pd-readall" id="pd-readall"><svg class="pd-ico-svg" style="width:15px;height:15px"><use href="#pd-i-sound"></use></svg> <span data-i18n="readAll"></span></button>

        <div class="pd-expert">👨‍🌾 <span data-i18n="expert"></span></div>
      </section>

      <!-- ─────────── ABOUT ─────────── -->
      <section class="pd-screen" id="s-about">
        <div class="pd-card k-green">
          <div class="pd-card-t c-green">
            <span class="pd-icobox"><svg class="pd-ico-svg"><use href="#pd-i-info"></use></svg></span><span class="st" data-i18n="aboutTitle"></span>
          </div>
          <p class="pd-p" data-i18n="aboutBody"></p>
        </div>
        <div class="pd-card k-teal">
          <div class="pd-card-t c-teal">
            <span class="pd-icobox"><svg class="pd-ico-svg"><use href="#pd-i-list"></use></svg></span><span class="st" data-i18n="howTitle"></span>
          </div>
          <ul class="pd-tips" id="pd-how"></ul>
        </div>
        <div class="pd-card k-amber">
          <div class="pd-card-t c-amber">
            <span class="pd-icobox"><svg class="pd-ico-svg"><use href="#pd-i-warn"></use></svg></span><span class="st" data-i18n="limitsTitle"></span>
          </div>
          <ul class="pd-tips warn" id="pd-limits"></ul>
        </div>
        <div class="pd-mini">
          <b data-i18n="modelTitle"></b><br><span id="pd-modelinfo2"></span>
        </div>
      </section>

    </main>

    <nav class="pd-nav">
      <button data-go="home"   class="active"><span><svg class="pd-ico-svg"><use href="#pd-i-home"></use></svg></span><small data-i18n="navHome"></small></button>
      <button data-go="camera"><span><svg class="pd-ico-svg"><use href="#pd-i-camera"></use></svg></span><small data-i18n="navCamera"></small></button>
      <button data-go="result"><span><svg class="pd-ico-svg"><use href="#pd-i-chart"></use></svg></span><small data-i18n="navResult"></small></button>
      <button data-go="care"><span><svg class="pd-ico-svg"><use href="#pd-i-leaf"></use></svg></span><small data-i18n="navCare"></small></button>
      <button data-go="about"><span><svg class="pd-ico-svg"><use href="#pd-i-info"></use></svg></span><small data-i18n="navAbout"></small></button>
    </nav>
  </div>
</div>

<style>
/* ══════════════════════════════════════════════════════════════
   KISAN PLANT DOCTOR — v3 theme
   palette  g900 #0A2E17 · g800 #123F1E · g700 #1B5E20 · g600 #2E7D32
            g500 #3E9A43 · g400 #43A047 · g300 #66BB6A · g200 #A5D6A7
            g100 #C8E6C9 · g050 #E8F5E9 · mint #DFF3E3 · lime #7CB342
   accents  teal #00695C · amber #EF6C00 · red #C62828 · blue #1565C0
   ══════════════════════════════════════════════════════════════ */
.pd-wrap{
  --wall-page:none; --wall-hero:none; --wall-app:none;
  --r-lg:20px; --r-md:16px; --r-sm:12px;
  --sh-1:0 1px 2px rgba(11,46,23,.05), 0 2px 8px rgba(11,46,23,.05);
  --sh-2:0 1px 2px rgba(11,46,23,.06), 0 8px 22px rgba(11,46,23,.09);
  --sh-3:0 10px 30px rgba(10,46,23,.16);
  position:relative; overflow:hidden; border-radius:26px; padding:32px 16px;
  display:flex; justify-content:center;
  font-family:"Inter","Inter var",system-ui,-apple-system,"Segoe UI Variable Text",
              "Segoe UI","Nirmala UI","Noto Sans Devanagari","Noto Sans",Roboto,sans-serif;
  -webkit-font-smoothing:antialiased; -moz-osx-font-smoothing:grayscale;
  font-feature-settings:"cv11" 1,"ss01" 1; font-optical-sizing:auto;
  background-color:#0B2E17;
  background-image:var(--wall-page),linear-gradient(150deg,#0E3D1C 0%,#123F1E 45%,#071E0E 100%);
  background-size:cover,cover; background-position:center,center;
  box-shadow:inset 0 0 140px rgba(0,0,0,.62)}
.pd-wrap:after{content:"";position:absolute;inset:0;pointer-events:none;
  background:radial-gradient(620px 320px at 18% 12%,rgba(102,187,106,.20),transparent 70%),
             radial-gradient(520px 280px at 82% 86%,rgba(124,179,66,.15),transparent 70%)}
.pd-sprite{display:none}
.pd-ico-svg{width:14px;height:14px;fill:none;stroke:currentColor;stroke-width:1.9;
  stroke-linecap:round;stroke-linejoin:round;flex:none}

/* ── device ─────────────────────────────────────────────────── */
.pd-phone{position:relative;z-index:1;width:352px;height:772px;background:#F2F8F3;
  border:11px solid #0B100D;border-radius:44px;overflow:hidden;
  display:flex;flex-direction:column;
  box-shadow:0 28px 70px rgba(0,0,0,.6),0 0 0 1px rgba(150,190,160,.20)}
.pd-notch{position:absolute;top:0;left:50%;transform:translateX(-50%);
  width:118px;height:17px;background:#0B100D;border-radius:0 0 12px 12px;z-index:9}

/* ── header ─────────────────────────────────────────────────── */
.pd-header{position:relative;overflow:hidden;color:#fff;padding:26px 15px 14px;
  display:flex;justify-content:space-between;align-items:center;
  background:linear-gradient(135deg,#0A2E17 0%,#1B5E20 42%,#2E7D32 74%,#43A047 100%);
  box-shadow:0 8px 22px rgba(10,46,23,.34)}
.pd-header:after{content:"";position:absolute;left:0;right:0;bottom:0;height:1px;
  background:linear-gradient(90deg,transparent,rgba(255,255,255,.35),transparent)}
.pd-hd-bg{position:absolute;inset:0;background-image:var(--wall-hero);
  background-size:cover;background-position:center;opacity:.34;mix-blend-mode:overlay}
.pd-header>*:not(.pd-hd-bg){position:relative;z-index:2}
.pd-brand{display:flex;gap:10px;align-items:center}
.pd-logo{width:36px;height:36px;border-radius:12px;font-size:18px;
  display:flex;align-items:center;justify-content:center;
  background:linear-gradient(150deg,#C8E6C9,#66BB6A 60%,#43A047);
  box-shadow:0 4px 12px rgba(0,0,0,.3),inset 0 1px 0 rgba(255,255,255,.6)}
.pd-appname{font-weight:800;font-size:15px;line-height:1.15;letter-spacing:-.2px;
  text-shadow:0 1px 4px rgba(0,0,0,.28)}
.pd-tagline{font-size:10px;opacity:.86;letter-spacing:.1px;margin-top:1px}
.pd-langs{display:flex;gap:3px;background:rgba(0,0,0,.28);padding:3px;border-radius:13px}
.pd-langs button{border:0;background:transparent;color:#C8E6C9;font-size:10px;font-weight:800;
  letter-spacing:.2px;padding:5px 9px;border-radius:10px;cursor:pointer;
  font-family:inherit;transition:.18s}
.pd-langs button:hover{color:#fff}
.pd-langs button.on{background:linear-gradient(180deg,#FFFFFF,#DFF3E3);color:#0A2E17;
  box-shadow:0 2px 7px rgba(0,0,0,.24)}

.pd-offline{display:flex;align-items:center;justify-content:center;gap:7px;
  background:linear-gradient(90deg,#07200F 0%,#123F1E 50%,#07200F 100%);
  color:#8FD9A0;font-size:8.5px;padding:6px;letter-spacing:1px;font-weight:800;
  text-transform:uppercase}
.pd-dot{width:6px;height:6px;border-radius:50%;background:#66BB6A;animation:pdpulse 2.2s infinite}
@keyframes pdpulse{0%{box-shadow:0 0 0 0 rgba(102,187,106,.85)}
  70%{box-shadow:0 0 0 8px rgba(102,187,106,0)}100%{box-shadow:0 0 0 0 rgba(102,187,106,0)}}

/* ── body ───────────────────────────────────────────────────── */
.pd-body{flex:1;overflow-y:auto;padding:14px 13px 18px;background-color:#F2F8F3;
  background-image:linear-gradient(180deg,rgba(247,252,248,.90) 0%,rgba(233,246,236,.94) 58%,rgba(223,241,227,.96) 100%),var(--wall-app);
  background-size:auto,cover;background-position:center,center top;
  background-repeat:no-repeat,no-repeat;scrollbar-width:thin}
.pd-body::-webkit-scrollbar{width:5px}
.pd-body::-webkit-scrollbar-thumb{background:#A5D6A7;border-radius:3px}
.pd-screen{display:none}
.pd-screen.active{display:block}
.pd-screen.active>*{animation:pdup .42s cubic-bezier(.2,.7,.3,1) both}
.pd-screen.active>*:nth-child(2){animation-delay:.05s}
.pd-screen.active>*:nth-child(3){animation-delay:.10s}
.pd-screen.active>*:nth-child(4){animation-delay:.15s}
.pd-screen.active>*:nth-child(5){animation-delay:.20s}
.pd-screen.active>*:nth-child(6){animation-delay:.25s}
@keyframes pdup{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:none}}

/* ── hero ───────────────────────────────────────────────────── */
.pd-hero{position:relative;overflow:hidden;color:#fff;border-radius:22px;
  padding:19px 16px 15px;text-align:center;margin-bottom:11px;
  background:linear-gradient(150deg,#0E3D1C 0%,#1B5E20 38%,#2E7D32 74%,#3E9A43 100%);
  box-shadow:0 10px 26px rgba(15,61,28,.30),inset 0 1px 0 rgba(255,255,255,.10)}
.pd-hero:before{content:"";position:absolute;inset:0;background-image:var(--wall-hero);
  background-size:cover;background-position:center;opacity:.32;mix-blend-mode:overlay}
.pd-hero:after{content:"🌿";position:absolute;right:-22px;bottom:-34px;font-size:120px;
  opacity:.12;transform:rotate(-14deg)}
.pd-hero>*{position:relative;z-index:2}
.pd-hero-t{font-size:19px;font-weight:800;letter-spacing:-.4px;line-height:1.25;
  text-shadow:0 1px 5px rgba(0,0,0,.30)}
.pd-hero-s{font-size:11.5px;color:#DFF3E3;margin:7px 0 14px;line-height:1.55;opacity:.95}

/* ── buttons ────────────────────────────────────────────────── */
.pd-scan{width:100%;border:0;border-radius:15px;padding:14px;font-size:13.5px;font-weight:800;
  letter-spacing:.2px;cursor:pointer;color:#0A2E17;display:flex;align-items:center;
  justify-content:center;gap:9px;font-family:inherit;
  background:linear-gradient(135deg,#F0FAF1 0%,#A5D6A7 45%,#5CB25F 100%);
  box-shadow:0 7px 18px rgba(10,46,23,.30),inset 0 1px 0 rgba(255,255,255,.7);
  transition:transform .12s,box-shadow .12s}
.pd-scan:hover{box-shadow:0 9px 22px rgba(10,46,23,.36),inset 0 1px 0 rgba(255,255,255,.7)}
.pd-scan:active{transform:scale(.985)}
.pd-scan.wide{margin-top:12px}
.pd-scan-ico{font-size:15px;display:flex}
.pd-ghost{width:100%;background:#fff;color:#2E7D32;border:1.5px solid #A5D6A7;border-radius:15px;
  padding:11px;font-size:12.5px;font-weight:800;letter-spacing:.2px;cursor:pointer;margin-top:9px;
  display:flex;align-items:center;justify-content:center;gap:8px;font-family:inherit;
  transition:.16s}
.pd-ghost:hover{background:#F4FBF5;border-color:#66BB6A}
.pd-ghost.light{background:rgba(255,255,255,.14);border-color:rgba(255,255,255,.45);color:#fff}
.pd-ghost.light:hover{background:rgba(255,255,255,.22);border-color:rgba(255,255,255,.65)}
.pd-ghost.small{padding:9px;font-size:11.5px;margin-top:10px}
.pd-readall{width:100%;border:0;border-radius:15px;padding:13px;font-size:12.5px;font-weight:800;
  letter-spacing:.2px;cursor:pointer;margin-bottom:12px;color:#EAF7EC;display:flex;
  align-items:center;justify-content:center;gap:8px;font-family:inherit;
  background:linear-gradient(135deg,#123F1E 0%,#2E7D32 55%,#3E9A43 100%);
  box-shadow:0 7px 18px rgba(27,94,32,.30),inset 0 1px 0 rgba(255,255,255,.16);
  transition:transform .12s}
.pd-readall:active{transform:scale(.985)}

/* ── cards ──────────────────────────────────────────────────── */
.pd-card{background:rgba(255,255,255,.96);border:1px solid rgba(11,46,23,.07);
  border-radius:var(--r-md);padding:13px;margin-bottom:10px;box-shadow:var(--sh-2)}
.pd-card-t{display:flex;align-items:center;gap:8px;font-size:12.5px;font-weight:800;
  letter-spacing:.1px;margin-bottom:9px}
.pd-card-t .st{flex:1}
.pd-icobox{width:26px;height:26px;border-radius:9px;flex:none;
  display:inline-flex;align-items:center;justify-content:center}
.pd-icobox .pd-ico-svg{width:15px;height:15px;stroke-width:2}
.k-teal{border-left:4px solid #00695C}.c-teal{color:#00695C}.c-teal .pd-icobox{background:#E0F2F1}
.k-green{border-left:4px solid #2E7D32}.c-green{color:#2E7D32}.c-green .pd-icobox{background:#E8F5E9}
.k-red{border-left:4px solid #C62828}.c-red{color:#C62828}.c-red .pd-icobox{background:#FFEBEE}
.k-blue{border-left:4px solid #1565C0}.c-blue{color:#1565C0}.c-blue .pd-icobox{background:#E3F2FD}
.k-amber{border-left:4px solid #EF6C00}.c-amber{color:#E65100}.c-amber .pd-icobox{background:#FFF3E0}
.k-lime{border-left:4px solid #7CB342}.c-lime{color:#558B2F}.c-lime .pd-icobox{background:#F1F8E9}
.pd-p{margin:0;font-size:12px;color:#3A3A3A;line-height:1.7}
.pd-spk{border:0;background:rgba(15,61,28,.07);color:inherit;border-radius:9px;width:28px;height:26px;
  cursor:pointer;display:flex;align-items:center;justify-content:center;flex:none;transition:.16s}
.pd-spk:hover{background:rgba(15,61,28,.14)}
.pd-spk .pd-ico-svg{width:15px;height:15px;stroke-width:2}

/* ── stat chips ─────────────────────────────────────────────── */
.pd-chips{display:flex;gap:7px;margin-bottom:10px}
.pd-chip{flex:1;background:rgba(255,255,255,.95);border:1px solid rgba(11,46,23,.07);
  border-radius:14px;padding:9px 4px;text-align:center;box-shadow:var(--sh-1)}
.pd-chip b{display:block;font-size:16px;font-weight:900;color:#1B5E20;line-height:1.1;
  letter-spacing:-.5px}
.pd-chip span{font-size:9px;font-weight:700;color:#7A8A7E;letter-spacing:.3px}

/* ── lists ──────────────────────────────────────────────────── */
.pd-tips{margin:0;padding-left:0;list-style:none}
.pd-tips li{font-size:11.5px;color:#414743;padding:5px 0 5px 27px;
  position:relative;line-height:1.55}
.pd-tips li:before{content:"";position:absolute;left:0;top:6px;width:18px;height:18px;
  border-radius:50%;background:#E8F5E9;
  background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%232E7D32' stroke-width='3' stroke-linecap='round' stroke-linejoin='round'><path d='M20 6 9 17l-5-5'/></svg>");
  background-size:12px;background-repeat:no-repeat;background-position:center}
.pd-tips.warn li:before{background-color:#FFF3E0;
  background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23E65100' stroke-width='2.6' stroke-linecap='round' stroke-linejoin='round'><path d='M12 9v4M12 17h.01'/></svg>")}
.pd-tips.compact li{font-size:11px;padding:5px 0 5px 26px}
.pd-mini{background:linear-gradient(135deg,#E8F5E9,#DFF3E3);border:1px solid #C8E6C9;
  border-radius:14px;padding:11px;font-size:10px;color:#2E5B32;line-height:1.7}

/* ── camera ─────────────────────────────────────────────────── */
.pd-view{position:relative;height:276px;border-radius:22px;overflow:hidden;background:#0B2E17;
  box-shadow:0 8px 22px rgba(11,46,23,.30)}
.pd-view img{width:100%;height:100%;object-fit:cover;display:block}
.pd-view:after{content:"";position:absolute;inset:0;pointer-events:none;
  background:radial-gradient(circle at 50% 47%,transparent 36%,rgba(6,20,10,.52) 100%)}
.pd-view-title{position:absolute;top:11px;left:0;right:0;text-align:center;color:#fff;z-index:4;
  font-size:11.5px;font-weight:800;letter-spacing:.2px;text-shadow:0 1px 6px rgba(0,0,0,.85)}
.pd-frame{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);z-index:3;
  width:176px;height:176px;border:2px dashed rgba(255,255,255,.92);border-radius:18px;
  box-shadow:0 0 0 9999px rgba(8,26,14,.34)}
.pd-frame .c{position:absolute;width:26px;height:26px;border:3px solid #9CCC65;border-radius:5px;
  filter:drop-shadow(0 0 5px rgba(156,204,101,.9))}
.pd-frame .tl{top:-3px;left:-3px;border-right:0;border-bottom:0}
.pd-frame .tr{top:-3px;right:-3px;border-left:0;border-bottom:0}
.pd-frame .bl{bottom:-3px;left:-3px;border-right:0;border-top:0}
.pd-frame .br{bottom:-3px;right:-3px;border-left:0;border-top:0}
.pd-frame-hint{position:absolute;bottom:-28px;left:0;right:0;text-align:center;color:#fff;
  font-size:10px;font-weight:700;letter-spacing:.2px;text-shadow:0 1px 5px rgba(0,0,0,.9)}

/* ── result ─────────────────────────────────────────────────── */
.pd-shot{position:relative;border-radius:22px;overflow:hidden;margin-bottom:12px;
  box-shadow:0 8px 22px rgba(11,46,23,.24)}
.pd-shot img{width:100%;height:152px;object-fit:cover;display:block}
.pd-verdict{display:flex;align-items:center;gap:13px;background:rgba(255,255,255,.97);
  border:1px solid rgba(11,46,23,.07);border-radius:var(--r-md);padding:13px;margin-bottom:11px;
  box-shadow:var(--sh-2)}
.pd-ring{width:72px;height:72px;border-radius:50%;flex:none;display:flex;align-items:center;
  justify-content:center;
  background:conic-gradient(from -90deg,var(--rc2,#7BC47F) 0deg,var(--rc,#1B5E20) calc(var(--v,0)*3.6deg),#DDEBE0 calc(var(--v,0)*3.6deg));
  box-shadow:0 4px 14px rgba(11,46,23,.24);transition:background .5s ease}
.pd-ringin{width:56px;height:56px;border-radius:50%;background:#fff;display:flex;flex-direction:column;
  align-items:center;justify-content:center;box-shadow:inset 0 1px 4px rgba(11,46,23,.14)}
.pd-ringin b{font-size:17px;font-weight:900;color:#1B5E20;letter-spacing:-.7px;line-height:1}
.pd-ringin small{font-size:7.5px;color:#93A096;font-weight:800;letter-spacing:.4px;margin-top:2px}
.pd-verdict-t{flex:1;min-width:0}
.pd-verdict-t small{display:block;font-size:8.5px;font-weight:800;letter-spacing:1px;
  text-transform:uppercase;color:#93A096;margin-bottom:3px}
.pd-verdict-t .nm{font-size:14px;font-weight:800;color:#14251A;letter-spacing:-.25px;line-height:1.3}
.pd-verdict-t .pd-sev{margin-top:7px}
.pd-sev{display:inline-block;padding:4px 11px;border-radius:20px;font-size:9.5px;font-weight:900;
  letter-spacing:.4px;text-transform:uppercase;box-shadow:0 2px 7px rgba(0,0,0,.14)}
.pd-row{padding:10px;border-radius:13px;cursor:pointer;margin-bottom:6px;
  border:1.5px solid transparent;transition:.16s;background:rgba(255,255,255,.72)}
.pd-row:hover{background:#F1F8E9;border-color:#C8E6C9}
.pd-row.sel{background:linear-gradient(90deg,#F1F8E9,#FFFFFF);border-color:#66BB6A;
  box-shadow:0 2px 8px rgba(46,125,50,.12)}
.pd-row-t{display:flex;justify-content:space-between;align-items:baseline;
  font-size:11.5px;font-weight:700;gap:8px}
.pd-row-t b{color:#1B1B1B;font-weight:700;letter-spacing:-.1px}
.pd-row-t span{color:#1B5E20;white-space:nowrap;font-weight:800;font-size:11.5px}
.pd-bar{background:#DFE8E0;height:8px;border-radius:6px;overflow:hidden;margin-top:7px;
  box-shadow:inset 0 1px 2px rgba(0,0,0,.09)}
.pd-bar i{display:block;height:100%;border-radius:6px;width:0;
  background:linear-gradient(90deg,#66BB6A,#2E7D32);
  transition:width .8s cubic-bezier(.2,.8,.2,1)}
.pd-row:nth-child(2) .pd-bar i{background:linear-gradient(90deg,#A5D6A7,#4E9B52)}
.pd-row:nth-child(3) .pd-bar i{background:linear-gradient(90deg,#C8E6C9,#7CB342)}
.pd-taphint{font-size:9.5px;color:#93A096;text-align:center;margin-top:9px;letter-spacing:.2px}
.pd-scanline{text-align:center;padding:64px 0;color:#2E7D32;font-size:12.5px;font-weight:700;
  letter-spacing:.2px}
.pd-spin{width:42px;height:42px;margin:0 auto 16px;border-radius:50%;
  border:4px solid #C8E6C9;border-top-color:#1B5E20;border-right-color:#43A047;
  animation:pds 900ms linear infinite}
@keyframes pds{to{transform:rotate(360deg)}}

/* ── treatment ──────────────────────────────────────────────── */
.pd-illhead{position:relative;overflow:hidden;color:#fff;border-radius:22px;padding:16px;
  margin-bottom:12px;
  background:linear-gradient(140deg,#0A2E17 0%,#1B5E20 48%,#2E7D32 100%);
  box-shadow:0 10px 26px rgba(15,61,28,.28),inset 0 1px 0 rgba(255,255,255,.10)}
.pd-illhead:before{content:"";position:absolute;inset:0;background-image:var(--wall-hero);
  background-size:cover;background-position:center;opacity:.30;mix-blend-mode:overlay}
.pd-illhead>*{position:relative;z-index:2}
.pd-illname{font-size:16.5px;font-weight:800;line-height:1.35;letter-spacing:-.3px;
  text-shadow:0 1px 7px rgba(0,0,0,.32)}
.pd-sevrow{display:flex;align-items:center;gap:9px;margin-top:11px;flex-wrap:wrap}
.pd-sevpct{font-size:10px;font-weight:700;color:#C8E6C9;letter-spacing:.2px}
.pd-expert{background:linear-gradient(135deg,#FFF8E1,#FFF3E0);border:1px solid #FFCC80;
  border-radius:16px;padding:12px;font-size:10.5px;color:#7F4F00;line-height:1.7}

/* ── nav ────────────────────────────────────────────────────── */
.pd-nav{display:flex;background:linear-gradient(180deg,#FFFFFF,#F4FAF6);
  border-top:1px solid #DDEBE0;padding:7px 4px 9px;
  box-shadow:0 -5px 16px rgba(11,46,23,.08)}
.pd-nav button{flex:1;background:none;border:0;cursor:pointer;padding:5px 0 3px;border-radius:14px;
  display:flex;flex-direction:column;align-items:center;gap:3px;font-family:inherit;
  transition:.18s}
.pd-nav button .pd-ico-svg{width:22px;height:22px;stroke-width:1.8;color:#8FA096;transition:.18s}
.pd-nav button small{font-size:8.5px;color:#9AA79E;font-weight:800;letter-spacing:.2px;
  transition:.18s}
.pd-nav button:hover .pd-ico-svg{color:#5C7A63}
.pd-nav button.active{background:linear-gradient(180deg,#E8F5E9,#DCF2E0)}
.pd-nav button.active .pd-ico-svg{color:#1B5E20;transform:translateY(-1px)}
.pd-nav button.active small{color:#1B5E20}
</style>

<script>
(function(){
  var STR = __STRINGS__;
  var RES = __RESULT__;
  var LANGTAG = {english:"en-IN", hindi:"hi-IN", marathi:"mr-IN"};
  var lang = "__LANG__";
  var sel  = 0;

  function T(k){ return (STR[lang] && STR[lang][k] != null) ? STR[lang][k]
                        : (STR.english[k] != null ? STR.english[k] : k); }
  function $(s){ return document.querySelector(s); }
  function $$(s){ return Array.prototype.slice.call(document.querySelectorAll(s)); }

  function fillList(el, arr){
    if(!el || !arr) return;
    el.innerHTML = "";
    arr.forEach(function(x){ var li=document.createElement("li"); li.textContent=x; el.appendChild(li); });
  }

  function staticText(){
    $$("[data-i18n]").forEach(function(e){ e.textContent = T(e.getAttribute("data-i18n")); });
    fillList($("#pd-tips"),   T("tips"));
    fillList($("#pd-tips2"),  T("tips"));
    fillList($("#pd-how"),    T("how"));
    fillList($("#pd-limits"), T("limits"));
    $$("#pd-langs button").forEach(function(b){
      b.className = (b.getAttribute("data-lang") === lang) ? "on" : "";
    });
    var mi = "__MODELINFO__";
    if($("#pd-modelinfo"))  $("#pd-modelinfo").textContent  = mi;
    if($("#pd-modelinfo2")) $("#pd-modelinfo2").textContent = mi;
  }

  function renderTop3(){
    var box = $("#pd-top3"); box.innerHTML = "";
    RES.top3.forEach(function(r, i){
      var d = document.createElement("div");
      d.className = "pd-row" + (i === sel ? " sel" : "");
      d.innerHTML = '<div class="pd-row-t"><b>' + r.plant + " — " + r.disease +
                    '</b><span>' + r.conf.toFixed(1) + "%</span></div>" +
                    '<div class="pd-bar"><i data-w="' + Math.max(r.conf,1.5) + '"></i></div>';
      d.onclick = function(){ sel = i; renderTop3(); renderCare(); go("care"); };
      box.appendChild(d);
    });
    requestAnimationFrame(function(){
      box.querySelectorAll(".pd-bar i").forEach(function(i){
        i.style.width = i.getAttribute("data-w") + "%";
      });
    });
  }

  function renderVerdict(){
    var top = RES.top3[0], M = __SEV__;
    var low = top.conf < __LOWCONF__;
    var ring = $("#pd-ring");
    ring.style.setProperty("--v", top.conf);
    ring.style.setProperty("--rc",  low ? "#E65100" : "#1B5E20");
    ring.style.setProperty("--rc2", low ? "#FFB74D" : "#7BC47F");
    $("#pd-badgepct").textContent = Math.round(top.conf) + "%";
    var t = (top.treat[lang] || top.treat.english || {});
    $("#pd-verdictname").textContent = t.name || (top.plant + " — " + top.disease);
    var meta = M[top.sevKey] ? M[top.sevKey] : M.medium;
    var sb = $("#pd-badgesev");
    sb.textContent = meta[2][lang] || meta[2].english;
    sb.style.background = meta[0]; sb.style.color = meta[1];
  }

  function renderResult(){
    var top = RES.top3[0];
    var th = document.getElementById("pd-thumb");  if(th) th.src = RES.image;
    var vi = document.getElementById("pd-viewimg"); if(vi) vi.src = RES.image;
    $("#pd-lowbox").style.display = (top.conf < __LOWCONF__) ? "block" : "none";
    renderVerdict(); renderTop3(); renderCare();
  }

  function renderCare(){
    var r = RES.top3[sel];
    if(!r) return;
    var t = r.treat[lang] || r.treat.english || {};
    $("#pd-tname").textContent = t.name || (r.plant + " — " + r.disease);
    $("#pd-desc").textContent  = t.desc || "—";
    $("#pd-org").textContent   = t.org  || "—";
    $("#pd-chem").textContent  = t.chem || "—";
    $("#pd-prev").textContent  = t.prev || "—";

    var M = __SEV__;
    var meta = M[r.sevKey] ? M[r.sevKey] : M.medium;
    var b = $("#pd-sev");
    b.textContent = (meta[2][lang] || meta[2].english);
    b.style.background = meta[0];
    b.style.color = meta[1];
    $("#pd-sevpct").textContent = r.conf.toFixed(1) + "% " + T("match");
  }

  function go(id){
    $$(".pd-screen").forEach(function(s){ s.classList.remove("active"); });
    var el = document.getElementById("s-" + id);
    if(el) el.classList.add("active");
    $$(".pd-nav button").forEach(function(b){
      b.classList.toggle("active", b.getAttribute("data-go") === id);
    });
    $("#pd-body").scrollTop = 0;
    if(id === "result") runAnalysis();
  }

  var analysed = false;
  function runAnalysis(){
    if(analysed) return;
    analysed = true;
    $("#pd-loading").style.display = "block";
    $("#pd-resultbody").style.display = "none";
    setTimeout(function(){
      $("#pd-loading").style.display = "none";
      $("#pd-resultbody").style.display = "block";
      renderResult();
    }, 1100);
  }

  function pickVoice(tag){
    var vs = window.speechSynthesis ? window.speechSynthesis.getVoices() : [];
    if(!vs.length) return null;
    var pref = tag.split("-")[0], i;
    for(i=0;i<vs.length;i++){ if(vs[i].lang && vs[i].lang.replace("_","-") === tag) return vs[i]; }
    for(i=0;i<vs.length;i++){ if(vs[i].lang && vs[i].lang.split("-")[0] === pref) return vs[i]; }
    return null;
  }
  function speak(text){
    if(!text) return;
    if(!("speechSynthesis" in window)){ alert("Speech not supported in this browser"); return; }
    try{ window.speechSynthesis.cancel(); }catch(e){}
    var u = new SpeechSynthesisUtterance(String(text));
    u.lang = LANGTAG[lang] || "en-IN";
    u.rate = 0.92; u.pitch = 1;
    var v = pickVoice(u.lang);
    if(v) u.voice = v;
    window.speechSynthesis.speak(u);
  }

  $$("[data-go]").forEach(function(b){
    b.addEventListener("click", function(){ go(b.getAttribute("data-go")); });
  });
  $$("#pd-langs button").forEach(function(b){
    b.addEventListener("click", function(){
      lang = b.getAttribute("data-lang");
      staticText(); renderVerdict(); renderTop3(); renderCare();
      try{ window.speechSynthesis.cancel(); }catch(e){}
    });
  });
  $$(".pd-spk").forEach(function(b){
    b.addEventListener("click", function(){
      var k = b.getAttribute("data-say"), r = RES.top3[sel];
      var t = (r && (r.treat[lang] || r.treat.english)) || {};
      speak((t.name ? t.name + ". " : "") + (t[k] || ""));
    });
  });
  $("#pd-readall").addEventListener("click", function(){
    var r = RES.top3[sel];
    var t = (r && (r.treat[lang] || r.treat.english)) || {};
    speak([t.name, T("desc") + ": " + t.desc, T("organic") + ": " + t.org,
           T("chemical") + ": " + t.chem, T("prevention") + ": " + t.prev].join(". "));
  });
  $("#pd-capture").addEventListener("click", function(){ analysed = false; go("result"); });

  if(window.speechSynthesis && window.speechSynthesis.getVoices){
    try{ window.speechSynthesis.getVoices(); }catch(e){}
  }

  staticText();
  renderResult();
  $("#pd-loading").style.display = "none";
  $("#pd-resultbody").style.display = "block";
  go("home");
})();
</script>
"""


# ══════════════════════════════════════════════════════════════════
#  5. RENDERER
# ══════════════════════════════════════════════════════════════════
def build_app_html(top3, image_b64, lang="hindi", model_info="", wallpaper_path=None,
                   font_css=""):
    """Build the phone-simulator HTML string."""
    for r in top3:
        healthy = "healthy" in r["disease"].lower()
        sev_src = (r["treat"].get("english", {}) or {}).get("sev", "")
        r["sevKey"] = _sev_key(sev_src, healthy)

    walls = {"page": "none", "hero": "none", "app": "none"}
    if wallpaper_path and os.path.exists(wallpaper_path):
        try:
            p, h, a = prepare_wallpapers(wallpaper_path)
            walls = {"page": p, "hero": h, "app": a}
        except Exception as e:
            print("⚠️  wallpaper skipped:", e)

    sev_json = {k: [v[0], v[1], v[2]] for k, v in SEV_META.items()}
    payload = {"top3": top3,
               "image": ("data:image/jpeg;base64," + image_b64) if image_b64 else ""}

    return (HTML_TEMPLATE
            .replace("--wall-page:none;", "--wall-page:" + walls["page"] + ";")
            .replace("--wall-hero:none;", "--wall-hero:" + walls["hero"] + ";")
            .replace("--wall-app:none;",  "--wall-app:"  + walls["app"]  + ";")
            .replace("__FONTCSS__",   font_css or "")
            .replace("__STRINGS__",   json.dumps(UI_STRINGS, ensure_ascii=False))
            .replace("__SEV__",       json.dumps(sev_json, ensure_ascii=False))
            .replace("__RESULT__",    json.dumps(payload, ensure_ascii=False))
            .replace("__MODELINFO__", json.dumps(model_info, ensure_ascii=False)[1:-1])
            .replace("__LOWCONF__",   str(float(LOW_CONF)))
            .replace("__LANG__",      lang))


LAST = {}   # remembers the last render, for rerun_ui()


def rerun_ui(lang="english"):
    """Re-render the LAST photo in another language. No re-upload, no re-inference."""
    if not LAST:
        print("Run  run_app_ui()  first.")
        return None
    display(HTML(build_app_html(LAST["top3"], LAST["b64"], lang=lang,
                                model_info=LAST["model_info"],
                                wallpaper_path=LAST["wallpaper_path"],
                                font_css=LAST["font_css"])))
    return LAST["top3"]


def run_app_ui(lang="hindi", photo_path=None, model_info=None, wallpaper_path=None):
    """Upload a photo (if needed), run TTA, render the app simulator."""
    _sync_globals()

    if wallpaper_path is None:
        wallpaper_path = WALLPAPER
        if wallpaper_path is None and os.path.exists("wallpaper.jpg"):
            wallpaper_path = "wallpaper.jpg"

    font_css = FONT_CSS
    if font_css is None and os.path.exists("inter_var.css"):
        try:
            font_css = io.open("inter_var.css", encoding="utf-8").read()
        except Exception:
            font_css = ""

    if photo_path is None:
        if files is None:
            raise RuntimeError("No photo path given and not running in Colab.")
        print("🍃 Choose a leaf photo:")
        up = files.upload()
        if not up:
            print("❌ No photo selected.")
            return
        photo_path = list(up.keys())[0]

    top3 = ui_predict_tta(photo_path, topk=3)

    img = Image.open(photo_path).convert("RGB")
    img.thumbnail((720, 720))
    buf = io.BytesIO(); img.save(buf, format="JPEG", quality=82)
    b64 = base64.b64encode(buf.getvalue()).decode()

    if model_info is None:
        model_info = ("MobileNetV2 · 38 classes · 160×160 · TFLite float16 · "
                      "94.66% lab validation · 5-view TTA · runs fully offline")

    LAST.clear()
    LAST.update(top3=top3, b64=b64, model_info=model_info,
                wallpaper_path=wallpaper_path, font_css=font_css)

    display(HTML(build_app_html(top3, b64, lang=lang,
                                model_info=model_info,
                                wallpaper_path=wallpaper_path,
                                font_css=font_css)))

    print("\nLanguage : %s" % lang)
    print("═" * 46)
    for i, r in enumerate(top3):
        print("  %s  %5.1f%%  %s — %s" % (["🥇", "🥈", "🥉"][i], r["conf"],
                                          r["plant"], r["disease"]))
    print("═" * 46)
    if top3[0]["conf"] < LOW_CONF:
        print("⚠️  Below %.0f%% — app will show the retake-photo screen." % LOW_CONF)
    print("✅  Confirm with your local agri-expert.\n")
    return top3


# ══════════════════════════════════════════════════════════════════
#  DEMO ONLY — preview builder for outside Colab. Delete if you like;
#  nothing above depends on it.
# ══════════════════════════════════════════════════════════════════
if __name__ == "__main__" and os.environ.get("PD_DEMO") == "1":
    import sys
    here = os.path.dirname(os.path.abspath(__file__))

    demo = []
    for plant, dis, conf in [("Tomato", "Early blight", 91.4),
                             ("Tomato", "Late blight", 5.2),
                             ("Tomato", "Septoria leaf spot", 1.8)]:
        demo.append({
            "plant": plant, "disease": dis, "conf": conf,
            "sevKey": _sev_key("Medium", False),
            "treat": {L: ui_treatment(plant, dis, L)
                      for L in ("english", "hindi", "marathi")},
        })

    leaf = os.path.join(here, "demo_leaf.jpg")
    if os.path.exists(leaf):
        im = Image.open(leaf).convert("RGB"); im.thumbnail((640, 640))
        b = io.BytesIO(); im.save(b, format="JPEG", quality=80)
        img_uri = "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()
    else:
        img_uri = ""

    fcss = ""
    fp = os.path.join(here, "inter_var.css")
    if os.path.exists(fp):
        fcss = io.open(fp, encoding="utf-8").read()

    html = build_app_html(demo, "", lang="hindi",
                          model_info=("MobileNetV2 · 38 classes · 160×160 · "
                                      "TFLite float16 · 94.66% lab validation · "
                                      "5-view TTA · runs fully offline"),
                          wallpaper_path=os.path.join(here, "wallpaper.jpg"),
                          font_css=fcss)
    html = html.replace('"image": ""', '"image": "%s"' % img_uri)

    page = ("<!doctype html><html><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>Kisan Plant Doctor — UI preview</title>"
            "<style>html,body{margin:0;padding:8px;background:#08170E;"
            "font-family:'Segoe UI',Roboto,sans-serif}</style></head><body>"
            + html + "</body></html>")
    out = sys.argv[1] if len(sys.argv) > 1 else "plant_doctor_preview.html"
    open(out, "w", encoding="utf-8").write(page)
    print("wrote", out, os.path.getsize(out) // 1024, "KB")
