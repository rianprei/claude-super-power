#!/bin/sh
# Depois do buildozer: alvo na API 29 (ver ferramentas/alvo_sdk_apk.py), alinhamento e assinatura de novo com a
# chave de debug do Gradle (a mesma com que o build assinou; criada se o runner não tiver).
#
#   sh ferramentas/finalizar_apk.sh entrega/ClaudeSuperPower.apk "$ANDROID_HOME/build-tools/35.0.0"
set -eu
APK="$1"
BT="$2"
CHAVE="$HOME/.android/debug.keystore"
python ferramentas/alvo_sdk_apk.py "$APK" "$APK.alvo" 29
"$BT/zipalign" -f -P 16 4 "$APK.alvo" "$APK.alinhado"
if [ ! -f "$CHAVE" ]; then
    mkdir -p "$(dirname "$CHAVE")"
    keytool -genkeypair -keystore "$CHAVE" -storepass android -keypass android -alias androiddebugkey \
        -keyalg RSA -keysize 2048 -validity 10000 -dname "CN=Android Debug,O=Android,C=US"
fi
"$BT/apksigner" sign --ks "$CHAVE" --ks-pass pass:android --key-pass pass:android --ks-key-alias androiddebugkey \
    --out "$APK" "$APK.alinhado"
rm -f "$APK.alvo" "$APK.alinhado" "$APK.idsig"
"$BT/apksigner" verify "$APK"
"$BT/aapt2" dump badging "$APK" | grep -E "^(package|sdkVersion|targetSdkVersion)"
