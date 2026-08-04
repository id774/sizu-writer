# しずかなインターネット向け文章生成システム 基本設計

対象要件: [`REQUIREMENTS.md`](REQUIREMENTS.md)（2026-08-04 版）

本書は要件定義書を実装可能な単位まで落とした基本設計である。詳細設計（各関数の実装、CSS の細部、プロンプト本文の確定）は本書の決定に従って行う。本システムは新規リポジトリで開発し、設計思想・コーディング規約・文書構成は [id774/ai-digest](https://github.com/id774/ai-digest) を踏襲する。

---

## 1. リポジトリ名の案

| 案 | 読み・意図 | 備考 |
| --- | --- | --- |
| **`sizu-writer`**（推奨） | 「しずかなインターネット」向けの文章を書く道具 | 要件定義書のファイル名と一致し、以後の呼称がぶれない。`ai-digest` と同じ小文字ハイフン形式 |
| `sizu-draft` | 生成物は投稿ではなく下書きであることを名前で示す | 「自動投稿しない」という本システムの一線が名前に出る。推奨案に次ぐ |
| `quiet-writer` | しずかなインターネット＝quiet internet の英語化 | 媒体名に依存しないため、将来ほかの媒体へ広げても名前が古びない。反面、何向けかが名前から消える |
| `sizuka-compose` | 媒体名を明示しつつ「組み立てる」を強調 | やや長い |
| `shizuka-writer` | ヘボン式表記 | `sizu-writer` と重複するので、表記の好みで択一 |

推奨は **`sizu-writer`**。理由は次の三点。

- 要件定義書（`20260804_sizu_writer_requirements.md`）の呼称をそのまま引き継げる。
- Python パッケージ名 `sizu_writer`、systemd ユニット名 `sizu-writer.service`、Apache の location `/sizu/` が機械的に決まる。
- `ai-digest` と同じ「用途 + 動作」の二語構成で、id774 のリポジトリ群の中で浮かない。

以降、本書ではリポジトリ名 `sizu-writer`、Python パッケージ名 `sizu_writer` を前提に記述する。名称を変える場合は、この二つと `deploy/` 配下のファイル名を置換すればよい。

---

## 2. 設計方針

### 2.1 本システムが引く線

要件 2、13、14 から、設計上の不変条件を先に固定する。以下は設定でも拡張でも越えない。

1. 投稿先へのネットワーク送信を行わない。HTTP クライアントの向き先は OpenAI 互換エンドポイントだけである。
2. 投稿先の認証情報を受け取らない。設定項目にもフォーム項目にも存在させない。
3. ブラウザ自動操作の依存を持ち込まない。`playwright`、`selenium` を `requirements.txt` に入れない。
4. API キーはサーバープロセスの外に出さない。テンプレート、JavaScript、レスポンスヘッダ、エラー画面のいずれにも現れない。
5. 生成した本文に、AI への指示、編集理由、内部メモ、レビュー結果を混入させない。画面上でも本文領域と補助情報領域を構造的に分離する。

### 2.2 ai-digest から継承する規約

新規リポジトリでも `doc/POLICY` を置き、次を ai-digest から引き継ぐ。相違点だけ後述する。

- モジュール先頭の定型ヘッダ（Description / Usage / Options / Routes / Requirements / Version History と Author・Source Code・License・Contact）。
- コメントは英語、命令形、簡潔に。
- 設定は `config.py` の `Config` データクラスに集約し、環境変数（任意で `.env`）から読む。`config.py` はネットワークにも `.env` 以外のファイルにも触れない。
- `logging` を使い、`print` で状態を出さない。ログ設定はエントリポイントで一度だけ行う。
- テストは `tests/test_*.py`、`unittest` と `unittest.mock` のみ、ネットワーク・API 呼び出しなし。
- モジュール版数は `major.minor` の二桁、`minor` が 10 に達する前に繰り上げ。リポジトリ版数は `doc/VERSIONS` に記録。
- Python 3.9 以降、`str.format()` を `f-string` より優先、型ヒントを付ける。
- ライセンスは GPLv3 / LGPLv3 のデュアル。

ai-digest との相違点は次の一点である。ai-digest はバッチ（`cli.py`）と読み取り専用ビューア（`app.py`）を独立させ、バッチの失敗がサイトを落とさない構造を取っている。本システムは Web リクエストの中で API を呼ぶため、この分離は成立しない。代わりに **生成コア（`sizu_writer/`）を Flask から独立させ、`app.py` と `cli.py` の双方から同じコアを呼ぶ** 構造とする。プロンプト調整も出力検証も、Web を立てずに `cli.py` で試せる。

### 2.3 状態を持たない

要件 11 で永続保存は必須ではない。ここを積極的に利用し、**サーバー側にセッションも一時ファイルも持たない**設計とする。

- 再生成に必要な入力文とその時点の本文は、結果画面のフォームに `textarea` と `hidden` として載せ、リクエストごとに往復させる。
- したがって Flask の `SECRET_KEY`、セッション Cookie、ワーカー間共有ストアがいずれも不要になる。gunicorn のワーカーを増やしても、プロセスが再起動しても、動作は変わらない。
- 将来の保存機能（要件 11）は、この往復に手を入れず `storage.py` を足すだけで載る（10.3 節）。

---

## 3. システム構成

```
[ブラウザ]
    |  HTTPS
    v
[Apache HTTP Server]
    |  - HTTPS 終端、Basic 認証 / IP 制限（運用側の判断）
    |  - ProxyPass /  ->  127.0.0.1:8090
    |  - アクセスログ、エラーログは Apache 側に閉じる
    v
[gunicorn]  systemd 管理、Restart=always、boot 時 enable
    |  WSGI
    v
[Flask app.py]  ---- sizu_writer/ (生成コア) ----> [OpenAI 互換 API]
                          ^
                          |
                     prompts/*.md
                          ^
                          |
                     [cli.py]  ← 保守・プロンプト調整用
```

- Apache と Flask の連携方式は **リバースプロキシ + gunicorn** を採用する。要件 5.1 は WSGI（`mod_wsgi`）も許容しているが、`mod_wsgi` は Apache 本体と Python の版数が結合し、Apache の再起動なしにアプリだけ入れ替えることができない。リバースプロキシならアプリの再起動は `systemctl restart sizu-writer` で完結し、ai-digest と同じ運用手順に揃う。
- gunicorn は `127.0.0.1` だけを listen する。外部から直接叩けない。
- Flask 開発サーバーは開発時のみ。`app.py` の `__main__` ブロックも `127.0.0.1` 固定とする。

### 3.1 プロセスとタイムアウトの整合

生成 1 回で数十秒かかりうるため、各層のタイムアウトを内側から外側へ広げる。

| 層 | 設定 | 既定値 | 根拠 |
| --- | --- | --- | --- |
| OpenAI クライアント | `OPENAI_TIMEOUT` | 60 秒 | 生成 1 回の上限。超えたら利用者にタイムアウトを返す |
| gunicorn | `--timeout` | 120 秒 | クライアント側タイムアウト + リトライ 1 回分の余裕 |
| Apache | `ProxyTimeout` | 180 秒 | 最も外側。ここで切れると Flask のエラー処理を通らず、素の 504 が出る |

`OPENAI_MAX_RETRIES` を上げる場合、gunicorn と Apache の値も見直す必要がある。この依存関係は README のデプロイ節に明記する。

---

## 4. リポジトリ構成

```
.
├── app.py                          Flask アプリケーション（Web エントリポイント）
├── cli.py                          コマンドラインからの生成（保守・プロンプト調整用）
├── config.py                       環境変数駆動の設定
├── requirements.txt
├── Procfile                        gunicorn の起動定義
├── .python-version
├── .env.example
├── .gitignore
├── sizu_writer/
│   ├── __init__.py                 Draft データクラス、__version__、共通ユーティリティ
│   ├── errors.py                   例外階層と利用者向けメッセージの対応表
│   ├── prompts.py                  prompts/ の読み込みとメッセージ組み立て
│   ├── generator.py                OpenAI 互換 API 呼び出しと応答検証
│   ├── formatter.py                本文 Markdown の後処理と点検
│   └── web/
│       ├── __init__.py             TEMPLATE_DIR / STATIC_DIR の解決
│       ├── templates/
│       │   ├── base.html
│       │   ├── index.html          入力画面
│       │   ├── result.html         結果画面
│       │   └── error.html          エラー画面
│       └── static/
│           ├── style.css
│           └── copy.js             クリップボードコピーのみを担う
├── prompts/
│   ├── system.md                   本文とタイトルを生成する際の共通方針
│   ├── body_user.md                入力文を渡すユーザーメッセージの型
│   ├── titles_system.md            タイトルのみ再生成の方針
│   └── titles_user.md              本文を渡してタイトルを求める型
├── tests/                          unittest、標準ライブラリのみ
├── deploy/
│   ├── sizu-writer.service         systemd ユニットの例
│   └── sizu-writer.conf            Apache リバースプロキシ設定の例
└── doc/
    ├── REQUIREMENTS.md             要件定義書
    ├── BASIC_DESIGN.md             本書
    ├── POLICY                      実装方針（ai-digest 準拠）
    ├── VERSIONS                    リポジトリ版数の履歴
    ├── LICENSE
    ├── COPYING
    └── COPYING.LESSER
```

`prompts/` をパッケージの外に置くのは、要件 10.3 の「プロンプトをアプリケーションコードから分離する」を運用面まで貫くためである。プロンプトの修正は Python の再インストールを伴わず、`PROMPT_DIR` を向け替えれば別のプロンプト一式で動く。

---

## 5. モジュール設計

### 5.1 `sizu_writer/__init__.py`

生成結果を表すデータクラスと版数を持つ。

```python
@dataclass
class Draft:
    body: str                       # 投稿本文の全文（Markdown、後処理済み）
    primary_title: str              # タイトル第一候補
    alternative_titles: List[str]   # その他の候補、最大 MAX_ALT_TITLES 件
    model: str                      # 実際に応答したモデル名
    generated_at: str               # ISO 8601 の生成時刻（画面の補助表示のみ）
    notices: List[str]              # 後処理で検出した注意。本文には混ぜない
```

`notices` は「本文に `#` 見出しがあったので `##` に降格した」「定型的な締めの表現を検出した」といった点検結果を運ぶ。**画面では本文領域の外に表示し、コピー対象に含めない**（要件 6.3）。

### 5.2 `sizu_writer/errors.py`

要件 6.6 の各エラーを型として持つ。表示メッセージ、HTTP ステータス、ログレベルをここで一元管理する。

```python
class SizuWriterError(Exception):
    """ Base of every error the user is allowed to see. """
    user_message: str
    status_code: int
```

| 例外 | 発生条件 | 画面表示（日本語） | HTTP | ログ |
| --- | --- | --- | --- | --- |
| `EmptyInputError` | 入力が空、または空白のみ | 短文を入力してください。 | 400 | INFO |
| `InputTooLongError` | 入力が `MAX_INPUT_CHARS` 超過 | 入力が長すぎます。◯◯字以内にしてください。 | 400 | INFO |
| `UpstreamConnectionError` | 接続失敗、DNS 失敗、TLS 失敗 | 文章生成サービスへ接続できませんでした。時間をおいて再度お試しください。 | 502 | ERROR |
| `UpstreamTimeoutError` | `OPENAI_TIMEOUT` 超過 | 生成に時間がかかりすぎたため中断しました。入力を短くするか、時間をおいてお試しください。 | 504 | ERROR |
| `UpstreamStatusError` | 4xx / 5xx 応答、認証エラー、レート超過 | 文章生成サービスがエラーを返しました。時間をおいて再度お試しください。 | 502 | ERROR |
| `InvalidResponseError` | JSON 不正、必須項目欠落、本文が空、出力打ち切り | 生成結果を読み取れませんでした。もう一度生成してください。 | 502 | ERROR |
| `InternalError` | 上記以外の想定外例外 | サーバー内部で処理に失敗しました。 | 500 | ERROR |

設計上の要点は次の四つ。

- **画面に出るのは `user_message` だけ**である。例外の `str()`、スタックトレース、URL、モデル名、キーの断片は画面に出さない。原因はサーバーログにのみ残す。
- 各エラー応答には 8 桁の **参照 ID**（リクエスト単位の乱数）を添え、同じ ID をログにも出す。利用者は「エラー ID: 3f9c1a72」だけを伝えればよく、運用側はログを引ける。
- 認証エラー（401 / 403）とレート超過（429）を利用者向けに区別しない。設定の不備を画面に書けば、それは内部情報の露出になる。ログでは区別する。
- `UpstreamStatusError` はステータスコードを属性に持ち、ログにだけ出す。

### 5.3 `sizu_writer/prompts.py`

責務はプロンプトファイルの読み込みと、API へ渡すメッセージの組み立てのみ。API 呼び出しはしない。

```python
def load_prompt(name: str, prompt_dir: str) -> str
def build_body_messages(input_text: str, prompt_dir: str) -> List[Dict[str, str]]
def build_titles_messages(input_text: str, body: str, prompt_dir: str) -> List[Dict[str, str]]
```

- プレースホルダは `{{input}}` と `{{body}}` の二種類だけとし、`str.replace()` で置換する。`str.format()` を使わないのは、プロンプト本文に現れる `{` `}` を機械的にエスケープさせないためである（POLICY の `str.format()` 優先はコード内の文字列整形についての規約であり、外部テキストの差し込みはこの限りではない）。
- 読み込み結果はプロセス内にキャッシュする。`PROMPT_RELOAD=on` のときだけ毎回読み直し、プロンプト調整中に再起動を要らなくする。
- 必須ファイルが欠けている場合は起動時ではなく最初の生成時に `InternalError` として扱い、ログにファイル名を出す。Web プロセスがプロンプト不備で起動不能になるより、健全性エンドポイントが生きている方が運用しやすい。

#### プロンプトの骨子

`prompts/system.md` には、要件 3、7、8 を「モデルへの指示」として書き下ろす。節構成は次のとおりとし、要件定義書の記述をそのまま指示文にできるよう対応づける。

| 節 | 対応する要件 | 内容の要点 |
| --- | --- | --- |
| 役割と媒体 | 2、7.1 | しずかなインターネットに投稿する数段落の文章。短文投稿の引き延ばしでもブログ記事の縮小版でもない |
| 書かないもの | 3 | 一次原典、記事の下書き、素材集、体系的論考、調査記事、手順書、解説記事にしない。将来の記事を見越した論点・根拠・一般化を足さない |
| 立て付け | 7.2 | 既知のテーマを初めて知った体裁にしない。整理し直す、関心の所在を確かめる、論点を切り分ける、言えることと言えないことを示す |
| 材料の保存 | 7.3 | 具体的な場面、対象、元の言葉遣い、迷い、違和感、問い、未決着を優先して残す。存在しない体験・感情・事実・因果を補わない |
| 説明量 | 7.4 | 背景説明は本文の理解に要る範囲まで。一般論、制度説明、用語解説、歴史、事例列挙、参考文献、体系的論証へ広げない |
| 文体 | 7.5 | 元のメモの語り口を優先。既定はです・ます調、原文が常体で統一なら常体を維持。論文調・広告調・SNS 調にしない。生成 AI 特有の定型を避ける |
| 導入 | 7.6 | 具体的な場面・対象・言葉・感覚から始める。禁止する導入文を列挙 |
| 終わり方 | 7.7 | 教訓・提言・結論を作らない。未決着は未決着のまま。放棄した印象にはしない。禁止する締め文を列挙 |
| Markdown | 7.8 | 短文では見出しなし。要る場合も `##` `###` のみ、`#` は使わない。箇条書き・引用・強調は必要時のみ。参考文献一覧は付けない。全角と半角英数字の間に半角スペース |
| タイトル | 8 | 本文にある場面・対象・言葉・問い・引っかかり・考え始めた地点に近づける。検索性・拡散性・クリック率のための語を足さない。解決済みに見せない。象徴的・文学的・扇情的にしない |
| 出力形式 | 5.3 | 指定した JSON スキーマに従い、本文とタイトルを分離して返す。本文に指示・注釈・見出し以外のメタ情報を混ぜない |

長さについては「数段落から数千字程度を目安。字数を満たすために背景説明・一般論・例示・結論を足さない。短く成立する内容は短いままにする」と、上限ではなく**下限を作らない指示**として書く（要件 7.1）。

`prompts/titles_system.md` は上表のうち「タイトル」節と媒体の位置づけだけを抜き出したものとし、本文の生成方針は書かない。タイトルのみ再生成のとき、本文はすでに確定しているためである。

### 5.4 `sizu_writer/generator.py`

OpenAI 互換 API を呼び、応答を検証して `Draft` を返す。

```python
def generate_draft(input_text: str, config: Config) -> Draft
def regenerate_titles(input_text: str, body: str, config: Config) -> Draft
```

#### 5.4.1 API 呼び出し方式

`openai` パッケージの Chat Completions を使い、`response_format` に JSON Schema を指定する（Structured Outputs）。ai-digest が tool use で構造化応答を得ているのと同じ狙いで、散文をヒューリスティックに切り分ける処理を作らない。

`base_url` を設定可能にしているため、OpenAI 以外の互換エンドポイントでも動く。ただし互換エンドポイントは `json_schema` に対応していないことがあるので、ai-digest が Anthropic 互換エンドポイントの差異を設定で吸収しているのと同じ方針で、応答形式の指定を段階的に落とせるようにする。

| `OPENAI_RESPONSE_FORMAT_MODE` | 送る指定 | 用途 |
| --- | --- | --- |
| `json_schema`（既定） | `response_format={"type": "json_schema", "json_schema": {..., "strict": true}}` | OpenAI 本家、および Structured Outputs 対応エンドポイント |
| `json_object` | `response_format={"type": "json_object"}` | JSON は返せるがスキーマ強制に非対応なエンドポイント |
| `none` | 指定しない | 上記いずれも通らないエンドポイント。プロンプト内の形式指示だけが頼りになる |

いずれの場合も、応答の検証（5.4.3）は同一の関数を通る。`json_schema` 以外を選んだときにだけ検証が甘くなる、ということは起こさない。

`temperature` は既定では**送らない**。値を送らなければエンドポイントの既定に従い、`temperature` を受け付けないモデルでもリクエストが通る。`OPENAI_TEMPERATURE` に値が設定されたときだけ送る。これは ai-digest の `ANTHROPIC_THINKING_MODE=default`（パラメータを送らず provider の既定を残す）と同じ考え方である。

#### 5.4.2 JSON スキーマ

本文生成:

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["body_markdown", "primary_title", "alternative_titles"],
  "properties": {
    "body_markdown":      { "type": "string" },
    "primary_title":      { "type": "string" },
    "alternative_titles": { "type": "array", "items": { "type": "string" } }
  }
}
```

タイトルのみ再生成では `body_markdown` を除いた同型のスキーマを使う。

`strict: true` の Structured Outputs では `maxItems` などの制約が効かないため、**その他の候補の件数（要件 8: 最大 4 件）はアプリケーション側で切り詰める**。4 件を超えたら先頭 4 件を採り、超過を `notices` に残さずログの DEBUG に留める（利用者にとっては無関係な内部事情である）。

#### 5.4.3 応答の検証

次の順に確かめ、いずれかで落ちたら `InvalidResponseError` を送出する。理由はログにだけ書き分ける。

1. 選択肢が 1 件以上あること。
2. `finish_reason` が `length` でないこと。打ち切られた本文を投稿候補として画面に出さない。ログには「出力上限に達した。`MAX_OUTPUT_TOKENS` を上げるか入力を短くする」と書く。
3. 本文が JSON として解釈でき、オブジェクトであること。
4. `body_markdown` が空でない文字列であること（タイトルのみ再生成では検証対象外）。
5. `primary_title` が空でない文字列であること。
6. `alternative_titles` が文字列のリストであること。空リストは許容する（要件 8 は最大件数のみを定める）。

`alternative_titles` の各要素は、空文字と `primary_title` との重複を取り除いたうえで先頭 `MAX_ALT_TITLES` 件を採る。

#### 5.4.4 リトライ

`openai` クライアントの `max_retries`（既定 2）に委ね、独自のリトライループを書かない。ai-digest 同様、`OPENAI_MAX_RETRIES=0` にすれば 1 リクエストで確実に終わるため、エンドポイントの挙動比較ができる。

### 5.5 `sizu_writer/formatter.py`

モデル出力を投稿可能な形へ整える。**書き換えは機械的に判定できるものに限り、文意に触れる修正はしない**。

```python
def normalize_body(text: str, ascii_spacing: bool) -> Tuple[str, List[str]]
```

適用する処理は次の四つ。

1. **外側のコードフェンス除去**: 応答全体が ` ```markdown ... ``` ` で包まれている場合に限り剥がす。本文中のコードブロックには触れない。
2. **`#` 見出しの降格**: 行頭 `# ` を `## ` にする（要件 7.8）。降格したら `notices` に「本文の見出し階層を調整しました」を積む。コードフェンス内の `#` は対象外。
3. **前後の空白と連続空行の整理**: 3 行以上の連続空行を 2 行に畳む。段落の意図は保つ。
4. **全角と半角英数字の間への半角スペース挿入**（要件 7.8、`BODY_ASCII_SPACING=on` が既定）。次を除外範囲とする。
   - フェンス付きコードブロックとインラインコード（`` ` `` で囲まれた範囲）
   - Markdown リンクの URL 部分（`](...)`）と自動リンク（`<...>`）
   - 半角の直後が句読点・閉じ括弧のとき、および全角の直前が開き括弧のとき（`（GPT）` を `（ GPT ）` にしない）

さらに、書き換えを伴わない**点検**を行い、該当すれば `notices` に積む。

- 禁止した定型表現（「いかがだったでしょうか」「ぜひ考えてみてください」「今回は」「この記事では」「近年」「皆さんは」など）を含む。
- 「以下の点に注意して」「ご指示のとおり」のような、AI への指示や作業説明が混じった疑いのある表現を含む。

点検は**検出のみで、本文を書き換えない**。誤検出で文章を壊すより、人間の確認に回すほうが要件 4（人間が最終確認して投稿する）に沿う。

### 5.6 `app.py`

Flask アプリケーション本体。ルートは四つ。

| メソッド | パス | 役割 |
| --- | --- | --- |
| GET | `/` | 入力画面 |
| POST | `/generate` | 生成し、結果画面を返す。`mode` で全文生成とタイトルのみ再生成を切り替える |
| GET | `/healthz` | プロセス生存確認。API は呼ばない |
| GET | `/static/<file>` | CSS と JS |

- 生成と再生成を 1 エンドポイントにまとめるのは、フォームの送信先が常に一つで済み、画面遷移の分岐がテンプレート側に閉じるためである。`mode` は送信ボタンの `name`/`value` で決まる（`mode=full` / `mode=titles`）。
- POST の応答として結果画面を直接描画する（PRG しない）。サーバーが状態を持たないため、リダイレクト先へ結果を引き継ぐ手段がないからである。結果画面でのリロードは再送信確認が出るが、再送信は「同じ入力からの再生成」であり、破壊的操作ではない。
- `SizuWriterError` は `errorhandler` で一括して受け、`error.html`（または結果画面上部のエラー領域）に `user_message` と参照 ID を描く。想定外の例外は `InternalError` に丸めてから同じ経路を通す。`DEBUG` は本番で必ずオフ、`app.config["PROPAGATE_EXCEPTIONS"]` も既定のままとし、スタックトレースを画面に出さない。
- `MAX_CONTENT_LENGTH` を設定し、巨大な POST をアプリケーションに到達させない。
- 同一オリジンからの POST だけを受ける任意の検査（`REQUIRE_SAME_ORIGIN`、既定 `on`）を入れる。`Origin` ヘッダが自サイト以外なら 400。Apache 側で `ProxyPreserveHost On` が要る点を `deploy/sizu-writer.conf` と README に明記する。

### 5.7 `cli.py`

Web を経由せず同じ生成コアを叩く。プロンプトの調整、互換エンドポイントの検証、受け入れ確認に使う。POLICY に従い `main() -> int` と `sys.exit(main())`、`-h` と `-v` を備える。

```sh
python cli.py generate --input memo.txt          # ファイルから読み、結果を標準出力へ
python cli.py generate --text "短い思いつき"     # 直接渡す
python cli.py generate --input memo.txt --json   # Draft を JSON で出す（テストやパイプ用）
python cli.py titles --input memo.txt --body draft.md   # タイトルのみ再生成
```

ai-digest の `cli.py` と同じく、主要な設定は同名のコマンドラインオプションでも上書きできるようにする（`--model`、`--timeout`、`--max-output-tokens`、`--prompt-dir` など）。**認証情報にはオプションを設けない**。コマンドラインは他者から読める。

終了コードは `0` 成功、`1` 一般失敗（POLICY の規約どおり）。

---

## 6. 設定設計

`config.py` に `Config` データクラスと `load_config()` を置く。値の妥当性検査は `validate_*()` として分け、誤った値は既定へ落とさず起動時または生成前に失敗させる（ai-digest が `SUMMARIZER_BACKEND` の綴り誤りを拒否しているのと同じ方針）。

| 環境変数 | 既定 | 説明 |
| --- | --- | --- |
| `OPENAI_API_KEY` | （なし・必須） | API キー。未設定なら生成時に `InternalError`。ログに「キーが未設定」と出し、画面には出さない |
| `OPENAI_BASE_URL` | （空＝OpenAI） | 互換エンドポイントの base URL。バージョンパスまで含める |
| `OPENAI_MODEL` | （なし・必須） | 使用モデル。既定値を置かない。妥当な既定はエンドポイントごとに違う |
| `OPENAI_TIMEOUT` | `60` | 1 リクエストの秒数上限 |
| `OPENAI_MAX_RETRIES` | `2` | SDK に委ねるリトライ回数。`0` で 1 リクエスト固定 |
| `OPENAI_TEMPERATURE` | （空＝送らない） | 設定時のみリクエストに載せる |
| `OPENAI_RESPONSE_FORMAT_MODE` | `json_schema` | `json_schema` / `json_object` / `none` |
| `MAX_OUTPUT_TOKENS` | `6000` | 応答の上限。数千字の日本語本文とタイトル案が収まる値 |
| `MAX_INPUT_CHARS` | `4000` | 入力欄の受け入れ上限 |
| `MAX_ALT_TITLES` | `4` | その他のタイトル候補の最大件数（要件 8） |
| `PROMPT_DIR` | `prompts` | プロンプト一式の置き場 |
| `PROMPT_RELOAD` | `off` | `on` でリクエストごとに読み直す（調整用） |
| `BODY_ASCII_SPACING` | `on` | 全角と半角英数字の間への半角スペース挿入 |
| `REQUIRE_SAME_ORIGIN` | `on` | POST の `Origin` 検査 |
| `LOG_LEVEL` | `INFO` | アプリケーションログの水準 |
| `LOG_PAYLOAD` | `off` | `on` のとき入力文と応答本文を DEBUG で記録する。既定 `off`（要件 10.1） |
| `PORT` | `8090` | 開発サーバーおよび gunicorn の待ち受けポート |

`.env.example` は ai-digest と同じ方針で書く。すなわち **秘密情報の欄は空のまま置き、プレースホルダを入れない**。ダミー値が入っていると「設定済み」に見え、認証エラーが実際の呼び出しまで顕在化しない。

`LOG_PAYLOAD=on` は入力内容と生成結果をログに残す。要件 10.1 が求める「保存目的と保存期間」を、README の該当節と `.env.example` のコメントに書く（目的: プロンプト調整と不具合調査。既定は無効。有効にする場合は logrotate で保存期間を定めること）。

---

## 7. 画面設計

### 7.1 共通

- `base.html` を土台に `index.html` / `result.html` / `error.html` が載る（ai-digest と同じ構成）。
- CSS はシステムフォントのみ、外部リクエストなし。`max-width` と 1 カラムのレイアウトで、スマートフォンと PC の双方に耐える（要件 10.4）。ブレークポイントは 1 箇所（狭い画面でボタンを縦積み）で足りる。
- JavaScript は `copy.js` のみ。生成も画面遷移も素の HTML フォームで動き、JS が無効でも「コピーボタンが効かない」以外の機能低下はない。
- 生成ボタン押下後は、二重送信を防ぐためボタンを無効化し、待機中である旨を表示する（JS 有効時のみ。無効時も送信は正しく行われる）。

### 7.2 入力画面（`/`）

| 要素 | 仕様 |
| --- | --- |
| ページタイトル | サービス名と一行の説明 |
| 短文入力欄 | `<textarea name="input_text">`。複数段落可、行数は初期 12 行程度、リサイズ可。`maxlength` に `MAX_INPUT_CHARS` |
| 文字数表示 | 現在の文字数と上限（JS 有効時のみ。無効時はサーバー側で検査） |
| 生成ボタン | `<button name="mode" value="full">` |
| 消去ボタン | `type="reset"` ではなく、入力欄を空にして焦点を戻す（`type="reset"` は編集途中の初期値へ戻るため、要件 6.1 の「入力内容を消去する」と意味がずれる） |

### 7.3 結果画面（`/generate` の応答）

上から順に次を配置する。**投稿に使う文字列と補助情報を視覚的にも DOM 構造的にも分離する**（要件 10.4）。

1. **タイトル第一候補**: ラベル「第一候補」と、タイトル本文、その右にコピーボタン。
2. **その他のタイトル候補**: 各行にタイトルと個別のコピーボタン。0 件なら節ごと表示しない。
3. **タイトル再生成ボタン**: `<button name="mode" value="titles">`。本文は変えずタイトルだけを作り直す。
4. **投稿本文**: 見出し「投稿本文」の下に `<textarea readonly>` を置き、Markdown 原文をそのまま入れる。
   - `readonly` の `textarea` にする理由は三つ。改行と Markdown 記法が視覚整形で失われない、コピーボタンが失敗しても利用者が選択してコピーできる（要件 9.3）、そしてラベルや説明文が構造的に混入しえない（要件 6.3）。
   - 高さは内容に応じて広げ、スクロールを最小にする。
5. **本文コピーボタン**: `textarea` の値だけをコピーする。
6. **注意（`notices`）**: 本文領域の外、本文の下。「見出し階層を調整しました」「定型的な締めの表現が含まれている可能性があります」など。空なら非表示。
7. **全文再生成ボタン**: `<button name="mode" value="full">`。
8. **入力内容**: 折りたたみ（`<details>`）の中に編集可能な `textarea name="input_text">`（初期値は今回の入力）。ここを直して全文再生成すれば、入力画面へ戻らずに作り直せる。加えて「新しく書き始める」リンク（`GET /`）を置く（要件 9.2）。
9. **補助情報**: 使用モデル名と生成時刻を小さく表示。

再生成のために結果画面のフォームが保持する値:

| フィールド | 種別 | 用途 |
| --- | --- | --- |
| `input_text` | `textarea`（折りたたみ内） | 全文再生成・タイトル再生成の双方で送る |
| `body` | `hidden` | タイトルのみ再生成のとき、現在の本文をモデルへ渡す |
| `mode` | 送信ボタンの value | `full` / `titles` |

### 7.4 コピー操作（`copy.js`）

```
click
  -> navigator.clipboard.writeText(value)      // セキュアコンテキスト
     成功 -> ボタン横に「コピーしました」を 2 秒表示
     失敗 -> フォールバックへ
  -> フォールバック: 対象を選択状態にして document.execCommand('copy')
     成功 -> 同上
     失敗 -> 「コピーできませんでした。選択してコピーしてください」を表示し、選択状態は残す
