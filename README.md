# Flask Practice 一頁式網站 🚀

[![Flask CI/CD Pipeline](https://github.com/maggy8511-collab/practice-0929/actions/workflows/cicd.yml/badge.svg)](https://github.com/maggy8511-collab/practice-0929/actions/workflows/cicd.yml)

這是一個使用 Python Flask 框架所建立的現代化一頁式網站，具備自動化 CI/CD 測試與部署流程。

## 專案架構
- **後端框架**：Python / Flask
- **前端頁面**：HTML5 + 原生 CSS / JavaScript（支援互動與動態效果）
- **WSGI 伺服器**：Gunicorn
- **自動化 CI/CD**：GitHub Actions（單元測試與品質檢查）
- **雲端部署**：Render (Web Service)

## 本地開發與執行

### 1. 啟用虛擬環境
```powershell
.\venv\Scripts\Activate.ps1
```

### 2. 安裝套件
```bash
pip install -r requirements.txt
```

### 3. 啟動服務
```bash
python app.py
```
啟動後請至瀏覽器開啟：`http://127.0.0.1:5000`

## CI/CD 部署流程
1. 每次推送到 `main` 分支時，GitHub Actions 會自動執行單元測試。
2. 測試通過後，自動透過 Render Deploy Hook 觸發雲端自動部署。
