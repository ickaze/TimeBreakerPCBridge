# libusb対応ソースとDLL交換

新Releaseはlibusb 1.0.30（LIBUSB_NANO=12037）を動的ロードします。libusb-package 1.0.30.0のWindows amd64 wheelに含まれるDLLを使用し、libusb-win32/libusb0.dllは使用しません。

Releaseのcorresponding_source/に以下を添付します。

- libusb-1.0.30-source.tar.gz：公式v1.0.30タグの完全なソース。COPYING、ビルド定義を含みます。
- libusb-package-1.0.30.0-source.tar.gz：公式v1.0.30.0タグのパッケージとWindowsビルドレシピ。

配布した正確なファイルの取得URLとSHA-256はDEPENDENCY_SOURCES.json、実際のDLLハッシュはBUILD_MANIFEST.jsonに記録します。これは将来変わるトップページへのリンクだけに依存したソース提供ではありません。初回ビルド時もこのハッシュを検証します。

DLLの交換場所は`_internal/libusb_package/libusb-1.0.dll`です。アプリを終了し、バックアップを取ってから、互換API/ABIを保つx64のDLLへ置き換えられます。置き換えを妨げる独自署名照合や暗号化はアプリに設けません。変更版の動作や既存SHA-256との一致は保証しません。

対応ソースを展開し、libusb-package側の`src/libusb`へlibusbのソース一式を配置すれば、元の上流サブモジュール構成を再現できます。libusb-packageのsetup.pyにはWindowsで使うMSVCプロジェクトとMSBuild引数が記載されています。Visual StudioのC++環境が必要です。libusbの`msvc/libusb_dll.vcxproj`をRelease/x64としてビルドしてDLLだけ交換する方法も使用できます。

アプリ自体のソースとspec・依存ロックはReleaseのsource_package/にも同梱します。Windowsビルド用Pythonの固定版とその他の依存を用意すれば、置き換えDLLを含むアプリを再ビルドできます。元のビルド機・MSVCの更新等の影響でバイト列まで同一になるとは限りません。

libusbのライセンスはLGPL-2.1-or-laterです。`licenses/libusb_LGPL-2.1.txt`の全文を保持してください。libusb-package自身のライセンス（Apache-2.0）と、ライブラリー本体のLGPLは別です。