```

- HTTP（非セキュアコンテキスト）では `navigator.clipboard` が使えないため、フォールバックは必須である。外部公開時は HTTPS 前提だが、LAN 内の HTTP でも使える状態を保つ。
- コピー対象は `data-copy-target` で指す要素の `value`（`textarea`）または `textContent`（タイトル）に限る。ラベル、ボタン文言、注意書きは対象要素の外にあるため、構造上コピーされない。

### 7.5 エラー表示

- 入力に起因するエラー（空、長すぎ）は、入力画面を再描画し、入力内容を保ったままエラーを上部に出す。入力を捨てない。
- 生成に起因するエラーは、直前の入力（と、タイトル再生成なら本文）を保持したまま `error.html` を描き、そこから再試行できるようにする。
- 表示するのは `user_message` と参照 ID のみ。

---

## 8. 非機能設計

### 8.1 セキュリティ

- API キーはサーバープロセスの環境変数（または `.env`、パーミッション `600`、所有者はサービス実行ユーザー）から読む。テンプレートへ渡さない。`config.py` は `Config` の `__repr__` でキーを伏せる。
- 外部公開時は Apache で HTTPS を終端する。Basic 認証・IP 制限・VPN は運用側の選択とし、`deploy/sizu-writer.conf` にコメント付きの雛形を置く。
- gunicorn は `127.0.0.1` のみ listen。
- `MAX_CONTENT_LENGTH` と `MAX_INPUT_CHARS` で入力量を抑える。
- 本文の表示は `textarea` の値として行うため、Jinja2 の自動エスケープと合わせて、モデル出力由来の HTML が実行されることはない。**モデル出力を `|safe` で描画しない**ことを設計上の禁止事項とする。
- レート制限はアプリケーションでは実装しない。gunicorn のワーカーをまたいだ計数ができず、正しく効かないためである。必要なら Apache 側（`mod_ratelimit`、`mod_qos`）または認証で絞る。この判断を README に書く。
- エラー画面に内部情報を出さない（5.2 節）。

### 8.2 可用性

- systemd で常時稼働させる。`deploy/sizu-writer.service` の要点:

```ini
[Service]
Type=simple
User=sizu
WorkingDirectory=/opt/sizu-writer
EnvironmentFile=/opt/sizu-writer/.env
ExecStart=/opt/sizu-writer/.venv/bin/gunicorn app:app \
          --bind 127.0.0.1:8090 --workers 2 --timeout 120
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

