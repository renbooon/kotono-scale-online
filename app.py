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
    html, body, [class*="css"] { font-family: 'Noto Sans JP', sans-serif; }

    /* メイン画面：暗めの背景に、本文は明るい文字で */
    .stApp { background: linear-gradient(140deg, #111827 0%, #1b2942 58%, #29213f 100%); }
    .stApp, .stApp p, .stApp label, .stApp [data-testid="stMarkdownContainer"] { color: #f5f7ff; }
    h1, h2, h3, h4 { color: #ffffff !important; letter-spacing: 0.01em; }
    [data-testid="stCaptionContainer"] { color: #c8d0e0 !important; }

    /* 上部バーは黒。標準のメニューボタン自体は隠さず、形状も変更しない */
    header[data-testid="stHeader"] { background: #090b10 !important; }
    header[data-testid="stHeader"] button,
    [data-testid="stSidebarCollapsedControl"] button {
        opacity: 1 !important;
        color: #ffffff !important;
    }
    [data-testid="stSidebarCollapsedControl"] button {
        background: #39465d !important;
        border: 2px solid #a9b8d3 !important;
        border-radius: 8px !important;
        min-width: 2.5rem !important;
        min-height: 2.5rem !important;
        box-shadow: 0 0 0 2px rgba(8, 12, 20, 0.6) !important;
    }
    [data-testid="stSidebarCollapsedControl"] button svg,
    header[data-testid="stHeader"] button svg {
        color: #ffffff !important;
        fill: #ffffff !important;
        stroke: #ffffff !important;
        opacity: 1 !important;
    }

    /* サイドバーは本文より少し明るいチャコールに */
    section[data-testid="stSidebar"],
    section[data-testid="stSidebar"] > div,
    [data-testid="stSidebarContent"] { background: #242c3b !important; }
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"],
    section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] { color: #f7f8fc !important; }

    /* 入力欄：背景と文字色を明確に分ける */
    .stApp input, .stApp textarea,
    .stApp [data-baseweb="select"] > div {
        color: #ffffff !important;
        background-color: #202a3b !important;
        border-color: #73829b !important;
    }
    .stApp input::placeholder, .stApp textarea::placeholder { color: #c2cada !important; opacity: 1 !important; }
    .stApp [data-baseweb="select"] *, .stApp [role="option"] { color: #ffffff !important; }

    /* ボタン：背景と文字のコントラストを確保 */
    div.stButton > button, div.stFormSubmitButton > button {
        border-radius: 12px !important;
        font-weight: 700 !important;
        min-height: 2.8rem !important;
        color: #ffffff !important;
        background: #354764 !important;
        border: 1px solid #8fa6ca !important;
    }
    div.stButton > button:hover, div.stFormSubmitButton > button:hover {
        background: #486187 !important;
        border-color: #d0def5 !important;
    }
    div.stButton > button:disabled, div.stFormSubmitButton > button:disabled {
        color: #c5ccda !important;
        background: #343b49 !important;
        border-color: #596273 !important;
    }
    div[data-testid="stMetric"] {
        background: #222f47 !important;
        padding: 14px !important;
        border-radius: 14px !important;
        border: 1px solid #60779e !important;
    }
    div[data-testid="stMetric"] label,
    div[data-testid="stMetric"] [data-testid="stMetricValue"] { color: #ffffff !important; }
    [data-testid="stVerticalBlockBorderWrapper"] { border-color: #66748d !important; }
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


def create_room_data(host_name: str, minutes: int, low: int, high: int, mode: str = "host_plays") -> dict:
    return {
        "host": host_name,
        "mode": mode,
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


# ------------------------------------------------------------
# サイドバー
# ------------------------------------------------------------
with st.sidebar:
    st.header("👤 プレイヤー")
    nickname_input = st.text_input(
        "ニックネーム",
        value=st.session_state.nickname,
        max_chars=18,
        help=". # $ / [ ] は使用できません。",
    )
    st.session_state.nickname = nickname_input.strip()
    st.caption("同じ名前がいる場合は、少し変えてね。")
    st.divider()
    st.markdown("### 📘 ルール")
    st.write("1. それぞれに秘密の数字が配られます。")
    st.write("2. 数字そのものは言わず、数字の大きさを言葉で表現します。")
    st.write("3. ヒントとチャットを使って、小さい順を相談します。")
    st.write("4. ゲームマスターが順番を確定して答え合わせします。")

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
        room_mode_label = st.radio(
            "遊び方",
            options=["自分も参加する", "友達だけで遊ぶ"],
            index=0,
            help="「友達だけで遊ぶ」では、作成者はプレイヤーに含まれず、参加した友達がゲーム開始・答え合わせを行えます。",
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

            room_mode = "friends_only" if room_mode_label == "友達だけで遊ぶ" else "host_plays"
            room = create_room_data(nickname, minutes, low, high, room_mode)
            # 友達だけで遊ぶ場合、作成者はプレイヤー一覧に追加しない。
            if room_mode != "friends_only":
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
room_mode = room.get("mode", "host_plays")
# 通常モードは作成者が進行役。友達だけモードは参加プレイヤー全員が進行操作できる。
can_manage_game = is_host if room_mode != "friends_only" else nickname in players

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
    if room_mode == "friends_only" and is_host and nickname not in players:
        st.info("友達だけで遊ぶモードです。あなたが退出しても、参加プレイヤーがゲームを開始・進行できます。")

    if can_manage_game:
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
        if seconds_left == 0 and can_manage_game:
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
    st.caption("参加者の中から進行できる人が回答を確定します。名前を小さい数字から順番に選んでください。")
    suggested_order = st.multiselect("小さい数字 → 大きい数字", list(players.keys()))
    if can_manage_game and st.button("🔒 この順番で答え合わせ", type="primary", use_container_width=True):
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
        if can_manage_game and st.button("答え合わせを終了する"):
            try:
                room["result"] = {"order": [], "reason": "time_up", "submitted_at": timestamp()}
                db_write(room_path(room_code), room)
                st.rerun()
            except Exception as exc:
                show_write_error("答え合わせ", exc)

    if can_manage_game and st.button("🔄 同じルームでもう一度遊ぶ"):
        try:
            fresh_room = create_room_data(
                room.get("host", nickname),
                room["settings"]["minutes"],
                room["settings"]["low"],
                room["settings"]["high"],
                room.get("mode", "host_plays"),
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
