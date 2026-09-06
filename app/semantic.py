"""Semantic (meaning-based) command matching.

Instead of comparing the spoken text letter-by-letter against the configured
trigger phrase, this encodes both into vectors with a small multilingual
embedding model and compares their meaning (cosine similarity). This lets
you say roughly what you want ("kannst du das lauter machen") and still hit
a command configured with a short phrase ("lauter").

Runs 100% locally after the one-time model download on first use.
"""

MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"


class SemanticMatcher:
    def __init__(self, model_name: str = MODEL_NAME):
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name)
        self._phrase_cache = {}

    def _embed(self, text: str):
        return self._model.encode(text, normalize_embeddings=True)

    def _phrase_embedding(self, phrase: str):
        if phrase not in self._phrase_cache:
            self._phrase_cache[phrase] = self._embed(phrase)
        return self._phrase_cache[phrase]

    def best_match(self, utterance: str, commands: list, threshold: float = 0.55):
        if not commands or not utterance:
            return None, 0.0

        utterance_vec = self._embed(utterance)
        best_score = -1.0
        best_command = None
        for command in commands:
            phrase_vec = self._phrase_embedding(command["phrase"])
            score = float(utterance_vec @ phrase_vec)
            if score > best_score:
                best_score = score
                best_command = command

        if best_score >= threshold:
            return best_command, best_score
        return None, best_score
