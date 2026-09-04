# mini-hsk-5

HSK 2.0 五級の模擬試験。Grok 4.6 が問題を生成し、作文だけ Grok が採点する。

仕様の正は `ARCH.md`。実装の決めは `Plan.md`（どちらも gitignore、ワークスペースローカル）。

## 制約

- Python 3.13、`uv`、`black --line-length 120`、`ty`。型ヒント必須
- モデルは `grok-4.6`。キーは `XAI_API_KEY`。サーバ起動時に無ければ即終了
- キーはサーバのみ。テンプレ / JS に出さない
- フロントは vanilla HTML/JS/CSS。npm / CDN / React / Vue / jQuery 禁止。JS は IIFE
- 語彙は `data/vocab/hsk5-old-inclusive.json`（HSK 2.0 inclusive old-5）
- 作文の採点に使ってよい: 字数、文法、意味が通るか、指定語の使用、画像との関連
- 使ってはいけない: 現実世界と矛盾しないか、嘘か、荒唐無稽か
- Listening / Reading / 連詞成句は生成時に正答を持つ。公開 JSON に正答・原稿・音声テキストを出さない（提出後だけ）
- 作文（第99・100題相当）だけ正答なし、Grok 採点
- デプロイ path は `/mini-hsk5/`。`ROOT_PATH` と `HSK5_DATA_DIR`（既定 `data/`、コンテナは `/data`）

## コマンド

```bash
uv sync
uv run uvicorn main:app --reload
uv run pytest -q
uv run black --line-length 120 .
uv run ty check
```

## 構成

```
main.py                 from hsk5.app import app
hsk5/                   FastAPI、生成、採点、store
templates/              index.html app.js app.css
data/vocab/             コミットする語彙
tests/                  HTTP は StubXAI。ライブ xAI 禁止
```

## やってはいけないこと

- `XAI_API_KEY` 無しでサーバを生かす
- 未提出の試験 JSON に `answer` / transcript / gold を載せる
- 作文採点で「内容が事実か」を減点する
- HSK 3.0（9級制）の形式に寄せる
- フロントに npm / CDN
- ライブ xAI をデフォルトテストから叩く（HTTP はスタブ）
