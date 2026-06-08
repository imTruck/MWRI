MWRI
یک اسکریپت ساده و تمیز برای:
دریافت کانفیگ از چند Subscription Source
استخراج لینک‌ها
حذف کانفیگ‌های تکراری
تغییر نام همه کانفیگ‌ها به فرمت یکسان
ساخت فایل‌های Subscription به‌صورت داینامیک و ۳۰۰تایی
---
✨ ویژگی‌ها
دریافت کانفیگ از چند سورس مختلف
پشتیبانی از فرمت‌های رایج مثل:
`vmess://`
`vless://`
`trojan://`
`ss://`
`ssr://`
`hysteria://`
`hy2://`
`tuic://`
حذف کانفیگ‌های تکراری
تغییر نام همه کانفیگ‌ها به این فرمت:
```text
mwri 🧘🏽 1
mwri 🧘🏽 2
mwri 🧘🏽 3
```
ساخت فایل‌های خروجی بر اساس تعداد واقعی کانفیگ‌ها
تقسیم خودکار کانفیگ‌ها به فایل‌های ۳۰۰تایی
ساخت نسخه متنی و Base64 از هر ساب
---
📦 ساختار پروژه
```text
MWRI/
├─ src/
│  └─ main.py
├─ output/
│  ├─ sub1.txt
│  ├─ sub1_sub.txt
│  ├─ sub2.txt
│  ├─ sub2_sub.txt
│  └─ ...
├─ requirements.txt
└─ README.md
```
---
🔗 سورس‌های فعلی
اسکریپت از این منابع استفاده می‌کند:
`https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_VLESS_RUS_mobile.txt`
`https://key.zarazaex.xyz/sub`
`https://raw.githubusercontent.com/Efration/ZerondOne/refs/heads/main/ZerondOne.txt`
`https://raw.githubusercontent.com/iampedii/whitedns-sub/refs/heads/main/base64.txt`
`https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/BLACK_SS+All_RUS.txt`
---
⚙️ نحوه کار
اسکریپت این مراحل را انجام می‌دهد:
دریافت داده از سورس‌ها
استخراج کانفیگ‌ها
Decode کردن ساب‌های Base64 در صورت نیاز
حذف موارد تکراری
تغییر نام همه کانفیگ‌ها
تقسیم خروجی به فایل‌های ۳۰۰تایی
ساخت فایل‌های متنی و Base64
---
🧠 منطق تقسیم فایل‌ها
تقسیم‌بندی کاملاً داینامیک است.
مثال:
اگر `900` کانفیگ استخراج شود → `3` ساب ساخته می‌شود
اگر `1000` کانفیگ استخراج شود → `4` ساب ساخته می‌شود
اگر `1200` کانفیگ استخراج شود → `4` ساب ساخته می‌شود
اگر `600` کانفیگ استخراج شود → `2` ساب ساخته می‌شود
یعنی تعداد فایل‌ها با این منطق ساخته می‌شود:
```text
total_subs = ceil(total_configs / 300)
```
همچنین قبل از هر اجرا، خروجی‌های قبلی پاک می‌شوند تا فقط فایل‌های جدید باقی بمانند.
---
🏷️ فرمت نام‌گذاری
تمام کانفیگ‌ها با این الگو rename می‌شوند:
```text
mwri 🧘🏽 {number}
```
نمونه:
```text
mwri 🧘🏽 1
mwri 🧘🏽 2
mwri 🧘🏽 3
...
```
---
🚀 اجرا
ابتدا وابستگی‌ها را نصب کنید:
```bash
pip install -r requirements.txt
```
سپس اسکریپت را اجرا کنید:
```bash
python .\src\main.py
```
---
📁 خروجی‌ها
در پوشه `output` این فایل‌ها ساخته می‌شوند:
`sub1.txt`
`sub1_sub.txt`
`sub2.txt`
`sub2_sub.txt`
...
`summary.json`
توضیح فایل‌ها
`subX.txt`
نسخه متنی خام کانفیگ‌ها
`subX_sub.txt`
نسخه Base64 همان فایل متنی
`summary.json`
شامل اطلاعات کلی مثل:
تعداد کل کانفیگ‌ها
تعداد کل ساب‌ها
اندازه هر chunk
لیست فایل‌های ساخته‌شده
---
📝 مثال خروجی
اگر ۹۲۰ کانفیگ پیدا شود:
`sub1.txt` → 300 config
`sub2.txt` → 300 config
`sub3.txt` → 300 config
`sub4.txt` → 20 config
---
✅ Git
برای ثبت تغییرات:
```bash
git add src/main.py requirements.txt README.md
```
اگر خواستی فایل‌های خروجی را هم push کنی:
```bash
git add -f output
```
سپس:
```bash
git commit -m "Build dynamic 300-size subscriptions"
git push origin main
```
---
📌 نکته
اگر تعداد کانفیگ‌ها در اجرای بعدی کمتر یا بیشتر شود، تعداد فایل‌های خروجی هم به‌صورت خودکار کم یا زیاد می‌شود.
---
❤️ MWRI
ساده، مرتب، داینامیک.