- `Restart=always` でプロセス終了時に自動復帰し、`systemctl enable` でサーバー再起動後も自動起動する（要件 10.2）。
- `/healthz` は API を呼ばず即座に応答する。監視から叩いても課金されない。
- OpenAI API 障害時は後続処理を持たないため、エラーを返して終わる。再試行は利用者の操作に委ねる（要件 10.2）。

### 8.3 保守性

- プロンプトはコードの外（`prompts/*.md`）。モデル名・タイムアウト・出力上限は環境変数（6 節）。
- HTML テンプレート、CSS、JS、Python、プロンプトがそれぞれ別ファイルに分かれる（4 節の構成）。
- アプリケーションログは stderr へ出し、systemd の journal に入る。Apache のログとはファイルもプロセスも別である（要件 10.3）。ログ書式は ai-digest と同じ `%(asctime)s %(levelname)s %(name)s: %(message)s`。
- 将来の保存機能は `sizu_writer/storage.py` を足し、`app.py` の生成成功直後に 1 行呼び出しを挿すだけで載る。`Draft` は保存したい項目（入力、本文、タイトル案、生成時刻、モデル）をすでに持つ。採用タイトルと投稿済みフラグは、保存を実装する際に画面から受け取る項目として追加する（要件 11）。

### 8.4 操作性

