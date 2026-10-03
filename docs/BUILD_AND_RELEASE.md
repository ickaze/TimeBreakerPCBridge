# Windowsビルドと公開手順

Copyright (C) 2026 by I.C.KaZe

このソースキットには実行用EXEを含みません。Windows x64 Python 3.13.16を固定し、通常権限で `build_exe_windows.bat` を実行してください。Pythonの場所を指定する場合は `TIMEBREAKER_PYTHON` 環境変数にpython.exeの絶対パスを設定します。ネット接続が必要です。

ビルドBATは専用 `.build_venv` の内容を毎回作り直します。ソース実行用 `.venv` とは別です。ビルド依存関係はハッシュ付きlockファイルで固定し、vgamepadのsetup.pyを実行せず、検証済みソースから必要なPythonコードとx64 ViGEmClient.dllだけを取り出します。古いドライバーMSIは取得アーカイブのキャッシュにあっても、成果物へは入りません。

テスト、不要物監査、EXE読込・日英GUIスモークテストに成功した場合だけ `release/` にZIPとSHA256SUMS.txtを生成します。失敗した実行では、以前のreleaseファイルが残っていても公開しないでください。BUILD_MANIFEST.jsonにはソースのGitコミット、Python、ビルド依存関係、PEバージョン・ハッシュ、テスト結果を記録します。バイト単位の再現性は保証しません。libusb DLLを交換できるフォルダー配布のみで、onefile版は作りません。

## GitHub Actions

ソースキットの**中身**をリポジトリのルートへ配置します。`.build_deps`、`.download_cache`、.venv、dist、build、releaseとバイナリーはコミットしません。対応ソースのtar.gzはソースアーカイブなので、そのまま含められます。Actionsの **Windows release build → Run workflow** を実行するとWindows runner上で同じBATを使います。vから始まるタグも起動条件です。

権限はcontents:readのみです。自動公開やリポジトリ作成は行いません。成功したArtifactをダウンロードし、MANUAL_VALIDATION.mdの実機試験を記録してから、GitHub Releasesの下書きにZIPとSHA256SUMSを添付してください。EXEはリポジトリ本体へ追加しません。署名証明書は含めていません。

この変更の作成環境はLinuxです。ここでWindows実行成功やUSB実機動作、ドライバー導入・削除成功を確認したとは扱えません。Windowsでのビルドを実行した後に、その結果をレビューする必要があります。

自己テストの途中経過は`build/evidence/runtime-smoke.json`に逐次保存されます。タイムアウトまたはEXE異常終了では`runtime-smoke-failure.json`に最後の段階を保存します。エラー報告にはこれらのJSONを添付してください。GUIテストではUSB読取、ホットキー監視、保存設定読込は起動しません。

最初のチェックポイント以前の障害も調べられるよう、PyInstaller早期runtime hookによるPython例外記録と、コンソール付き診断EXEを追加しました。失敗時は自動で診断版を実行し、`runtime-smoke-diagnostic.console.log`と`runtime-smoke-diagnostic.json`、異常終了時は`runtime-smoke-diagnostic-failure.json`を残します。通常版の失敗は診断版が成功しても無視しません。診断版はdistの別フォルダーへ作り、Releaseには含めません。
