# Manual data / داده‌های دستی

These indicators are not available from free APIs, so they are typed in by hand every month.
After you save a file on GitHub, the site rebuilds automatically within a few minutes.

این شاخص‌ها API رایگان ندارند و هر ماه دستی وارد می‌شوند. بعد از ذخیرهٔ فایل در گیت‌هاب، سایت چند دقیقه بعد خودکار به‌روز می‌شود.

## چطور یک ماه جدید اضافه کنم
1. در گیت‌هاب وارد همین پوشه (`data/manual`) شو و روی فایل موردنظر کلیک کن.
2. آیکون مداد (**Edit this file**) را بزن.
3. یک خط جدید در انتهای فایل اضافه کن. ستون‌ها با کاما جدا می‌شوند و ترتیبشان باید با خط اول یکی باشد.
4. ماه را به شکل `YYYY-MM` بنویس (مثلاً `2026-09`). اعداد را بدون علامت درصد بنویس (مثلاً `48.7`).
5. اگر عددی را نداری، خانه‌اش را خالی بگذار (دو کامای پشت‌سرهم).
6. **Commit changes** را بزن.

| File | Source | When |
|---|---|---|
| `ism_manufacturing.csv` | ISM Manufacturing PMI® Report on Business (ismworld.org) | 1st business day of the month |
| `ism_services.csv` | ISM Services PMI® Report on Business | 3rd business day |
| `ism_industries.csv` | Same reports: industries reporting growth / contraction + respondent comments | monthly |
| `nfib_sbet.csv` | NFIB Small Business Economic Trends report (PDF, nfib.com) | 2nd Tuesday |
| `china_pmi.csv` | NBS official PMIs (stats.gov.cn) and RatingDog China PMIs by S&P Global (formerly Caixin) | end / start of month |

Column notes
- `ism_industries.csv`: one row per industry per month; `status` = `growth` or `contraction`; `rank` = position in
  ISM's list (1 = first listed); `comment` is optional (put the text in double quotes if it contains a comma).
- `china_pmi.csv`: before Aug 2025 the private PMI was called Caixin — enter it in the same `ratingdog_*` columns.
- NFIB components are net percentages as printed in the report (can be negative).

## Automatic checks
Every time a file here changes, GitHub validates it (Actions → **Update data & deploy site** → job
**Check manual data**; locally: `python -m pipeline.manual --check`). Each problem is reported with its line and
column, on the run page and on the website's **Data health** page. A row with an error is never used (both copies
of a duplicated month are left out); every other row still is.

- `month` must be `YYYY-MM` (e.g. `2026-09`), not in the future, one row per month.
- ISM and PMI values: 0–100. NFIB components: −100 to 100. NFIB Optimism Index: 60–140.
- No `%` sign; decimals with a dot (`48.7`). Empty cell = missing value.

Freshness, from each report's release calendar: **Up to date** → **New report out** (released, not yet entered,
for up to 5 days) → **Awaiting data** (shown with its last date and left out of every score until entered).

## بررسی خودکار
هر بار که فایلی در این پوشه تغییر کند، گیت‌هاب آن را بررسی می‌کند (Actions ← **Update data & deploy site** ← بخش
**Check manual data**). هر خطا با شمارهٔ خط و نام ستون نشان داده می‌شود؛ هم در صفحهٔ اجرا و هم در صفحهٔ **Data health** سایت.
سطری که خطا دارد استفاده نمی‌شود (اگر ماهی دو بار آمده باشد، هیچ‌کدام استفاده نمی‌شود) ولی بقیهٔ سطرها استفاده می‌شوند.

- ستون `month` باید به شکل `YYYY-MM` باشد (مثلاً `2026-09`)، نه در آینده، و هر ماه فقط یک سطر.
- اعداد ISM و PMI بین ۰ تا ۱۰۰؛ اجزای NFIB بین ۱۰۰- تا ۱۰۰؛ شاخص اصلی NFIB بین ۶۰ تا ۱۴۰.
- بدون علامت `%`؛ اعشار با نقطه (`48.7`)؛ خانهٔ خالی یعنی عدد موجود نیست.

وضعیت به‌روز بودن بر اساس تقویم انتشار هر گزارش: **Up to date** (به‌روز) ← **New report out** (گزارش جدید منتشر شده و تا ۵ روز
فرصت ورود دارید) ← **Awaiting data** (با آخرین تاریخ نشان داده می‌شود و تا وقتی وارد نشود در هیچ امتیازی حساب نمی‌شود).