- 一度の入力と 1 クリックで、本文全文とタイトル案が揃う（要件 10.4）。
- 投稿までの操作は「本文コピー → 貼り付け → タイトルコピー → 貼り付け → 確認 → 投稿」で完結する。
- 1 カラムのレイアウトとし、スマートフォンでも横スクロールが出ないようにする。

---

## 9. テスト設計

`tests/` に `unittest` で置く。ネットワークへは出ず、OpenAI クライアントはスタブに差し替える。

| ファイル | 主な検証内容 |
| --- | --- |
| `test_config.py` | 既定値、空文字の扱い、`OPENAI_RESPONSE_FORMAT_MODE` の綴り誤りを拒否すること、必須値の欠落を検出すること、`repr` にキーが出ないこと |
| `test_prompts.py` | プロンプトの読み込み、`{{input}}` `{{body}}` の置換、置換対象がプロンプト本文の他の記号を壊さないこと、ファイル欠落時の挙動、`PROMPT_RELOAD` の効き |
| `test_generator.py` | 正常応答から `Draft` を組めること、`alternative_titles` が 5 件以上でも 4 件へ切り詰めること、`primary_title` との重複と空文字を除くこと、JSON 不正・必須項目欠落・空本文・`finish_reason=length` がいずれも `InvalidResponseError` になること、接続失敗・タイムアウト・4xx/5xx が対応する例外へ写ること、`temperature` 未設定時にパラメータを送らないこと、`OPENAI_RESPONSE_FORMAT_MODE` ごとにリクエストが変わり検証は変わらないこと |
| `test_formatter.py` | 外側フェンスの除去、`#` 見出しの降格と `notices`、コードブロック内を書き換えないこと、ASCII スペーシングの挿入と除外規則（インラインコード、URL、括弧・句読点の隣接）、`BODY_ASCII_SPACING=off` で何もしないこと、定型表現の検出 |
| `test_errors.py` | 各例外が `user_message` と `status_code` を持つこと、機密になりうる文字列（キー、URL、パス）が `user_message` に含まれないこと |
| `test_web.py` | Flask の `test_client` で、入力画面が描かれること、空入力がエラーになり入力を保持すること、生成成功時に本文とタイトルが結果画面に出ること、`mode=titles` が本文を保持したままタイトルだけを更新すること、生成例外時にスタックトレースが応答本文に出ないこと、`Origin` 不一致の POST が 400 になること、`/healthz` が API を呼ばずに 200 を返すこと |

