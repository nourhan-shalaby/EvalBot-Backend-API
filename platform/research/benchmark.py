import csv, re, warnings
import numpy as np, pandas as pd
from sklearn.linear_model import RidgeCV
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.model_selection import GroupKFold, cross_val_predict
from text_features import interviewee_turns, text_features
warnings.filterwarnings("ignore")

feat = pd.read_csv("evalbot_features.csv").set_index("interview")
tx = {}
for row in csv.reader(open("interview_transcripts_by_turkers.csv", encoding="utf-8", errors="replace")):
    if len(row) >= 2:
        tx[row[0].strip().lower()] = text_features(interviewee_turns(row[1]))
feat = feat.join(pd.DataFrame(tx).T)
s = pd.read_csv("turker_scores_full_interview.csv")
y = s[s.Worker == "AGGR"].assign(Participant=lambda d: d.Participant.str.lower()).set_index("Participant")
traits = ["Overall", "RecommendHiring", "Excited", "EngagingTone", "Friendly", "Smiled", "EyeContact", "NoFillers",
          "StructuredAnswers", "Calm", "NotAwkward", "Engaged", "Focused"]
data = feat.join(y[traits], how="inner")
groups = data.index.str.extract(r"(\d+)")[0].astype(int).values
sets = {
    "prosody": [c for c in feat.columns if c.startswith("pros_")],
    "face": [c for c in feat.columns if c.startswith("face_")],
    "smile": [c for c in feat.columns if c.startswith("smile_")],
    "text": [c for c in feat.columns if c.startswith("txt_")],
}
sets["all"] = sum(sets.values(), [])
cv = GroupKFold(n_splits=10)

def model(kind):
    if kind == "ridge":
        return make_pipeline(SimpleImputer(), StandardScaler(), RidgeCV(alphas=np.logspace(-1, 4, 30)))
    return make_pipeline(SimpleImputer(), ExtraTreesRegressor(n_estimators=400, min_samples_leaf=3, max_features=0.3, random_state=0, n_jobs=-1))

res = {}
for name, cols in sets.items():
    X = data[cols].replace([np.inf, -np.inf], np.nan).values
    for t in traits:
        best = -1
        for kind in ("ridge", "trees"):
            pred = cross_val_predict(model(kind), X, data[t].values, cv=cv, groups=groups)
            r = np.corrcoef(pred, data[t].values)[0, 1]
            res[(t, name, kind)] = r
print("n =", len(data))
tab = pd.Series(res).unstack([1, 2]).round(2)
best = tab.T.groupby(level=0).max().T
print(best[["prosody", "face", "smile", "text", "all"]].to_string())
tab.to_csv("benchmark_results.csv")
data.to_csv("training_table.csv")
