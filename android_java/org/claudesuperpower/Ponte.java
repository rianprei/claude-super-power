package org.claudesuperpower;

import android.app.Activity;
import android.app.AppOpsManager;
import android.app.usage.UsageEvents;
import android.app.usage.UsageStatsManager;
import android.content.SharedPreferences;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageManager;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.ComponentCallbacks;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.res.Configuration;
import android.graphics.Bitmap;
import android.graphics.PixelFormat;
import android.graphics.Rect;
import android.net.LocalServerSocket;
import android.net.LocalSocket;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.os.Process;
import android.provider.Settings;
import android.util.DisplayMetrics;
import android.util.Log;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.View;
import android.view.WindowInsets;
import android.view.WindowManager;
import android.view.WindowMetrics;
import android.widget.ImageView;

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Ponte entre o Python (Qt) e as janelas flutuantes do Android.
 *
 * O Python desenha cada janela de topo do Qt (pet, bolinha, Ki, menu...) numa imagem e manda por um socket local;
 * aqui cada uma vira uma janela flutuante (TYPE_APPLICATION_OVERLAY) que não recebe toque, na mesma posição.
 * As áreas de toque (o corpo do pet, como a região de clique no PC) são janelas transparentes à parte: o resto
 * da tela continua sendo dos outros apps. Os toques voltam para o Python, que os entrega ao Qt como mouse.
 * A notificação faz o papel do ícone da bandeja do PC.
 *
 * Protocolo (big-endian, DataInput/OutputStream):
 *   Python -> aqui  'F' id x y w h flags n [rx ry rw rh]*n tamanho [RGBA premultiplicado]   janela (tamanho 0: só move)
 *                   'H' id                                                                  esconde a janela
 *                   'N' pausado escondido                                                   estado da notificação
 *   aqui -> Python  'M' modo                    1 = sobreposição permitida
 *                   'S' w h topo baixo esq dir  tela em pixels físicos e as barras do sistema
 *                   'T' id acao x y             toque (MotionEvent: 0 desce, 1 sobe, 2 move, 3 cancela), x/y na tela
 *                   'O' id                      toque fora (em outro app): conta como atividade; fecha menus
 *                   'C' texto                   comando da notificação (hide, settings, quit)
 *                   'P' categoria texto         app em primeiro plano (pacote e ApplicationInfo.category), se o
 *                                               acesso de uso foi liberado
 *                   'U' cheia                   a tela está cheia (as barras do sistema sumiram: vídeo, jogo)
 */
public final class Ponte {
    static final String NOME = "claudesuperpower.ponte";        // socket local, namespace abstrato
    static final String ACAO = "org.claudesuperpower.COMANDO";
    static final int FLAG_POPUP = 1;
    private static final String TAG = "PonteSobreposicao";
    private static final int MAXIMO = 8192;                      // px: lado máximo de uma janela
    private static Ponte atual;

    private final Context ctx;
    private final WindowManager wm;
    private final Handler ui = new Handler(Looper.getMainLooper());
    private final ExecutorService escritor = Executors.newSingleThreadExecutor();
    private final Map<Integer, Janela> janelas = new HashMap<>();   // só na thread da interface
    private volatile DataOutputStream saida;
    private volatile Activity atividade;
    private volatile boolean recebeuQuadro;
    private boolean recuou;
    private View sensor;                    // janela invisível de 1 px: vê se as barras do sistema somem
    private Boolean cheia;
    private String appAtivo = "";

    private static final class Janela {
        ImageView vista;
        WindowManager.LayoutParams params;
        final List<View> toques = new ArrayList<>();
    }

    private Ponte(Activity a) {
        ctx = a.getApplicationContext();
        wm = (WindowManager) ctx.getSystemService(Context.WINDOW_SERVICE);
        atividade = a;
    }