受け入れ条件（要件 14）のうち文章の質に関する項目（7〜9）は自動テストでは判定できない。これらは `cli.py generate` で実入力を通し、目視で確認する手順として README に書く。

---

## 10. 要件との対応

### 10.1 初期実装範囲（要件 12）

| 要件 | 実現箇所 |
| --- | --- |
| 1. Apache と Flask の連携 | 3 節、`deploy/sizu-writer.conf`、`deploy/sizu-writer.service` |
| 2. 短文入力画面 | 7.2 節、`index.html` |
| 3. OpenAI API による文章生成 | 5.4 節、`generator.py` |
| 4. 本文全文の表示 | 7.3 節 4、`result.html` |
| 5. タイトル案の表示 | 7.3 節 1〜2 |
| 6. 本文全文の一括コピー | 7.3 節 5、7.4 節 |
| 7. タイトルごとのコピー | 7.3 節 1〜2、7.4 節 |
| 8. 全文再生成 | 7.3 節 7、`mode=full` |
| 9. タイトル案だけの再生成 | 7.3 節 3、`mode=titles`、`regenerate_titles()` |
| 10. 基本的なエラー処理 | 5.2 節、7.5 節 |
| 11. API キーのサーバー側管理 | 6 節、8.1 節 |

### 10.2 受け入れ条件（要件 14）

