import json
import os
import random
import string
from datetime import datetime, timedelta, timezone

import firebase_admin
import streamlit as st
from firebase_admin import credentials, db


# ------------------------------------------------------------
# 基本設定
# ------------------------------------------------------------
st.set_page_config(
    page_title="コトノスケール ONLINE",
    page_icon="🎚️",
    layout="wide",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700;900&display=swap');

    /* 全体 */
    html, body, [class*="css"], [data-testid="stAppViewContainer"] {
        font-family: 'Noto Sans JP', sans-serif;
    }
    .stApp {
        background: linear-gradient(140deg, #10162a 0%, #182443 55%, #241b3d 100%);
        color: #f4f6ff;
    }
    /* 見出し・本文・説明文 */
    h1, h2, h3, h4, p, label, li, span, small,
    [data-testid="stMarkdownContainer"],
    [data-testid="stCaptionContainer"],
    [data-testid="stWidgetLabel"],
    [data-testid="stHelp"] {
        color: #f4f6ff;
    }
    [data-testid="stCaptionContainer"] { color: #cbd5ee !important; }

    /* 入力欄：背景を明るめの紺、文字を白に */
    .stTextInput input, .stNumberInput input, .stTextArea textarea,
    [data-baseweb="input"] input, [data-baseweb="textarea"] textarea {
        background-color: #26334f !important;
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
        border: 1px solid #7183ad !important;
        border-radius: 9px !important;
        caret-color: #ffffff !important;
    }
    input::placeholder, textarea::placeholder {
        color: #cbd5e1 !important;
        -webkit-text-fill-color: #cbd5e1 !important;
        opacity: 1 !important;
    }
    /* セレクトボックス */
    [data-baseweb="select"] > div {
        background-color: #26334f !important;
        color: #ffffff !important;
        border-color: #7183ad !important;
    }
    [data-baseweb="select"] *, [role="option"] {
        color: #ffffff !important;
    }
    ul[data-testid="stSelectboxVirtualDropdown"] {
        background-color: #26334f !important;
    }

    /* ボタン */
    div.stButton > button, div.stFormSubmitButton > button {
        border-radius: 12px;
        font-weight: 700;
        min-height: 2.7rem;
        background-color: #526ee8 !important;
        color: #ffffff !important;
        border: 1px solid #8798ff !important;
    }
    div.stButton > button:hover, div.stFormSubmitButton > button:hover {
        background-color: #6b82ff !important;
        color: #ffffff !important;
        border-color: #c7d2fe !important;
    }

    /* メトリクス・カード */
    div[data-testid="stMetric"] {
        background: #222e4d;
        padding: 14px;
        border-radius: 14px;
        border: 1px solid #39496f;
    }
    [data-testid="stMetricLabel"], [data-testid="stMetricValue"],
    [data-testid="stMetricDelta"] { color: #ffffff !important; }

    /* チェックボックス・ラジオ・スライダーなど */
    [data-testid="stCheckbox"] label, [data-testid="stRadio"] label,
    [data-testid="stSlider"] label, [data-testid="stSelectSlider"] label {
        color: #f4f6ff !important;
    }
    [data-testid="stAlert"] { color: #172033; }

    /* サイドバー */
    [data-testid="stSidebar"] {
        background-color: #151d32;
        border-right: 1px solid #303d5c;
    }
    [data-testid="stSidebar"] * { color: #f4f6ff; }

    /* サイドバーが閉じているときのボタンを三本線にする。
       Streamlitのバージョンによってtest idが異なるため複数指定。 */
    [data-testid="stSidebarCollapsedControl"] svg,
    button[data-testid="stSidebarCollapsedControl"] svg,
    [data-testid="collapsedControl"] svg,
    button[data-testid="collapsedControl"] svg {
        display: none !important;
        visibility: hidden !important;
    }
    [data-testid="stSidebarCollapsedControl"],
    button[data-testid="stSidebarCollapsedControl"],
    [data-testid="collapsedControl"],
    button[data-testid="collapsedControl"] {
        color: #f4f6ff !important;
        min-width: 2.75rem !important;
        min-height: 2.75rem !important;
        position: relative !important;
    }
    [data-testid="stSidebarCollapsedControl"]::after,
    button[data-testid="stSidebarCollapsedControl"]::after,
    [data-testid="collapsedControl"]::after,
    button[data-testid="collapsedControl"]::after {
        content: "☰" !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        color: #f4f6ff !important;
        font-family: Arial, sans-serif !important;
        font-size: 25px !important;
        font-weight: 700 !important;
        line-height: 1 !important;
        visibility: visible !important;
    }

    /* 区切り線 */
    hr { border-color: #465577 !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🎚️ コトノスケール ONLINE")
st.caption("言葉の感覚を頼りに、みんなの数字を小さい順に並べよう。")


# ------------------------------------------------------------
# 設定・Firebase接続
# ------------------------------------------------------------
def read_config(key: str, default: str = "") -> str:
    """Streamlit Secretsを優先し、なければ環境変数を読む。"""
    try:
        value = st.secrets.get(key, default)
    except Exception:
        value = os.environ.get(key, default)
    return value if isinstance(value, str) else default


DATABASE_URL = read_config("FIREBASE_DATABASE_URL").strip().rstrip("/")
SERVICE_ACCOUNT_TEXT = read_config("FIREBASE_SERVICE_ACCOUNT_JSON").strip()

if not DATABASE_URL or not SERVICE_ACCOUNT_TEXT:
    st.error("Firebase接続設定が見つかりません。StreamlitのSecretsを確認してください。")
    st.code(
        "FIREBASE_DATABASE_URL = \"https://YOUR-DATABASE-URL\"\n"
        "FIREBASE_SERVICE_ACCOUNT_JSON = '''Firebaseから取得したJSON全文'''",
        language="toml",
    )
    st.stop()

try:
    service_account_info = json.loads(SERVICE_ACCOUNT_TEXT)
    if not isinstance(service_account_info, dict):
        raise ValueError("サービスアカウントJSONの形式がオブジェクトではありません。")

    if not firebase_admin._apps:
        certificate = credentials.Certificate(service_account_info)
        firebase_admin.initialize_app(certificate, {"databaseURL": DATABASE_URL})
except Exception as exc:
    st.error("Firebaseの初期化に失敗しました。SecretsのURLとJSONを確認してください。")
    st.caption(f"エラー種別: {type(exc).__name__}")
    st.stop()


def db_read(path: str):
    """Firebaseからデータを読み込む。失敗時は呼び出し元で表示する。"""
    return db.reference(path).get()


def db_write(path: str, value) -> None:
    """Firebaseへデータを書き込む。失敗時は例外を呼び出し元へ返す。"""
    db.reference(path).set(value)


def room_path(code: str) -> str:
    return f"kotono_rooms/{code}"


def make_room_code() -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=5))


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def timestamp() -> str:
    return utc_now().isoformat()


def create_room_data(host_name: str, minutes: int, low: int, high: int) -> dict:
    return {
        "host": host_name,
        "phase": "lobby",
        "created": timestamp(),
        "settings": {"minutes": int(minutes), "low": int(low), "high": int(high)},
        "deadline": None,
        "players": {},
        "chat": [],
        "result": None,
    }


def remaining_seconds(room: dict):
    deadline = room.get("deadline")
    if not deadline:
        return None
    try:
        end_time = datetime.fromisoformat(deadline)
        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=timezone.utc)
        return max(0, int((end_time - utc_now()).total_seconds()))
    except (TypeError, ValueError):
        return None


def format_time(seconds: int) -> str:
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def valid_nickname(value: str) -> bool:
    """Firebaseのキーに使えない文字をニックネームから除外する。"""
    forbidden = set(".#$/[]")
    return bool(value) and not any(char in forbidden or ord(char) < 32 for char in value)


def show_write_error(action: str, exc: Exception) -> None:
    st.error(f"{action}に失敗しました。")
    st.caption(f"エラー種別: {type(exc).__name__} / 詳細: {str(exc)[:300]}")


# ------------------------------------------------------------
# セッション状態
# ------------------------------------------------------------
if "nickname" not in st.session_state:
    st.session_state.nickname = ""
if "room_code" not in st.session_state:
    st.session_state.room_code = ""
if "sidebar_section" not in st.session_state:
    st.session_state.sidebar_section = "遊び方"


# ------------------------------------------------------------
# サイドバー（左上の≡ボタンで開閉できます）
# ------------------------------------------------------------
with st.sidebar:
    st.markdown("### 👤 プレイヤー")
    nickname_input = st.text_input(
        "ニックネーム",
        value=st.session_state.nickname,
        max_chars=18,
        key="sidebar_nickname",
        help=". # $ / [ ] は使用できません。",
    )
    st.session_state.nickname = nickname_input.strip()
    st.caption("同じ名前がいる場合は、少し変えてね。")
    st.divider()
    st.markdown("## ☰ メニュー")
    st.caption("画面左上の三本線から、いつでも開閉できます。")

    if st.button("📘 遊び方", key="menu_howto", use_container_width=True):
        st.session_state.sidebar_section = "遊び方"
    if st.button("🏠 ルーム情報", key="menu_room_info", use_container_width=True):
        st.session_state.sidebar_section = "ルーム情報"
    if st.button("⚙️ 設定", key="menu_settings", use_container_width=True):
        st.session_state.sidebar_section = "設定"
    if st.button("🚪 ゲームから退出する", key="menu_exit", use_container_width=True):
        st.session_state.sidebar_section = "退出確認"

    st.divider()
    section = st.session_state.sidebar_section

    if section == "遊び方":
        st.markdown("### 📘 遊び方")
        st.write("1. それぞれに秘密の数字が配られます。")
        st.write("2. 数字そのものは言わず、数字の大きさを言葉で表現します。")
        st.write("3. ヒントとチャットを使って、小さい順を相談します。")
        st.write("4. ゲームマスターが順番を確定して答え合わせします。")

    elif section == "ルーム情報":
        st.markdown("### 🏠 ルーム情報")
        current_code = st.session_state.room_code
        if current_code:
            st.markdown(f"**参加コード：`{current_code}`**")
            try:
                current_room = db_read(room_path(current_code))
                if current_room:
                    phase_names = {"lobby": "準備中", "playing": "プレイ中", "finished": "終了"}
                    st.write(f"状態：{phase_names.get(current_room.get('phase'), '不明')}")
                    st.write(f"ホスト：{current_room.get('host', '不明')}")
                    current_players = list((current_room.get("players") or {}).keys())
                    st.write(f"参加人数：{len(current_players)}人")
                    if current_players:
                        st.caption("参加者：" + "、".join(current_players))
                else:
                    st.info("ルーム情報を取得できませんでした。")
            except Exception:
                st.warning("ルーム情報を読み込めません。少し待ってから更新してください。")
        else:
            st.info("まだルームに参加していません。")

    elif section == "設定":
        st.markdown("### ⚙️ 設定")
        st.write("現在のニックネーム：" + (st.session_state.nickname or "未設定"))
        st.caption("ニックネームを変更するときは、サイドバー上部の入力欄を編集してください。")
        st.caption("画面の配色は読みやすいダークテーマに設定されています。")

    elif section == "退出確認":
        st.markdown("### 🚪 ゲームから退出")
        if st.session_state.room_code:
            st.warning("現在のルームから退出して、ルーム選択画面に戻ります。ルーム自体や他の参加者は削除されません。")
            if st.button("退出する", key="confirm_leave_room", type="primary", use_container_width=True):
                st.session_state.room_code = ""
                st.session_state.sidebar_section = "遊び方"
                st.rerun()
            if st.button("キャンセル", key="cancel_leave_room", use_container_width=True):
                st.session_state.sidebar_section = "遊び方"
                st.rerun()
        else:
            st.info("現在、参加中のルームはありません。")
            if st.button("戻る", key="cancel_leave_no_room", use_container_width=True):
                st.session_state.sidebar_section = "遊び方"
                st.rerun()

if not st.session_state.nickname:
    st.info("まず左側でニックネームを入力してください。")
    st.stop()

if not valid_nickname(st.session_state.nickname):
    st.error("ニックネームに . # $ / [ ] や制御文字は使えません。別の名前にしてください。")
    st.stop()

nickname = st.session_state.nickname


# ------------------------------------------------------------
# ルーム作成・参加
# ------------------------------------------------------------
st.subheader("🏠 ルーム")
create_col, join_col = st.columns(2)

with create_col:
    st.markdown("#### ルームを作成")
    with st.form("create_room_form"):
        minutes = st.selectbox("制限時間（分）", options=[1, 2, 3, 4, 5, 7, 10, 15], index=4)
        number_range = st.selectbox(
            "数字の範囲",
            options=[(1, 10), (1, 50), (1, 100), (1, 1000)],
            index=2,
            format_func=lambda item: f"{item[0]}〜{item[1]}",
        )
        create_clicked = st.form_submit_button("✨ 新しいルームを作る", use_container_width=True)

    if create_clicked:
        low, high = number_range
        try:
            code = ""
            for _ in range(5):
                candidate = make_room_code()
                if db_read(room_path(candidate)) is None:
                    code = candidate
                    break
            if not code:
                raise RuntimeError("空いているルームコードを作成できませんでした。もう一度お試しください。")

            room = create_room_data(nickname, minutes, low, high)
            room["players"][nickname] = {
                "number": random.randint(low, high),
                "hint": "",
                "joined": timestamp(),
            }
            db_write(room_path(code), room)
            st.session_state.room_code = code
            st.rerun()
        except Exception as exc:
            show_write_error("ルーム作成", exc)

with join_col:
    st.markdown("#### ルームに参加")
    with st.form("join_room_form"):
        join_code = st.text_input("参加コード（5文字）", max_chars=5).strip().upper()
        join_clicked = st.form_submit_button("🚪 参加する", use_container_width=True)

    if join_clicked:
        if len(join_code) != 5 or not join_code.isalnum():
            st.error("参加コードは英数字5文字で入力してください。")
        else:
            try:
                room = db_read(room_path(join_code))
                if not room:
                    st.error("ルームが見つかりません。コードを確認してください。")
                elif room.get("phase") != "lobby":
                    st.error("このルームはすでにゲームが始まっています。")
                elif nickname in room.get("players", {}):
                    st.session_state.room_code = join_code
                    st.rerun()
                else:
                    low = int(room["settings"]["low"])
                    high = int(room["settings"]["high"])
                    room.setdefault("players", {})[nickname] = {
                        "number": random.randint(low, high),
                        "hint": "",
                        "joined": timestamp(),
                    }
                    db_write(room_path(join_code), room)
                    st.session_state.room_code = join_code
                    st.rerun()
            except Exception as exc:
                show_write_error("ルーム参加", exc)


# ------------------------------------------------------------
# ルーム本体
# ------------------------------------------------------------
room_code = st.session_state.room_code
if not room_code:
    st.stop()

try:
    room = db_read(room_path(room_code))
except Exception as exc:
    show_write_error("ルーム読み込み", exc)
    st.stop()

if not room:
    st.error("現在のルームを読み込めません。ルームが削除された可能性があります。")
    if st.button("ルーム選択に戻る"):
        st.session_state.room_code = ""
        st.rerun()
    st.stop()

players = room.get("players", {}) or {}
is_host = room.get("host") == nickname

header_a, header_b, header_c = st.columns([2, 1, 1])
header_a.markdown(f"### ルームコード：`{room_code}`")
header_b.metric("参加人数", len(players))
phase_labels = {"lobby": "準備中", "playing": "プレイ中", "finished": "終了"}
header_c.metric("状態", phase_labels.get(room.get("phase"), "不明"))
if header_a.button("📋 参加コードを表示"):
    st.toast(f"参加コード：{room_code}")
st.caption("他の人の操作を反映するには、画面下の「画面を更新」を押してください。")


# ------------------------------------------------------------
# 待機中
# ------------------------------------------------------------
if room.get("phase") == "lobby":
    st.markdown("### 👥 参加プレイヤー")
    st.write("、".join(players.keys()) if players else "まだ参加者はいません")

    if is_host:
        settings = room.get("settings", {})
        st.markdown("#### ゲーム設定")
        st.write(f"数字の範囲：{settings.get('low')}〜{settings.get('high')} ／ 制限時間：{settings.get('minutes')}分")
        if st.button("▶ ゲーム開始", type="primary", use_container_width=True, disabled=len(players) < 2):
            try:
                latest_room = db_read(room_path(room_code))
                if not latest_room or len(latest_room.get("players", {})) < 2:
                    st.error("ゲーム開始には2人以上が必要です。")
                else:
                    latest_room["phase"] = "playing"
                    latest_room["started"] = timestamp()
                    latest_room["deadline"] = (utc_now() + timedelta(minutes=int(latest_room["settings"]["minutes"]))).isoformat()
                    db_write(room_path(room_code), latest_room)
                    st.rerun()
            except Exception as exc:
                show_write_error("ゲーム開始", exc)
    else:
        st.info("ゲームマスターが開始するまで待ってね。")


# ------------------------------------------------------------
# プレイ中
# ------------------------------------------------------------
if room.get("phase") == "playing":
    seconds_left = remaining_seconds(room)
    st.markdown("### ⏳ 残り時間")
    if seconds_left is not None:
        st.markdown(f"## {format_time(seconds_left)}")
        if seconds_left == 0 and is_host:
            try:
                latest_room = db_read(room_path(room_code)) or room
                latest_room["phase"] = "finished"
                latest_room["result"] = {"reason": "time_up", "order": []}
                db_write(room_path(room_code), latest_room)
                st.rerun()
            except Exception as exc:
                show_write_error("時間切れ処理", exc)

    my_player = players.get(nickname)
    if my_player:
        st.markdown("### 🔐 あなたの秘密の数字")
        st.markdown(f"# {my_player.get('number', '?')}")
        st.caption("この数字は自分だけの秘密！チャットに数字そのものを書かないようにしよう。")
        with st.form("hint_form"):
            hint_text = st.text_input(
                "ヒント（数字を直接書かずに表現）",
                value=my_player.get("hint", ""),
                max_chars=80,
                placeholder="例：かなり控えめ／少し大胆／想像以上に大きい",
            )
            hint_clicked = st.form_submit_button("ヒントを公開")
        if hint_clicked:
            try:
                latest_room = db_read(room_path(room_code))
                if latest_room and nickname in latest_room.get("players", {}):
                    latest_room["players"][nickname]["hint"] = hint_text.strip()
                    db_write(room_path(room_code), latest_room)
                    st.rerun()
                else:
                    st.error("プレイヤー情報が見つかりません。画面を更新してください。")
            except Exception as exc:
                show_write_error("ヒント投稿", exc)

    st.markdown("### 💡 みんなのヒント")
    for player_name, player_info in players.items():
        with st.container(border=True):
            st.markdown(f"**{player_name}**")
            st.write(player_info.get("hint") or "ヒント入力待ち…")

    st.markdown("### 🧩 並び順を提案")
    st.caption("ゲームマスターが回答を確定します。名前を小さい数字から順番に選んでください。")
    suggested_order = st.multiselect("小さい数字 → 大きい数字", list(players.keys()))
    if is_host and st.button("🔒 この順番で答え合わせ", type="primary", use_container_width=True):
        if len(suggested_order) != len(players):
            st.error("全員を1回ずつ選んでください。")
        else:
            try:
                latest_room = db_read(room_path(room_code))
                if not latest_room:
                    raise RuntimeError("ルームが見つかりません。")
                latest_players = latest_room.get("players", {})
                if set(suggested_order) != set(latest_players.keys()):
                    st.error("参加者が変わっています。画面を更新してから、もう一度選んでください。")
                else:
                    latest_room["phase"] = "finished"
                    latest_room["result"] = {"order": suggested_order, "reason": "submitted", "submitted_at": timestamp()}
                    db_write(room_path(room_code), latest_room)
                    st.rerun()
            except Exception as exc:
                show_write_error("答え合わせ", exc)


# ------------------------------------------------------------
# 結果
# ------------------------------------------------------------
if room.get("phase") == "finished":
    st.markdown("## 🎉 答え合わせ")
    try:
        room = db_read(room_path(room_code)) or room
    except Exception:
        pass
    players = room.get("players", {}) or {}
    result = room.get("result") or {}
    submitted_order = result.get("order", [])

    if submitted_order:
        for position, player_name in enumerate(submitted_order, start=1):
            player_info = players.get(player_name, {})
            with st.container(border=True):
                st.markdown(f"**{position}位：{player_name}**　—　数字：**{player_info.get('number', '?')}**")
                st.write(f"ヒント：{player_info.get('hint') or '（なし）'}")

        actual_order = [name for name, _ in sorted(players.items(), key=lambda item: item[1].get("number", 0))]
        st.markdown("### 📊 結果")
        if submitted_order == actual_order:
            st.success("全員正解！完璧なスケール感！")
        else:
            exact_positions = sum(1 for chosen, actual in zip(submitted_order, actual_order) if chosen == actual)
            st.info(f"正しい順番：{' → '.join(actual_order)} ／ 位置一致 {exact_positions}/{len(actual_order)}人")
    else:
        st.warning("制限時間終了。ゲームマスターが順番を確定していません。")
        if is_host and st.button("答え合わせを終了する"):
            try:
                room["result"] = {"order": [], "reason": "time_up", "submitted_at": timestamp()}
                db_write(room_path(room_code), room)
                st.rerun()
            except Exception as exc:
                show_write_error("答え合わせ", exc)

    if is_host and st.button("🔄 同じルームでもう一度遊ぶ"):
        try:
            fresh_room = create_room_data(
                nickname,
                room["settings"]["minutes"],
                room["settings"]["low"],
                room["settings"]["high"],
            )
            for player_name in players:
                fresh_room["players"][player_name] = {
                    "number": random.randint(fresh_room["settings"]["low"], fresh_room["settings"]["high"]),
                    "hint": "",
                    "joined": timestamp(),
                }
            db_write(room_path(room_code), fresh_room)
            st.rerun()
        except Exception as exc:
            show_write_error("再プレイ", exc)


# ------------------------------------------------------------
# チャット・操作
# ------------------------------------------------------------
st.divider()
st.markdown("### 💬 ルームチャット")
chat_messages = room.get("chat", []) or []
for chat_message in chat_messages[-60:]:
    with st.container(border=True):
        st.markdown(f"**{chat_message.get('name', '?')}**　· {chat_message.get('time', '')}")
        st.write(chat_message.get("text", ""))

with st.form("chat_form", clear_on_submit=True):
    message_text = st.text_input(
        "メッセージ",
        max_chars=240,
        placeholder="相談しよう！（秘密の数字そのものは書かないでね）",
    )
    send_clicked = st.form_submit_button("送信", use_container_width=True)

if send_clicked and message_text.strip():
    try:
        latest_room = db_read(room_path(room_code))
        if not latest_room:
            raise RuntimeError("ルームが見つかりません。")
        messages = latest_room.get("chat", []) or []
        messages.append({
            "name": nickname,
            "text": message_text.strip(),
            "time": datetime.now().strftime("%H:%M"),
        })
        latest_room["chat"] = messages[-100:]
        db_write(room_path(room_code), latest_room)
        st.rerun()
    except Exception as exc:
        show_write_error("メッセージ送信", exc)

refresh_col, leave_col = st.columns(2)
with refresh_col:
    if st.button("🔄 画面を更新", use_container_width=True):
        st.rerun()
with leave_col:
    if st.button("🚪 このルームから退出", use_container_width=True):
        st.session_state.room_code = ""
        st.rerun()

st.caption("友人向けの試作版です。各プレイヤーは画面下の更新ボタンで最新状態を確認してください。")
