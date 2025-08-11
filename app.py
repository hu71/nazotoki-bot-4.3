from flask import Flask, request, abort, render_template, redirect, url_for
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, ImageMessage, TextSendMessage, ImageSendMessage
import os
import datetime

app = Flask(__name__)

# --- LINE API 設定 ---
CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "00KCkQLhlaDFzo5+UTu+/C4A49iLmHu7bbpsfW8iamonjEJ1s88/wdm7Yrou+FazbxY7719UNGh96EUMa8QbsG Bf9K5rDWhJpq8XTxakXRuTM6HiJDSmERbIWfyfRMfscXJPcRyTL6YyGNZxqkYSAQdB04t89/1O/w1cDnyilFU=")
CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "6c12aedc292307f95ccd67e959973761")

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# --- 謎データ ---
PUZZLES = [
    {"story": "第1問：物語が始まる…", "image_id": "1GhjyvsaWP23x_wdz7n-nSqq5cziFcf1U", "hint_word": "apple"},
    {"story": "第2問：奇妙な出来事が…", "image_id": "1GhjyvsaWP23x_wdz7n-nSqq5cziFcf1U", "hint_word": "banana"},
    {"story": "第3問：怪しい影が…", "image_id": "1GhjyvsaWP23x_wdz7n-nSqq5cziFcf1U", "hint_word": "cat"},
    {"story": "第4問：真実が近づく…", "image_id": "1GhjyvsaWP23x_wdz7n-nSqq5cziFcf1U", "hint_word": "dog"},
    {"story": "第5問：最後の決断…", "image_id": "1GhjyvsaWP23x_wdz7n-nSqq5cziFcf1U", "hint_word": "egg"},
]

ENDING_GOOD = "おめでとう！Goodエンディングです！"
ENDING_BAD = "正解だけど…Badエンディングです。"
ENDING_WRONG = "残念、不正解です。"

FINAL_CHAPTER = "終章：全ての真実が明らかになった…"
BONUS_PUZZLE = {"image_id": "xxxxxx", "hint_word": "fish"}
BONUS_CLEAR = "大正解！クリア特典があるよ。探偵事務所にお越しください。"

# --- ユーザー状態管理 ---
progress = {}       # {user_id: 現在の問題番号}
last_image_id = {}  # {user_id: LINE画像メッセージID}
user_names = {}     # {user_id: 表示名}

# --- Webhook ---
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

    # ユーザー名保存
    if user_id not in user_names:
        profile = line_bot_api.get_profile(user_id)
        user_names[user_id] = profile.display_name

    # startコマンドでゲーム開始
    if text == "start":
        progress[user_id] = 0
        send_puzzle(user_id)
    else:
        # ヒントコマンド
        if user_id in progress:
            current_q = progress[user_id]
            if current_q < len(PUZZLES):
                if text == PUZZLES[current_q]["hint_word"].lower():
                    line_bot_api.reply_message(event.reply_token, TextSendMessage(text="ヒント：これは秘密の情報だ…"))
            elif current_q == len(PUZZLES) + 1:  # おまけ
                if text == BONUS_PUZZLE["hint_word"].lower():
                    line_bot_api.reply_message(event.reply_token, TextSendMessage(text="おまけヒント：最後の鍵は…"))
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="「start」と送ってゲームを始めよう！"))

# --- 画像受信 ---
@handler.add(MessageEvent, message=ImageMessage)
def handle_image_message(event):
    user_id = event.source.user_id
    if user_id not in progress:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="まずは「start」と送ってね！"))
        return

    last_image_id[user_id] = event.message.id
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text="画像を受け取りました。主催者が判定します。"))

# --- 問題送信 ---
def send_puzzle(user_id):
    q_index = progress[user_id]
    if q_index < len(PUZZLES):
        p = PUZZLES[q_index]
        line_bot_api.push_message(user_id, [
            TextSendMessage(text=p["story"]),
            ImageSendMessage(original_content_url=f"https://drive.google.com/uc?id={p['image_id']}",
                             preview_image_url=f"https://drive.google.com/uc?id={p['image_id']}"),
            TextSendMessage(text="答えとなるものの写真を送ってね")
        ])
    elif q_index == len(PUZZLES):
        line_bot_api.push_message(user_id, [
            TextSendMessage(text=FINAL_CHAPTER),
            ImageSendMessage(original_content_url=f"https://drive.google.com/uc?id={BONUS_PUZZLE['image_id']}",
                             preview_image_url=f"https://drive.google.com/uc?id={BONUS_PUZZLE['image_id']}"),
            TextSendMessage(text="答えとなるものの写真を送ってね")
        ])

# --- 主催者用フォーム ---
@app.route("/judge")
def judge():
    data = []
    for uid, q_index in progress.items():
        if uid in last_image_id:
            img_url = f"/image/{uid}"
            data.append({
                "user_id": uid,
                "name": user_names.get(uid, "名無し"),
                "question": q_index + 1 if q_index < len(PUZZLES) else "おまけ",
                "image_url": img_url
            })
    return render_template("judge.html", data=data)

# --- 画像取得エンドポイント ---
@app.route("/image/<user_id>")
def get_image(user_id):
    if user_id in last_image_id:
        message_content = line_bot_api.get_message_content(last_image_id[user_id])
        return message_content.content, 200, {'Content-Type': 'image/jpeg'}
    abort(404)

# --- 判定処理 ---
@app.route("/send_result/<user_id>/<result>")
def send_result(user_id, result):
    q_index = progress.get(user_id, 0)

    if q_index < len(PUZZLES) - 1:  # 1〜4問目
        if result == "correct":
            line_bot_api.push_message(user_id, TextSendMessage(text="大正解！"))
            progress[user_id] += 1
            send_puzzle(user_id)
        else:
            line_bot_api.push_message(user_id, [TextSendMessage(text="残念。もう一度考えてみよう！"),
                                                TextSendMessage(text=f"「{PUZZLES[q_index]['hint_word']}」と送ったら何かあるかも")])
    elif q_index == len(PUZZLES) - 1:  # 5問目
        if result == "good":
            line_bot_api.push_message(user_id, [TextSendMessage(text="大正解！"), TextSendMessage(text=ENDING_GOOD)])
            progress[user_id] += 1
            send_puzzle(user_id)
        elif result == "bad":
            line_bot_api.push_message(user_id, [TextSendMessage(text="正解！"), TextSendMessage(text=ENDING_BAD)])
            progress[user_id] += 1
            send_puzzle(user_id)
        else:
            line_bot_api.push_message(user_id, [TextSendMessage(text=ENDING_WRONG),
                                                TextSendMessage(text=f"「{PUZZLES[q_index]['hint_word']}」と送ったら何かあるかも")])
    else:  # おまけ問題
        if result == "correct":
            line_bot_api.push_message(user_id, [TextSendMessage(text="大正解！"), TextSendMessage(text=BONUS_CLEAR)])
        else:
            line_bot_api.push_message(user_id, [TextSendMessage(text="残念。もう一度考えてみよう！"),
                                                TextSendMessage(text=f"「{BONUS_PUZZLE['hint_word']}」と送ったら何かあるかも")])
    return redirect(url_for('judge'))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