    static synchronized void iniciar(Activity a) {
        if (atual == null) {
            atual = new Ponte(a);
            atual.ouvir();
            atual.registrarComandos();
            ComponentCallbacks telas = new ComponentCallbacks() {
                @Override public void onConfigurationChanged(Configuration c) { atual.enviarTela(); }
                @Override public void onLowMemory() { }
            };
            a.getApplicationContext().registerComponentCallbacks(telas);
            atual.vigiarApps();
        }
        atual.atividade = a;
    }

    static synchronized Ponte atual() {
        return atual;
    }

    boolean sobreposicao() {
        return Settings.canDrawOverlays(ctx);
    }

    /** A activity voltou para a frente: com a sobreposição no ar, ela sai da frente (o pet flutua). */
    void atividadeVisivel(Activity a) {
        atividade = a;
        enviarModo();
        if (sobreposicao() && saida != null && recebeuQuadro) {
            a.moveTaskToBack(true);
        }
    }

    // ---------------- socket ----------------

    private void ouvir() {
        Thread t = new Thread(() -> {
            LocalServerSocket servidor;
            try {
                servidor = new LocalServerSocket(NOME);
            } catch (IOException e) {
                Log.e(TAG, "sem socket local", e);
                return;
            }
            while (true) {
                try (LocalSocket s = servidor.accept()) {
                    if (s.getPeerCredentials().getUid() != Process.myUid()) {
                        Log.w(TAG, "conexão de outro app recusada");
                        continue;
                    }
                    saida = new DataOutputStream(new BufferedOutputStream(s.getOutputStream(), 1 << 12));
                    appAtivo = "";
                    cheia = null;
                    enviarModo();
                    enviarTela();
                    ui.post(this::ligarSensor);
                    ler(new DataInputStream(new BufferedInputStream(s.getInputStream(), 1 << 16)));
                } catch (IOException e) {
                    Log.i(TAG, "Python desconectou: " + e.getMessage());
                }
                saida = null;
                recebeuQuadro = false;
                ui.post(this::limparTudo);
            }
        }, "ponte-pet");
        t.setDaemon(true);
        t.start();
    }

