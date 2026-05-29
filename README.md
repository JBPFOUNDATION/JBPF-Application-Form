# 📄 Application Form Download Server

A web server that serves your PDF application form online.  
Every download gets a **unique serial number** stamped on it automatically:

```
JBPF / 2026 / JUN / 0001
JBPF / 2026 / JUN / 0002
JBPF / 2026 / JUN / 0003  ← auto-increments forever
```

The counter resets to `0001` every new month.

---

## 📁 Files in This Repo

```
├── app.py                  ← Flask web server (main code)
├── Application_Form.pdf    ← Your blank form (replace with yours)
├── templates/
│   └── index.html          ← The download webpage
├── requirements.txt        ← Python packages needed
├── Procfile                ← Tells Render how to start the server
├── render.yaml             ← Render one-click deploy config
├── runtime.txt             ← Python version
└── .gitignore
```

---

## 🚀 How to Deploy (Step by Step)

### STEP 1 — Put code on GitHub

1. Go to **https://github.com** and sign in (or create a free account)
2. Click the **"+"** button (top right) → **"New repository"**
3. Name it: `application-form-server`
4. Keep it **Public** → Click **"Create repository"**
5. On the next page, click **"uploading an existing file"**
6. **Drag and drop ALL files** from this folder into the upload area:
   - `app.py`
   - `Application_Form.pdf`
   - `requirements.txt`
   - `Procfile`
   - `render.yaml`
   - `runtime.txt`
   - `.gitignore`
   - The `templates/` folder with `index.html` inside
7. Click **"Commit changes"** (green button at bottom)

✅ Your code is now on GitHub!

---

### STEP 2 — Deploy for free on Render

1. Go to **https://render.com** and sign up with your GitHub account
2. Click **"New +"** → **"Web Service"**
3. Click **"Connect a repository"** → select `application-form-server`
4. Fill in the settings:
   - **Name**: `application-form-server` (or anything you like)
   - **Region**: Choose closest to India (e.g. Singapore)
   - **Branch**: `main`
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
   - **Plan**: Free
5. Click **"Create Web Service"**
6. Wait 2–3 minutes for it to build...
7. 🎉 You get a live URL like: `https://application-form-server.onrender.com`

**Share that URL** — anyone who opens it can download a uniquely numbered form!

---

## ⚙️ Customization

### Change the prefix (JBPF → your initials)
Open `app.py` and find this line near the top:
```python
PREFIX = "JBPF"   # ← Change this
```

### Change the form PDF
Replace `Application_Form.pdf` with your updated PDF (keep the same filename).  
Then push to GitHub → Render will auto-redeploy.

---

## 📊 Check Download Count

Visit your URL + `/stats` to see how many forms have been downloaded:

```
https://your-app.onrender.com/stats
```

Returns:
```json
{
  "total_downloads_this_period": 47,
  "current_period": "JUN 2026",
  "next_serial": "JBPF/2026/JUN/0048"
}
```

---

## ❓ FAQ

**Q: Is Render free?**  
A: Yes, the free tier is enough for this. It may sleep after 15 min of inactivity (first load is slow), but the paid plan ($7/mo) keeps it always on.

**Q: Will the counter reset if Render restarts?**  
A: On the free tier, the file system resets on restart. To make it permanent, you can use Render's **disk** add-on or switch to a small database. Contact me for help with that.

**Q: Can I use Railway instead of Render?**  
A: Yes! Go to https://railway.app → New Project → Deploy from GitHub repo → select your repo. It auto-detects everything.
