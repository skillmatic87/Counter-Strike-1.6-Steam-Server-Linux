"""Stable browser error identifiers; technical details remain English."""
import hashlib

def error_payload(message):
    text=str(message)
    return dict(error=text,message_key='error.'+hashlib.sha256(text.encode('utf-8')).hexdigest()[:12])

def picker_title(game,language):
    from pathlib import Path
    import json
    labels=json.loads(Path(__file__).with_name('ui_text.json').read_text(encoding='utf-8'))
    return labels[game].get(language,labels[game]['en'])
