# ============================================================
# COSMETICS INGREDIENT CONCERN SCORE ANALYSIS
# ============================================================

import re
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy import stats


# ------------------------------------------------------------
# STEP 0 — CONFIGURATION
# ------------------------------------------------------------

PRODUCTS_FILE = "../data/processed/combined_cosmetics.csv"
FLAGGED_FILE = "../data/flagged/flagged_ingredients.csv"

COL_NAME = "Name"
COL_BRAND = "Brand"
COL_PRICE = "Price"
COL_RATING = "Rank"
COL_INGREDIENTS = "Ingredients"
COL_LABEL = "Label"


# ------------------------------------------------------------
# STEP 1 — LOAD DATA
# ------------------------------------------------------------

print("Loading data...")

products = pd.read_csv(PRODUCTS_FILE)
flagged = pd.read_csv(FLAGGED_FILE)

products.columns = products.columns.str.strip()
flagged.columns = flagged.columns.str.strip().str.lower()

# Your flagged file has: Ingredient | Risk Score
flagged = flagged.rename(columns={
    "ingredient": "ingredient",
    "risk score": "severity"
})

flagged["ingredient"] = flagged["ingredient"].astype(str).str.strip().str.lower()
flagged["severity"] = pd.to_numeric(flagged["severity"], errors="coerce")

flagged = flagged.dropna(subset=["ingredient", "severity"])
flagged["severity"] = flagged["severity"].astype(int)

print(f"Products loaded: {len(products)}")
print(f"Flagged ingredients loaded: {len(flagged)}")


# ------------------------------------------------------------
# STEP 2 — BUILD FLAGGED INGREDIENT LOOKUP
# ------------------------------------------------------------

ingredient_lookup = dict(zip(flagged["ingredient"], flagged["severity"]))

print(f"Lookup dictionary built: {len(ingredient_lookup)} ingredients")


# ------------------------------------------------------------
# STEP 3 — HELPER FUNCTIONS
# ------------------------------------------------------------

