"""Conservative Italian cardinal normalization for speech, without model imports."""
import re

_SMALL = ('zero', 'uno', 'due', 'tre', 'quattro', 'cinque', 'sei', 'sette',
          'otto', 'nove', 'dieci', 'undici', 'dodici', 'tredici', 'quattordici',
          'quindici', 'sedici', 'diciassette', 'diciotto', 'diciannove')
_TENS = ('', '', 'venti', 'trenta', 'quaranta', 'cinquanta', 'sessanta',
         'settanta', 'ottanta', 'novanta')
# Capture structured numbers whole so a date/decimal is never partly rewritten.
_NUMBER = re.compile(r'(?<![\w.,:/+−-])[+−-]?[0-9]+(?:[.,:/−-][0-9]+)*(?!\w|[.,:/−-][0-9])')


def _cardinal(n):
    if n < 20:
        return _SMALL[n]
    if n < 100:
        tens, unit = divmod(n, 10)
        prefix = _TENS[tens]
        if unit in (1, 8):
            prefix = prefix[:-1]
        return prefix + (_SMALL[unit] if unit else '')
    if n < 1000:
        hundreds, rest = divmod(n, 100)
        prefix = ('' if hundreds == 1 else _SMALL[hundreds]) + 'cento'
        if rest == 8 or 80 <= rest < 90:
            prefix = prefix[:-1]
        return prefix + (_cardinal(rest) if rest else '')
    if n < 1_000_000:
        thousands, rest = divmod(n, 1000)
        prefix = 'mille' if thousands == 1 else _cardinal(thousands) + 'mila'
        return prefix + (_cardinal(rest) if rest else '')
    millions, rest = divmod(n, 1_000_000)
    prefix = 'un milione' if millions == 1 else _accent(_cardinal(millions)) + ' milioni'
    return prefix + (' ' + _cardinal(rest) if rest else '')


def _accent(word):
    return word[:-3] + 'tré' if word.endswith('tre') and word != 'tre' else word


def normalize_speech_numbers(text, language):
    """Read standalone unsigned cardinals 0..999999999; preserve other formats.

    Leading zeroes, signed values, decimals, dates, times and identifiers are
    intentionally unchanged. English is passed through untouched.
    """
    if language != 'it':
        return text

    def replace(match):
        token = match.group()
        if not token.isascii() or not token.isdecimal() or len(token) > 9:
            return token
        if len(token) > 1 and token.startswith('0'):
            return token
        return _accent(_cardinal(int(token)))

    return _NUMBER.sub(replace, text)
