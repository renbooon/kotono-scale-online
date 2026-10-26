# コトノスケール ONLINE

Python + Streamlit で動く、ブラウザから遊ぶためのオンライン版の土台です。

## 機能
- ルーム作成 / 5文字の参加コード
- ニックネームと秘密の数字
- ヒント投稿
- ルーム内テキストチャット
- 制限時間（1〜15分）
- ゲームマスターによる順番確定と答え合わせ
- 同じルームで再プレイ

## ローカル起動
1. Python 3.10 以上を用意
2. `pip install -r requirements.txt`
3. Firebase Realtime Database を設定（下記）
4. `streamlit run app.py`

## オンライン公開
1. Firebase Console でプロジェクトを作成。
2. Build → Realtime Database でDBを作成。
3. DB URLを控える。
4. GitHub に `app.py`, `requirements.txt`, `README.md` をアップロード。
5. Streamlit Community Cloud で GitHub リポジトリを選択し、`app.py` を指定してデプロイ。
6. App settings → Secrets に設定を追加。

```toml
FIREBASE_DATABASE_URL = "https://YOUR-DATABASE-URL"
FIREBASE_AUTH_TOKEN = "YOUR_VALID_FIREBASE_ID_TOKEN"
```

`FIREBASE_AUTH_TOKEN` は Firebase REST API に使う有効な ID token です。通常は期限切れになるため、これは試作・動作確認向けです。継続利用する場合は Firebase Authentication と適切な Realtime Database Security Rules を組み合わせ、トークンを安全に更新する仕組みを追加してください。

## セキュリティ上の注意
- **本番利用で `.read` / `.write` を全員に許可しないでください。** 誰でもルームやチャットを読んだり書き換えたりできてしまいます。
- Firebase のサービスアカウント秘密鍵や管理者資格情報を、GitHub やアプリコードに置かないでください。
- このサンプルは教育・友人間での試作向けです。DBルールや認証の設定なしに、一般公開しないでください。
- ルーム内の秘密の数字は、UIでは各プレイヤー本人にだけ表示する想定ですが、現状の単一JSON構造はデータベースの読み取り権限があるユーザーには見えます。厳密な秘匿性が必要なら、サーバー側で権限チェックする設計に変更してください。
