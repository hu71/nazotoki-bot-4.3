import os
from flask import Flask, request, render_template, redirect, url_for
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, ImageMessage, TextSendMessage, ImageSendMessage
from linebot.exceptions import InvalidSignatureError
from uuid import uuid4

app = Flask(__name__)

# LINE設定（環境変数が無い場合は直接ここに書いてもOK）
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "00KCkQLhlaDFzo5+UTu+/C4A49iLmHu7bbpsfW8iamonjEJ1s88/wdm7Yrou+FazbxY7719UNGh96EUMa8QbsG Bf9K5rDWhJpq8XTxakXRuTM6HiJDSmERbIWfyfRMfscXJPcRyTL6YyGNZxqkYSAQdB04t89/1O/w1cDnyilFU=")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "6c12aedc292307f95ccd67e959973761")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# ユーザーの進捗保存 { user_id: puzzle_index }
progress = {}
# ユーザーの最新送信画像保存 { user_id: { "puzzle": idx, "image_url": url } }
submissions = {}

# 問題データ
PUZZLES = [
    {"story": "第1問：物語が始まる…", "image_id": "6c12aedc292307f95ccd67e959973761", "hint_word": "apple", "hint": "赤くて甘い果物だよ"},
    {"story": "第2問：謎は深まる…", "image_id": "6c12aedc292307f95ccd67e959973761", "hint_word": "banana", "hint": "黄色くて長い果物だよ"},
    {"story": "第3問：不穏な気配…", "image_id": "6c12aedc292307f95ccd67e959973761", "hint_word": "cat", "hint": "よく鳴くペットだよ"},
    {"story": "第4問：核心に迫る…", "image_id": "6c12aedc292307f95ccd67e959973761", "hint_word": "dog", "hint": "散歩が大好きな動物だよ"},
    {"story": "第5問：最後の謎…", "image_id": "6c12aedc292307f95ccd67e959973761", "hint_word": "egg", "hint": "鳥が産む丸いものだよ"},
]

BONUS_PUZZLE = {"story": "おまけ問題：最後の挑戦！", "image_id": "6c12aedc292307f95ccd67e959973761", "hint_word": "fish", "hint": "海の中を泳ぐ生き物だよ"}

ENDING_GOOD = "Goodエンディング（大団円！）"
ENDING_BAD = "Badエンディング（少し後味が悪い…）"
ENDING_WRONG = "残念！最後の最後で間違えてしまった…"
EPILOGUE = "終章：物語は静かに幕を閉じる…"

# LINE webhook
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        return "Invalid signature", 400
    return "OK"

# 受信処理（テキスト）
@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip().lower()

    # startで開始
    if text == "start":
        progress[user_id] = 0
        send_puzzle(user_id)
        return

    # 現在の問題番号
    idx = progress.get(user_id)
    if idx is not None:
        # ヒント判定
        if idx < len(PUZZLES) and text == PUZZLES[idx]["hint_word"]:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"ヒント：{PUZZLES[idx]['hint']}"))
        elif idx == "bonus" and text == BONUS_PUZZLE["hint_word"]:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"ヒント：{BONUS_PUZZLE['hint']}"))

# 受信処理（画像）
@handler.add(MessageEvent, message=ImageMessage)
def handle_image_message(event):
    user_id = event.source.user_id
    idx = progress.get(user_id)

    if idx is None:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="まずは start と送ってね"))
        return

    # 画像を取得して一時URL化
    message_content = line_bot_api.get_message_content(event.message.id)
    file_path = f"static/{uuid4()}.jpg"
    with open(file_path, "wb") as f:
        for chunk in message_content.iter_content():
            f.write(chunk)
    image_url = request.host_url + file_path

    # 保存
    submissions[user_id] = {"puzzle": idx, "image_url": image_url}

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text="判定中です…"))

# 問題送信
def send_puzzle(user_id):
    idx = progress[user_id]
    if idx < len(PUZZLES):
        puzzle = PUZZLES[idx]
        line_bot_api.push_message(user_id, [
            TextSendMessage(text=puzzle["story"]),
            ImageSendMessage(original_content_url=f"https://drive.google.com/uc?export=view&id={puzzle['image_id']}",
                             preview_image_url=f"https://drive.google.com/uc?export=view&id={puzzle['image_id']}"),
            TextSendMessage(text="答えとなるものの写真を送ってね")
        ])
    elif idx == "bonus":
        line_bot_api.push_message(user_id, [
            TextSendMessage(text=BONUS_PUZZLE["story"]),
            ImageSendMessage(original_content_url=f"https://drive.google.com/uc?export=view&id={BONUS_PUZZLE['image_id']}",
                             preview_image_url=f"https://drive.google.com/uc?export=view&id={BONUS_PUZZLE['image_id']}"),
            TextSendMessage(text="答えとなる画像を送ってね")
        ])

# 判定フォーム
@app.route("/judge")
def judge():
    return render_template("judge.html", submissions=submissions, progress=progress, total=len(PUZZLES))

# 判定送信
@app.route("/send_result/<user_id>/<result>")
def send_result(user_id, result):
    idx = progress.get(user_id)
    if idx is None:
        return redirect(url_for("judge"))

    # 5問目だけ3パターン
    if idx == 4:
        if result == "good":
            line_bot_api.push_message(user_id, [TextSendMessage(text="大正解！"), TextSendMessage(text=ENDING_GOOD)])
            progress[user_id] = "bonus"
        elif result == "bad":
            line_bot_api.push_message(user_id, [TextSendMessage(text="正解！"), TextSendMessage(text=ENDING_BAD)])
            progress[user_id] = "bonus"
        elif result == "wrong":
            line_bot_api.push_message(user_id, [TextSendMessage(text="残念。もう一度考えてみよう！"), TextSendMessage(text="〜と送ったら何かあるかも")])
        send_puzzle(user_id)
        return redirect(url_for("judge"))

    # ボーナス問題
    if idx == "bonus":
        if result == "correct":
            line_bot_api.push_message(user_id, [TextSendMessage(text="大正解！"), TextSendMessage(text="クリア特典があるよ。探偵事務所にお越しください。")])
        elif result == "wrong":
            line_bot_api.push_message(user_id, [TextSendMessage(text="残念。もう一度考えてみよう！"), TextSendMessage(text="〜と送ったら何かあるかも")])
        return redirect(url_for("judge"))

    # 通常問題
    if result == "correct":
        line_bot_api.push_message(user_id, TextSendMessage(text="大正解！"))
        progress[user_id] += 1
        send_puzzle(user_id)
    elif result == "wrong":
        line_bot_api.push_message(user_id, [TextSendMessage(text="残念。もう一度考えてみよう！"), TextSendMessage(text="〜と送ったら何かあるかも")])

    return redirect(url_for("judge"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
