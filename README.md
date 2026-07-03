# MWRI

<p align="center">
  <b>Dynamic Subscription Builder</b>
  <br>
  Extract • Rename • Split • Publish
</p>

<p align="center">
  کانفیگ‌ها از چند سورس جمع می‌شوند، موارد تکراری واقعی حذف می‌شوند، ترتیب خروجی‌ها رندوم می‌شود و اسم همه به فرمت یکسان تغییر می‌کند.
</p>

---

## ✨ Features

- استخراج کانفیگ از چند Subscription Source
- حذف کانفیگ‌های تکراری واقعی حتی اگر اسمشان فرق داشته باشد
- رندوم شدن ترتیب خروجی‌ها در هر آپدیت
- Rename کردن همه کانفیگ‌ها با فرمت زیر:

```text
mwri 🧘🏽 1
mwri 🧘🏽 2
mwri 🧘🏽 3
```

- ساخت خروجی‌های داینامیک
- `sub1` تا `sub4` هرکدام حداکثر `300` کانفیگ
- باقی کانفیگ‌ها همگی داخل `sub5`
- ساخت نسخه متنی و Base64 برای هر خروجی
- آپدیت خودکار `README.md` با لینک‌های قابل کپی

---

## 📊 Current Build

- **Total Configs:** `461`
- **Chunk Size:** `300`
- **Total Subs:** `2`
- **بروزرسانی خودکار:** `هر 6 ساعت یک بار`
- **Output Folder:** [output/](https://github.com/imTruck/MWRI/tree/main/output)

---

## 🚀 Quick Copy Links

### Subscription 1

- **Base64 File:** [sub1_sub.txt](https://github.com/imTruck/MWRI/blob/main/output/sub1_sub.txt)
- **Text File:** [sub1.txt](https://github.com/imTruck/MWRI/blob/main/output/sub1.txt)
- **Raw Link:** [https://raw.githubusercontent.com/imTruck/MWRI/main/output/sub1_sub.txt](https://raw.githubusercontent.com/imTruck/MWRI/main/output/sub1_sub.txt)

> برای کپی سریع، از دکمه `Copy` بالای باکس استفاده کن.

```text
https://raw.githubusercontent.com/imTruck/MWRI/main/output/sub1_sub.txt
```

### Subscription 2

- **Base64 File:** [sub2_sub.txt](https://github.com/imTruck/MWRI/blob/main/output/sub2_sub.txt)
- **Text File:** [sub2.txt](https://github.com/imTruck/MWRI/blob/main/output/sub2.txt)
- **Raw Link:** [https://raw.githubusercontent.com/imTruck/MWRI/main/output/sub2_sub.txt](https://raw.githubusercontent.com/imTruck/MWRI/main/output/sub2_sub.txt)

> برای کپی سریع، از دکمه `Copy` بالای باکس استفاده کن.

```text
https://raw.githubusercontent.com/imTruck/MWRI/main/output/sub2_sub.txt
```

---

## 🧠 Split Logic

قانون تقسیم این پروژه این است:

- `sub1` تا `sub4` → هرکدام حداکثر `300` کانفیگ
- اگر کانفیگ اضافه بماند → همه داخل `sub5`

### مثال
- `850` config → `sub1=300`, `sub2=300`, `sub3=250`
- `1200` config → `4` sub
- `1400` config → `sub1..sub4=300`, `sub5=200`
- `2500` config → `sub1..sub4=300`, `sub5=1300`

---

## ⚙️ Run Locally

```bash
pip install -r requirements.txt
python .\src\main.py
```

---

## 🛠 Sources

```text
https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_VLESS_RUS_mobile.txt
https://key.zarazaex.xyz/sub
https://raw.githubusercontent.com/Efration/ZerondOne/refs/heads/main/ZerondOne.txt
https://raw.githubusercontent.com/iampedii/whitedns-sub/refs/heads/main/base64.txt
https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/BLACK_SS+All_RUS.txt
```

---

## ❤️ MWRI

Simple, clean, focused.
