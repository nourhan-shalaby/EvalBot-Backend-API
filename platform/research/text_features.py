"""Lexical features from the interviewee's words (computable from any transcript)."""
import re
import numpy as np

FILLERS = re.compile(r"\b(um+|uh+|uhm+|er+|ah+|hmm+|like|you know|i mean|kind of|sort of|basically|actually)\b")
POS = set("good great love enjoy excited happy interesting passion passionate fun amazing excellent best success successful proud glad".split())
NEG = set("bad hard difficult problem problems stress stressed worried hate fail failed failure wrong sorry unfortunately".split())
TENTATIVE = set("maybe perhaps guess probably possibly somewhat seems".split())
WE = {"we", "us", "our", "team", "together"}
I = {"i", "me", "my", "i'm", "i've", "myself"}

def interviewee_turns(transcript: str):
    turns = []
    for t in transcript.split("|"):
        if ":" in t:
            who, text = t.split(":", 1)
            if who.strip().lower().startswith("interviewee"):
                turns.append(re.sub(r"\[.*?\]", " ", text).strip())
    return [t for t in turns if t]

def text_features(turns):
    text = " ".join(turns).lower()
    words = re.findall(r"[a-z']+", text)
    n = max(len(words), 1)
    sents = [s for s in re.split(r"[.!?]+", text) if s.strip()]
    uniq = len(set(words))
    return {
        "txt_words": len(words),
        "txt_words_per_turn": len(words) / max(len(turns), 1),
        "txt_type_token": uniq / n,
        "txt_unique_words": uniq,
        "txt_filler_rate": len(FILLERS.findall(text)) / n,
        "txt_i_rate": sum(w in I for w in words) / n,
        "txt_we_rate": sum(w in WE for w in words) / n,
        "txt_pos_rate": sum(w in POS for w in words) / n,
        "txt_neg_rate": sum(w in NEG for w in words) / n,
        "txt_tentative_rate": sum(w in TENTATIVE for w in words) / n,
        "txt_number_rate": len(re.findall(r"\b\d+\b|\b(one|two|three|four|five|ten|hundred|percent)\b", text)) / n,
        "txt_avg_word_len": float(np.mean([len(w) for w in words])) if words else 0,
        "txt_avg_sentence_len": len(words) / max(len(sents), 1),
        "txt_long_word_rate": sum(len(w) >= 7 for w in words) / n,
        "txt_because_rate": len(re.findall(r"\b(because|so that|therefore|which meant|as a result)\b", text)) / n,
    }
