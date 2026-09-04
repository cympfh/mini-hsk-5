# mini-hsk-5

HSK 2.0 五級の模擬試験。Grok 4.6 が問題を作り、听力・阅读・連詞成句は自動採点、短文だけ Grok が採点する。

## 必要

- Python 3.13
- `XAI_API_KEY`（無いとサーバは起動しない）

## 起動

```
uv sync
export XAI_API_KEY=...
uv run uvicorn main:app --reload
```

http://127.0.0.1:8000/

規模 1–100%（100 が本番 100 題）。10% 前後が短いセット。

## 試験

- 听力 45 / 阅读 45 / 书写 10（100% 時）。配点は各 100、合計 300
- 目安 180/300。合否は出さない
- 生成済みの試験は再利用できる。最高点はその試験 ID ごと

## 開発

```
uv run pytest -q
uv run black --line-length 120 .
uv run ty check
```

デフォルトのテストは xAI に繋がない（HTTP をスタブする）。