    private void ler(DataInputStream in) throws IOException {
        while (true) {
            int cmd = in.readUnsignedByte();
            if (cmd == 'F') {
                final int id = in.readInt(), x = in.readInt(), y = in.readInt(), w = in.readInt(), h = in.readInt();
                final int flags = in.readInt();
                int n = in.readInt();
                if (n < 0 || n > 16 || w <= 0 || h <= 0 || w > MAXIMO || h > MAXIMO) {
                    throw new IOException("quadro inválido");
                }
                final int[] areas = new int[n * 4];
                for (int i = 0; i < areas.length; i++) {
                    areas[i] = in.readInt();
                }
                int tamanho = in.readInt();
                Bitmap imagem = null;
                if (tamanho != 0) {
                    if (tamanho != w * h * 4) {
                        throw new IOException("tamanho de imagem inválido");
                    }
                    byte[] px = new byte[tamanho];
                    in.readFully(px);
                    imagem = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888);
                    imagem.copyPixelsFromBuffer(ByteBuffer.wrap(px));
                }
                final Bitmap pronta = imagem;
                ui.post(() -> aplicar(id, x, y, w, h, flags, areas, pronta));
                if (!recebeuQuadro) {
                    recebeuQuadro = true;
                    ui.post(this::recuar);
                }
            } else if (cmd == 'H') {
                final int id = in.readInt();
                ui.post(() -> remover(id));
            } else if (cmd == 'N') {
                final boolean pausado = in.readBoolean(), escondido = in.readBoolean();
                ui.post(() -> notificar(pausado, escondido));
            } else {
                throw new IOException("comando desconhecido: " + cmd);
            }
        }
    }

    private interface Escrita {
        void em(DataOutputStream o) throws IOException;
    }

    private void enviar(Escrita escrita) {
        escritor.execute(() -> {
            DataOutputStream o = saida;
            if (o == null) {
                return;
            }
            try {
                escrita.em(o);
                o.flush();
            } catch (IOException e) {
                Log.w(TAG, "falha ao enviar: " + e.getMessage());
            }
        });
    }

    private void enviarModo() {
        final boolean pode = sobreposicao();
        enviar(o -> { o.writeByte('M'); o.writeBoolean(pode); });
    }

    private void enviarTela() {
        int w, h, topo = 0, baixo = 0, esq = 0, dir = 0;
        if (Build.VERSION.SDK_INT >= 30) {
            WindowMetrics m = wm.getMaximumWindowMetrics();
            Rect r = m.getBounds();
            w = r.width();
            h = r.height();
            android.graphics.Insets ins = m.getWindowInsets().getInsetsIgnoringVisibility(
                    WindowInsets.Type.systemBars() | WindowInsets.Type.displayCutout());
            topo = ins.top; baixo = ins.bottom; esq = ins.left; dir = ins.right;
        } else {
            DisplayMetrics dm = new DisplayMetrics();
            wm.getDefaultDisplay().getRealMetrics(dm);
            w = dm.widthPixels;
            h = dm.heightPixels;
            topo = dimensao("status_bar_height");
            baixo = dimensao("navigation_bar_height");
        }
        final int[] v = {w, h, topo, baixo, esq, dir};
        enviar(o -> { o.writeByte('S'); for (int x : v) o.writeInt(x); });
    }

    private int dimensao(String nome) {
        int id = ctx.getResources().getIdentifier(nome, "dimen", "android");
        return id > 0 ? ctx.getResources().getDimensionPixelSize(id) : 0;
    }

    // ---------------- janelas (thread da interface) ----------------

    private WindowManager.LayoutParams parametros(int x, int y, int w, int h, boolean toque, boolean popup) {
        int flags = WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE
                | WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS
                | WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN;
        if (toque) {
            flags |= WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL | WindowManager.LayoutParams.FLAG_WATCH_OUTSIDE_TOUCH;
        } else {
            flags |= WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE;
        }
        WindowManager.LayoutParams p = new WindowManager.LayoutParams(w, h,
                WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY, flags, PixelFormat.TRANSLUCENT);
        p.gravity = Gravity.TOP | Gravity.LEFT;
        p.x = x;
        p.y = y;
        if (Build.VERSION.SDK_INT >= 28) {
            p.layoutInDisplayCutoutMode = WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES;
        }
        return p;
    }

    private void aplicar(int id, int x, int y, int w, int h, int flags, int[] areas, Bitmap imagem) {
        if (!sobreposicao()) {
            return;
        }
        Janela j = janelas.get(id);
        try {
            if (j == null) {
                j = new Janela();
                j.vista = new ImageView(ctx);
                j.vista.setScaleType(ImageView.ScaleType.FIT_XY);
                j.params = parametros(x, y, w, h, false, false);
                wm.addView(j.vista, j.params);
                janelas.put(id, j);
            } else if (j.params.x != x || j.params.y != y || j.params.width != w || j.params.height != h) {
                j.params.x = x;
                j.params.y = y;
                j.params.width = w;
                j.params.height = h;
                wm.updateViewLayout(j.vista, j.params);
            }
            if (imagem != null) {
                j.vista.setImageBitmap(imagem);
            }
            ajustarToques(id, j, x, y, areas, (flags & FLAG_POPUP) != 0);
        } catch (RuntimeException e) {          // WindowManager.BadTokenException, permissão revogada...
            Log.w(TAG, "janela " + id + ": " + e);
        }
    }

    private void ajustarToques(final int id, Janela j, int x, int y, int[] areas, boolean popup) {
        int n = areas.length / 4;
        while (j.toques.size() > n) {
            wm.removeView(j.toques.remove(j.toques.size() - 1));
        }
        for (int i = 0; i < n; i++) {
            int ax = x + areas[4 * i], ay = y + areas[4 * i + 1], aw = areas[4 * i + 2], ah = areas[4 * i + 3];
            if (i < j.toques.size()) {
                View v = j.toques.get(i);
                WindowManager.LayoutParams p = (WindowManager.LayoutParams) v.getLayoutParams();
                if (p.x != ax || p.y != ay || p.width != aw || p.height != ah) {
                    p.x = ax; p.y = ay; p.width = aw; p.height = ah;
                    wm.updateViewLayout(v, p);
                }
            } else {
                View v = new View(ctx);
                v.setOnTouchListener((vista, ev) -> toque(id, ev));
                wm.addView(v, parametros(ax, ay, aw, ah, true, popup));
                j.toques.add(v);
            }
        }
    }

    private boolean toque(final int id, MotionEvent ev) {
        final int acao = ev.getActionMasked();
        if (acao == MotionEvent.ACTION_OUTSIDE) {
            enviar(o -> { o.writeByte('O'); o.writeInt(id); });
            return false;
        }
        if (acao > MotionEvent.ACTION_CANCEL) {
            return true;                        // segundo dedo etc.: o pet só entende um
        }
        final float x = ev.getRawX(), y = ev.getRawY();
        enviar(o -> { o.writeByte('T'); o.writeInt(id); o.writeInt(acao); o.writeFloat(x); o.writeFloat(y); });
        return true;
    }

    private void remover(int id) {
        Janela j = janelas.remove(id);
        if (j == null) {
            return;
        }
        for (View v : j.toques) {
            wm.removeView(v);
        }
        wm.removeView(j.vista);
    }

    private void limparTudo() {
        for (Integer id : new ArrayList<>(janelas.keySet())) {
            remover(id);
        }
        if (sensor != null) {
            wm.removeView(sensor);
            sensor = null;
        }
        ((NotificationManager) ctx.getSystemService(Context.NOTIFICATION_SERVICE)).cancel(1);
    }

    private void recuar() {
        Activity a = atividade;
        if (a != null && sobreposicao() && !recuou) {
            recuou = true;
            a.moveTaskToBack(true);
            pedirAcessoDeUso(a);
        }
        notificar(false, false);
    }

    // ---------------- sentidos: app em primeiro plano e tela cheia ----------------

    private boolean acessoDeUso() {
        AppOpsManager ops = (AppOpsManager) ctx.getSystemService(Context.APP_OPS_SERVICE);
        int modo = ops.checkOpNoThrow(AppOpsManager.OPSTR_GET_USAGE_STATS, Process.myUid(), ctx.getPackageName());
        return modo == AppOpsManager.MODE_ALLOWED;
    }

    /** Uma vez só: abre a tela do acesso de uso (o pet sente o app em uso, como sente o programa no PC). */
    private void pedirAcessoDeUso(Activity a) {
        SharedPreferences prefs = ctx.getSharedPreferences("ponte", Context.MODE_PRIVATE);
        if (acessoDeUso() || prefs.getBoolean("pediu_uso", false)) {
            return;
        }
        prefs.edit().putBoolean("pediu_uso", true).apply();
        try {
            a.startActivity(new Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS));
        } catch (RuntimeException e) {
            Log.w(TAG, "sem a tela de acesso de uso: " + e);
        }
    }

    /** A cada 2 s: o app em primeiro plano (o último que foi para a frente), se o acesso de uso foi liberado. */
    private void vigiarApps() {
        Thread t = new Thread(() -> {
            UsageStatsManager uso = (UsageStatsManager) ctx.getSystemService(Context.USAGE_STATS_SERVICE);
            while (true) {
                try {
                    Thread.sleep(2000);
                } catch (InterruptedException e) {
                    return;
                }
                if (saida == null || uso == null || !acessoDeUso()) {
                    continue;
                }
                long agora = System.currentTimeMillis();
                UsageEvents eventos = uso.queryEvents(agora - 60_000, agora);
                UsageEvents.Event ev = new UsageEvents.Event();
                String ultimo = null;
                while (eventos.hasNextEvent()) {
                    eventos.getNextEvent(ev);
                    if (ev.getEventType() == UsageEvents.Event.ACTIVITY_RESUMED) {
                        ultimo = ev.getPackageName();
                    }
                }
                if (ultimo == null || ultimo.equals(ctx.getPackageName()) || ultimo.equals(appAtivo)) {
                    continue;
                }
                appAtivo = ultimo;
                int categoria = -1;
                try {
                    ApplicationInfo info = ctx.getPackageManager().getApplicationInfo(ultimo, 0);
                    categoria = info.category;
                } catch (PackageManager.NameNotFoundException e) {
                    // sem informação de categoria
                }
                final String pacote = ultimo;
                final int cat = categoria;
                enviar(o -> { o.writeByte('P'); o.writeInt(cat); o.writeUTF(pacote); });
            }
        }, "ponte-apps");
        t.setDaemon(true);
        t.start();
    }

    /** Janela invisível de 1 px que recebe as margens do sistema: sem barra de status, a tela está cheia. */
    private void ligarSensor() {
        if (sensor != null || !sobreposicao() || Build.VERSION.SDK_INT < 30) {
            return;
        }
        sensor = new View(ctx);
        sensor.setOnApplyWindowInsetsListener((v, insets) -> {
            boolean agora = !insets.isVisible(WindowInsets.Type.statusBars());
            if (cheia == null || cheia != agora) {
                cheia = agora;
                enviar(o -> { o.writeByte('U'); o.writeBoolean(agora); });
            }
            return insets;
        });
        try {
            wm.addView(sensor, parametros(0, 0, 1, 1, false, false));
        } catch (RuntimeException e) {
            Log.w(TAG, "sem sensor de tela cheia: " + e);
            sensor = null;
        }
    }

    // ---------------- notificação (a bandeja do PC) ----------------

    private void registrarComandos() {
        BroadcastReceiver receptor = new BroadcastReceiver() {
            @Override
            public void onReceive(Context c, Intent i) {
                final String texto = i.getStringExtra("cmd");
                if (texto != null) {
                    enviar(o -> { o.writeByte('C'); o.writeUTF(texto); });
                }
            }
        };
        IntentFilter filtro = new IntentFilter(ACAO);
        if (Build.VERSION.SDK_INT >= 33) {
            ctx.registerReceiver(receptor, filtro, 4);    // Context.RECEIVER_NOT_EXPORTED (API 33: a variante
                                                          // compatível compila com um SDK mais antigo)
        } else {
            ctx.registerReceiver(receptor, filtro);
        }
    }

    private PendingIntent comando(String texto, int codigo) {
        Intent i = new Intent(ACAO).setPackage(ctx.getPackageName()).putExtra("cmd", texto);
        return PendingIntent.getBroadcast(ctx, codigo, i,
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
    }

    private void notificar(boolean pausado, boolean escondido) {
        if (saida == null) {
            return;
        }
        NotificationManager nm = (NotificationManager) ctx.getSystemService(Context.NOTIFICATION_SERVICE);
        nm.createNotificationChannel(new NotificationChannel("pet", "Pet na tela", NotificationManager.IMPORTANCE_LOW));
        String estado = escondido ? "Escondido" : (pausado ? "Pausado" : "Na tela");
        Notification n = new Notification.Builder(ctx, "pet")
                .setSmallIcon(ctx.getApplicationInfo().icon)
                .setContentTitle("Claude Super Power")
                .setContentText(estado + " · toque para as configurações")
                .setOngoing(true)
                .setContentIntent(comando("settings", 1))
                .addAction(new Notification.Action.Builder(null, escondido ? "Mostrar" : "Esconder",
                        comando("hide", 2)).build())
                .addAction(new Notification.Action.Builder(null, pausado ? "Continuar" : "Pausar",
                        comando("pause", 3)).build())
                .addAction(new Notification.Action.Builder(null, "Sair", comando("quit", 4)).build())
                .build();
        nm.notify(1, n);
    }
}
