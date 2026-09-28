"""
Categorical HMM with Baum-Welch, BIC model selection and MAP decoding.

This is a from-scratch re-implementation of the analysis pipeline used on the chicks in
Diffine et al. (bead floor): peck sequences are treated as emissions of a categorical
HMM, the number of hidden states is chosen by BIC over multiple random restarts, and
each peck is then assigned to a phase by the MAP state sequence.

`hmmlearn` is not installable in this sandbox, so everything here is written and tested
in numpy. The API mirrors what you would call in hmmlearn, so swapping it back in later
changes three lines.

    python src/hmm_phases.py            # self-test on synthetic two-phase sequences
"""
from __future__ import annotations

import numpy as np


class CategoricalHMM:
    """HMM with discrete observations, trained by Baum-Welch on multiple sequences."""

    def __init__(self, n_states: int, n_symbols: int, seed: int = 0):
        self.K, self.M = n_states, n_symbols
        self.rng = np.random.default_rng(seed)
        self._init_params()

    def _init_params(self):
        r = self.rng
        self.start = r.dirichlet(np.ones(self.K))
        self.trans = np.array([r.dirichlet(np.ones(self.K) * 2) for _ in range(self.K)])
        self.emis = np.array([r.dirichlet(np.ones(self.M)) for _ in range(self.K)])

    # ---------------------------------------------------------------- inference
    def _forward(self, obs):
        T = len(obs)
        alpha = np.zeros((T, self.K)); scale = np.zeros(T)
        alpha[0] = self.start * self.emis[:, obs[0]]
        scale[0] = alpha[0].sum() or 1e-300
        alpha[0] /= scale[0]
        for t in range(1, T):
            alpha[t] = (alpha[t - 1] @ self.trans) * self.emis[:, obs[t]]
            scale[t] = alpha[t].sum() or 1e-300
            alpha[t] /= scale[t]
        return alpha, scale

    def _backward(self, obs, scale):
        T = len(obs)
        beta = np.zeros((T, self.K)); beta[-1] = 1.0 / scale[-1]
        for t in range(T - 2, -1, -1):
            beta[t] = (self.trans @ (self.emis[:, obs[t + 1]] * beta[t + 1])) / scale[t]
        return beta

    def loglik(self, sequences) -> float:
        return float(sum(np.log(self._forward(o)[1]).sum() for o in sequences))

    # ---------------------------------------------------------------- learning
    def fit(self, sequences, max_iter: int = 120, tol: float = 1e-6):
        prev = -np.inf
        for _ in range(max_iter):
            s_num = np.zeros(self.K)
            t_num = np.zeros((self.K, self.K)); t_den = np.zeros(self.K)
            e_num = np.zeros((self.K, self.M)); e_den = np.zeros(self.K)
            ll = 0.0
            for obs in sequences:
                obs = np.asarray(obs, dtype=int)
                alpha, scale = self._forward(obs)
                beta = self._backward(obs, scale)
                ll += float(np.log(scale).sum())
                gamma = alpha * beta
                gamma /= gamma.sum(axis=1, keepdims=True)
                s_num += gamma[0]
                # xi summed over t, vectorised: with scaled alpha/beta each xi_t already
                # normalises to 1, so the sum over t needs no per-step division
                A = alpha[:-1]                                   # (T-1, K)
                B = self.emis[:, obs[1:]].T * beta[1:]           # (T-1, K)
                xi_sum = self.trans * (A.T @ B)
                t_num += xi_sum; t_den += xi_sum.sum(axis=1)
                for m in range(self.M):
                    e_num[:, m] += gamma[obs == m].sum(axis=0)
                e_den += gamma.sum(axis=0)
            self.start = s_num / s_num.sum()
            self.trans = t_num / np.maximum(t_den[:, None], 1e-300)
            self.emis = e_num / np.maximum(e_den[:, None], 1e-300)
            if abs(ll - prev) < tol * max(1.0, abs(prev)):
                break
            prev = ll
        self.loglik_ = ll
        return self

    def n_params(self) -> int:
        return (self.K - 1) + self.K * (self.K - 1) + self.K * (self.M - 1)

    def bic(self, sequences) -> float:
        n_obs = sum(len(o) for o in sequences)
        return -2.0 * self.loglik(sequences) + self.n_params() * np.log(n_obs)

    def bic_per_element(self, sequences) -> float:
        return self.bic(sequences) / sum(len(o) for o in sequences)

    def decode(self, obs):
        """Viterbi MAP state sequence (used to label each peck with its phase)."""
        obs = np.asarray(obs, dtype=int); T = len(obs)
        lp = np.log(np.maximum(self.emis, 1e-300))
        lt = np.log(np.maximum(self.trans, 1e-300))
        d = np.log(np.maximum(self.start, 1e-300)) + lp[:, obs[0]]
        psi = np.zeros((T, self.K), dtype=int)
        for t in range(1, T):
            m = d[:, None] + lt
            psi[t] = m.argmax(axis=0)
            d = m.max(axis=0) + lp[:, obs[t]]
        path = np.zeros(T, dtype=int); path[-1] = int(d.argmax())
        for t in range(T - 2, -1, -1):
            path[t] = psi[t + 1, path[t + 1]]
        return path


def select_n_states(sequences, k_range=range(1, 6), restarts: int = 20, seed: int = 0):
    """Fit each K with several random restarts, keep the best by BIC (the paper's protocol)."""
    n_symbols = int(max(max(o) for o in sequences)) + 1
    out = {}
    for K in k_range:
        best = None
        for r in range(restarts):
            m = CategoricalHMM(K, n_symbols, seed=seed + 1000 * K + r).fit(sequences)
            b = m.bic_per_element(sequences)
            if best is None or b < best[0]:
                best = (b, m)
        out[K] = best
    best_k = min(out, key=lambda k: out[k][0])
    return best_k, {k: v[0] for k, v in out.items()}, out[best_k][1]


def phase_emissions(model, sequences):
    """Observed symbol frequency within each MAP-decoded phase (the paper's Fig. 10)."""
    K, M = model.K, model.M
    counts = np.zeros((K, M))
    for obs in sequences:
        path = model.decode(obs)
        for s, o in zip(path, np.asarray(obs, dtype=int)):
            counts[s, o] += 1
    return counts / np.maximum(counts.sum(axis=1, keepdims=True), 1)


# ---------------------------------------------------------------- self-test
if __name__ == "__main__":
    rng = np.random.default_rng(0)
    # ground truth: an exploratory phase (pecks spread over items) that switches once into
    # a stable phase (mostly food) — i.e. exactly the structure reported for the chicks
    true_emis = np.array([[0.45, 0.11, 0.17, 0.07, 0.12, 0.04, 0.04],
                          [0.82, 0.09, 0.03, 0.03, 0.02, 0.01, 0.00]])
    seqs = []
    for _ in range(30):
        s, obs = 0, []
        for _ in range(80):
            obs.append(int(rng.choice(7, p=true_emis[s])))
            if s == 0 and rng.random() < 0.06:
                s = 1
        seqs.append(obs)

    k, bics, model = select_n_states(seqs, restarts=8)
    print("BIC per element:", {kk: round(v, 4) for kk, v in bics.items()})
    print("selected K =", k)
    print("start:", np.round(model.start, 3))
    print("transition:\n", np.round(model.trans, 3))
    print("emission:\n", np.round(model.emis, 3))
    print("recovered vs true emission (sorted by P(food)):")
    order = np.argsort(-model.emis[:, 0])
    print(np.round(model.emis[order], 2))
