"""
Leitura tolerante de Excel.

Alguns arquivos gerados por sistemas de banco gravam, em celulas marcadas como numero,
valores como "1234,56" (virgula decimal) ou "-". O openpyxl tenta converter isso para
inteiro e quebra a leitura inteira (ValueError: invalid literal for int()).

Este modulo ajusta essa conversao UMA vez, ao ser importado:
- valores normais continuam sendo lidos exatamente como antes;
- numero com virgula vira numero ("1234,56" -> 1234.56; "1.234,56" -> 1234.56);
- "-" ou vazio vira celula vazia;
- qualquer outro conteudo invalido vira celula vazia, sem derrubar a leitura.
"""
from openpyxl.worksheet import _reader as _openpyxl_reader

if not getattr(_openpyxl_reader, "_lle_tolerante", False):
    _cast_original = _openpyxl_reader._cast_number

    def _cast_number_tolerante(value):
        try:
            return _cast_original(value)
        except (ValueError, TypeError):
            pass
        txt = str(value).strip()
        if txt in ("", "-"):
            return None
        if "," in txt:
            try:
                return float(txt.replace(".", "").replace(",", "."))
            except ValueError:
                pass
        # celula marcada como numero, mas com conteudo invalido: vira vazia
        # (devolver texto quebraria a leitura um passo adiante, no pandas)
        return None

    _openpyxl_reader._cast_number = _cast_number_tolerante
    _openpyxl_reader._lle_tolerante = True
