# TimeBreaker PC Bridge v0.2.2

Copyright (C) 2026 by I.C.KaZe. 自作コードは0BSDです。第三者のライブラリーには各ライセンスが適用されます。

Time BreakerのPS2用USBドングル（VID 0B9A / PID 016A）をPCで利用する非公式ツールです。照準をマウス、ボタンを仮想Xbox 360 / XInput入力へ変換します。公式製品サイトが使用するブランド表記INTECGAMINGおよび製品・商標の各権利者とは関係がなく、公式に認定・提供されたツールではありません。Time Breaker、GunCon2、PS2などの名称は互換性を説明するために使用しています。公式ロゴ、ゲーム画像、ROMは同梱しません。

主な機能:
- 照準表示と四隅校正（トリガーを引いた受信座標で確定）
- マウス入力、XInputボタン、割り当て変更
- 画面外・照準未取得でもXInputボタンを出力（標準ON）
- PC側連射の周期・押下時間・開始遅延
- WinUSB / ViGEmBusの導入状況確認、公式インストーラー取得・署名検証
- 対象ドライバーの選択削除、USB再接続、エラーログ保存
- OS表示言語に応じた日英初期表示、実行中の切り替え

詳細はmanual_ja.htmlをご覧ください。PS2実機の動作やガンのファームウェアは変更しません。

## 配布形式と今回の変更

このアーカイブは**ソース公開・正式Windowsビルド用**です。過去のEXEを再構成した実行ファイルは入れません。Windowsでビルドすると、動的DLLを交換できるフォルダー版のRelease ZIPを生成します。起動はTimeBreakerPCBridge.exeを直接実行する方式で、利用者にPythonやBATの実行は不要です。ZIPの_internalフォルダーも保持してください。

libusb-packageのライセンスをApache-2.0へ訂正しました。libusb0.dll、旧ViGEmBus MSI、x86 DLL、setuptools等を除外する構成と監査を追加しました。第三者ライセンス全文、固定バージョン、対応ソースとビルド証跡を整備しました。GUIや入力処理はv0.2.1の修正を維持しています。

## Windowsで正式ビルド

1. 公式Windows x64 Python **3.13.16**を用意します。この版の依存関係・ライセンスを固定しています。
2. `build_exe_windows.bat`を実行します。専用`.build_venv`と、ハッシュ固定した依存関係を使用します。
3. 24件の動作テスト、構文・ソース検査、PyInstallerビルド、不要物監査、Windows EXEのライブラリー読込と日英GUI作成のスモークテストを行います。
4. 全チェックが成功した場合だけ`release/TimeBreakerPCBridge_v0.2.2_Windows_x64.zip`と`SHA256SUMS.txt`を生成します。

vgamepad 0.1.0の上流setup.pyは旧MSIを起動し得るため、実行しません。検証したソースアーカイブから必要なPythonファイルとx64 ViGEmClient.dllだけを取り出します。このビルド処理ではドライバーを導入・削除しません。

GitHub Actionsの定義は`.github/workflows/windows-build.yml`です。リポジトリにソース一式を置き、Actionsから手動実行できます。vで始まるタグのpushでもビルドします。成功したArtifactをダウンロードし、実機確認後にReleasesの下書きへ添付して公開してください。自動公開は行いません。手順はdocs/BUILD_AND_RELEASE.mdにあります。

同じ固定入力とレシピで第三者がビルド・検査できる構成です。タイムスタンプや署名などを含むEXEのバイト単位の完全一致は保証しません。実際に使用したバージョン、Gitコミット、ハッシュ、PE情報、チェック結果をBUILD_MANIFEST.jsonに記録します。

## ソースから実行

ソース実行には**64ビットPython 3.11以上**が必要です。`setup_windows.bat`は`TIMEBREAKER_PYTHON`指定、`py -3`、PATHの`python`の順でPythonを選びます。Pythonがない場合はインストール方法を表示し、導入失敗は`setup_windows.log`へ記録します。配布用ビルドだけは3.13.16固定です。

