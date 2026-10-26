"""Train EvalBot's human-calibrated score models on the MIT Interview Dataset.

Steps: diarization JSON + 16 kHz audio + human transcripts -> calibration.extract_features
-> per-trait models evaluated with person-grouped 10-fold CV -> bundle saved for the app.
"""
import csv, json, os, sys, time, warnings
import numpy as np, pandas as pd, librosa, joblib
from sklearn.linear_model import RidgeCV
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import GroupKFold, cross_val_predict

warnings.filterwarnings("ignore")
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)
import calibration as cal  # noqa: E402
from text_features import interviewee_turns  # noqa: E402

AUDIO = os.getenv("EVALBOT_AUDIO_DIR", "audio16k")
FEAT_CACHE = "calibrated_features.csv"


def utterances_from_diar(d, gap_ms=1000):
    utts = []
    for s, e, c in d["segments"]:
        role = "Interviewee" if c else "Interviewer"
        if utts and utts[-1]["role"] == role and s - utts[-1]["end"] < gap_ms:
            utts[-1]["end"] = e
        else:
            utts.append({"role": role, "start": s, "end": e})
    return utts


def build_features():
    tx = {}
    for row in csv.reader(open("interview_transcripts_by_turkers.csv", encoding="utf-8", errors="replace")):
        if len(row) >= 2:
            tx[row[0].strip().lower()] = interviewee_turns(row[1])
    done = pd.read_csv(FEAT_CACHE).set_index("interview") if os.path.exists(FEAT_CACHE) else pd.DataFrame()
    rows = [] if done.empty else [dict(r, interview=i) for i, r in done.iterrows()]
    for f in sorted(os.listdir("diar")):
        k = f[:-5]
        if k in done.index or k not in tx:
            continue
        t = time.time()
        d = json.load(open(f"diar/{f}"))
        y, sr = librosa.load(os.path.join(AUDIO, k.upper() + ".flac"), sr=16000)
        feats = cal.extract_features(y, sr, utterances_from_diar(d), tx[k])
        feats["interview"] = k
        rows.append(feats)
        pd.DataFrame(rows).set_index("interview").to_csv(FEAT_CACHE)
        print(k, f"{time.time() - t:.1f}s", flush=True)
    return pd.read_csv(FEAT_CACHE).set_index("interview")


def human_agreement(scores, traits):
    r = scores[scores.Worker != "AGGR"].copy()
    out = {}
    for t in traits:
        vals = []
        for w, g in r.groupby("Worker"):
            if len(g) < 10:
                continue
            others = r[r.Worker != w].groupby("Participant")[t].mean()
            m = g.set_index("Participant")[t].to_frame("me").join(others.rename("oth")).dropna()
            if len(m) >= 10:
                vals.append(m.me.corr(m.oth))
        out[t] = float(np.nanmean(vals))
    return out


def candidates():
    return {
        "ridge": lambda: make_pipeline(SimpleImputer(), StandardScaler(), RidgeCV(alphas=np.logspace(-1, 4, 30))),
        "trees": lambda: make_pipeline(SimpleImputer(), ExtraTreesRegressor(
            n_estimators=500, min_samples_leaf=3, max_features=0.3, random_state=0, n_jobs=-1)),
    }


def main():
    X = build_features()
    s = pd.read_csv("turker_scores_full_interview.csv")
    s["Participant"] = s.Participant.str.lower()
    y = s[s.Worker == "AGGR"].set_index("Participant")
    traits = ["Overall", "RecommendHiring", "Colleague", "Engaged", "Excited", "EngagingTone", "Friendly",
              "NoFillers", "StructuredAnswers", "Calm", "NotStressed", "Focused", "Authentic", "NotAwkward",
              "Paused", "SpeakingRate", "Smiled", "EyeContact"]
    data = X.join(y[traits], how="inner")
    # interviewer-dependent features are excluded: in EvalBot mock interviews the "interviewer" is the browser
    feat_names = [c for c in X.columns if c not in ("voc_talk_share", "voc_turns_per_min")]
    groups = data.index.str.extract(r"(\d+)")[0].astype(int).values
    Xv = data[feat_names].replace([np.inf, -np.inf], np.nan).values
    lo, hi = np.nanpercentile(Xv, 1, axis=0), np.nanpercentile(Xv, 99, axis=0)
    Xv = np.where(np.isnan(Xv), Xv, np.clip(Xv, lo, hi))
    human = human_agreement(s, traits)
    cv = GroupKFold(n_splits=10)

    results, models = [], {}
    for t in traits:
        yt = data[t].values
        best = None
        for name, make in candidates().items():
            pred = cross_val_predict(make(), Xv, yt, cv=cv, groups=groups)
            r = float(np.corrcoef(pred, yt)[0, 1])
            mae = float(np.mean(np.abs(pred - yt)))
            if best is None or r > best[1]:
                best = (name, r, mae)
        results.append({"trait": t, "model": best[0], "cv_r": round(best[1], 3), "cv_mae": round(best[2], 3),
                        "human_r": round(human[t], 3)})
        if best[1] >= 0.35:  # only ship traits the model predicts reliably
            m = candidates()[best[0]]().fit(Xv, yt)
            models[t] = {"model": m, "cv_r": best[1], "cv_mae": best[2], "human_r": human[t],
                         "ref_mean": float(yt.mean()), "ref_std": float(yt.std())}
    res = pd.DataFrame(results).set_index("trait")
    print(res.to_string())
    res.to_csv("calibration_results.csv")

    display = ["RecommendHiring", "Overall", "Excited", "EngagingTone", "Engaged", "Friendly", "StructuredAnswers",
               "NoFillers", "Calm", "NotStressed", "Focused", "Colleague", "Authentic", "NotAwkward", "Paused",
               "SpeakingRate", "Smiled", "EyeContact"]
    bundle = {
        "version": time.strftime("%Y-%m-%d"),
        "feature_names": feat_names,
        "feature_bounds": [lo.tolist(), hi.tolist()],
        "models": models,
        "display_order": display,
        "reference": {"dataset": "MIT Interview Dataset (Naim et al., IEEE Trans. Affective Computing)",
                      "interviews": int(len(data)), "raters_per_interview": 9,
                      "validation": "10-fold cross-validation grouped by participant"},
    }
    os.makedirs(os.path.join(APP, "assets", "models"), exist_ok=True)
    joblib.dump(bundle, os.path.join(APP, "assets", "models", "calibrated_scores.joblib"), compress=3)
    print("shipped traits:", list(models))


if __name__ == "__main__":
    main()
