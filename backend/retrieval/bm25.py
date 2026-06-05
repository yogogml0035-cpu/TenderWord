from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
import re
from typing import Sequence


TOKEN_RE = re.compile(r"[a-z0-9_]+|[\u4e00-\u9fff]+", re.IGNORECASE)


def tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    for match in TOKEN_RE.finditer(text.lower()):
        term = match.group(0)
        if re.fullmatch(r"[a-z0-9_]+", term):
            tokens.append(term)
            continue
        tokens.extend(term)
        tokens.extend(term[index : index + 2] for index in range(max(len(term) - 1, 0)))
        tokens.extend(term[index : index + 3] for index in range(max(len(term) - 2, 0)))
    return [token for token in tokens if token.strip()]


@dataclass(frozen=True)
class BM25Hit:
    index: int
    score: float


class BM25Index:
    def __init__(
        self,
        documents: Sequence[str],
        *,
        k1: float = 1.5,
        b: float = 0.75,
    ) -> None:
        self.documents = list(documents)
        self.k1 = k1
        self.b = b
        self.doc_tokens = [tokenize(document) for document in self.documents]
        self.doc_lengths = [len(tokens) for tokens in self.doc_tokens]
        self.avg_doc_length = (
            sum(self.doc_lengths) / len(self.doc_lengths) if self.doc_lengths else 0.0
        )
        self.term_frequencies = [Counter(tokens) for tokens in self.doc_tokens]
        self.document_frequencies: Counter[str] = Counter()
        for terms in self.term_frequencies:
            self.document_frequencies.update(terms.keys())
        self.document_count = len(self.documents)

    def score(self, query: str) -> list[BM25Hit]:
        query_terms = tokenize(query)
        if not query_terms or not self.documents:
            return []

        query_counter = Counter(query_terms)
        hits: list[BM25Hit] = []
        for index, term_frequency in enumerate(self.term_frequencies):
            score = 0.0
            doc_length = self.doc_lengths[index] or 1
            for term, query_weight in query_counter.items():
                frequency = term_frequency.get(term, 0)
                if frequency <= 0:
                    continue
                document_frequency = self.document_frequencies.get(term, 0)
                idf = math.log(
                    1.0
                    + (self.document_count - document_frequency + 0.5)
                    / (document_frequency + 0.5)
                )
                denominator = frequency + self.k1 * (
                    1.0 - self.b + self.b * doc_length / (self.avg_doc_length or 1.0)
                )
                score += (
                    idf
                    * frequency
                    * (self.k1 + 1.0)
                    / denominator
                    * max(1.0, math.log1p(query_weight))
                )
            if score > 0:
                hits.append(BM25Hit(index=index, score=score))

        return sorted(hits, key=lambda item: item.score, reverse=True)

