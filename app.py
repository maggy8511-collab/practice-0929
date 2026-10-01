from flask import Flask, render_template

app = Flask(__name__)

@app.route("/")
def home():
    return render_template(
        "index.html",
        title="Hello, World!",
        message="這是一個使用 Python Flask 框架所建立的現代化一頁式網站。"
    )

if __name__ == "__main__":
    # debug=True 會啟用即時重載與偵錯模式
    app.run(debug=True, host="127.0.0.1", port=5000)
