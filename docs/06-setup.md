# One-time setup / راه‌اندازی (یک بار)

The site is built and published by GitHub Actions (`.github/workflows/update.yml`): every day at 22:23 UTC,
after every change to `data/manual/` on `main`, and on demand. It needs five things from the repository owner.

| # | What | Where (exact GitHub labels) |
|---|---|---|
| 1 | Pages must be allowed for the repo | Free plan: the repo must be **public** (Settings → General → Danger Zone → Change repository visibility). Or keep it private with GitHub Pro. |
| 2 | FRED API key as a secret | Settings → Secrets and variables → Actions → **New repository secret** → Name `FRED_API_KEY` |
| 3 | Pages published by Actions | Settings → Pages → Build and deployment → Source: **GitHub Actions** |
| 4 | The code on `main` | Merge the work branch with a pull request |
| 5 | SEC EDGAR contact (Screener "Evidence" numbers) | Settings → Secrets and variables → Actions → **New repository secret** → Name `SEC_USER_AGENT`, value `PTM-Fundamental-Dashboard your@email.com` (SEC requires a contact e-mail in every request) |

Then run it once: Actions → **Update data & deploy site** → **Run workflow**. The site address appears in
Settings → Pages ("Your site is live at …"), normally `https://sinafxd.github.io/StockMarket/`.

Troubleshooting
- *Configure GitHub Pages* step fails: step 1 or 3 is missing.
- *Commit updated data* fails with 403: Settings → Actions → General → Workflow permissions →
  **Read and write permissions** → Save.
- FRED series show "Fetch failed: FRED_API_KEY is not set": step 2 is missing or the name is misspelled.
- Data health shows "SEC EDGAR: SEC_USER_AGENT is not set": step 5 is missing; the Screener works without the
  Evidence columns.
- GitHub pauses scheduled workflows in a public repo after 60 days without activity. Entering manual data
  every month counts as activity; if it ever happens, Actions shows a button to re-enable the workflow.

---

<div dir="rtl">

## راهنمای فارسی

سایت را GitHub Actions می‌سازد و منتشر می‌کند. این کار هر روز ساعت ۲۲:۲۳ به وقت UTC (حدود ۱:۵۳ بامداد تهران)، بعد از هر تغییر در پوشهٔ `data/manual/` و هر وقت که خودتان بخواهید انجام می‌شود. فقط یک بار باید این مراحل را انجام دهید.

### ۱) اجازهٔ GitHub Pages
ریپوی شما الان **Private** است. در حساب رایگان گیت‌هاب، Pages فقط برای ریپوی Public کار می‌کند. یکی از این دو راه را انتخاب کنید:
- **راه رایگان: Public کردن ریپو**
  1. در صفحهٔ ریپو روی **Settings** کلیک کنید.
  2. در تب **General** تا پایین صفحه بروید، به بخش **Danger Zone**.
  3. روی **Change visibility** کلیک کنید و **Make public** را بزنید.
  4. با پیام‌های تأیید، کار را تمام کنید.
  - توجه: با این کار یادداشت‌های بازنویسی‌شدهٔ دوره در `docs/` هم عمومی می‌شوند. کلید FRED عمومی نمی‌شود، چون در Secrets نگه داشته می‌شود.
- **راه پولی:** خرید GitHub Pro (حدود ماهی ۴ دلار). در این حالت ریپو خصوصی می‌ماند، ولی خود سایت باز هم عمومی است.

### ۲) گذاشتن کلید FRED به‌عنوان Secret
1. **Settings** ← در منوی چپ **Secrets and variables** ← **Actions**
2. روی دکمهٔ سبز **New repository secret** بزنید.
3. در **Name** بنویسید: `FRED_API_KEY`
4. در **Secret** کلید FRED خود را بچسبانید. کلید رایگان را از fredaccount.stlouisfed.org، بخش **API Keys**، می‌گیرید.
5. **Add secret** را بزنید.

### ۲ب) گذاشتن ایمیل تماس برای SEC EDGAR (ستون‌های Evidence در Screener)
1. **Settings** ← در منوی چپ **Secrets and variables** ← **Actions**
2. روی دکمهٔ سبز **New repository secret** بزنید.
3. در **Name** بنویسید: `SEC_USER_AGENT`
4. در **Secret** بنویسید: `PTM-Fundamental-Dashboard` بعد یک فاصله و بعد ایمیل خودتان؛ مثلاً `PTM-Fundamental-Dashboard you@example.com`
5. **Add secret** را بزنید.

SEC در هر درخواست یک ایمیل تماس می‌خواهد. این ایمیل فقط برای SEC فرستاده می‌شود و در کد یا سایت دیده نمی‌شود.

### ۳) روشن کردن Pages
1. **Settings** ← در منوی چپ **Pages**
2. در بخش **Build and deployment**، گزینهٔ **Source** را روی **GitHub Actions** بگذارید.

### ۴) آوردن کد روی شاخهٔ main
کد فاز ۰ روی شاخهٔ `claude/wonderful-fermi-rtmrmf` است. باید با یک Pull Request وارد `main` شود:
1. تب **Pull requests** ← **New pull request**
2. **base** را `main` و **compare** را `claude/wonderful-fermi-rtmrmf` بگذارید.
3. **Create pull request** و بعد **Merge pull request** ← **Confirm merge** را بزنید.

(اگر بخواهید، Claude می‌تواند Pull Request را برایتان بسازد.)

### ۵) اولین اجرا و آدرس سایت
1. تب **Actions** ← در فهرست چپ **Update data & deploy site** ← دکمهٔ **Run workflow** ← دوباره **Run workflow**
2. چند دقیقه صبر کنید تا تیک سبز بیاید.
3. آدرس سایت را در **Settings** ← **Pages** پیدا می‌کنید: «Your site is live at …». معمولاً `https://sinafxd.github.io/StockMarket/` است.

### اگر چیزی قرمز شد
- **Check manual data قرمز شد:** در یکی از فایل‌های CSV دستی خطایی هست. روی اجرا کلیک کنید؛ شمارهٔ خط و توضیح خطا نوشته شده. همین خطاها در صفحهٔ **Data health** سایت هم دیده می‌شوند. بقیهٔ داده‌ها باز هم منتشر می‌شوند.
- **Configure GitHub Pages قرمز شد:** مرحلهٔ ۱ یا ۳ انجام نشده.
- **Commit updated data با خطای 403 قرمز شد:**
  1. **Settings** ← **Actions** ← **General** را باز کنید.
  2. در بخش **Workflow permissions** گزینهٔ **Read and write permissions** را انتخاب کنید.
  3. **Save** را بزنید.
- **در صفحهٔ Data health، سری‌های FRED پیام FRED_API_KEY is not set دارند:** مرحلهٔ ۲ انجام نشده، یا نام Secret دقیقاً `FRED_API_KEY` نیست.
- **در صفحهٔ Data health پیام SEC_USER_AGENT is not set هست:** مرحلهٔ ۲ب انجام نشده، یا نام Secret دقیقاً `SEC_USER_AGENT` نیست. Screener بدون ستون‌های Evidence کار می‌کند.
- **اجرای روزانه متوقف شد:** گیت‌هاب در ریپوی عمومی، بعد از ۶۰ روز بدون هیچ فعالیتی، اجرای زمان‌بندی‌شده را متوقف می‌کند. وارد کردن ماهانهٔ داده‌های دستی فعالیت حساب می‌شود. اگر باز هم متوقف شد، در تب Actions دکمه‌ای برای روشن کردن دوباره هست.

</div>
