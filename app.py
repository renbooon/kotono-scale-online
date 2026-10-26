import streamlit as st
import requests, random, string, time, json, os
from datetime import datetime, timezone

st.set_page_config(page_title="コトノスケール ONLINE", page_icon="🎚️", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700;900&display=swap');
html, body, [class*="css"] {font-family:'Noto Sans JP',sans-serif;}
.stApp {background:linear-gradient(140deg,#10162a 0%,#182443 55%,#241b3d 100%); color:#f4f6ff;}
h1,h2,h3,p,label {color:#f4f6ff;}
div[data-testid="stMetric"] {background:#222e4d;padding:14px;border-radius:14px;border:1px solid #39496f;}
div.stButton > button {border-radius:12px;font-weight:700;min-height:2.8rem;}
.small-muted {color:#b8c3df;font-size:.9rem;}
.card {background:#202b49;border:1px solid #3a496c;border-radius:16px;padding:16px;margin:8px 0;}
.chatline {background:#202b49;border-radius:12px;padding:9px 12px;margin:6px 0;}
</style>
""", unsafe_allow_html=True)

st.title("🎚️ コトノスケール ONLINE")
st.caption("言葉の感覚を頼りに、みんなの数字を小さい順に並べよう。")

def cfg(key, default=""):
    try:
        return st.secrets.get(key, default)
    except Exception:
        return os.environ.get(key, default)

DB_URL = cfg("FIREBASE_DATABASE_URL", "").rstrip("/")
DB_TOKEN = cfg("FIREBASE_AUTH_TOKEN", "")

def db_url(path):
    u = f"{DB_URL}/{path.strip('/')}.json"
    if DB_TOKEN:
        u += f"?auth={DB_TOKEN}"
    return u

def db_get(path):
    if not DB_URL:
        return None
    try:
        r = requests.get(db_url(path), timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None

def db_put(path, value):
    if not DB_URL:
        return False
    try:
        r = requests.put(db_url(path), json=value, timeout=5)
        r.raise_for_status()
        return True
    except Exception:
        return False

def db_patch(path, value):
    if not DB_URL:
        return False
    try:
        r = requests.patch(db_url(path), json=value, timeout=5)
        r.raise_for_status()
        return True
    except Exception:
        return False

def room_path(code):
    return "kotono_rooms/" + code

def make_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))

def now():
    return datetime.now(timezone.utc).isoformat()

def new_room(host, minutes, low, high):
    return {
        "host": host, "phase": "lobby", "created": now(),
        "settings": {"minutes": int(minutes), "low": int(low), "high": int(high)},
        "deadline": None, "players": {}, "chat": [], "result": None
    }

def get_room(code):
    return db_get(room_path(code))

def save_room(code, room):
    return db_put(room_path(code), room)

def remaining(room):
    if not room.get("deadline"):
        return None
    try:
        end = datetime.fromisoformat(room["deadline"])
        return max(0, int((end - datetime.now(timezone.utc)).total_seconds()))
    except Exception:
        return None

def fmt_time(seconds):
    return f"{seconds//60:02d}:{seconds%60:02d}"

if not DB_URL:
    st.warning("まず Firebase Realtime Database を設定してください。下の「公開手順」に沿って設定すると、複数人で同じルームを共有できます。")
    st.info("このアプリは画面だけでなく、ルーム・チャット・回答を共有データベースに保存する構成です。")
    with st.expander("公開手順（初回設定）", expanded=True):
        st.markdown("""
1. [Firebase Console](https://console.firebase.google.com/) でプロジェクトを作成します。
2. **Build → Realtime Database** からデータベースを作成し、URL（`https://....firebasedatabase.app` など）を控えます。
3. データベースのルールを設定します。公開読み書きルールは誰でも操作できて危険なので、**本番利用では認証とルールを設定してください**。このサンプルは認証設定をしていないデータベースでは動きません。
4. このフォルダを GitHub にアップロードし、[Streamlit Community Cloud](https://share.streamlit.io/) でデプロイします。
5. Streamlit の **App settings → Secrets** に以下を登録します。
""")
        st.code('FIREBASE_DATABASE_URL = "https://YOUR-DATABASE-URL"\nFIREBASE_AUTH_TOKEN = "YOUR_VALID_FIREBASE_ID_TOKEN"', language="toml")
        st.caption("IDトークンは期限切れになるため、継続運用には認証方式の追加が必要です。秘密情報をコードやGitHubに書かないでください。")
    st.stop()

if "name" not in st.session_state:
    st.session_state.name = ""
if "code" not in st.session_state:
    st.session_state.code = ""
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = 0

with st.sidebar:
    st.header("👤 プレイヤー")
    name = st.text_input("ニックネーム", value=st.session_state.name, max_chars=18)
    st.session_state.name = name.strip()
    st.caption("同じ名前がいる場合は、少し変えてね。")
    st.divider()
    st.markdown("### 📘 ルール")
    st.write("1. それぞれに秘密の数字が配られます。")
    st.write("2. 数字そのものは言わず、数字の大きさを言葉で表現します。")
    st.write("3. チャットで相談して、小さい順に並べます。")
    st.write("4. ゲームマスターが順番を確定し、答え合わせ！")
    st.caption("例：数字が小さいほど「控えめ」、大きいほど「めちゃくちゃ」など。")

if not st.session_state.name:
    st.info("まず左側でニックネームを入力してください。")
    st.stop()

st.subheader("🏠 ルーム")
c1, c2 = st.columns(2)
with c1:
    st.markdown("#### ルームを作成")
    with st.form("create_form"):
        mins = st.select_slider("制限時間（分）", options=[1,2,3,4,5,7,10,15], value=5)
        low, high = st.selectbox(
    "数字の範囲",
    options=[(1, 10), (1, 50), (1, 100), (1, 1000)],
    index=2,
    format_func=lambda x: f"{x[0]}〜{x[1]}"
    )
        create = st.form_submit_button("✨ 新しいルームを作る", use_container_width=True)
    if create:
        code = make_code()
        room = new_room(st.session_state.name, mins, low, high)
        room["players"][st.session_state.name] = {"number": random.randint(low, high), "hint": "", "order": None, "joined": now()}
        if save_room(code, room):
            st.session_state.code = code
            st.rerun()
        else:
            st.error("ルームを作成できませんでした。FirebaseのURL・認証・ルールを確認してください。")
with c2:
    st.markdown("#### ルームに参加")
    with st.form("join_form"):
        join_code = st.text_input("参加コード（5文字）", max_chars=5).strip().upper()
        join = st.form_submit_button("🚪 参加する", use_container_width=True)
    if join:
        room = get_room(join_code)
        if not room:
            st.error("ルームが見つかりません。コードを確認してください。")
        elif room.get("phase") != "lobby":
            st.error("このルームはすでにゲームが始まっています。")
        elif st.session_state.name in room.get("players", {}):
            st.session_state.code = join_code
            st.rerun()
        else:
            lo, hi = room["settings"]["low"], room["settings"]["high"]
            room["players"][st.session_state.name] = {"number": random.randint(lo, hi), "hint": "", "order": None, "joined": now()}
            if save_room(join_code, room):
                st.session_state.code = join_code
                st.rerun()
            else:
                st.error("参加できませんでした。データベースの設定を確認してください。")

code = st.session_state.code
if not code:
    st.stop()
room = get_room(code)
if not room:
    st.error("現在のルームを読み込めません。接続設定か参加コードを確認してください。")
    if st.button("ルーム選択に戻る"):
        st.session_state.code = ""
        st.rerun()
    st.stop()

# Refreshing makes the app usable without installing anything client-side.
st.caption("ルームの更新は画面下の更新ボタンから行えます。")
head1, head2, head3 = st.columns([2,1,1])
head1.markdown(f"### ルームコード：`{code}`")
head2.metric("参加人数", len(room.get("players", {})))
head3.metric("状態", {"lobby":"準備中","playing":"プレイ中","finished":"終了"}.get(room.get("phase"),"不明"))
if head1.button("📋 コードを再表示"):
    st.toast(f"参加コード：{code}")

players = room.get("players", {})
is_host = room.get("host") == st.session_state.name

if room.get("phase") == "lobby":
    st.markdown("### 👥 参加プレイヤー")
    st.write("、".join(players.keys()) if players else "まだ参加者はいません")
    if is_host:
        st.markdown("#### ゲーム設定")
        st.write(f"数字の範囲：{room['settings']['low']}〜{room['settings']['high']} ／ 制限時間：{room['settings']['minutes']}分")
        if st.button("▶ ゲーム開始", type="primary", use_container_width=True, disabled=len(players)<2):
            room["phase"] = "playing"
            room["deadline"] = datetime.now(timezone.utc).timestamp()
            from datetime import timedelta
            room["deadline"] = (datetime.now(timezone.utc) + timedelta(minutes=room["settings"]["minutes"])).isoformat()
            room["started"] = now()
            save_room(code, room)
            st.rerun()
        if len(players)<2:
            st.caption("ゲーム開始には2人以上が必要です。")
    else:
        st.info("ゲームマスターが開始するまで待ってね。")

if room.get("phase") == "playing":
    sec = remaining(room)
    st.markdown("### ⏳ 残り時間")
    if sec is not None:
        st.markdown(f"<div style='font-size:2.5rem;font-weight:900;color:{'#ff6b6b' if sec<30 else '#f5d76e'}'>{fmt_time(sec)}</div>", unsafe_allow_html=True)
        if sec == 0 and is_host:
            room["phase"] = "finished"
            room["result"] = {"reason":"time_up"}
            save_room(code, room)
            st.rerun()
    me = players.get(st.session_state.name)
    if me:
        st.markdown("### 🔐 あなたの秘密の数字")
        st.markdown(f"<div style='font-size:3rem;font-weight:900;background:#28385f;border-radius:18px;padding:18px;text-align:center'>{me['number']}</div>", unsafe_allow_html=True)
        st.caption("この数字は自分だけの秘密！チャットに数字をそのまま書かないようにしよう。")
        with st.form("hint_form"):
            hint = st.text_input("ヒント（数字を直接書かずに表現）", value=me.get("hint",""), max_chars=80,
                                 placeholder="例：かなり控えめ／少し大胆／想像以上に大きい")
            hint_submit = st.form_submit_button("ヒントを公開")
        if hint_submit:
            room = get_room(code)
            if room and st.session_state.name in room.get("players",{}):
                room["players"][st.session_state.name]["hint"] = hint.strip()
                save_room(code, room)
                st.rerun()
    st.markdown("### 💬 みんなのヒント")
    room = get_room(code) or room
    players = room.get("players",{})
    for pname, p in players.items():
        st.markdown(f"<div class='card'><b>{pname}</b><br>{p.get('hint') or '<span class=\"small-muted\">ヒント入力待ち…</span>'}</div>", unsafe_allow_html=True)

    st.markdown("### 🧩 並び順を提案")
    st.caption("ゲームマスターが回答を確定します。各プレイヤーの名前を小さい順に選んでください。")
    order_names = list(players.keys())
    chosen = st.multiselect("小さい数字 → 大きい数字", order_names, default=[n for n,p in sorted(players.items(), key=lambda x: (x[1].get("order") is None, x[1].get("order") or 0)) if p.get("order") is not None])
    if is_host and st.button("🔒 この順番で答え合わせ", type="primary", use_container_width=True):
        if len(chosen) != len(players):
            st.error("全員を1回ずつ選んでください。")
        else:
            room = get_room(code)
            room["phase"] = "finished"
            room["result"] = {"order": chosen, "reason":"submitted", "submitted_at":now()}
            save_room(code, room)
            st.rerun()

if room.get("phase") == "finished":
    st.markdown("## 🎉 答え合わせ")
    room = get_room(code) or room
    players = room.get("players",{})
    result = room.get("result") or {}
    ordered = result.get("order", [])
    if ordered:
        for i, pname in enumerate(ordered, 1):
            p = players.get(pname,{})
            st.markdown(f"<div class='card'><b>{i}位：{pname}</b>　—　数字：<b>{p.get('number','?')}</b><br>ヒント：{p.get('hint') or '（なし）'}</div>", unsafe_allow_html=True)
        actual = sorted(players.items(), key=lambda kv: kv[1].get("number",0))
        actual_order = [n for n,p in actual]
        st.markdown("### 📊 結果")
        if ordered == actual_order:
            st.success("全員正解！完璧なスケール感！")
        else:
            correct_positions = sum(1 for a,b in zip(ordered,actual_order) if a==b)
            st.info(f"正しい順番：{' → '.join(actual_order)} ／ 完全一致ではありません（位置一致 {correct_positions}/{len(actual_order)}人）")
    else:
        st.warning("制限時間終了。ゲームマスターが答え合わせを確定していません。")
        if is_host and st.button("答え合わせ画面へ"):
            room["phase"]="finished"; room["result"]={"order":[],"reason":"time_up"}; save_room(code,room); st.rerun()
    if is_host and st.button("🔄 同じルームでもう一度遊ぶ"):
        fresh = new_room(st.session_state.name, room["settings"]["minutes"], room["settings"]["low"], room["settings"]["high"])
        for pname in players:
            fresh["players"][pname] = {"number":random.randint(fresh["settings"]["low"],fresh["settings"]["high"]),"hint":"","order":None,"joined":now()}
        save_room(code,fresh)
        st.rerun()

st.divider()
st.markdown("### 💬 ルームチャット")
chat = room.get("chat", [])
for msg in chat[-60:]:
    st.markdown(f"<div class='chatline'><b>{msg.get('name','?')}</b> <span class='small-muted'>· {msg.get('time','')}</span><br>{msg.get('text','')}</div>", unsafe_allow_html=True)
with st.form("chat_form", clear_on_submit=True):
    message = st.text_input("メッセージ", max_chars=240, placeholder="相談しよう！（秘密の数字そのものは書かないでね）")
    send = st.form_submit_button("送信", use_container_width=True)
if send and message.strip():
    room = get_room(code)
    if room:
        room.setdefault("chat",[]).append({"name":st.session_state.name,"text":message.strip(),"time":datetime.now().strftime("%H:%M")})
        room["chat"] = room["chat"][-100:]
        if save_room(code,room):
            st.rerun()
        else:
            st.error("メッセージを送れませんでした。")
if st.button("🔄 画面を更新", use_container_width=True):
    st.rerun()
if st.button("🚪 このルームから退出"):
    st.session_state.code = ""
    st.rerun()

st.caption("試作版：同時操作が重なると更新が競合することがあります。チャット・ゲーム状態は設定したFirebaseに保存されます。")
