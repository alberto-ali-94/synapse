"""Bounded local/cloud memory decisions with a shared label vocabulary."""
from nova_core.console import api_call
import json
import os
import re
import tomllib
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

QUESTIONS = {
    'write': ('Quale operazione di memoria personale richiede questo messaggio?', {
        'explicit': 'Chiede esplicitamente di ricordare o aggiornare un fatto personale reale del parlante.',
        'suggest': 'Afferma una preferenza, abitudine o fatto personale durevole, senza chiedere di salvarlo.',
        'none': 'Domanda, esempio, citazione, ipotesi, fatto su altri, informazione temporanea o nessun ricordo utile.'}),
    'read': ('Quale recupero di ricordi personali serve per rispondere alla richiesta?', {
        'search': 'Serve conoscere fatti o preferenze del parlante ricordati in passato.',
        'count': 'Chiede quanti ricordi o preferenze personali sono memorizzati.',
        'none': 'Basta conoscenza generale o il messaggio corrente, senza leggere ricordi personali.'}),
    'type': ('Di quale tipo sono il ricordo personale affermato o i ricordi personali richiesti?', {
        'preference': 'Gusti, preferenze e abitudini personali.',
        'fact': 'Fatto personale durevole, progetto o informazione biografica.',
        'event': 'Appuntamento o evento personale.',
        'any': 'Tipo assente, ambiguo, misto o non specificato.'}),
    'domain': ('Quale argomento riguarda il ricordo affermato o i ricordi cercati?', {
        'programming': 'Programmazione, software, linguaggi e progetti informatici.',
        'food': 'Alimentazione, cibo, bevande e gusti alimentari.',
        'home': 'Casa e dispositivi domestici.',
        'personal': 'Informazioni personali e biografiche.',
        'any': 'Altro, piu argomenti o dominio non specificato.'}),
}


def load_jev_key(path):
    key = os.environ.get('TYPESAFE_API_KEY', '').strip()
    if not key:
        try:
            with Path(path).open('rb') as source:
                key = tomllib.load(source).get('JEV_API_KEY', '')
        except (OSError, tomllib.TOMLDecodeError):
            pass
    if not isinstance(key, str) or not key.strip() or any(c.isspace() for c in key):
        raise RuntimeError('Configura JEV_API_KEY in config.toml oppure TYPESAFE_API_KEY per la modalita online.')
    return key.strip()


def validate_decisions(raw):
    result = {}
    for name, (_, options) in QUESTIONS.items():
        entry = raw.get(name, {})
        label = entry.get('choice')
        confidence = entry.get('confidence')
        if label not in options or type(confidence) not in (int, float) or not 0 <= confidence <= 1:
            raise ValueError('Risposta del classificatore non valida.')
        result[name] = label if confidence >= .8 else ('none' if name in ('write', 'read') else 'any')
    return result


def constrain_intent(text, decision):
    """Deterministic consent rules complement semantic classification."""
    lower = text.casefold().strip()
    explicit = bool(re.search(r'\b(ricordati|ricorda|ricordare|ricordarti|memorizza|memorizzare|salva|salvare|tieni a mente)\b', lower))
    negative = bool(re.search(r"\bnon\s+(?:ricord|salv|memorizz)|\b(?:esempio|ipotizziamo|supponiamo)\b", lower))
    request = '?' in lower or bool(re.match(r'^(qual|che cosa|cosa|come|quant|quando|dove|chi |dimmi|parlami|ricordi|ti ricordi|sai |puoi |potresti )', lower))
    if explicit and not negative:
        decision['write'] = 'explicit'
    elif decision['write'] == 'explicit':
        decision['write'] = 'suggest'
    if negative or (request and not explicit):
        decision['write'] = 'none'
    if not request:
        decision['read'] = 'none'
    elif decision['read'] != 'none' and re.search(r'\b(quant[ie]|numero)\b', lower) and re.search(r'ricord|preferenz|memori', lower):
        decision['read'] = 'count'
    if decision['read'] == 'count' and re.search(r'preferenz|gusti', lower):
        decision['type'] = 'preference'
    return decision


class JevClassifier:
    def __init__(self, config_path):
        self.config_path = config_path
        load_jev_key(config_path)  # Offline validation only.

    def classify(self, text, check=lambda: None):
        check()
        body = {'model': 'jev-latest', 'state': text[:6000], 'questions': {
            name: {'type': 'choice', 'instructions': question, 'criteria': labels}
            for name, (question, labels) in QUESTIONS.items()}}
        request = Request('https://api.typesafe.ai/v1/systemone',
            data=json.dumps(body).encode(), method='POST', headers={
                'Authorization': 'Bearer ' + load_jev_key(self.config_path), 'Content-Type': 'application/json'})
        api_call('Jev', 'classificazione memoria')
        try:
            with urlopen(request, timeout=12) as response:
                data = response.read(262145)
            if len(data) > 262144:
                raise ValueError('Risposta Jev troppo grande.')
            result = json.loads(data)
        except HTTPError as exc:
            status = exc.code
            exc.close()
            raise RuntimeError(f'Jev HTTP {status}: classificazione non disponibile.') from None
        except (URLError, TimeoutError, OSError):
            raise RuntimeError('Connessione Jev non riuscita o scaduta.') from None
        except (ValueError, UnicodeError):
            raise RuntimeError('Risposta Jev non valida.') from None
        check()
        return constrain_intent(text, validate_decisions(result.get('answers', {})))


class LocalClassifier:
    def __init__(self):
        from gliclass import GLiClassModel, ZeroShotClassificationPipeline
        from transformers import AutoTokenizer
        from nova_core.paths import model_source
        name = model_source('knowledgator/gliclass-multilang-mini')
        model = GLiClassModel.from_pretrained(name)
        self.pipeline = ZeroShotClassificationPipeline(model, AutoTokenizer.from_pretrained(name),
            classification_type='multi-label', device='cpu')

    def classify(self, text, check=lambda: None):
        # Each question has a separate option set: memory type and topic are not competitors.
        raw = {}
        for name, (question, labels) in QUESTIONS.items():
            check()
            descriptions = list(labels.values())
            if name == 'write':
                descriptions = ['richiesta di memorizzare informazioni personali',
                    'affermazione di preferenze o fatti personali', 'domanda o informazione generale']
            elif name == 'read':
                descriptions = ['domanda sui ricordi e sulle preferenze personali',
                    'domanda sul numero di ricordi memorizzati', 'domanda di conoscenza generale']
            scores = self.pipeline(text[:6000], descriptions, threshold=0.0)[0]
            ranked = sorted(scores, key=lambda item: item['score'], reverse=True)
            fallback = 'none' if name in ('write', 'read') else 'any'
            winner = ranked[0] if ranked else None
            if winner and winner['score'] >= .8 and (len(ranked) < 2 or winner['score'] - ranked[1]['score'] >= .15):
                label = list(labels)[descriptions.index(winner['label'])]
            else:
                label = fallback
            raw[name] = {'choice': label, 'confidence': 1.0}
        check()
        return constrain_intent(text, validate_decisions(raw))
