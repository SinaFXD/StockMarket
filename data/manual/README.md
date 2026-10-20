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
