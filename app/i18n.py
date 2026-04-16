import os
import json
from flask import session

I18N_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'translations.json')

translations = {"en": {}, "tr": {}}
_dirty = False

def load_translations():
    global translations, _dirty
    if os.path.exists(I18N_FILE):
        try:
            with open(I18N_FILE, 'r', encoding='utf-8') as f:
                translations = json.load(f)
        except Exception:
            translations = {"en": {}, "tr": {}}
    else:
        translations = {"en": {}, "tr": {}}
    
    if "en" not in translations: translations["en"] = {}
    if "tr" not in translations: translations["tr"] = {}
    _dirty = False

def save_translations():
    global _dirty
    if _dirty:
        with open(I18N_FILE, 'w', encoding='utf-8') as f:
            json.dump(translations, f, indent=2, ensure_ascii=False)
        _dirty = False

def t(text):
    global _dirty
    
    # Safely get session language outside of request contexts if triggered internally
    try:
        lang = session.get('lang', 'en')
    except RuntimeError:
        lang = 'en'
    
    # Auto-register english string if missing
    if text not in translations["en"]:
        translations["en"][text] = text
        _dirty = True
        save_translations()

    if lang == 'en':
        return text

    # Try mapping to turkish
    if text in translations["tr"]:
        return translations["tr"][text]

    return text # fallback to english
