"""Local 2-speaker diarization: energy VAD -> ~1.5 s chunks -> TitaNet embeddings -> 2 clusters."""
import json, os, sys, time
import numpy as np, librosa, torch
from sklearn.cluster import AgglomerativeClustering
from nemo.collections.asr.models import EncDecSpeakerLabelModel
import logging; logging.getLogger("nemo_logger").setLevel(logging.ERROR)

SR = 16000
model = EncDecSpeakerLabelModel.from_pretrained("nvidia/speakerverification_en_titanet_large", map_location="cpu").eval()
torch.set_num_threads(os.cpu_count())

def chunks(y):
    out = []
    for s, e in librosa.effects.split(y, top_db=32, frame_length=1024, hop_length=256):
        s_ms, e_ms = s * 1000 // SR, e * 1000 // SR
        if e_ms - s_ms < 400:
            continue
        t = s_ms
        while t < e_ms:
            end = min(t + 1500, e_ms)
            if end - t >= 400:
                out.append((int(t), int(end)))
            t = end
    return out

@torch.no_grad()
def embed(y, segs, batch=64):
    embs = []
    for i in range(0, len(segs), batch):
        part = segs[i:i + batch]
        sigs = [torch.tensor(y[s * SR // 1000: e * SR // 1000]) for s, e in part]
        lens = torch.tensor([len(x) for x in sigs])
        pad = torch.nn.utils.rnn.pad_sequence(sigs, batch_first=True)
        _, emb = model.forward(input_signal=pad, input_signal_length=lens)
        embs.append(torch.nn.functional.normalize(emb, dim=1).numpy())
    return np.vstack(embs)

def diarize(path):
    y, _ = librosa.load(path, sr=SR)
    segs = chunks(y)
    E = embed(y, segs)
    lab = AgglomerativeClustering(n_clusters=2, metric="cosine", linkage="average").fit_predict(E)
    # smooth isolated labels (a single chunk between two of the other speaker)
    for i in range(1, len(lab) - 1):
        if lab[i - 1] == lab[i + 1] != lab[i] and segs[i + 1][0] - segs[i - 1][1] < 3000:
            lab[i] = lab[i - 1]
    dur = {k: sum(e - s for (s, e), l in zip(segs, lab) if l == k) for k in (0, 1)}
    cand = max(dur, key=dur.get)  # the candidate does most of the talking in these interviews
    return {"duration_s": len(y) / SR, "segments": [[s, e, int(l == cand)] for (s, e), l in zip(segs, lab)],
            "candidate_share": dur[cand] / max(sum(dur.values()), 1)}

if __name__ == "__main__":
    src = "/mnt/user-data/uploads/data/processed/audio16k"
    files = sys.argv[1:] or sorted(os.listdir(src))
    for f in files:
        out = f"diar/{os.path.splitext(f)[0].lower()}.json"
        if os.path.exists(out):
            continue
        t = time.time()
        r = diarize(os.path.join(src, f))
        json.dump(r, open(out, "w"))
        print(f, f"{r['duration_s']/60:.1f} min", len(r["segments"]), "chunks", f"cand share {r['candidate_share']:.2f}", f"{time.time()-t:.1f}s", flush=True)