`setup_windows.bat`で`.venv`とUSB依存関係、検証済みvgamepad入力を準備し、`start_windows.bat`で起動します。ソース実行でもWinUSB / ViGEmBusのOS導入はGUIから別途行います。旧版のsetup_xinput.batでvgamepadをpipインストールする方式は使用しません。

## ドライバー操作と無保証

本ツールは管理者権限でのドライバー導入・削除を伴います。対象機器や共有ドライバーへの影響を理解したうえで、自己責任で使用してください。ViGEmBusは開発終了しており、他アプリも利用する共有ドライバーです。0BSDの無保証条項はLICENSE.txtにあります。

署名のないPyInstaller製EXEはウイルス対策ソフトで検出される場合があります。配布元、ReleaseのSHA-256、ビルド記録を確認してください。検出内容の確認なしに保護機能を無効化することは導入手順に含みません。公式インストーラーの署名検証は、本アプリEXE自体へのコード署名とは別です。

## 検証状況

この更新時点で、開発環境における入力・ログ・言語切り替えの24件のテスト、依存アーカイブのハッシュ・選別、ライセンス全文のハッシュ、ソース構成を確認しています。**このアーカイブからの正式WindowsビルドとEXEスモークテストは、実行先が未指定のため未実行です。** GitHub Actions / Windowsのバッチが、それらを実行し、失敗時はRelease ZIPの生成を止めます。

CIのスモークテストはWindowsでGUIを作成し、日英を切り替え、必要なDLLをロードする検査です。実際のUSB機器、発射動作、仮想パッド、ドライバー導入・削除の検証を代替しません。公開前の実機項目はdocs/MANUAL_VALIDATION.mdを参照してください。

エラーはdiagnostics/error_日時.txtとerror_latest.txtへ保存します。書き込み不能時はLOCALAPPDATA下へ保存します。公開用パッケージへ実行ログや個人の設定を入れない構成です。

自己テストはUSB読取・ホットキー・保存設定を起動せず、GUI生成と日英切り替えだけを検査します。途中経過はbuild/evidence/runtime-smoke.json、タイムアウト時はruntime-smoke-failure.jsonに残します。失敗したテストを飛ばしてReleaseを生成する機能はありません。

起動直後の障害は早期runtime hookで記録し、通常EXEの検査失敗時だけ同じ構成の診断用コンソールEXEを実行します。終了コードとコンソール出力もbuild/evidence/へ保存します。診断用EXEはRelease ZIPへ含めません。

PyInstallerの汎用USB runtime hookは旧libusb0/openusbを無条件にimportするため、libusb1専用構成では除外します。libusb-packageの明示的なライブラリー探索をそのまま使用し、EXE監査で汎用hookの混入も検出します。

XInputの出力設定チェックは初期ONです（保存済み設定がある場合はその値を優先）。実際の出力開始は従来どおり操作で行います。削除処理は管理者PowerShellへ進捗を表示し、LOCALAPPDATA/TimeBreakerPCBridge/diagnosticsへ開始時からログを保存します。失敗時には終了コードとログの場所を表示します。削除対象の再確認と共有パッケージ保護は維持します。

削除前の関連付け調査はGet-PnpDeviceを1回実行し、デバイスごとの遅いプロパティ照会を行わず、Enum/Control Classのレジストリ情報で確認します。25件ごとに件数を表示します。レジストリを読めない、関連付け先のINFを確認できない場合は削除を停止します。

導入状況は起動時に自動表示しません。開いても診断は開始せず、「状態を再確認」を押した場合だけチェックします。説明書はmanual_ja.html / manual_en.htmlで、GUIの表示言語に応じて選択します。

ブランド表記の確認元：https://intecgaming.com/pages/time-breaker-lightgun （2026-10-03確認）。この表記は法人名や商標登録の権利者を断定するものではありません。
