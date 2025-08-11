import os
from flask import Flask, request, abort, render_template, Response
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, ImageMessage, TextSendMessage, ImageSendMessage
from collections import defaultdict

app = Flask(__name__)

# 環境変数（プログラム内で直書きも可能）
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "00KCkQLhlaDFzo5+UTu+/C4A49iLmHu7bbpsfW8iamonjEJ1s88/wdm7Yrou+FazbxY7719UNGh96EUMa8QbsG Bf9K5rDWhJpq8XTxakXRuTM6HiJDSmERbIWfyfRMfscXJPcRyTL6YyGNZxqkYSAQdB04t89/1O/w1cDnyilFU=")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "6c12aedc292307f95ccd67e959973761")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# 問題データ（ダミー）
PUZZLES = [
    {"story": "第1問：物語が始まる…", "image_id": "1GhjyvsaWP23x_wdz7n-nSqq5cziFcf1U", "hint_word": "apple"},
    {"story": "第2問：謎は深まる…", "image_id": "1GhjyvsaWP23x_wdz7n-nSqq5cziFcf1U", "hint_word": "banana"},
    {"story": "第3問：不穏な気配…", "image_id": "1GhjyvsaWP23x_wdz7n-nSqq5cziFcf1U", "hint_word": "cat"},
    {"story": "第4問：核心に迫る…", "image_id": "1GhjyvsaWP23x_wdz7n-nSqq5cziFcf1U", "hint_word": "dog"},
    {"story": "第5問：最後の謎…", "image_id": "1GhjyvsaWP23x_wdz7n-nSqq5cziFcf1U", "hint_word": "egg"},
]

ENDING_GOOD = "Goodエンディング（大団円！）"
ENDING_BAD = "Badエンディング（少し後味が悪い…）"
ENDING_WRONG = "残念！最後の最後で間違えてしまった…"

EPILOGUE = "終章：物語は静かに幕を閉じる…"
BONUS_PUZZLE = {"story": "おまけ問題：最後の挑戦！", "image_id": "xxxxxx", "hint_word": "fish"}

# 進行状況・最新画像ID保存
progress = defaultdict(int)  # user_id → 現在の問題番号（0スタート）
last_image_id = {}           # user_id → LINE画像メッセージID

# --- Webhook受信 ---
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

# --- メッセージ受信 ---
@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip().lower()

    # startで開始
    if text == "start":
        progress[user_id] = 0
        send_puzzle(user_id)
    # ヒント
    else:
        idx = progress.get(user_id, None)
        if idx is not None and idx < len(PUZZLES):
            if text == PUZZLES[idx]["hint_word"]:
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text=f"ヒント：これは{PUZZLES[idx]['hint_word']}に関係があるかも？")
                )

@handler.add(MessageEvent, message=ImageMessage)
def handle_image_message(event):
    user_id = event.source.user_id
    last_image_id[user_id] = event.message.id
    # 主催者がフォームで判定するので返信は不要
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="画像を受け取りました。判定結果をお待ちください。")
    )

# --- 問題送信 ---
def send_puzzle(user_id):
    idx = progress[user_id]
    if idx < len(PUZZLES):
        p = PUZZLES[idx]
        messages = [
            TextSendMessage(text=p["story"]),
            ImageSendMessage(
                original_content_url=f"https://drive.google.com/uc?id={p['image_id']}",
                preview_image_url=f"https://drive.google.com/uc?id={p['image_id']}"
            ),
            TextSendMessage(text="答えとなるものの写真を送ってね")
        ]
        line_bot_api.push_message(user_id, messages)
    elif idx == len(PUZZLES):
        # 終章＋おまけ問題
        messages = [
            TextSendMessage(text=EPILOGUE),
            TextSendMessage(text=BONUS_PUZZLE["story"]),
            ImageSendMessage(
                original_content_url=f"https://drive.google.com/uc?id={BONUS_PUZZLE['image_id']}",
                preview_image_url=f"https://drive.google.com/uc?id={BONUS_PUZZLE['image_id']}"
            ),
            TextSendMessage(text="答えとなるものの写真を送ってね")
        ]
        line_bot_api.push_message(user_id, messages)

# --- 判定フォーム ---
@app.route("/judge")
def judge():
    return render_template("judge.html", users=last_image_id.keys(), progress=progress)

# --- 画像取得 ---
@app.route("/image/<user_id>")
def get_image(user_id):
    if user_id in last_image_id:
        message_content = line_bot_api.get_message_content(last_image_id[user_id])
        img_data = b''.join(message_content.iter_content())
        return Response(img_data, mimetype='image/jpeg')
    abort(404)

# --- 判定送信 ---
@app.route("/send_result/<user_id>/<result>")
def send_result(user_id, result):
    idx = progress.get(user_id, 0)

    if idx < len(PUZZLES):
        # 1〜4問目: 正解/不正解
        if result == "correct":
            line_bot_api.push_message(user_id, TextSendMessage(text="大正解！"))
            progress[user_id] += 1
            send_puzzle(user_id)
        elif result == "wrong":
            line_bot_api.push_message(user_id, TextSendMessage(text="残念。もう一度考えてみよう！"))
    elif idx == len(PUZZLES) - 1:
        # 5問目
        if result == "correct1":
            line_bot_api.push_message(user_id, [TextSendMessage(text="大正解！"), TextSendMessage(text=ENDING_GOOD)])
            progress[user_id] += 1
            send_puzzle(user_id)
        elif result == "correct2":
            line_bot_api.push_message(user_id, [TextSendMessage(text="正解！"), TextSendMessage(text=ENDING_BAD)])
            progress[user_id] += 1
            send_puzzle(user_id)
        elif result == "wrong":
            line_bot_api.push_message(user_id, [TextSendMessage(text="残念。もう一度考えてみよう！"), TextSendMessage(text=ENDING_WRONG)])
    elif idx == len(PUZZLES):
        # おまけ問題
        if result == "correct":
            line_bot_api.push_message(user_id, [TextSendMessage(text="大正解！"), TextSendMessage(text="クリア特典があるよ。探偵事務所にお越しください。")])
        elif result == "wrong":
            line_bot_api.push_message(user_id, TextSendMessage(text="残念。もう一度考えてみよう！"))

    return "OK"

if __name__ == "__main__":
    app.run(port=5000)
