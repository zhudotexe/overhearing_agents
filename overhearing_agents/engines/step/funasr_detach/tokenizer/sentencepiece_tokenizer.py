from pathlib import Path
from typing import Iterable, List, Union

import sentencepiece as spm
from funasr_detach.register import tables
from funasr_detach.tokenizer.abs_tokenizer import BaseTokenizer


@tables.register("tokenizer_classes", "SentencepiecesTokenizer")
class SentencepiecesTokenizer(BaseTokenizer):
    def __init__(self, bpemodel: Union[Path, str], **kwargs):
        super().__init__(**kwargs)
        self.bpemodel = str(bpemodel)
        # NOTE(kamo):
        # Don't build SentencePieceProcessor in __init__()
        # because it's not picklable and it may cause following error,
        # "TypeError: can't pickle SwigPyObject objects",
        # when giving it as argument of "multiprocessing.Process()".
        self.sp = None

    def __repr__(self):
        return f'{self.__class__.__name__}(model="{self.bpemodel}")'

    def _build_sentence_piece_processor(self):
        # Build SentencePieceProcessor lazily.
        if self.sp is None:
            self.sp = spm.SentencePieceProcessor()
            self.sp.load(self.bpemodel)

    def text2tokens(self, line: str) -> List[str]:
        self._build_sentence_piece_processor()
        return self.sp.EncodeAsPieces(line)

    def tokens2text(self, tokens: Iterable[str]) -> str:
        self._build_sentence_piece_processor()
        return self.sp.DecodePieces(list(tokens))

    def encode(self, line: str) -> List[int]:
        self._build_sentence_piece_processor()
        return self.sp.EncodeAsIds(line)

    def decode(self, line: List[int]):
        self._build_sentence_piece_processor()
        return self.sp.DecodeIds(line)
