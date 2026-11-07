# Data source

| Item | Value |
|---|---|
| Title | Synthetic Dataset for E-Commerce Return Analysis |
| Publisher | Sayali Khot (Kaggle user `sayalikhot21`) |
| Page | https://www.kaggle.com/datasets/sayalikhot21/synthetic-dataset-for-e-commerce-return-analysis |
| Licence (as listed on Kaggle) | MIT |
| Version | 1 ("Initial release"); Kaggle metadata last updated 2024-08-30 |
| Retrieved | 2026-11-08 |
| Nature | **Synthetic practice data**: not real company transactions. Rates are not industry benchmarks. |

## How it was downloaded

The public Kaggle API download endpoint returned the archive without credentials:

```
https://www.kaggle.com/api/v1/datasets/download/sayalikhot21/synthetic-dataset-for-e-commerce-return-analysis
```

The response was checked to be `application/zip` (not an HTML login/error page) and contained one CSV.
If that endpoint ever requires sign-in, download the dataset from the page above in a browser
and extract it so the file sits at:

```
data/raw/ecommerce_returns_synthetic_data.csv
```

No dataset code was executed; only the CSV is read.

## Files and checksums (SHA-256)

| File | Bytes | SHA-256 |
|---|---|---|
| `ecommerce_returns_synthetic_data.csv` | 1,329,832 | `6434342079240d30cd983a816508ed4abfc3c759188e6a79f6ebf072a67cde24` |
| `synthetic-dataset-for-e-commerce-return-analysis.zip` (archive as downloaded) | 293,410 | `51b7acb54cca04d71e530ac67002acc0f724c0899827892572edc6500d768c72` |

`python pipeline.py` records the CSV checksum in `outputs/run_metadata.json` and in the database
(`build_metadata`), so exported results can always be matched to the exact input file.

## Redistribution

The raw files are not committed (they are re-downloadable and listed in `.gitignore`).
The Kaggle page lists an MIT licence; the small aggregated outputs in `outputs/` are derived summaries.
Keep this citation with any reuse.

## Verified profile (from the downloaded file)

* 10,000 rows × 17 columns; no exact duplicate rows; no surrounding whitespace; only empty strings
  as missing values.
* `Order_ID`, `Product_ID` and `User_ID` are each unique per row: **one row = one purchase**, and no
  product or user appears twice.
* Order dates 2023-01-01 to 2024-12-31 (ISO `YYYY-MM-DD`; no day/month ambiguity). Every month has
  352–464 purchases.
* `Return_Status`: `Returned` 5,052, `Not Returned` 4,948. Return date, reason and `Days_to_Return` are
  present for exactly the returned rows and blank for all others (no status conflicts).
* Reasons: Defective 1,327; Wrong item 1,258; Changed mind 1,255; Not as described 1,212.
* `Days_to_Return` equals `Return_Date − Order_Date` exactly, but it is **negative for 2,513 returns**
  (return date before the order date). Return dates span the same 2023–2024 window as order dates.
* `Product_Price` 5.01–499.89; `Order_Quantity` integers 1–5; `Discount_Applied` 0–50.
* `User_Age`, `User_Gender`, `User_Location` are present but not used in the analysis.

## What the publisher's description says vs what could be verified

| Claim on the page | Status |
|---|---|
| Price is in USD | Stated by the publisher; cannot be verified from records. Values shown without a currency symbol, labelled "publisher-stated USD". |
| `Product_Price` is the product price, `Order_Quantity` the units ordered | Consistent with the records; used as unit price × quantity. |
| `Discount_Applied` is "discount applied to the order in USD" | Not verifiable: 395 rows have a discount above the unit price, 137 above price × quantity, and nothing indicates whether it is per item or per order. **Not analysed.** |
| `Days_to_Return` = days between order and return | True arithmetically, but half the values are negative, so the date pair is unreliable for those rows. |
| No cancellation, delivery date, refund amount or partial-return field exists | Confirmed by inspection; no analysis relies on them. |
