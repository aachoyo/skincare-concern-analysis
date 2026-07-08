import pandas as pd

# Load both .csv files
cleaned = pd.read_csv('../data/interim/cleaned_cosmetics.csv')
manual = pd.read_csv('../data/interim/manual_review_completed.csv')

# Create a composite key for matching (Brand + Name)
# Avoids duplicates
def make_key(df):
    return df['Brand'].str.strip().str.lower() + '||' + df['Name'].str.strip().str.lower()

cleaned['_key'] = make_key(cleaned)
manual['_key'] = make_key(manual)

# Set index on cleaned, update with manual rows, reset
cleaned = cleaned.set_index('_key')
manual = manual.set_index('_key')

# update() replaces values in 'cleaned' sheet with values from manual
# overwrite=True means manual wins where rows overlap
cleaned.update(manual, overwrite=True)

# For any rows in manual that weren't in cleaned at all, add them
new_rows = manual[~manual.index.isin(cleaned.index)]
cleaned = pd.concat([cleaned, new_rows])

# Drop the helper key column and save
cleaned = cleaned.reset_index(drop=True)
merged = cleaned.drop(columns=['_key'], errors='ignore')

merged.to_csv('../data/processed/combined_cosmetics.csv', index=False)
print(f"Done! {len(manual)} rows from manual_review applied to cleaned_cosmetics")
print(f"Final dataset: {len(merged)} rows")

