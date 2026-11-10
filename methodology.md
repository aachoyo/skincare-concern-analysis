# Methodology

This document explains how the ingredient concern score was designed and how each
flagged ingredient was assigned a severity, the parts of the project that involve
judgment rather than code. It is meant to make the analysis transparent and challengeable.

## 1. What the concern score is (and is not)

The concern score is a proxy for how many potentially concerning ingredients a product
contains and how prominent they are in the formula. It is deliberately simple so it can be
computed consistently across ~1,400 products and interpreted without domain expertise.

It is not a safety rating. It ignores concentration, ingredient interactions, and the
fact that a flagged ingredient may be present for a legitimate functional reason
(preservation, stability, texture, UV protection). A high score flags a product for closer
reading; it does not mean the product is harmful.

## 2. The flagged-ingredient list

50 ingredients were selected because they commonly appear in discussions of irritation,
sensitization, debated safety, or toxicological concern. Sources consulted include
[CIR (Cosmetic Ingredient Review)](https://www.cir-safety.org) assessments and ingredient
pages on [INCIdecoder](https://incidecoder.com). The full list with severities lives in
[`data/flagged/flagged_ingredients.csv`](data/flagged/flagged_ingredients.csv).

Selection bias is worth stating plainly: this is a hand-picked list reflecting the author's
reading of common-concern ingredients, not an exhaustive or regulatory list. Ingredients
not on the list contribute nothing to a product's score, so the score only measures concern
*as defined by this list*.

## 3. Severity scale (1–3)

Each flagged ingredient was assigned a severity reflecting the type and strength of concern
associated with it:

**Severity 3, highest concern (formaldehyde-releasing preservatives):**
diazolidinyl urea, dmdm hydantoin, imidazolidinyl urea, quaternium-15,
sodium hydroxymethylglycinate.
These slowly release formaldehyde, a known contact allergen and sensitizer, which is why
they sit above ordinary preservatives.

**Severity 2, moderate concern:**
avobenzone, benzophenone-3 (oxybenzone), bha, bht, butylparaben, chlorhexidine,
cyclopentasiloxane, dimethicone, ethylparaben, fragrance, homosalate, methylparaben,
octinoxate, octocrylene, parfum, peg, phthalates, polysorbate, propylparaben, resorcinol,
triclosan.
This tier covers ingredient families with recurring but debated concerns: parabens
(endocrine debate), chemical UV filters (sensitization / environmental questions),
"fragrance"/"parfum" as an undisclosed allergen mixture, silicones and PEGs (occlusion /
processing-contaminant debates), and a few specific actives with documented irritation or
regulatory attention.

**Severity 1, lower concern:**
alcohol denat, benzyl alcohol, benzyl salicylate, chlorphenesin, citral, citronellol,
coumarin, eucalyptus oil, eugenol, farnesol, geraniol, hexyl cinnamal, isopropyl alcohol,
lavender oil, limonene, linalool, peppermint oil, phenoxyethanol, sd alcohol 40,
sodium benzoate, sodium lauryl sulfate, sorbic acid, talc.
Mostly EU-labelled fragrance allergens (limonene, linalool, geraniol, citronellol, etc.),
essential oils, drying alcohols, and milder preservatives, ingredients that bother
sensitive or reactive skin but are widely tolerated otherwise.

Because severities are small integers, the score is dominated by how many flagged
ingredients appear and where they sit, not by fine gradations of severity. This is
intentional; it keeps the score resilient to arguments over whether a given ingredient is
"really" a 2 vs a 3.

## 4. Position weighting

Cosmetic ingredient lists are ordered by decreasing concentration (above ~1%), so an
ingredient near the top is present in far greater quantity than one near the bottom. The
score reflects this with a linear position weight:

```
position_weight = max(0.05, (total_ingredients - position) / total_ingredients)
```

- `position` is 0-based; the first ingredient gets a weight near 1.0, the last a floor of 0.05.
- The 0.05 floor ensures a flagged ingredient at the very end still registers a small amount.

Each match then contributes `severity × position_weight`, and the product's concern score is
the sum over all flagged matches. A product listing "fragrance" (severity 2) as its 2nd of
20 ingredients earns ~1.8 from it; the same ingredient listed 18th earns ~0.2.

Matching is done on cleaned, lowercased text using word boundaries to avoid loose substring
hits. A flagged term can match more than once per product (e.g. multiple PEG derivatives),
and each occurrence is counted at its own position, which is why products with very long
lists can accumulate high scores.

## 5. Price tiers

Products are split into three tiers by price percentile, so tier sizes are roughly equal
and the cutoffs are data-driven rather than arbitrary round numbers:

- **Budget:** price ≤ 33rd percentile
- **Mid-Range:** 33rd–67th percentile
- **Premium:** price > 67th percentile

## 6. Statistics reported

**Exclusions.** Unrated products (rating 0, meaning no reviews) and multi-product
sets/kits/duos/trios (matched by name) are dropped, since a set's ingredient list combines
several products. Repeated ingredients within a listing are de-duplicated, keeping the first
(real) position. This leaves 1,433 products.

**Skew.** Price is strongly right-skewed (median ≈ $43, max $370) and the concern score is
right-skewed with a spike at 0. Pearson's r on raw values can be pulled around by a few
outliers, so each relationship is reported three ways: Pearson r on raw values, Pearson r
on log(price), and Spearman's ρ (rank-based, robust to skew). The price-vs-concern plot
uses a log price axis.

**List length.** Because the concern score is a *sum* over flagged matches, products with
longer ingredient lists score higher almost automatically (ingredient count vs. concern:
ρ ≈ 0.60), and pricier products tend to have longer lists. Two checks address this: a
per-ingredient concern score (score ÷ number of ingredients), and a regression of concern
score on log(price) plus ingredient count. Both show that the weak price–concern
relationship disappears once list length is accounted for.

With ~1,400 products, even a very weak correlation can be "statistically significant," so
the writeup leans on effect size (r, ρ and R²) rather than p-values alone. The raw
price–concern relationship is significant but explains only about 2 to 3% of variance:
statistically real but practically negligible, and explained by list length.

## 7. Data provenance and reproducibility note

The product dataset used for the slide-deck figures was `cleaned_final_cosmetics.csv`, the
final cleaned product file after the INCIdecoder scrape and manual review. The version
shipped in this repo, `data/processed/combined_cosmetics.csv`, is the equivalent merged
product file produced by `dataset_build.py`; re-running `analysis.py` against it reproduces
the same ranking of products and the same qualitative findings, with correlation values
within rounding of the deck (price–concern r ≈ 0.13 vs 0.12 reported). The exclusions,
de-duplication and robustness checks in §6 were added after the deck, so the README
figures differ slightly from the slides.

The raw Kaggle file (`cosmetics.csv`) is intentionally **not** committed. Note that the
processed CSVs still contain Kaggle-derived product fields (name, brand, price, rating,
ingredient lists); they are kept here for reproducibility. Anyone reusing this repo should
check the original Kaggle dataset's license before redistributing that content further.
