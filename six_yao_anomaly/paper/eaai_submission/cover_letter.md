# Cover Letter — EAAI Submission

> 投稿时上传到 Editorial Manager 的 "Cover Letter" 栏，或作为第一个附件。

---

**To:** The Editors-in-Chief
*Engineering Applications of Artificial Intelligence*
Elsevier

**Date:** 〔投稿日期〕

**Subject:** Submission of a Full Length Article

---

Dear Editors,

We are pleased to submit our manuscript entitled **"A Yijing Yao-Variation
Framework for Unsupervised Industrial Image Anomaly Detection"** for
consideration as a Full Length Article in *Engineering Applications of
Artificial Intelligence*.

**Motivation.** Unsupervised industrial image anomaly detection is
currently dominated by methods that depend on ImageNet-pretrained features
and large memory banks. This hinders deployment on edge devices and
obscures interpretability. In this work we propose a different organizing
principle inspired by the *Yijing* (*I Ching*), whose theoretical core is
**yao variation**: the essence of an anomaly is a change in *relational
structure* rather than a deviation in absolute magnitude.

**What we do.**
- We map an image's anomaly-response field to the readings of a
  **six-yao sensor array** and declare an anomaly when the correlation
  structure among the yao readings departs from its normal manifold.
- The framework is **signal-agnostic**: the same criterion is instantiated
  with purely hand-crafted signals (requiring *no* pretraining) and with
  frozen ImageNet-pretrained ResNet features.
- It learns **online** from the very first sample via Welford updates with
  an **auto-adaptive threshold**, and is robust to cold-start contamination.

**Key results.**
- On the full 15-class MVTec AD benchmark, the pretrained instantiation
  reaches **0.862** average image-level AUROC; the hand-crafted,
  pretraining-free instantiation reaches **0.709**.
- A controlled ablation yields a clean signal ladder: random ResNet
  (0.772) < hand-crafted fixed convolution (0.799) < hand-crafted six-yao
  (0.854) < ImageNet-pretrained (0.932), showing the framework *organizes*
  rather than *produces* knowledge.
- The method is lightweight (52x less storage, 55x faster inference than a
  PatchCore-style memory bank) and fully interpretable.

**Fit with EAAI.** The work is a concrete *engineering application* of an
interpretable, edge-friendly AI method to real industrial inspection,
directly matching the journal's scope.

**Originality.** This manuscript is original, has not been published
before, and is not under consideration elsewhere. All authors have
approved the submission. The authors declare no competing interests.

We would be grateful if you would consider our manuscript for publication.
We look forward to your response.

Sincerely,

**Xinglu Ma** (Corresponding author)
School of Information Science and Technology
Qingdao University of Science and Technology
Qingdao 266061, China
Email: mxl@qust.edu.cn

---

## 建议推荐审稿人（可选，Elsevier 系统可填）

> 投稿系统通常让你推荐 3–5 名审稿人。建议选择工业异常检测 / 视觉检测方向、
> 且非本团队合作者的学者。可从 PaDiM、PatchCore、SimpleNet、WinCLIP 等
> 论文的作者群中挑选（注意回避利益冲突）。

〔待补：3–5 名推荐审稿人姓名 + 邮箱 + 单位〕