def clean_ingredient_text(text):
    """Normalize ingredient text for matching."""
    text = str(text).lower().strip()
    text = re.sub(r"[^a-z0-9\s\-]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def get_position_weight(position, total_ingredients):
    """
    Uses relative position in ingredient list.

    Earlier ingredients receive higher weights because ingredient lists
    are generally ordered by concentration.

    position is 0-based:
    - first ingredient gets weight close to 1
    - last ingredient gets a smaller weight
    """
    if total_ingredients <= 0:
        return 0

    return max(0.05, (total_ingredients - position) / total_ingredients)


def ingredient_matches(flagged_name, ingredient):
    """
    Matches flagged ingredients safely using word boundaries.
    This avoids overly loose substring matching.
    """
    flagged_name = clean_ingredient_text(flagged_name)
    ingredient = clean_ingredient_text(ingredient)

    if ingredient == flagged_name:
        return True

    pattern = r"\b" + re.escape(flagged_name) + r"\b"
    return bool(re.search(pattern, ingredient))


def compute_concern_score(ingredients_string):
    """
    Computes concern score for one product.

    Returns:
    - concern score
    - flagged ingredient details
    - number of flagged ingredients found
    - total number of (unique) ingredients
    """

    if pd.isna(ingredients_string) or str(ingredients_string).strip() == "":
        return 0.0, "", 0, 0

    ingredient_list = [
        clean_ingredient_text(i)
        for i in str(ingredients_string).split(",")
        if str(i).strip() != ""
    ]

    # Some listings repeat ingredients (e.g. a "key ingredients" list appended to
    # the full INCI list). Keep only the first occurrence of each ingredient,
    # since that is its real position, so repeats are not double counted.
    seen = set()
    deduped = []
    for ingredient in ingredient_list:
        if ingredient not in seen:
            seen.add(ingredient)
            deduped.append(ingredient)
    ingredient_list = deduped

    total_ingredients = len(ingredient_list)

    total_score = 0.0
    details = []
    matched_count = 0

    for position, ingredient in enumerate(ingredient_list):
        for flagged_name, severity in ingredient_lookup.items():

            if ingredient_matches(flagged_name, ingredient):
                position_weight = get_position_weight(position, total_ingredients)
                contribution = severity * position_weight

                total_score += contribution
                matched_count += 1

                details.append(
                    f"{flagged_name} "
                    f"(pos {position + 1}/{total_ingredients}, "
                    f"severity {severity}, "
                    f"weight {position_weight:.2f}, "
                    f"score {contribution:.2f})"
                )

                break

    return round(total_score, 4), " | ".join(details), matched_count, total_ingredients


def add_regression_line(ax, x, y, color="black"):
    """Adds a regression line and returns r and p values."""
    slope, intercept, r_value, p_value, _ = stats.linregress(x, y)

    x_line = np.linspace(x.min(), x.max(), 300)
    y_line = slope * x_line + intercept

    ax.plot(
        x_line,
        y_line,
        color=color,
        linewidth=2,
        label=f"r = {r_value:.2f}, p = {p_value:.3f}"
    )

    return r_value, p_value


# ------------------------------------------------------------
# STEP 4 — CLEAN PRODUCT DATA
# ------------------------------------------------------------

print("\nCleaning product data...")

products[COL_PRICE] = pd.to_numeric(products[COL_PRICE], errors="coerce")
products[COL_RATING] = pd.to_numeric(products[COL_RATING], errors="coerce")

products_clean = products.dropna(
    subset=[COL_PRICE, COL_RATING, COL_INGREDIENTS]
).copy()

print(f"Products with valid price, rating, and ingredients: {len(products_clean)}")

# A rating of 0 means the product has no reviews, not a zero-star rating.
unrated = products_clean[COL_RATING] <= 0
print(f"Dropping unrated products (rating 0): {unrated.sum()}")
products_clean = products_clean[~unrated].copy()

# Sets, kits, duos etc. combine several products' ingredient lists into one,
# which inflates their concern score, so they are excluded.
SET_PATTERN = r"\b(?:set|kit|trio|duo|regimen|bundle|starter)\b"
is_set = products_clean[COL_NAME].fillna("").str.contains(
    SET_PATTERN, case=False, regex=True
)
print(f"Dropping multi-product sets/kits: {is_set.sum()}")
products_clean = products_clean[~is_set].copy()

print(f"Products in final analysis: {len(products_clean)}")


# ------------------------------------------------------------
# STEP 5 — COMPUTE CONCERN SCORES
# ------------------------------------------------------------

print("\nComputing ingredient concern scores...")

results = products_clean[COL_INGREDIENTS].apply(compute_concern_score)

products_clean["concern_score"] = results.apply(lambda x: x[0])
products_clean["flagged_detail"] = results.apply(lambda x: x[1])
products_clean["flagged_count"] = results.apply(lambda x: x[2])
products_clean["ingredient_count"] = results.apply(lambda x: x[3])

# The concern score is a sum, so products with longer ingredient lists score
# higher almost by default. As a robustness check, also compute concern per
# ingredient, which removes the effect of list length.
products_clean["concern_per_ingredient"] = np.where(
    products_clean["ingredient_count"] > 0,
    products_clean["concern_score"] / products_clean["ingredient_count"],
    0.0
)
products_clean["log_price"] = np.log(products_clean[COL_PRICE])

print("\nConcern score summary:")
print(products_clean["concern_score"].describe().round(3))

print(
    "\nProducts with at least one flagged ingredient:",
    (products_clean["flagged_count"] > 0).sum()
)


# ------------------------------------------------------------
# STEP 6 — PRICE TIERS
# ------------------------------------------------------------

p33 = products_clean[COL_PRICE].quantile(0.333)
p67 = products_clean[COL_PRICE].quantile(0.667)

def assign_price_tier(price):
    if price <= p33:
        return "Budget"
    elif price <= p67:
        return "Mid-Range"
    else:
        return "Premium"

products_clean["price_tier"] = products_clean[COL_PRICE].apply(assign_price_tier)

tier_order = ["Budget", "Mid-Range", "Premium"]

print("\nPrice tier cutoffs:")
print(f"Budget: ≤ ${p33:.2f}")
print(f"Mid-Range: ${p33:.2f} – ${p67:.2f}")
print(f"Premium: > ${p67:.2f}")


# ------------------------------------------------------------
# STEP 7 — SUMMARY STATISTICS
# ------------------------------------------------------------

print("\nAverage concern score by price tier:")
print(
    products_clean
    .groupby("price_tier")["concern_score"]
    .agg(["count", "mean", "median", "std"])
    .reindex(tier_order)
    .round(3)
)

print("\nAverage rating by price tier:")
print(
    products_clean
    .groupby("price_tier")[COL_RATING]
    .agg(["count", "mean", "median", "std"])
    .reindex(tier_order)
    .round(3)
)

# Price and concern score are both right-skewed (a few very expensive products,
# many products with a score of 0), so Pearson's r on raw values can be pulled
# around by outliers. We therefore report three versions:
#   - Pearson r on raw price (original analysis)
#   - Pearson r on log(price), which reduces the skew in price
#   - Spearman's rho, which uses ranks and is robust to skew and outliers

def correlation_report(x, y, label):
    pearson_r, pearson_p = stats.pearsonr(x, y)
    spearman_rho, spearman_p = stats.spearmanr(x, y)
    print(
        f"{label}: Pearson r = {pearson_r:.3f} (p = {pearson_p:.3g}, "
        f"R^2 = {pearson_r ** 2:.3f}) | Spearman rho = {spearman_rho:.3f} "
        f"(p = {spearman_p:.3g})"
    )
    return pearson_r, spearman_rho

print("\nCorrelations:")
price_r, price_rho = correlation_report(
    products_clean[COL_PRICE], products_clean["concern_score"],
    "Price vs Concern Score"
)
log_price_r, _ = correlation_report(
    products_clean["log_price"], products_clean["concern_score"],
    "log(Price) vs Concern Score"
)
correlation_report(
    products_clean[COL_PRICE], products_clean["concern_per_ingredient"],
    "Price vs Concern per Ingredient"
)
correlation_report(
    products_clean["ingredient_count"], products_clean["concern_score"],
    "Ingredient Count vs Concern Score"
)
rating_r, rating_rho = correlation_report(
    products_clean[COL_RATING], products_clean["concern_score"],
    "Rating vs Concern Score"
)
correlation_report(
    products_clean[COL_PRICE], products_clean[COL_RATING],
    "Price vs Rating"
)

# Regression of concern score on log(price), controlling for ingredient count
X = np.column_stack([
    np.ones(len(products_clean)),
    products_clean["log_price"],
    products_clean["ingredient_count"],
])
coef, *_ = np.linalg.lstsq(X, products_clean["concern_score"], rcond=None)
print(
    "\nOLS: concern_score ~ log(price) + ingredient_count -> "
    f"log(price) coef = {coef[1]:.3f}, ingredient_count coef = {coef[2]:.3f}"
)


# ------------------------------------------------------------
# STEP 8 — VISUALIZATIONS
# ------------------------------------------------------------

plt.rcParams["figure.dpi"] = 130
plt.rcParams["font.family"] = "sans-serif"

ACCENT = "#E05C5C"
NAVY = "#1B3A6B"


# Plot 1: Price vs Concern Score
print("\nGenerating Plot 1...")

fig, ax = plt.subplots(figsize=(10, 6))

ax.scatter(
    products_clean[COL_PRICE],
    products_clean["concern_score"],
    alpha=0.35,
    s=25,
    color=ACCENT,
    edgecolors="none"
)

# Regression on log(price), drawn back on a log-scaled price axis
slope, intercept, _, _, _ = stats.linregress(
    products_clean["log_price"], products_clean["concern_score"]
)
x_line = np.linspace(
    products_clean["log_price"].min(), products_clean["log_price"].max(), 300
)
ax.plot(
    np.exp(x_line),
    slope * x_line + intercept,
    color=NAVY,
    linewidth=2,
    label=f"Spearman ρ = {price_rho:.2f}, Pearson r (log price) = {log_price_r:.2f}"
)

ax.set_xscale("log")
ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"${v:,.0f}"))
ax.set_xlabel("Product Price (log scale)")
ax.set_ylabel("Ingredient Concern Score")
ax.set_title("Price vs. Ingredient Concern Score", fontweight="bold")
ax.legend()

