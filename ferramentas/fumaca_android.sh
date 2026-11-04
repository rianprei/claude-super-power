#!/bin/sh
# Teste de fumaça do APK num emulador (ou aparelho) ligado ao adb:
#
#   sh ferramentas/fumaca_android.sh Pestinha.apk "$ANDROID_HOME/build-tools/35.0.0/aapt"
#
# Instala, dá a permissão "Exibir sobre outros apps", abre, espera 45 s e confere: o processo continua vivo,
# não houve erro do Python nem crash nativo, o pet gravou a memória (o app salva a cada 30 s) e está flutuando
# (janelas APPLICATION_OVERLAY do app, com a activity fora da frente). Deixa logcat.txt e tela.png para conferir.
set -eu
APK="$1"
AAPT="$2"
PACOTE="$("$AAPT" dump badging "$APK" | sed -n "s/^package: name='\([^']*\)'.*/\1/p")"
echo "== pacote $PACOTE · Android $(adb shell getprop ro.build.version.release | tr -d '\r') (API $(adb shell getprop ro.build.version.sdk | tr -d '\r')) · $(adb shell getprop ro.product.cpu.abi | tr -d '\r')"
adb install -r "$APK"
adb shell appops set "$PACOTE" SYSTEM_ALERT_WINDOW allow
adb logcat -c
adb shell monkey -p "$PACOTE" -c android.intent.category.LAUNCHER 1 >/dev/null
sleep 45
adb logcat -d >logcat.txt
adb exec-out screencap -p >tela.png
falhou=0
if ! adb shell ps -A | grep -q "$PACOTE"; then
    echo "FALHOU: o app não está mais rodando"
    falhou=1
fi
if grep -E "Traceback|FATAL EXCEPTION|Fatal signal|Fatal Python error" logcat.txt; then
    echo "FALHOU: erro no logcat"
    falhou=1
fi
if ! adb shell "run-as $PACOTE ls 'files/Claude Super Power/memory/pets'"; then     # aspas: o adb junta tudo numa linha
    echo "FALHOU: não gravou a memória"
    falhou=1
fi
flutuando="$(adb shell dumpsys window windows | grep -c "ty=APPLICATION_OVERLAY.*" || true)"
adb shell dumpsys window windows | grep -E "Window\{.*($PACOTE|PythonActivity)" | head -n 12 || true
if [ "${flutuando:-0}" -lt 1 ]; then
    echo "FALHOU: nenhuma janela flutuante (o pet não saiu do app)"
    falhou=1
fi
grep -E " python *:| PonteSobreposicao" logcat.txt | tail -n 40 || true
[ "$falhou" -eq 0 ] && echo "OK: abriu, ficou 45 s rodando, gravou a memória e flutua ($flutuando janelas)"
exit "$falhou"