| 条件 | 設計上の担保 |
| --- | --- |
| 1. Web 画面から短文を入力できる | 7.2 節 |
| 2. 生成ボタンで OpenAI API が呼ばれる | 5.6 節 `POST /generate` → 5.4 節 |
| 3. 本文全文が表示される | 7.3 節 4 |
| 4. そのままコピーして貼り付けられる | `textarea` に Markdown 原文を格納、7.4 節 |
| 5. 第一候補と複数候補が表示される | 5.4.2 節のスキーマ、7.3 節 1〜2 |
| 6. 本文と各タイトルを個別にコピーできる | 7.4 節、コピー対象は `data-copy-target` の要素に限定 |
| 7. 本文に AI の内部指示や編集説明が混入しない | 5.4.2 節で本文を独立したフィールドとして受け取る、5.5 節の点検、7.3 節の領域分離 |
| 8. 説明記事や体系的論考へ過剰に拡張されない | 5.3 節「書かないもの」「説明量」、7.1 の下限を作らない指示 |
| 9. 既知のテーマを初めて知った体裁へ変えない | 5.3 節「立て付け」 |
| 10. コピー・貼り付け・確認だけで投稿できる | 8.4 節 |
| 11. 投稿先へ自動投稿しない | 2.1 節の不変条件 1〜3。投稿先への通信経路をコードに持たない |
| 12. API キーがブラウザへ露出しない | 2.1 節の不変条件 4、8.1 節 |

