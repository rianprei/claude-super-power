package org.claudesuperpower;

import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.provider.Settings;
import android.widget.Toast;

import org.kivy.android.PythonActivity;

/**
 * Entrada do app no Android: a activity do python-for-android (Qt) mais a sobreposição.
 *
 * O Python (o pet) roda nesta activity, mas aparece flutuando sobre os outros apps, como no PC: a Ponte
 * desenha cada janela do Qt numa janela flutuante do Android ("Exibir sobre outros apps"). Sem essa permissão,
 * o pet fica dentro do app, como antes, e a tela de permissão abre.
 */
public class Entrada extends PythonActivity {

    private boolean pediuPermissao = false;

    @Override
    public void onCreate(Bundle estado) {
        super.onCreate(estado);
        Ponte.iniciar(this);
        if (!Settings.canDrawOverlays(this)) {
            pediuPermissao = true;
            Toast.makeText(this, "Permita \"Exibir sobre outros apps\" para o pet flutuar como no PC",
                    Toast.LENGTH_LONG).show();
            startActivity(new Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                    Uri.parse("package:" + getPackageName())));
        }
    }

    @Override
    public void onResume() {
        super.onResume();
        Ponte ponte = Ponte.atual();
        if (ponte == null) {
            return;
        }
        if (pediuPermissao && Settings.canDrawOverlays(this)) {
            pediuPermissao = false;
        }
        ponte.atividadeVisivel(this);
    }
}
