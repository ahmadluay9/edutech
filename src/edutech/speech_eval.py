import re
from typing import Any
from pydantic import BaseModel
from rapidfuzz import distance, fuzz


CONTRACTIONS_MAP = {
    "i'm": "i am",
    "you're": "you are",
    "he's": "he is",
    "she's": "she is",
    "it's": "it is",
    "we're": "we are",
    "they're": "they are",
    "that's": "that is",
    "what's": "what is",
    "there's": "there is",
    "don't": "do not",
    "doesn't": "does not",
    "didn't": "did not",
    "can't": "cannot",
    "won't": "will not",
    "isn't": "is not",
    "aren't": "are not",
    "wasn't": "was not",
    "weren't": "were not",
    "haven't": "have not",
    "hasn't": "has not",
    "hadn't": "had not",
    "i've": "i have",
    "you've": "you have",
    "we've": "we have",
    "they've": "they have",
    "i'll": "i will",
    "you'll": "you will",
    "we'll": "we will",
    "i'd": "i would",
    "let's": "let us",
}


class DialogOption(BaseModel):
    id: str
    text: str
    is_correct: bool
    explanation: str = ""


class WordFeedback(BaseModel):
    word: str
    spoken_word: str | None = None
    status: str  # "correct" | "partial" | "missing"
    score: float


class SpeechEvaluationResult(BaseModel):
    transcript: str
    matched_option_id: str | None
    matched_option_text: str | None
    is_correct_option: bool
    pronunciation_score: float
    option_scores: dict[str, float]
    passed: bool
    word_feedback: list[WordFeedback]
    feedback_message: str


def normalize_text(text: str, expand_contractions: bool = True) -> str:
    cleaned = text.lower().strip()
    cleaned = cleaned.replace("’", "'").replace("‘", "'")
    if expand_contractions:
        for contr, expanded in CONTRACTIONS_MAP.items():
            cleaned = re.sub(rf"\b{re.escape(contr)}\b", expanded, cleaned)
    cleaned = re.sub(r"[^a-z0-9\s]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def tokenize_original(text: str) -> list[str]:
    return [w for w in re.split(r"\s+", text.strip()) if w]


def compute_word_alignment(target_text: str, spoken_text: str) -> tuple[list[WordFeedback], float]:
    orig_words = tokenize_original(target_text)
    spoken_tokens = normalize_text(spoken_text, expand_contractions=False).split()

    if not orig_words:
        return [], 0.0

    feedback_list: list[WordFeedback] = []
    used_spoken_indices: set[int] = set()
    total_word_score = 0.0

    for idx, orig_word in enumerate(orig_words):
        norm_target = normalize_text(orig_word, expand_contractions=False)
        expanded_target = normalize_text(orig_word, expand_contractions=True)

        best_score = 0.0
        best_spoken: str | None = None
        best_j = -1

        # Search in a window around the expected position first, then full list
        for j, sp_word in enumerate(spoken_tokens):
            if j in used_spoken_indices:
                continue
            s1 = fuzz.ratio(norm_target, sp_word)
            # Also check if contraction was expanded across 2 spoken words
            s2 = 0.0
            if " " in expanded_target and j + 1 < len(spoken_tokens):
                two_words = f"{sp_word} {spoken_tokens[j + 1]}"
                s2 = fuzz.ratio(expanded_target, two_words)

            score = max(s1, s2)
            # Small positional bonus for words close to target index
            pos_penalty = min(abs(idx - j) * 2.0, 12.0)
            adjusted = score - pos_penalty
            if adjusted > best_score - 5.0 and score > best_score:
                best_score = score
                best_spoken = sp_word
                best_j = j

        if best_j >= 0 and best_score >= 45.0:
            used_spoken_indices.add(best_j)
        else:
            best_score = 0.0
            best_spoken = None

        if best_score >= 80.0:
            status = "correct"
        elif best_score >= 50.0:
            status = "partial"
        else:
            status = "missing"

        total_word_score += best_score
        feedback_list.append(
            WordFeedback(
                word=orig_word,
                spoken_word=best_spoken,
                status=status,
                score=round(best_score, 1),
            )
        )

    avg_word_score = total_word_score / len(orig_words)
    full_norm_target = normalize_text(target_text, expand_contractions=True)
    full_norm_spoken = normalize_text(spoken_text, expand_contractions=True)
    sentence_ratio = fuzz.ratio(full_norm_target, full_norm_spoken)

    combined_score = round((avg_word_score * 0.65) + (sentence_ratio * 0.35), 1)
    return feedback_list, combined_score


def evaluate_spoken_response(
    transcript: str,
    options: list[DialogOption],
    pass_threshold: float = 65.0,
) -> SpeechEvaluationResult:
    cleaned_transcript = transcript.strip()
    if not cleaned_transcript:
        return SpeechEvaluationResult(
            transcript="",
            matched_option_id=None,
            matched_option_text=None,
            is_correct_option=False,
            pronunciation_score=0.0,
            option_scores={opt.id: 0.0 for opt in options},
            passed=False,
            word_feedback=[],
            feedback_message="Suara tidak terdengar jelas. Silakan klik tombol mikrofon dan ucapkan salah satu pilihan (A, B, atau C).",
        )

    norm_spoken = normalize_text(cleaned_transcript, expand_contractions=True)
    option_scores: dict[str, float] = {}
    best_option: DialogOption | None = None
    best_match_score = -1.0

    for opt in options:
        norm_opt = normalize_text(opt.text, expand_contractions=True)
        r_full = fuzz.ratio(norm_opt, norm_spoken)
        r_token = fuzz.token_set_ratio(norm_opt, norm_spoken)
        score = round((r_full * 0.6) + (r_token * 0.4), 1)
        option_scores[opt.id] = score
        if score > best_match_score:
            best_match_score = score
            best_option = opt

    if best_option is None or best_match_score < 30.0:
        return SpeechEvaluationResult(
            transcript=cleaned_transcript,
            matched_option_id=None,
            matched_option_text=None,
            is_correct_option=False,
            pronunciation_score=round(max(best_match_score, 0.0), 1),
            option_scores=option_scores,
            passed=False,
            word_feedback=[],
            feedback_message=f'Terdeteksi: "{cleaned_transcript}". Kalimat belum cocok dengan opsi A, B, atau C. Coba baca salah satu opsi dengan jelas.',
        )

    word_feedback, pron_score = compute_word_alignment(best_option.text, cleaned_transcript)
    is_correct = best_option.is_correct
    passed = is_correct and (pron_score >= pass_threshold)

    if is_correct and passed:
        msg = f"Bagus sekali! Opsi {best_option.id} tepat dan pelafalan Anda sangat baik ({pron_score}%)."
    elif is_correct and not passed:
        msg = (
            f"Anda memilih opsi {best_option.id} yang benar, namun skor pelafalan masih {pron_score}% "
            f"(minimal {int(pass_threshold)}%). Perhatikan kata yang ditandai kuning/merah dan coba ucapkan lagi."
        )
    else:
        explanation = f" {best_option.explanation}" if best_option.explanation else ""
        msg = (
            f"Anda mengucapkan Opsi {best_option.id} (pelafalan {pron_score}%), "
            f"tetapi pilihan tersebut kurang tepat untuk menjawab pertanyaan di video.{explanation}"
        )

    return SpeechEvaluationResult(
        transcript=cleaned_transcript,
        matched_option_id=best_option.id,
        matched_option_text=best_option.text,
        is_correct_option=is_correct,
        pronunciation_score=pron_score,
        option_scores=option_scores,
        passed=passed,
        word_feedback=word_feedback,
        feedback_message=msg,
    )