### 10.3 将来拡張（要件 11）

保存を実装する際に触る箇所を、あらかじめ限定しておく。

- 追加: `sizu_writer/storage.py`（JSON を `data/drafts/<日付>/<id>.json` へ）、`DATA_DIR` 設定、一覧・詳細ルート。
- 変更: `app.py` の生成成功直後に保存呼び出し 1 行、結果画面に「採用したタイトル」「投稿済み」を記録する小さなフォーム。
- 不変: `generator.py`、`formatter.py`、`prompts.py`、プロンプト一式。生成コアは永続化を知らないままでよい。

保存を実装しても、投稿先への送信は行わない（要件 11 末尾）。

---

## 11. 初期実装の進め方

| 段階 | 内容 | 完了の目安 |
| --- | --- | --- |
| 1 | リポジトリ初期化。`doc/`（POLICY、VERSIONS、ライセンス、要件、本書）、`.gitignore`、`.python-version`、`requirements.txt` | `pip install -r requirements.txt` が通る |
| 2 | `config.py` と `.env.example`、`tests/test_config.py` | 設定の読み込みと検証がテストで固まる |
| 3 | `prompts/*.md` の初版と `prompts.py`、`tests/test_prompts.py` | プロンプトが要件 3・7・8 を網羅する |
| 4 | `generator.py`、`formatter.py`、`errors.py` と各テスト | `cli.py` なしでも生成コアが単体で検証できる |
| 5 | `cli.py` | 実キーで生成を試し、出力の質をプロンプトへ反映する反復ができる |
| 6 | `app.py`、テンプレート、CSS、`copy.js`、`tests/test_web.py` | 開発サーバーで一連の操作が通る |
| 7 | `deploy/` 一式と README のデプロイ節 | 本番相当の Apache + gunicorn + systemd で稼働する |
| 8 | 受け入れ確認（要件 14 の 12 項目） | 文章の質に関する 7〜9 を実入力で目視確認する |

段階 5 を段階 6 より前に置くのが要点である。この種のシステムで最も手戻りが大きいのはプロンプトであり、画面を作る前に `cli.py` で出力の質を詰めておけば、画面側の作り直しが起きない。

---

## 12. 未決事項

実装着手前に決めておきたい項目を挙げる。いずれも本書の構造には影響しない。

1. **モデルの選定**: `OPENAI_MODEL` に既定値を置かない設計としたため、運用で使うモデルを決める必要がある。文体の指示追従性が結果を大きく左右するので、段階 5 で複数を比べる。
2. **入力上限**: `MAX_INPUT_CHARS=4000` は仮値。実際に投げるメモの長さで見直す。
3. **公開範囲**: Basic 認証、IP 制限、VPN のいずれを採るか。`deploy/sizu-writer.conf` の雛形に反映する。
4. **`LOG_PAYLOAD` の運用**: 既定 `off` のまま運用するか、調整期間だけ `on` にして保存期間を定めるか（要件 10.1）。
5. **公開リポジトリとするか**: 公開する場合、`prompts/` の内容もそのまま公開される。