plt.tight_layout()
plt.savefig("../figures/plot1_price_vs_concern_score.png", bbox_inches="tight")
plt.close()


# Plot 2: Price Tier vs Concern Score
print("Generating Plot 2...")

fig, ax = plt.subplots(figsize=(9, 6))

tier_data = [
    products_clean.loc[products_clean["price_tier"] == tier, "concern_score"]
    for tier in tier_order
]

box = ax.boxplot(
    tier_data,
    labels=tier_order,
    patch_artist=True,
    medianprops={"color": "white", "linewidth": 2}
)

colors = ["#7EC8E3", "#5A9FBF", ACCENT]

for patch, color in zip(box["boxes"], colors):
    patch.set_facecolor(color)
    patch.set_alpha(0.85)

ax.set_xticklabels([
    f"Budget\n≤ ${p33:.0f}",
    f"Mid-Range\n${p33:.0f}–${p67:.0f}",
    f"Premium\n> ${p67:.0f}"
])

ax.set_ylabel("Ingredient Concern Score")
ax.set_title("Ingredient Concern Score by Price Tier", fontweight="bold")

plt.tight_layout()
plt.savefig("../figures/plot2_price_tier_vs_concern_score.png", bbox_inches="tight")
plt.close()


# Plot 3: Rating vs Concern Score
print("Generating Plot 3...")

