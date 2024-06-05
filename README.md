# mokumoku-bot

定期的にoViceからユーザの状態を取得し入退室状況をSlackに通知するボット

## prerequisites
以下のツールをインストールしておく。
- Rye: Pythonのプロジェクトマネージャ([公式サイト](https://rye.astral.sh/))
- AWS SAM CLI: サーバレスアプリの作成に特化したCloudFormationのラッパー用のCLIツール（[公式サイト](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html)）

## 環境構築
### 1. リポジトリをクローン
```
$ git clone 後で書く
$ cd mokumoku-bot
```

### 2. 開発環境のセットアップ
#### 1. 仮想環境やスクリプトのセットアップ
```
rye sync
```
#### 2. pre-commitの設定
```
pre-commit install
```

## デプロイ手順
※各サービスの権限周りの設定は省略
### Slack Appの作成
1. [Slack APIのページ](https://api.slack.com/apps)にアクセスしてログインする。
2. Your appsのページに遷移し、Create New Appをクリックする。
3. From an app manifestを選択、導入先のワークスペースを選択、マニフェストとしてリポジトリ内の`slack_app_manifest.yaml`の内容をコピーしてアプリを作成する。
4. アプリ設定画面から、Features > Incoming Webhooksを選択し、導入先のチャンネルを選択してWebhook URLを取得する。

### oVice パブリックAPIの有効化
1. oViceにログインしてスペースにアクセスする。
2. 画面左のメニューから組織の設定にアクセスする。
3. APIの設定から、組織APIキーを発行してクライアントIDとクライアントシークレットを取得する。

### AWSリソースの作成
1. リポジトリ直下で`sam build`を実行する。
2. `sam deploy --guided`を実行し、デプロイ先のリージョンやスタック名、パラメータを入力する。
   - 各パラメータ
     - OviceClientId: oViceのクライアントID
     - OviceClientSecret: oViceのクライアントシークレット
     - SlackWebhookUrl: SlackのWebhook URL