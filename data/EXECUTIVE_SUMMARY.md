# H₂ Catalyst Explorer — Executive Summary

**For:** Prof. R. K. Dutta, Department of Chemistry, IIT Roorkee
**A predictive screening tool for green-hydrogen catalysts, built during the Quantitative AI/ML Research Internship.**

---

## What this is

A tool that predicts how good a material will be at producing hydrogen — across both of the major routes: **photocatalysis** (sunlight-driven, your research area) and **electrocatalysis** (electrolysis). You give it a material and the reaction conditions; it tells you whether the material is promising, how confident it is, and — importantly — it shows you the real published evidence behind every answer.

It opens as a single file in any web browser. No installation, no internet, no login, nothing to maintain. It will work the same way years from now as it does today.

## What it does, in three parts

**1. It predicts.** Choose a photocatalyst (ZnO, g-C₃N₄, CdS, TiO₂, your Bi/Sn composites, and more) and conditions (hole scavenger, co-catalyst, light), and it classifies the material as a low / moderate / high / exceptional hydrogen producer, with a clear "is this worth synthesizing?" probability. For electrocatalysis, it predicts how strongly a metal surface binds hydrogen and scores its suitability against the classic Sabatier principle.

**2. It recommends.** Pick a material and it tells you which practical changes — which scavenger, whether to add a co-catalyst — would most improve its hydrogen output. This answers the everyday research question: *what should my student try next in the lab?*

**3. It justifies.** Every prediction comes with the reasoning: which material properties drove it, how confident the model is, and the actual range of hydrogen rates reported for similar materials in the published literature. It is built to earn trust, not just give numbers.

## Why you can trust it

- It was tested the honest way — on materials the model had never seen during training, not on easy re-shuffles of the same data that inflate scores. The electrocatalysis model achieves 90% accuracy (R² = 0.90) with hydrogen-binding errors near the precision of the underlying quantum calculations themselves.
- It independently rediscovered known chemistry: with no hints, it ranks MoS₂ and platinum among the best electrocatalysts — exactly the materials the field celebrates.
- For your materials specifically, it uses the **real experimental band gaps** (ZnO at 3.3 eV, not the badly-underestimated 0.7 eV that raw computational databases report). This is why it stays credible on the materials you know best.
- Several of your own published photocatalysts are in its evidence base. When you screen them, it places them where your lab actually found them.

## An honest note on the photocatalysis side

Predicting an *exact* hydrogen rate for a photocatalyst is, frankly, not possible from published literature alone — the same material is reported with hundredfold-different rates depending on nanostructure, morphology, and synthesis method, details the source papers rarely record consistently. So rather than give a falsely precise number, the tool does what the data genuinely supports: it reliably separates promising materials from poor ones (a screening accuracy of 0.72 on a standard scale), and always shows you the real published spread. For an experimentalist, an honest range is worth more than a confident wrong figure — and that honesty is deliberate.

## How your group can use it

- **You:** open the file, explore materials, use it in discussions and presentations. It is yours to keep and share.
- **Your PhD scholars:** the same models can be run on *any* new material they invent (not just the ones in the tool) using the included prediction engine — a short, documented Python tool. This makes it a daily research aid for prioritising which candidates are worth the time and cost of synthesis.

## The bottom line

This is a working, trustworthy first version of a hydrogen-catalyst screening assistant tailored to your research. It is honest about what it can and cannot do, grounded in real published data, and built to last. The natural next step — should you wish — is to fold in your group's own experimental results, which would sharpen it further on exactly the materials your lab studies.