fig, ax = plt.subplots(figsize=(10, 6))

ax.scatter(
    products_clean[COL_RATING],
    products_clean["concern_score"],
    alpha=0.35,
    s=25,
    color=ACCENT,
    edgecolors="none"
)

add_regression_line(
    ax,
    products_clean[COL_RATING].values,
    products_clean["concern_score"].values,
    color=NAVY
)

ax.set_xlabel("Product Rating")
ax.set_ylabel("Ingredient Concern Score")
ax.set_title("Do Ratings Reflect Ingredient Concern?", fontweight="bold")
ax.legend()

plt.tight_layout()
plt.savefig("../figures/plot3_rating_vs_concern_score.png", bbox_inches="tight")
plt.close()


# Plot 4: Price Tier vs Rating
print("Generating Plot 4...")

fig, ax = plt.subplots(figsize=(9, 6))

rating_tier_data = [
    products_clean.loc[products_clean["price_tier"] == tier, COL_RATING]
    for tier in tier_order
]

box = ax.boxplot(
    rating_tier_data,
    labels=tier_order,
    patch_artist=True,
    medianprops={"color": "white", "linewidth": 2}
)

for patch, color in zip(box["boxes"], colors):
    patch.set_facecolor(color)
    patch.set_alpha(0.85)

ax.set_xticklabels([
    f"Budget\n≤ ${p33:.0f}",
    f"Mid-Range\n${p33:.0f}–${p67:.0f}",
    f"Premium\n> ${p67:.0f}"
])

ax.set_ylabel("Product Rating")
ax.set_title("Product Ratings by Price Tier", fontweight="bold")

plt.tight_layout()
plt.savefig("../figures/plot4_price_tier_vs_rating.png", bbox_inches="tight")
plt.close()


# ------------------------------------------------------------
# STEP 9 — EXPORT RESULTS
# ------------------------------------------------------------

output_cols = [
    COL_LABEL,
    COL_NAME,
    COL_BRAND,
    COL_PRICE,
    COL_RATING,
    "price_tier",
    "concern_score",
    "flagged_count",
    "ingredient_count",
    "concern_per_ingredient",
    "flagged_detail"
]

output_cols = [col for col in output_cols if col in products_clean.columns]

output = products_clean[output_cols].sort_values(
    "concern_score",
    ascending=False
)

output.to_csv("../data/processed/results_with_concern_scores.csv", index=False)

print("\nExported: results_with_concern_scores.csv")

print("\nTop 5 products by concern score:")
print(
    output[
        [COL_NAME, COL_BRAND, COL_PRICE, COL_RATING, "concern_score", "flagged_count"]
    ]
    .head()
    .to_string(index=False)
)

print("\nDone!")