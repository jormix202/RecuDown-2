import sys
import os
import json
import subprocess
import threading
import winsound
import re
import time
import random
import string
import ctypes
import shutil
from datetime import datetime
from urllib.parse import urlparse
import urllib.request
import tempfile

from PySide6.QtWidgets import (
    QApplication, QWidget, QPushButton, QLineEdit, QTextBrowser, QLabel,
    QVBoxLayout, QHBoxLayout, QFrame, QSpinBox, QAbstractSpinBox,
    QSizePolicy, QMenu, QFileDialog, QDialog, QWidgetAction, QPlainTextEdit
)
from PySide6.QtCore import Qt, Signal, QObject, QTimer, QEvent, QRect, QRectF, QPointF, QPoint
from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import (
    QFont, QIcon, QPixmap, QPainter, QColor, QShortcut,
    QKeySequence, QCursor, QPainterPath, QTextOption, QTextCursor
)
from PySide6.QtGui import QRegularExpressionValidator


# ============================================================
#  Helpers compartidos
# ============================================================
MENU_STYLE = ("QMenu{background-color:#34383f;color:#d0d0d0;border:1px solid #50575d;"
              "border-radius:0px;padding:0px;font-family:Arial;font-size:10pt;}"
              "QMenu::item{padding:0px;margin:0px;border-radius:0px;}"
              "QMenu::item:selected{background-color:#4a4f57;border-radius:0px;}"
              "QMenu::separator{height:1px;background:#50575d;margin:4px 10px;}")

BTN_QSS = (
    "QPushButton {"
    "  background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, "
    "    stop:0 #50575d, stop:0.48 #34383f, stop:0.52 #2a2e33, stop:1 #222529);"
    "  color: #d0d0d0;"
    "  border-top: 1px solid #6c747d;"
    "  border-left: 1px solid #50575d;"
    "  border-right: 1px solid #1f2226;"
    "  border-bottom: 1px solid #1a1c1f;"
    "  border-radius: 6px;"
    "  font-family: Arial;"
    "  font-size: 10pt;"
    "  font-weight: bold;"
    "  padding: 0px 0px 4px 0px;"
    "}"
    "QPushButton:hover {"
    "  background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, "
    "    stop:0 #5c646b, stop:0.48 #40454d, stop:0.52 #34383f, stop:1 #2a2e33);"
    "  border-top: 1px solid #7a828b;"
    "  border-left: 1px solid #5c646b;"
    "}"
    "QPushButton:pressed {"
    "  background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, "
    "    stop:0 #2a2e33, stop:0.5 #222529, stop:1 #1a1c1f);"
    "  border-top: 1px solid #1f2226;"
    "  border-left: 1px solid #1f2226;"
    "  border-right: 1px solid #50575d;"
    "  border-bottom: 1px solid #50575d;"
    "}")


def _subprocess_kwargs():
    """Devuelve kwargs + creationflags para ocultar ventanas de consola en Windows."""
    if sys.platform != "win32":
        return {}, 0
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = subprocess.SW_HIDE
    return {"startupinfo": si}, subprocess.CREATE_NO_WINDOW


def play_key_tap():
    try:
        base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        winsound.PlaySound(os.path.join(base, "tap.wav"),
                           winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
    except Exception:
        pass


def make_menu_item(menu, icon, text, cb, icon_pad, text_pad):
    action = QWidgetAction(menu)
    w = QWidget()
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(0)
    for content, pad in ((icon, icon_pad), (text, text_pad)):
        lbl = QLabel(content)
        lbl.setStyleSheet(f"QLabel{{color:#d0d0d0;background:transparent;"
                          f"font-family:Arial;font-size:10pt;padding:{pad};"
                          f"{'min-width:20px;' if content == icon else ''}}}")
        h.addWidget(lbl)
    h.addStretch()
    w.setLayout(h)
    w.setStyleSheet("QWidget:hover{background-color:#4a4f57;}")
    w.mousePressEvent = lambda e: (e.button() == Qt.LeftButton and (play_key_tap(), cb(), menu.close()))
    action.setDefaultWidget(w)
    return action


def hide_file_windows(path):
    if os.name == 'nt' and os.path.exists(path):
        if os.path.basename(path).lower() == "download_progress.json":
            return
        try:
            kw, cf = _subprocess_kwargs()
            subprocess.run(['attrib', '+h', path],
                           capture_output=True, timeout=5,
                           creationflags=cf, **kw)
        except Exception:
            pass


def _safe_remove(path, sleep=0.0):
    if not path or not os.path.exists(path):
        return
    if os.name == 'nt':
        try:
            kw, cf = _subprocess_kwargs()
            subprocess.run(['attrib', '-h', '-r', '-s', path],
                           capture_output=True, timeout=5,
                           creationflags=cf, **kw)
        except Exception:
            pass
    try: os.remove(path)
    except Exception: pass
    if sleep: time.sleep(sleep)


def _read_json(path, default=None):
    try:
        if not os.path.exists(path): return default
        with open(path, encoding="utf-8") as f: return json.load(f)
    except Exception:
        return default


def _write_json(path, data, indent=2, retries=3, sleep=0.1, atomic=False):
    tmp = path + ".tmp"
    for _ in range(retries):
        if not atomic:
            _safe_remove(path, sleep)
        else:
            if os.name == 'nt' and os.path.exists(path):
                try:
                    kw, cf = _subprocess_kwargs()
                    subprocess.run(['attrib', '-h', '-r', '-s', path],
                                   capture_output=True, timeout=5,
                                   creationflags=cf, **kw)
                except Exception:
                    pass
        try:
            target = tmp if atomic else path
            with open(target, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=indent, ensure_ascii=False)
                f.flush(); os.fsync(f.fileno())
            if atomic:
                if os.name == 'nt':
                    _safe_remove(path)
                os.replace(tmp, path)
            hide_file_windows(path)
            return True
        except Exception:
            if atomic: _safe_remove(tmp)
            time.sleep(sleep)
    return False


def cleanup_old_configs(folder):
    if not folder or not os.path.isdir(folder):
        return
    for f in os.listdir(folder):
        if f in ("config.json", "config_seq.json") or (
                f.startswith("config_seq_") and f.endswith(".json")):
            _safe_remove(os.path.join(folder, f))


def get_recu_launcher(widget):
    p = widget.parent()
    while p and not isinstance(p, RecuLauncher):
        p = p.parent()
    return p


def urlopen_localhost(url, timeout=3):
    return urllib.request.build_opener(urllib.request.ProxyHandler({})).open(url, timeout=timeout)


def normalize_time_separators(value):
    return value.translate(str.maketrans(',.;-', '::::')) if isinstance(value, str) else value


def format_video_name(raw_name, rename_format='yyyy-mm-dd'):
    name = raw_name
    if name.startswith("CB_"):
        name = name[3:]
    if name.endswith(".ts"):
        name = name[:-3]

    prefix = year = month = day = ""
    m = re.search(r'(\d{2})-(\d{2})-(\d{4})', name)
    if m:
        prefix = name[:m.start()].rstrip('_')
        n1, n2, n3 = m.groups()
        year = n3
        day, month = (n1, n2) if int(n1) > 12 else (n2, n1)
    else:
        m = re.search(r'(\d{2})-(\d{2})-(\d{2})', name)
        if m:
            prefix = name[:m.start()].rstrip('_')
            n1, n2, n3 = m.groups()
            year, month, day = f"20{n1}", n2, n3

    mt = re.search(r'_(\d{2}-\d{2})$', name)
    if not mt and m:
        mt = re.search(r'_(\d{2}-\d{2})', name[m.end():])
    hh = mt.group(1) if mt else ""

    if rename_format == "original":
        if m and hh:
            d = f"{year}-{month}-{day}"
            final = f"{prefix}_{d}_{hh}" if prefix else f"{d}_{hh}"
        elif m:
            d = f"{year}-{month}-{day}"
            final = f"{prefix}_{d}" if prefix else d
        else:
            final = name
    elif m:
        d = (f"{day}-{month}-{year}" if rename_format == "dd-mm-yyyy"
             else f"{year}-{month}-{day}")
        final = f"{prefix}_{d}" if prefix else d
    else:
        final = name

    final = re.sub(r'[\\/*?:"<>|]', '', final).replace(':', '-')
    final = re.sub(r'[^\w\-_]', '', re.sub(r'[_ ]+', '_', final))
    return re.sub(r'__+', '_', final).strip('_') or "video"


def _format_progress(line, tr, lang):
    try:
        pct = float(m.group(1)) if (m := re.search(r'(\d+(?:\.\d+)?)\s*%', line)) else 0.0
        secs = [float(v) * (3600 if u[0] == 'h' else 60 if u[0] == 'm' else 1)
                for v, u in re.findall(r'(\d+(?:\.\d+)?)\s*(hours?|hrs?|mins?|secs?)', line, re.I)]
        sp = re.search(r'(\d+(?:\.\d+)?)\s*(KB/s|MB/s)', line)
        spd, spu = (sp.group(1), sp.group(2)) if sp else ("", "")
        spu = tr("kb_s" if spu == "KB/s" else "mb_s") if spu else ""
        rem = sum(secs) if secs else 0.0
        dl, rn = tr("downloading"), tr("remaining")
        ps = f"{int(pct)}%" if pct.is_integer() else f"{pct:.1f}%"
        if rem >= 3600:
            rd = (f"{rem/3600:.1f} {tr('hours')}" if lang == "Русский"
                  else f"{rem/3600:.1f} h" if lang == "Português"
                  else f"{rem/3600:.1f} hrs")
        elif rem >= 60:
            rd = f"{rem/60:.1f} {tr('mins')}"
        else:
            rd = f"{rem:.0f} {tr('secs')}"
        sp_ = {"Русский": "     ", "Español": "   ", "Português": "     "}.get(lang, "   ")
        return f"> {dl}: {ps}{sp_}{rn}: {rd}{sp_}{spd} {spu}".rstrip()
    except Exception:
        return f"> {line}"


# ============================================================
#  Sesión
# ============================================================
_SESSION_ID = None


def get_or_create_session_id():
    global _SESSION_ID
    if _SESSION_ID is None:
        _SESSION_ID = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return _SESSION_ID


def reset_session_id():
    global _SESSION_ID
    _SESSION_ID = None


# ============================================================
#  Traducciones
# ============================================================
_FFMPEG_CMD1 = 'powershell -c "irm get.scoop.sh|'
_FFMPEG_CMD2 = 'iex;scoop install ffmpeg"'

_T = {
    "settings_title":           ("Settings", "Configuración", "Configurações", "Настройки"),
    "save_videos_to":           ("Save videos to  ", "Guardar videos en  ", "Salvar vídeos em  ", "Сохранять видео в  "),
    "download_mode":            ("Download method", "Modo de descarga  ", "Modo de download  ", "Режим загрузки  "),
    "change_format_to":         ("Output file format", "Formato de salida  ", "Formato de saida ", "Смена формата  "),
    "change_language":          ("Change lenguage", "Cambiar lenguaje  ", "Configurar idioma", "Изменить язык  "),
    "rename_videos":            ("Date format option", "Formato de fecha  ", "Formato de data  ", "Переименовать  "),
    "dd_mm_yyyy":               ("D/M/Y", "D/M/A", "D/M/A", "Д/М/Г"),
    "yyyy_mm_dd":               ("Y/M/D", "A/M/D", "A/M/D", "Г/М/Д"),
    "original":                 ("Original", "Original", "Original", "Оригинал"),
    "save_settings":            ("Save settings", "Guardar configuración", "Salvar configurações", "Сохранить настройки"),
    "parallel":                 ("Parallel", "Paralelo", "Paralelo", "Паралл"),
    "series":                   ("Series", "Serie", "Série", "Серии"),
    "settings_saved":           ("Settings saved", "Configuración guardada", "Configuração salva", "Настройки сохранены"),
    "ffmpeg_not_found":         ("FFmpeg is not found on your system", "FFmpeg no está instalado en el sistema", "FFmpeg não encontrado no sistema", "FFmpeg не найден в системе"),
    "ffmpeg_ts_only":           ("Videos will be downloaded in TS format", "Los videos se descargarán en formato TS", "Os vídeos serão baixados em formato TS", "Видео будут загружены в формате TS"),
    "ffmpeg_install_details":   ("More information on how to install FFmpeg", "Más información sobre cómo instalar FFmpeg", "Mais informações sobre como instalar o FFmpeg", "Подробнее о том, как установить FFmpeg"),
    "ffmpeg_install_step1":     ("1. On your PC, search for and open CMD", "1. En su PC busque y abra CMD", "1. No seu PC, procure e abra o CMD", "1. На ПК найдите и откройте CMD"),
    "ffmpeg_install_step2":     ("2. Copy and paste this command into CMD:", "2. Copie y pegue este comando en CMD:", "2. Copie e cole este comando no CMD:", "2. Скопируйте и вставьте эту команду в CMD:"),
    "ffmpeg_install_cmd1":      (_FFMPEG_CMD1, _FFMPEG_CMD1, _FFMPEG_CMD1, _FFMPEG_CMD1),
    "ffmpeg_install_cmd2":      (_FFMPEG_CMD2, _FFMPEG_CMD2, _FFMPEG_CMD2, _FFMPEG_CMD2),
    "ffmpeg_install_step3":     ("3. Press Enter and confirm the installation", "3. Presione enter y confirme la instalación", "3. Pressione Enter e confirme a instalação", "3. Нажмите Enter и подтвердите установку"),
    "ffmpeg_install_step4":     ("4. Done. Close the app and open it again", "4. Listo. cierre la app y vuelva a abrirlo", "4. Pronto. Feche o app e abra novamente", "4. Готово. Закройте приложение и откройте снова"),
    "save_settings_msg":        ("Save settings", "Configuración guardada", "Configuração salva", "Настройки сохранены"),
    "download_folder_set":      ("Download folder set to:", "Carpeta de descarga establecida a:", "Pasta de download definida como:", "Папка загрузки установлена:"),
    "custom_folder_using":      ("Using custom download folder:", "Usando carpeta personalizada:", "Usando pasta personalizada:", "Используется пользовательская папка:"),
    "no_custom_folder":         ("No custom folder - will use 'videos' folder", "Sin carpeta personalizada - se usará carpeta 'videos'", "Sem pasta personalizada - será usada pasta 'videos'", "Нет пользовательской папки - будет использована папка 'videos'"),
    "created_videos_folder":    ("Created 'videos' folder for downloads", "Creada carpeta 'videos' para descargas", "Pasta 'videos' criada para downloads", "Создана папка 'videos' для загрузок"),
    "download_folder_updated":  ("Download folder updated to:", "Carpeta de descarga actualizada a:", "Pasta de download atualizada para:", "Папка загрузки обновлена:"),
    "all_params_cleared":       ("All parameters cleared", "Todos los parámetros borrados", "Todos os parâmetros limpos", "Все параметры очищены"),
    "ready_new_config":         ("Ready for new configuration", "Listo para nueva configuración", "Pronto para nova configuração", "Готов к новой настройке"),
    "restarting_process":       ("Restarting process...", "Reiniciando proceso...", "Reiniciando processo...", "Перезапуск процесса..."),
    "previous_process_killed":  ("Previous process terminated", "Proceso anterior terminado", "Processo anterior terminado", "Предыдущий процесс завершен"),
    "start_fields_restored":    ("Start fields restored to original state", "Campos 'Start' restaurados a su estado original", "Campos 'Start' restaurados ao estado original", "Поля 'Start' восстановлены в исходное состояние"),
    "console_restarted":        ("Console restarted - ready for new downloads", "Consola reiniciada - lista para nuevas descargas", "Console reiniciada - pronta para novos downloads", "Консоль перезапущена - готова к новым загрузкам"),
    "adjust_params":            ("Adjust the parameters and click Download", "Ajusta los parámetros y haz clic en Descargar", "Ajuste os parâmetros e clique em Baixar", "Настройте параметры и нажмите Загрузить"),
    "url_required":             ("Error: You must enter at least one URL", "Error: Debes ingresar al menos una URL", "Erro: Você deve inserir pelo menos uma URL", "Ошибка: Вы должны ввести хотя бы один URL"),
    "downloading_to":           ("Downloading to {} folder", "Descargando en carpeta {}", "Baixando para pasta {}", "Загрузка в папку {}"),
    "saving_config":            ("Saving configuration...", "Guardando configuración...", "Salvando configuração...", "Сохранение конфигурации..."),
    "config_updated":           ("config.json automatically updated", "config.json actualizado automáticamente", "config.json atualizado automaticamente", "config.json автоматически обновлен"),
    "starting_download":        ("Starting download...", "Iniciando descarga...", "Iniciando download...", "Начало загрузки..."),
    "process_completed":        ("Process completed", "Proceso completado", "Processo concluído", "Процесс завершен"),
    "close_confirm":            ("Are you sure you want to close the application!", "Estás seguro de que quieres cerrar la aplicación!", "Tem certeza que deseja fechar o aplicativo!", "Вы уверены, что хотите закрыть приложение?"),
    "exiting_app":              ("Exiting application...", "Saliendo de la aplicación...", "Saindo do aplicativo...", "Выход из приложения..."),
    "url_quantity":             ("URL Quantity", "Cantidad URL", "Quantidade URL", "Количество URL"),
    "recudown_title":           ("RecuDown 2", "RecuDown 2", "RecuDown 2", "RecuDown 2"),
    "cookies_placeholder":      ("Cookies", "Cookies", "Cookies", "Cookies"),
    "user_agent_placeholder":   ("User-Agent", "User-Agent", "User-Agent", "User-Agent"),
    "download_button":          ("⯈ Download", "⯈ Descargar", "⯈ Baixar", "⯈ Загрузить"),
    "url_placeholder":          ("URL {}", "URL {}", "URL {}", "URL {}"),
    "start_placeholder":        ("Start", "Inic", "Início", "Старт"),
    "end_placeholder":          ("End", "Fin", "Fim", "Конец"),
    "dur_placeholder":          ("Dur", "Dur", "Dur", "Длит"),
    "copy":                     ("Copy", "Copiar", "Copiar", "Копировать"),
    "reboot":                   ("Reboot", "Reiniciar", "Reiniciar", "Перезапуск"),
    "delete_all":               ("Delete all", "Limpiar", "Limpar", "Очистить"),
    "paste":                    ("Paste", "Pegar", "Colar", "Вставить"),
    "delete":                   ("Delete", "Eliminar", "Excluir", "Удалить"),
    "downloading_playlists":    ("Downloading Playlists: In progress", "Descargando listas: En proceso", "Baixando playlists: Em andamento", "Загрузка плейлистов: В процессе"),
    "downloading_playlists_complete": ("Downloading Playlists: Starting Download", "Descargando listas: Iniciando Descarga", "Baixando playlists: Iniciando Download", "Загрузка плейлистов: Начало загрузки"),
    "downloading":              ("Downloading", "Descargando", "Baixando", "Загрузка"),
    "remaining":                ("Remaining", "Restante", "Restante", "Осталось"),
    "completed":                ("Completed", "Completado", "Concluído", "Завершено"),
    "secs":                     ("secs", "segs", "segs", "сек"),
    "mins":                     ("mins", "mins", "mins", "мин"),
    "hours":                    ("hours", "horas", "horas", "час"),
    "kb_s":                     ("KB/s", "KB/s", "KB/s", "КБ/с"),
    "mb_s":                     ("MB/s", "MB/s", "MB/s", "МБ/с"),
    "write_error":              ("Error: Cannot write to download folder!", "Error: ¡No se puede escribir en la carpeta de descarga!", "Erro: Não é possível escrever na pasta de download!", "Ошибка: Невозможно записать в папку загрузки!"),
    "choose_folder":            ("Please choose a different folder with 'Save in'", "Por favor elige otra carpeta con 'Guardar en'", "Por favor escolha outra pasta com 'Salvar em'", "Пожалуйста, выберите другую папку с 'Сохранить в'"),
    "config_save_error":        ("Error: Failed to save configuration", "Error: Falló al guardar la configuración", "Erro: Falha ao salvar configuração", "Ошибка: Не удалось сохранить конфигурацию"),
    "exe_not_found":            ("Error: recu-windows-amd64.exe not found.", "Error: No se encontró recu-windows-amd64.exe", "Erro: recu-windows-amd64.exe não encontrado", "Ошибка: recu-windows-amd64.exe не найден"),
    "place_exe":                ("Please place the executable in the same folder", "Por favor coloca el ejecutable en la misma carpeta", "Por favor coloque o executável na mesma pasta", "Пожалуйста, поместите исполняемый файл в ту же папку"),
    "process_error":            ("Error starting process: {}", "Error al iniciar proceso: {}", "Erro ao iniciar processo: {}", "Ошибка запуска процесса: {}"),
    "downloading_html_complete": ("Downloading HTML: Complete", "Descargando HTML: Completado", "Baixando HTML: Concluído", "Загрузка HTML: Завершено"),
    "getting_link_complete":    ("Getting Link: Complete", "Obteniendo enlace: Completado", "Obtendo link: Concluído", "Получение ссылки: Завершено"),
    "browser_launched_debug":   ("{} launched with debug ✓", "{} lanzado con debug ✓", "{} iniciado com debug ✓", "{} запущен с отладкой ✓"),
    "browser_already_open_debug": ("{} with debug already open ✓", "{} con debug ya estaba abierto ✓", "{} com debug já estava aberto ✓", "{} с отладкой уже был открыт ✓"),
    "login_prompt":             ("Log in at recu.me if you're not, or", "Logueate en recu.me si no lo estás o", "Faça login em recu.me se ainda não estiver ou", "Войдите на recu.me, если вы ещё не вошли, или"),
    "paste_cookies_prompt":     ("Import cookies from an active session", "Importar cookies de una sesion activa", "Importar cookies de uma sessão ativa", "Импорт файлов cookie из активной сессии"),
    "cookies_ua_updated":       ("Cookies and User-Agent updated ✓", "Cookies y User-Agent actualizados ✓", "Cookies e User-Agent atualizados ✓", "Cookies и User-Agent обновлены ✓"),
    "no_debug_browser":         ("No browser with debug open", "No hay navegador con debug abierto", "Nenhum navegador com debug aberto", "Нет браузера с отладкой"),
    "open_debug_browser":       ("1. Close the app", "1. Cerrá la app", "1. Feche o app", "1. Закройте приложение"),
    "close_browser":            ("2. Run the app again", "2. Ejecutá la app de nuevo", "2. Execute o app novamente", "2. Запустите приложение снова"),
    "run_app_again":            ("3. The debug browser will open", "3. El navegador con debug se abrirá", "3. O navegador com debug será aberto", "3. Браузер с отладкой откроется"),
    "login_recu":               ("4. Log in at recu.me", "4. Logueate en recu.me", "4. Faça login em recu.me", "4. Войдите на recu.me"),
    "click_again":              ("5. Click ⭮ update cookies", "5. Clic en ⭮ actualizar cookies", "5. Clique em ⭮ atualizar cookies", "5. Нажмите ⭮ обновить cookies"),
    "update_cookies_tooltip":   ("Update cookies", "Actualizar cookies", "Atualizar cookies", "Обновить cookies"),
    "inject_cookies_tooltip":   ("Import cookies", "Importar cookies", "Importar cookies", "Импорт cookies"),
    "cookies_injected_ok":      ("Imported {ok} cookies, {fail} failed ✓", "Importadas {ok} cookies, {fail} fallidas ✓", "Importadas {ok} cookies, {fail} falharam ✓", "Импортировано {ok}, ошибок {fail} ✓"),
    "cookies_invalid_format":   ("Invalid cookie format (must be 'name=value; ...' or Cookie-Editor JSON)", "Formato inválido (debe ser 'nombre=valor; ...' o JSON de Cookie-Editor)", "Formato inválido (deve ser 'nome=valor; ...' ou JSON do Cookie-Editor)", "Неверный формат (должно быть 'имя=значение; ...' или JSON Cookie-Editor)"),
    "cookies_inject_header":    ("Import cookies", "Importar cookies", "Importar cookies", "Импорт cookies"),
    "cookies_inject_hint":      ("Paste session cookies here", "Pegar cookies de sesión aquí", "Colar cookies de sessão aqui", "Вставить cookies сессии здесь"),
    "cookies_inject_confirm":   ("Import", "Importar", "Importar", "Импорт"),
    "cookies_export_btn":       ("Export", "Exportar", "Exportar", "Экспорт"),
    "cookies_inject_success":   ("Login cookies imported successfully ✓", "Cookies de login importadas correctamente ✓", "Cookies de login importadas com sucesso ✓", "Cookies входа успешно импортированы ✓"),
    "cookies_inject_failed":    ("Failed to import cookies: {err}", "Error al importar cookies: {err}", "Falha ao importar cookies: {err}", "Ошибка импорта cookies: {err}"),
    "tab_reloaded":             ("Tab reloaded ✓", "Pestaña recargada ✓", "Aba recarregada ✓", "Вкладка перезагружена ✓"),
    "no_cookies_ua":            ("No cookies or User-Agent", "No hay cookies ni User-Agent", "Sem cookies ou User-Agent", "Нет cookies или User-Agent"),
    "press_refresh_cookies":    ("Press ⭮ to obtain them automatically.", "Presione ⭮ para obtenerlas automáticamente.", "Pressione ⭮ para obtê-las automaticamente.", "Нажмите ⭮, чтобы получить их автоматически."),
    "skipping_completed":       ("{n}/{total} URL(s) already downloaded, skipping", "{n}/{total} URL(s) ya descargadas, omitiendo", "{n}/{total} URL(s) já baixadas, ignorando", "{n}/{total} URL уже загружено, пропуск"),
    "url_bad_times":            ("URL {n} failed, verify the times", "URL {n} fallo verifica los tiempos", "URL {n} falhou, verifique os tempos", "URL {n} не удалось, проверьте времена"),
    "url_bad_times_fix":        ("Start/End fix them and press Download", "Inic/Fin corrigelos y pulsa Descargar", "Início/Fim corrija e clique em Baixar", "Старт/Конец исправьте и нажмите Загрузить"),
}
_LANGS = ("English", "Español", "Português", "Русский")
TRANSLATIONS = {lang: {k: v[i] for k, v in _T.items()} for i, lang in enumerate(_LANGS)}


# ============================================================
#  Detección de navegadores
# ============================================================
_BROWSERS = {
    "Slimjet": [("PF", r"Slimjet\slimjet.exe"), ("PF86", r"Slimjet\slimjet.exe"),
                ("LOCAL", r"Slimjet\Application\slimjet.exe")],
    "Opera GX": [("LOCAL", r"Programs\Opera GX\opera.exe"),
                 ("LOCAL", r"Programs\Opera GX\launcher.exe"),
                 ("PF", r"Opera GX\opera.exe"),
                 ("PF86", r"Opera GX\opera.exe")],
    "Chrome": [("PF", r"Google\Chrome\Application\chrome.exe"),
               ("PF86", r"Google\Chrome\Application\chrome.exe"),
               ("LOCAL", r"Google\Chrome\Application\chrome.exe")],
    "Edge": [("PF86", r"Microsoft\Edge\Application\msedge.exe"),
             ("PF", r"Microsoft\Edge\Application\msedge.exe")],
    "Brave": [("PF", r"BraveSoftware\Brave-Browser\Application\brave.exe"),
              ("PF86", r"BraveSoftware\Brave-Browser\Application\brave.exe")],
    "Vivaldi": [("LOCAL", r"Vivaldi\Application\vivaldi.exe")],
    "Chromium": [("LOCAL", r"Chromium\Application\chrome.exe")],
    "Opera": [("LOCAL", r"Programs\Opera\opera.exe"), ("PF", r"Opera\opera.exe"),
              ("PF86", r"Opera\opera.exe"), ("LOCAL", r"Programs\Opera\launcher.exe"),
              ("PF", r"Opera\launcher.exe"), ("PF86", r"Opera\launcher.exe")],
}


def _resolve_browser(name):
    env = {"PF": os.environ.get('ProgramFiles', ''),
           "PF86": os.environ.get('ProgramFiles(x86)', ''),
           "LOCAL": os.environ.get('LOCALAPPDATA', '')}
    for k, rel in _BROWSERS.get(name, []):
        base = env.get(k)
        if base:
            full = os.path.join(base, rel)
            if os.path.exists(full):
                return name, full
    return None, None


def get_default_browser_exe():
    try:
        import winreg
        k = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Windows\Shell\Associations\UrlAssociations\http\UserChoice")
        prog_id, _ = winreg.QueryValueEx(k, "ProgId")
        winreg.CloseKey(k)
        low = prog_id.lower()

        if "operagx" in low or "opera gx" in low:
            return _resolve_browser("Opera GX")
        if "chrome" in low and "chromium" not in low:
            return _resolve_browser("Chrome")
        if "edge" in low or "msedge" in low:
            return _resolve_browser("Edge")
        if "brave" in low:
            return _resolve_browser("Brave")
        if "vivaldi" in low:
            return _resolve_browser("Vivaldi")
        if "slimjet" in low:
            return _resolve_browser("Slimjet")
        if "opera" in low:
            return _resolve_browser("Opera")
        if "chromium" in low:
            return _resolve_browser("Chromium")
    except Exception:
        pass
    return None, None


def find_chromium_browser():
    for name in ("Slimjet", "Edge", "Chrome", "Opera GX", "Brave",
                 "Vivaldi", "Chromium", "Opera"):
        found = _resolve_browser(name)
        if found[0]:
            return found
    return None, None


def get_process_using_port(port=9222):
    try:
        kw, cf = _subprocess_kwargs()
        r = subprocess.run(['netstat', '-ano'], capture_output=True, text=True,
                           timeout=5, creationflags=cf, **kw)
        for line in r.stdout.splitlines():
            p = line.split()
            if len(p) >= 5 and p[1].endswith(f':{port}') and p[3] == 'LISTENING':
                return int(p[4])
    except Exception:
        pass
    return None


def kill_process_by_pid(pid):
    try:
        kw, cf = _subprocess_kwargs()
        return subprocess.run(['taskkill', '/F', '/PID', str(pid), '/T'],
                              capture_output=True, text=True, timeout=10,
                              creationflags=cf, **kw).returncode == 0
    except Exception:
        return False


def kill_all_chromium_browsers():
    kw, cf = _subprocess_kwargs()
    for proc in ("msedge.exe", "chrome.exe", "brave.exe", "vivaldi.exe",
                 "slimjet.exe", "opera.exe", "chromium.exe", "yandex.exe"):
        try:
            subprocess.run(['taskkill', '/F', '/IM', proc, '/T'],
                           capture_output=True, timeout=5,
                           creationflags=cf, **kw)
        except Exception:
            pass


def launch_browser_with_debug():
    try:
        name, exe = get_default_browser_exe() or find_chromium_browser()
        if not exe:
            return False, "No se encontró ningún navegador Chromium instalado", None
        profile = os.path.join(tempfile.gettempdir(), "recudown_browser_profile")
        os.makedirs(profile, exist_ok=True)

        active = False
        try:
            import websocket
            r = urlopen_localhost("http://127.0.0.1:9222/json", timeout=2)
            targets = json.loads(r.read().decode())
            for t in targets:
                if t.get("type") == "page" and t.get("webSocketDebuggerUrl"):
                    try:
                        ws = websocket.create_connection(t["webSocketDebuggerUrl"], timeout=2)
                        ws.close()
                        active = True
                        break
                    except Exception:
                        pass
        except Exception:
            pass

        if active:
            return True, "ya estaba abierto", name

        pid = get_process_using_port(9222)
        if pid:
            kill_process_by_pid(pid)
            time.sleep(1)
            if get_process_using_port(9222):
                kill_all_chromium_browsers()
                time.sleep(2)

        try:
            subprocess.Popen(
                [exe, '--remote-debugging-port=9222',
                 '--remote-allow-origins=*',
                 f'--user-data-dir={profile}',
                 '--no-first-run',
                 '--no-default-browser-check',
                 'https://es.recu.me/'],
                creationflags=subprocess.CREATE_NO_WINDOW)
            return True, "lanzado", name
        except Exception as e:
            return False, f"Error al lanzar {name}: {e}", name
    except Exception:
        return False, "Error al lanzar navegador", None


# ============================================================
#  CDP: lectura
# ============================================================
def _cdp_target_ws(port=9222):
    try:
        import websocket  # noqa
    except ImportError:
        return None, "Falta websocket-client"
    try:
        r = urlopen_localhost(f"http://127.0.0.1:{port}/json", timeout=3)
        targets = json.loads(r.read().decode())
    except Exception as e:
        return None, f"puerto cerrado ({e})"
    if not targets:
        return None, "sin pestañas"
    target = next((t for t in targets if t.get("type") == "page"
                   and "recu" in t.get("url", "").lower()), None)
    target = target or next((t for t in targets if t.get("type") == "page"), None)
    if not target or not target.get("webSocketDebuggerUrl"):
        return None, "sin websocket"
    return target["webSocketDebuggerUrl"], None


def _cdp_call(ws_url, method, params=None, timeout=3):
    import websocket
    ws = websocket.create_connection(ws_url, timeout=timeout)
    try:
        ws.send(json.dumps({"id": 1, "method": method, "params": params or {}}))
        return json.loads(ws.recv())
    finally:
        try: ws.close()
        except Exception: pass


def get_user_agent_via_cdp(port=9222):
    ws_url, err = _cdp_target_ws(port)
    if err:
        return None, err
    try:
        resp = _cdp_call(ws_url, "Runtime.evaluate",
                         {"expression": "navigator.userAgent", "returnByValue": True})
        return resp["result"]["result"].get("value"), None
    except Exception as e:
        return None, str(e)


def get_cookies_via_cdp(port=9222, domain_filter="recu.me"):
    ws_url, err = _cdp_target_ws(port)
    if err:
        return None, err
    try:
        resp = _cdp_call(ws_url, "Network.getAllCookies")
    except Exception as e:
        return None, f"error WS: {e}"

    cookies = resp.get("result", {}).get("cookies", [])
    de_recu = [c for c in cookies if "recu" in c.get("domain", "").lower()]
    if not de_recu:
        return None, "sin cookies de recu.me"

    login_ok = any(
        (c.get("name") == "ref" and c.get("value") == "recuto")
        or (c.get("name") == "ref_" and c.get("value") == "_")
        or c.get("name") in ("ref_ets", "akey", "mid", "cf_clearance")
        for c in de_recu)
    if not login_ok:
        return {c["name"]: c.get("value", "") for c in de_recu if c.get("name")}, "sin login"

    de_recu.sort(
        key=lambda c: (500 * c.get("domain", "").startswith(".")) +
                      (100 * (c.get("path", "/") == "/")) +
                      (min(c.get("expires", 0), 999) / 1000 if c.get("expires", 0) > 0 else 0),
        reverse=True)
    return {c["name"]: c.get("value", "") for c in de_recu if c.get("name")}, None


def get_video_duration_via_cdp(port=9222, expected_url=None):
    ws_url, err = _cdp_target_ws(port)
    if err:
        return None, err
    try:
        resp = _cdp_call(ws_url, "Runtime.evaluate", {"expression":
            "(function(){var e=document.querySelector('.video-length');"
            "return {url:location.href, dur:e?e.textContent.trim():null};})()",
            "returnByValue": True})
        data = resp.get("result", {}).get("result", {}).get("value") or {}
        if expected_url and data.get("url"):
            w = urlparse(expected_url).path.rstrip('/')
            g = urlparse(data["url"]).path.rstrip('/')
            if w and g and w != g:
                return None, f"pestaña en {g!r}, se esperaba {w!r}"
        return data.get("dur"), None
    except Exception as e:
        return None, str(e)


def reload_tab_via_cdp(port=9222, wait_seconds=3.0):
    import websocket
    ws_url, err = _cdp_target_ws(port)
    if err:
        return False, err
    try:
        ws = websocket.create_connection(ws_url, timeout=5)
        mid = 0

        def send(method, params=None):
            nonlocal mid
            mid += 1
            ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
            return mid

        send("Page.enable")
        send("Page.reload", {"ignoreCache": True})

        deadline = time.time() + wait_seconds
        while time.time() < deadline:
            time.sleep(0.3)
            try:
                rid = send("Runtime.evaluate",
                           {"expression": "document.readyState", "returnByValue": True})
                ws.settimeout(1.0)
                for _ in range(20):
                    resp = json.loads(ws.recv())
                    if resp.get("id") == rid:
                        if resp.get("result", {}).get("result", {}).get("value") == "complete":
                            ws.close()
                            return True, None
                        break
            except Exception:
                continue

        ws.close()
        return True, None
    except Exception as e:
        return False, str(e)


# ============================================================
#  CDP: inyección
# ============================================================
_LOGIN_NAMES = {"ref", "ref_", "ref_ets", "akey", "mid", "cf_clearance",
                "session", "sessionid", "auth", "token", "jwt"}
_SS_MAP = {"no_restriction": "None", "lax": "Lax", "strict": "Strict", None: "None", "": "None"}


def _parse_cookies(s):
    s = (s or "").strip()
    if s.startswith("["):
        try:
            return [{
                "name": c["name"], "value": c.get("value", ""),
                "expires": c.get("expirationDate") or c.get("expires"),
                "domain": c.get("domain"), "path": c.get("path", "/"),
                "secure": bool(c.get("secure", True)),
                "httpOnly": bool(c.get("httpOnly", False)),
                "sameSite": _SS_MAP.get(c.get("sameSite"), "None"),
            } for c in json.loads(s) if isinstance(c, dict) and c.get("name")]
        except Exception:
            pass
    return [{"name": k.strip(), "value": v.strip()}
            for p in s.split(";") if "=" in p
            for k, v in [p.split("=", 1)] if k.strip()]


def inject_cookies_via_cdp(cookie_string, url="https://recu.me", port=9222,
                           reload_page=True, recu_launcher=None, persist_days=365):
    try:
        import websocket
    except ImportError:
        return False, "Falta websocket-client", {}

    items = _parse_cookies(cookie_string)
    if not items:
        return False, "sin cookies válidas", {}

    ws_url, err = _cdp_target_ws(port)
    if err:
        return False, f"CDP: {err}", {}

    host = urlparse(url).netloc.split(":")[0].lstrip("www.")
    default_domain = f".{host}" if host else ".recu.me"
    default_exp = time.time() + persist_days * 86400

    try:
        ws = websocket.create_connection(ws_url, timeout=5)
    except Exception as e:
        return False, f"WS: {e}", {}

    stats = {"ok": 0, "fail": 0, "errors": []}
    mid = 0

    def send(method, params=None):
        nonlocal mid
        mid += 1
        ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        try:
            return json.loads(ws.recv())
        except Exception:
            return {}

    send("Network.enable")
    for it in items:
        name = it["name"]
        try:
            exp = float(it["expires"]) if it.get("expires") else default_exp
        except (TypeError, ValueError):
            exp = default_exp
        params = {
            "name": name, "value": it.get("value", ""),
            "domain": it.get("domain") or default_domain,
            "path": it.get("path", "/"),
            "secure": it.get("secure", True),
            "httpOnly": it.get("httpOnly", name in _LOGIN_NAMES),
            "sameSite": it.get("sameSite") or "None",
            "expires": exp,
        }
        r = send("Network.setCookie", params)
        if r.get("result", {}).get("success"):
            stats["ok"] += 1
        else:
            stats["fail"] += 1
            stats["errors"].append(f"{name}: {r.get('error', {}).get('message', '?')}")

    if reload_page and stats["ok"]:
        send("Page.reload", {"ignoreCache": True})

    try:
        ws.close()
    except Exception:
        pass

    if recu_launcher is not None:
        try:
            recu_launcher.console.append(
                f"> {recu_launcher.tr_text('cookies_injected_ok').format(ok=stats['ok'], fail=stats['fail'])}")
            if reload_page and stats["ok"]:
                recu_launcher.console.append(f"> {recu_launcher.tr_text('tab_reloaded')}")
        except Exception:
            pass

    return stats["ok"] > 0, None, stats


# ============================================================
#  ProcessReader
# ============================================================
class ProcessReader(QObject):
    output_signal = Signal(str)
    finished_signal = Signal()
    video_completed_signal = Signal(str, str, int)

    def __init__(self, process, download_folder, sound_path, recu_launcher,
                 url_markers, url_path_counts=None, url_row_map=None, urls_data=None):
        super().__init__()
        self.process = process
        self.download_folder = download_folder
        self.sound_path = sound_path
        self.rl = recu_launcher
        self.last_line = ""
        self.video_counter = {}
        self.pending_deletes = set()
        self.url_markers = url_markers
        self.url_path_counts = url_path_counts or {}
        self.url_row_map = url_row_map or {}
        self.urls_data = urls_data or []
        self._no_cookies_shown = False
        self._in_help = False
        threading.Thread(target=self.read_output, daemon=True).start()

    def read_output(self):
        try:
            for raw in iter(self.process.stdout.readline, ''):
                line = raw.strip()
                if "Process completed" in line:
                    continue
                if "Completed:" in line:
                    self.on_completed(line)
                    continue
                if "Downloading:" not in line:
                    if line == self.last_line:
                        continue
                    self.last_line = line
                if line and (f := self.fmt(line)):
                    self.output_signal.emit(f)
        except Exception as e:
            self.output_signal.emit(f"> Error lectura proceso: {e}")
        finally:
            self._cleanup_pending_deletes()
            self.finished_signal.emit()

    def _cleanup_pending_deletes(self):
        for p in list(self.pending_deletes):
            for _ in range(20):
                try:
                    if os.path.exists(p):
                        os.remove(p)
                    self.pending_deletes.discard(p)
                    break
                except OSError:
                    time.sleep(0.5)

    def fmt(self, line):
        if "Process completed" in line or "timestamps is in wrong format:" in line:
            return ""
        if "Completed:" in line and "✓" not in line:
            return ""
        for s in ("Downloading HTML:", "Getting Link to Playlist:", "Downloading Playlist:"):
            if (s in line and "Complete" in line) or line == s:
                return ""
        line = re.sub(r'\x1b\[[0-9;]*[A-Za-z]', '', line)

        if "Please fill in the config.json" in line:
            self._in_help = True
            self.rl._last_run_no_cookies = True
            if not self._no_cookies_shown:
                self._no_cookies_shown = True
                return (f'> {self.rl.tr_text("no_cookies_ua")}<br>'
                        f'> {self.rl.tr_text("press_refresh_cookies")}')
            return ""
        if self._in_help:
            if line.strip() in ("URLs to Download", "Cookies", "User-Agent"):
                return ""
            self._in_help = False

        if "Downloading Playlists:" in line:
            key = 'downloading_playlists_complete' if "Complete" in line else 'downloading_playlists'
            return f"> {self.rl.tr_text(key)}"
        if "Downloading:" in line and "Remaining:" in line and ("KB/s" in line or "MB/s" in line):
            return _format_progress(line, self.rl.tr_text, self.rl.download_language)
        if "Completed:" in line and "✓" in line:
            m = re.search(r'Completed:\s*(.+?)\s*✓', line)
            if m:
                return f"> {self.rl.tr_text('completed')}: {m.group(1)} ✓"
        if "[URL" in line and "Completed:" in line:
            m = re.search(r'(\[URL \d+\])\s*Completed:\s*(.+?)\s*✓', line)
            if m:
                return f"> {m.group(1)} {self.rl.tr_text('completed')}: {m.group(2)} ✓"
        return f"> {line}"

    def on_completed(self, completed_line):
        try:
            cleaned = re.sub(r'\x1b\[[0-9;]*[A-Za-z]', '', completed_line)
            found_index = next((i for i, m in self.url_markers.items() if m in cleaned), None)
            m = (re.search(r'Completed:\s*([^\s:]+(?:\.ts)?)(?::https://|$)', cleaned)
                 or re.search(r'Completed:\s*([^:]+?)(?:\.ts|:https://|$)', cleaned))
            if not m:
                return
            filename = m.group(1).strip()
            if " (" in filename and filename.endswith('.ts'):
                filename = filename.split(" (")[0] + ".ts"
            if not filename.endswith('.ts'):
                filename += '.ts'
            display = self.fmt_filename(filename)
            marker_idx = found_index or self.find_url_index(display)
            row_idx_1based = (self.url_row_map[marker_idx] + 1
                              if marker_idx in self.url_row_map else marker_idx)
            self.video_counter[display] = self.video_counter.get(display, 0) + 1
            n = self.video_counter[display]
            repeated = any(count > 1 and path.strip('/').split('/')[0] in display
                           for path, count in self.url_path_counts.items())
            planned = f"{display} ({n})" if repeated else display

            if os.path.exists(self.sound_path):
                try:
                    threading.Thread(target=lambda: winsound.PlaySound(
                        self.sound_path, winsound.SND_FILENAME | winsound.SND_ASYNC),
                        daemon=True).start()
                except Exception:
                    pass

            base = planned
            for marker in self.url_markers.values():
                if marker in base:
                    base = base.replace(marker, '').strip('_')

            actual_name = self.rename_file_immediately(filename, base) or planned

            try:
                if self.urls_data and 0 <= marker_idx - 1 < len(self.urls_data):
                    u_, s_, e_, d_, _ = self.urls_data[marker_idx - 1]
                    fname = actual_name if actual_name.endswith(".ts") else f"{actual_name}.ts"
                    if hasattr(self.rl, "_mark_completed"):
                        self.rl._mark_completed(
                            self.download_folder, u_, s_, e_, d_, fname, 0)
            except Exception:
                pass

            self.video_completed_signal.emit(actual_name, actual_name, row_idx_1based)
            self.output_signal.emit(
                f"> {self.rl.tr_text('completed')} URL {marker_idx}: {actual_name} ✓")
        except Exception:
            pass

    def find_url_index(self, filename):
        return next((i for i, m in self.url_markers.items() if m in filename),
                    min(len(self.video_counter) + 1, len(self.url_markers)))

    def rename_file_immediately(self, original, new_basename):
        try:
            if not original.endswith('.ts'):
                original += '.ts'
            base, ext = os.path.splitext(original)
            cands = []
            p = os.path.join(self.download_folder, original)
            if os.path.exists(p):
                cands.append(p)
            for i in range(1, 100):
                for alt in (f"{base}({i}){ext}", f"{base} ({i}){ext}"):
                    p = os.path.join(self.download_folder, alt)
                    if os.path.exists(p):
                        cands.append(p)
            if not cands:
                return None
            cands.sort(key=lambda p: os.path.getmtime(p), reverse=True)
            actual_file = os.path.basename(cands[0])

            rl = self.rl
            if rl and hasattr(rl, '_finalize_named_file'):
                new_name = rl._finalize_named_file(
                    self.download_folder, actual_file, 0, use_index_suffix=False)
                if new_name:
                    return new_name[:-3] if new_name.endswith('.ts') else new_name
            return None
        except Exception:
            return None

    def fmt_filename(self, filename):
        return format_video_name(filename, getattr(self.rl, 'rename_format', 'yyyy-mm-dd'))


# ============================================================
#  Menús
# ============================================================
def create_console_context_menu(console, rl=None):
    menu = QMenu()
    menu.setStyleSheet(MENU_STYLE)

    def copy_txt():
        if rl and hasattr(rl, '_copy_console_clean'):
            rl._copy_console_clean()
        else:
            QApplication.clipboard().setText(console.toPlainText())

    menu.addAction(make_menu_item(menu, "📄", rl.tr_text("copy") if rl else "Copy",
                                  copy_txt, "4px 3px 4px 8px", "6px 4px 6px 3px"))
    if rl:
        menu.addAction(make_menu_item(menu, "🔄", rl.tr_text("reboot"),
                                      rl.restart_process, "4px 3px 4px 7px", "6px 8px 6px 1px"))
        menu.addAction(make_menu_item(menu, "🗑️", rl.tr_text("delete_all"),
                                      rl.delete_all_parameters, "4px 3px 4px 7px", "6px 8px 6px 1px"))
    menu.aboutToShow.connect(
        lambda: menu.setFixedWidth(125 if rl and rl.download_language == "Русский" else 112))
    return menu


def _clear_row_siblings(url_widget):
    parent = url_widget.parent()
    if not parent:
        return
    lay = parent.layout()
    if not lay:
        return

    container = None
    p = url_widget.parent()
    while p:
        if isinstance(p, URLContainerWidget):
            container = p
            break
        p = p.parent()

    if container:
        for i, (u, ini, fin, dur, fr) in enumerate(container.row_frames):
            if u is not url_widget:
                continue
            if isinstance(ini, QPushButton) and hasattr(ini, 'original_ini_widget'):
                orig = ini.original_ini_widget
                lay.removeWidget(ini)
                ini.hide()
                orig.show()
                lay.insertWidget(1, orig)
                container.row_frames[i] = (u, orig, fin, dur, fr)
                if i in container.row_states:
                    container.row_states[i]['has_play_button'] = False
            break

    for i in range(lay.count()):
        w = lay.itemAt(i).widget()
        if isinstance(w, QLineEdit) and w is not url_widget:
            w.clear()
            w._auto_set = False
            w._for_url = None


def create_context_menu(widget, is_url=False, parent=None):
    menu = QMenu()
    menu.setStyleSheet(MENU_STYLE)
    rl = parent.get_recu_launcher() if parent and hasattr(parent, 'get_recu_launcher') else None

    def paste():
        t = QApplication.clipboard().text().strip()
        if not t:
            return
        if is_url and parent and hasattr(parent, 'clean_url'):
            widget.setText(parent.clean_url(t))
            widget.original_url = t
            _clear_row_siblings(widget)
        else:
            widget.setText(t)

    def copy():
        if hasattr(widget, 'hasSelectedText') and widget.hasSelectedText():
            widget.copy()
        else:
            clip = QApplication.clipboard()
            clip.setText(widget.original_url if is_url and getattr(widget, 'original_url', None)
                         else widget.text())

    def delete():
        if hasattr(widget, 'hasSelectedText') and widget.hasSelectedText():
            widget.backspace()
        else:
            widget.clear()

    for icon, key, cb, pad in (
        ("📋", "paste", paste, "6px 8px 6px 2px"),
        ("📄", "copy", copy, "6px 8px 6px 2px"),
        ("🗑️", "delete", delete, "6px 8px 6px 1px"),
    ):
        txt = rl.tr_text(key) if rl else key.title()
        menu.addAction(make_menu_item(menu, icon, txt, cb, "4px 3px 4px 8px", pad))

    menu.aboutToShow.connect(
        lambda: menu.setFixedWidth(123 if rl and rl.download_language == "Русский" else 112))
    return menu


# ============================================================
#  Estilos QLineEdit
# ============================================================
_LE_MAIN = (
    "QLineEdit{"
    "  background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, "
    "    stop:0 #50575d, stop:0.48 #34383f, stop:0.52 #2a2e33, stop:1 #222529);"
    "  color:#e0e0e0;"
    "  border-top: 1px solid #6c747d;"
    "  border-left: 1px solid #50575d;"
    "  border-right: 1px solid #1f2226;"
    "  border-bottom: 1px solid #1a1c1f;"
    "  border-radius:6px;"
    "  padding:1px 4px 4px 8px;"
    "  selection-background-color:#4a6a8a;selection-color:#ffffff;}"
    "QLineEdit:focus{border:1px solid #bfbfbf;}"
    "QLineEdit:hover{"
    "  background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, "
    "    stop:0 #5c646b, stop:0.48 #40454d, stop:0.52 #34383f, stop:1 #2a2e33);"
    "}"
)

_LE_TIME = (
    "QLineEdit {"
    "  background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, "
    "    stop:0 #50575d, stop:0.48 #34383f, stop:0.52 #2a2e33, stop:1 #222529);"
    "  color: #e0e0e0;"
    "  border-top: 1px solid #6c747d;"
    "  border-left: 1px solid #50575d;"
    "  border-right: 1px solid #1f2226;"
    "  border-bottom: 1px solid #1a1c1f;"
    "  border-radius: 6px;"
    "  padding: 1px 1px 1px 4px;"
    "  selection-background-color: #4a6a8a;"
    "  selection-color: #ffffff;"
    "}"
    "QLineEdit:hover {"
    "  background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, "
    "    stop:0 #5c646b, stop:0.48 #40454d, stop:0.52 #34383f, stop:1 #2a2e33);"
    "  border-top: 1px solid #7a828b;"
    "  border-left: 1px solid #5c646b;"
    "}"
    "QLineEdit:focus {"
    "  background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, "
    "    stop:0 #50575d, stop:0.48 #34383f, stop:0.52 #2a2e33, stop:1 #222529);"
    "  border: 1px solid #bfbfbf;"
    "}"
)


def _attach_line_edit(widget, is_url, parent, double_click_paste=True):
    widget.setContextMenuPolicy(Qt.CustomContextMenu)
    widget.customContextMenuRequested.connect(
        lambda pos: create_context_menu(widget, is_url, parent).exec(widget.mapToGlobal(pos)))
    if not double_click_paste:
        return

    def dbl(event):
        if event.button() == Qt.LeftButton and (t := QApplication.clipboard().text().strip()):
            if is_url and parent and hasattr(parent, 'clean_url'):
                widget.original_url = t
                widget.setText(parent.clean_url(t))
                _clear_row_siblings(widget)
            else:
                widget.setText(t)
            event.accept()
            return
        QLineEdit.mouseDoubleClickEvent(widget, event)
    widget.mouseDoubleClickEvent = dbl


# ============================================================
#  QuickSettingsDialog
# ============================================================
class QuickSettingsDialog(QDialog):
    def __init__(self, parent=None, folder=None, mode="parallel", language="English", fmt="TS"):
        super().__init__(parent)
        self.parent_app = parent
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.original_language = language
        self.languages = ["English", "Español", "Português", "Русский"]
        self.rename_format_value = getattr(parent, 'rename_format', 'yyyy-mm-dd')

        if parent and hasattr(parent, 'top_bar'):
            tb = parent.top_bar
            pos = tb.mapToGlobal(tb.rect().bottomLeft())
            x = pos.x() + (tb.width() - 242) // 2
            y = pos.y() + 1
            sg = QApplication.primaryScreen().availableGeometry()
            x = max(0, min(x, sg.width() - 242))
            self.move(x, y)
        elif parent:
            g = parent.geometry()
            self.move(g.x() + (g.width() - 242) // 2, g.y() + (g.height() - 320) // 2)

        self.setStyleSheet(
            "QDialog{background-color:#1a1c1f;color:#bfbfbf;}"
            "QLabel{color:#bfbfbf;font-size:10pt;font-family:Arial;}"
            "QLineEdit{background-color:#34383f;color:#bfbfbf;border:1px solid #50575d;"
            "border-radius:4px;padding:4px;font:10pt Arial;"
            "selection-background-color:#4a6a8a;selection-color:#ffffff;}"
        )

        main = QFrame(self)
        main.setStyleSheet("QFrame{background-color:#1a1c1f;border:1px solid #50575d;}")
        ml = QVBoxLayout(main)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(0)

        self.title_bar = QFrame()
        self.title_bar.setFixedHeight(25)
        self.title_bar.setStyleSheet("background:#3c4048;border:none;")
        tl = QHBoxLayout(self.title_bar)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(0)
        self.title_label = QLabel(self.tr_text("settings_title"))
        self.title_label.setFont(QFont("Arial", 10, QFont.Bold))
        self.title_label.setStyleSheet("color:#bfbfbf;background:transparent;border:none;padding:0 8px 0 10px;")
        tl.addWidget(self.title_label)
        tl.addStretch()
        x = QPushButton("✕")
        x.setFixedSize(25, 25)
        x.setStyleSheet("QPushButton{color:#f0f0f0;background:transparent;border:none;"
                        "border-radius:0px;font:13pt Arial;padding:0;}"
                        "QPushButton:hover{background:#e74c3c;border-radius:0px;}"
                        "QPushButton:pressed{background:#c0392b;border-radius:0px;}")
        # La ✕ guarda (accept) y cierra: hereda el comportamiento del antiguo Save settings
        x.clicked.connect(lambda: (play_key_tap(), self.accept()))
        tl.addWidget(x)

        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setContentsMargins(11, 10, 11, 10)
        cl.setSpacing(8)

        _row = QHBoxLayout()
        _row.setContentsMargins(0, 0, 0, 0)
        _row.setSpacing(0)
        self.folder_label = self._lbl("save_videos_to")
        _row.addWidget(self.folder_label)
        _row.addStretch()
        cl.addLayout(_row)
        cl.addSpacing(2)

        fl = QHBoxLayout()
        fl.setSpacing(10)
        fl.setContentsMargins(0, 0, 0, 0)
        self.folder_path_edit = QLineEdit(folder or os.path.join(os.getcwd(), "videos"))
        self.folder_path_edit.setReadOnly(True)
        self.folder_path_edit.setFixedHeight(30)
        self.folder_path_edit.setStyleSheet(_LE_MAIN)
        self.folder_path_edit.setContextMenuPolicy(Qt.NoContextMenu)

        folder_frame = QWidget()
        folder_frame.setStyleSheet("background-color:#3c4048;border-radius:8px;")
        folder_frame.setFixedHeight(32)
        folder_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        ffl = QHBoxLayout(folder_frame)
        ffl.setContentsMargins(1, 1, 1, 1)
        ffl.setSpacing(0)
        ffl.addWidget(self.folder_path_edit)

        fb = QPushButton("📁")
        fb.setStyleSheet(BTN_QSS.replace("padding: 0px 0px 4px 0px;",
                                         "padding: 0px 1px 4px 2px;"))
        fb.setFixedSize(33, 30)
        fb.setFont(QFont("Arial", 10, QFont.Bold))
        fb.clicked.connect(self.browse_folder)

        fb_frame = QWidget()
        fb_frame.setStyleSheet("background-color:#3c4048;border-radius:8px;")
        fb_frame.setFixedSize(35, 32)
        fbl = QHBoxLayout(fb_frame)
        fbl.setContentsMargins(1, 1, 1, 1)
        fbl.setSpacing(0)
        fbl.addWidget(fb)

        fl.addWidget(folder_frame)
        fl.addWidget(fb_frame)
        cl.addLayout(fl)
        cl.addSpacing(2)

        self.mode_label, self.mode_btn = self._toggle(
            "download_mode", self.tr_text("parallel" if mode == "parallel" else "series"),
            self.toggle_mode, cl)
        self.format_label, self.format_btn = self._toggle(
            "change_format_to", fmt, self.toggle_format, cl)
        self.rename_label, self.rename_btn = self._toggle(
            "rename_videos", self.get_rename_text(language), self.toggle_rename, cl)
        self.language_label, self.language_btn = self._toggle(
            "change_language", language, self.toggle_language, cl)

        cl.addStretch()

        ml.addWidget(self.title_bar)
        ml.addWidget(content)
        QVBoxLayout(self).addWidget(main)
        self.layout().setContentsMargins(0, 0, 0, 0)

        self.setFixedSize(246, 265)
        self._initial = self._current_settings()
        self._drag = None

    def _current_settings(self):
        mt = self.mode_btn.text()
        mode = "parallel" if mt in (self.tr_text("parallel"), "Parallel", "Paralelo", "Паралл") else "series"
        return (self.folder_path_edit.text(), mode, self.language_btn.text(),
                self.format_btn.text(), self.rename_format_value)

    def _lbl(self, key):
        lb = QLabel("\u2009" + self.tr_text(key))
        lb.setFont(QFont("Arial", 10, QFont.Bold))
        lb.setStyleSheet("border:none;")
        return lb

    def _toggle(self, key, text, cb, parent_l):
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        lb = self._lbl(key)
        lb.setFixedWidth(140)

        btn = QPushButton(text)
        btn.setFixedSize(80, 30)
        btn.setFont(QFont("Arial", 10, QFont.Bold))
        btn.setStyleSheet(BTN_QSS)
        btn.clicked.connect(lambda: (play_key_tap(), cb()))

        frame = QWidget()
        frame.setStyleSheet("background-color:#3c4048;border-radius:8px;")
        frame.setFixedSize(82, 32)
        fl = QHBoxLayout(frame)
        fl.setContentsMargins(1, 1, 1, 1)
        fl.setSpacing(0)
        fl.addWidget(btn)

        row.addWidget(lb)
        row.addStretch()
        row.addWidget(frame)

        parent_l.addLayout(row)
        parent_l.addSpacing(2)
        return lb, btn

    def tr_text(self, key):
        return TRANSLATIONS.get(self.original_language, TRANSLATIONS["English"]).get(
            key, TRANSLATIONS["English"].get(key, key))

    def get_rename_text(self, lang):
        rf = getattr(self.parent_app, 'rename_format', 'yyyy-mm-dd')
        return self.tr_text({"dd-mm-yyyy": "dd_mm_yyyy", "yyyy-mm-dd": "yyyy_mm_dd"}.get(rf, "original"))

    def toggle_rename(self):
        c = self.rename_btn.text()
        cycle = [("dd_mm_yyyy", "dd-mm-yyyy"), ("yyyy_mm_dd", "yyyy-mm-dd"), ("original", "original")]
        for i, (label, val) in enumerate(cycle):
            if c == self.tr_text(label):
                next_label, next_val = cycle[(i + 1) % 3]
                self.rename_btn.setText(self.tr_text(next_label))
                self.rename_format_value = next_val
                return

    def toggle_mode(self):
        c = self.mode_btn.text()
        self.mode_btn.setText(self.tr_text("series") if c == self.tr_text("parallel")
                              else self.tr_text("parallel"))

    def toggle_language(self):
        c = self.language_btn.text()
        i = self.languages.index(c) if c in self.languages else 0
        self.language_btn.setText(self.languages[(i + 1) % len(self.languages)])

    def toggle_format(self):
        c = self.format_btn.text()
        self.format_btn.setText("MP4" if c == "TS" else "MKV" if c == "MP4" else "TS")

    def browse_folder(self):
        play_key_tap()
        f = QFileDialog.getExistingDirectory(
            self, "Select Download Folder", self.folder_path_edit.text(),
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        if f:
            self.folder_path_edit.setText(f)

    def update_dialog_language(self):
        for label, key in ((self.title_label, "settings_title"),
                           (self.folder_label, "save_videos_to"),
                           (self.mode_label, "download_mode"),
                           (self.format_label, "change_format_to"),
                           (self.language_label, "change_language"),
                           (self.rename_label, "rename_videos")):
            label.setText(self.tr_text(key))
        if self.mode_btn.text() in ("Parallel", "Serie", "Paralelo", "Série", "Паралл", "Серии"):
            self.mode_btn.setText(self.tr_text(
                "parallel" if self.parent_app and self.parent_app.download_mode == "parallel"
                else "series"))
        self.rename_btn.setText(self.get_rename_text(self.original_language))

    def save(self):
        mt = self.mode_btn.text()
        mode = "parallel" if mt in (self.tr_text("parallel"), "Parallel", "Paralelo", "Паралл") else "series"
        data = {"folder": self.folder_path_edit.text(), "mode": mode,
                "language": self.language_btn.text(), "format": self.format_btn.text(),
                "rename_format": self.rename_format_value}
        if self.parent_app:
            self.parent_app.download_folder = data["folder"]
            self.parent_app.download_mode = data["mode"]
            self.parent_app.download_language = data["language"]
            self.parent_app.download_format = data["format"]
            self.parent_app.rename_format = data["rename_format"]
            self.parent_app.update_ui_language()
            self.parent_app.save_download_config()
            if hasattr(self.parent_app, 'console'):
                self.parent_app.console.append(f"> {self.parent_app.tr_text('save_settings_msg')}")
        self.original_language = data["language"]
        self.update_dialog_language()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and self.title_bar.geometry().contains(e.pos()):
            self._drag = (e.globalPosition().toPoint(), self.pos())
        else:
            super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._drag:
            self.move(self._drag[1] + e.globalPosition().toPoint() - self._drag[0])
        else:
            super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        self._drag = None
        super().mouseReleaseEvent(e)

    def showEvent(self, e):
        super().showEvent(e)
        self.raise_()
        self.activateWindow()
        self.setFocus()


# ============================================================
#  FixedSpinBox
# ============================================================
class FixedSpinBox(QSpinBox):
    BTN_W, ARROW, ARROW_UP, RADIUS, PAD_RIGHT = 21, 3.2, 3.4, 5, 17

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(QFont("Arial", 11, QFont.Bold))
        self.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.setMouseTracking(True)
        self._hover = self._pressed = None
        self.setStyleSheet(
            "QSpinBox{color:#d0d0d0;background:#3c4048;border:1px solid #50575d;"
            f"border-radius:{self.RADIUS}px;padding:3px {self.PAD_RIGHT}px 3px 0px;"
            "selection-background-color:transparent;selection-color:#d0d0d0;}"
            "QSpinBox::up-button,QSpinBox::down-button{width:0;height:0;border:none;}"
            "QSpinBox::up-arrow,QSpinBox::down-arrow{width:0;height:0;image:none;}")
        le = self.lineEdit()
        le.setReadOnly(True)
        le.setAlignment(Qt.AlignCenter)
        le.setStyleSheet("QLineEdit{padding:0;margin:0;border:none;background:transparent;}")
        le.setMouseTracking(True)
        le.installEventFilter(self)
        le.deselect()
        self.valueChanged.connect(le.deselect)
        self.editingFinished.connect(le.deselect)

    def eventFilter(self, obj, event):
        if obj is self.lineEdit() and event.type() in (QEvent.Type.Enter, QEvent.Type.MouseMove):
            if self._hover is not None:
                self._set_hover(None)
        return super().eventFilter(obj, event)

    def _rect(self):
        return QRect(self.width() - self.BTN_W - 1, 1, self.BTN_W, max(self.height() - 2, 0))

    def _zone(self, pos):
        r = self._rect()
        if not r.contains(pos):
            return None
        return 'up' if pos.y() < r.y() + r.height() / 2.0 else 'down'

    def _set_hover(self, z):
        if z != self._hover:
            self._hover = z
            self.update()

    def enterEvent(self, e):
        self._set_hover(self._zone(self.mapFromGlobal(QCursor.pos())))

    def leaveEvent(self, e):
        self._set_hover(None)

    def mouseMoveEvent(self, e):
        self._set_hover(self._zone(e.position().toPoint()))
        super().mouseMoveEvent(e)

    def mousePressEvent(self, e):
        z = self._zone(e.position().toPoint()) if e.button() == Qt.LeftButton else None
        if z:
            self._pressed = z
            self.update()
            e.accept()
        else:
            super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self._pressed:
            if self._zone(e.position().toPoint()) == self._pressed:
                self.setValue(self.value() + (-1 if self._pressed == 'up' else 1))
                play_key_tap()
            self._pressed = None
            self.update()
            e.accept()
        else:
            super().mouseReleaseEvent(e)

    def focusInEvent(self, e):
        super().focusInEvent(e)
        self.lineEdit().deselect()

    def stepBy(self, steps):
        super().stepBy(-steps)

    def wheelEvent(self, e):
        self.setValue(self.value() + (-1 if e.angleDelta().y() > 0 else 1))
        e.accept()

    def paintEvent(self, e):
        super().paintEvent(e)
        r = self._rect()
        if r.width() <= 0 or r.height() <= 0:
            return
        half = r.height() / 2.0
        top = QRectF(r.x(), r.y(), self.BTN_W, half + 0.5)
        bot = QRectF(r.x(), r.y() + half + 0.5, self.BTN_W, half - 0.5)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(0.5, 0.5, self.width() - 1, self.height() - 1),
                            self.RADIUS, self.RADIUS)
        p.setClipPath(clip)
        active = self._pressed or self._hover
        p.fillRect(r, QColor("#3c4048"))
        ar = top if active == 'up' else (QRectF(bot.x(), bot.y() - 1, bot.width(), bot.height() + 1)
                                         if active == 'down' else None)
        if ar:
            p.fillRect(ar, QColor("#3a3f45" if self._pressed else "#60676f"))
        p.setPen(QColor("#50575d"))
        p.drawLine(r.x(), r.y(), r.x(), r.bottom())
        y_mid = int(r.y() + half + 0.5)
        p.drawLine(r.x(), y_mid, r.right() + 1, y_mid)
        if ar:
            p.setPen(QColor("#3c4048"))
            p.drawRect(ar.adjusted(0, 0, 0, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#e0e0e0"))
        cx = r.x() + r.width() / 2.0
        cy_up = top.y() + top.height() / 2.0
        p.drawPolygon([QPointF(cx, cy_up - self.ARROW_UP),
                       QPointF(cx - self.ARROW_UP, cy_up + self.ARROW_UP),
                       QPointF(cx + self.ARROW_UP, cy_up + self.ARROW_UP)])
        cy_dn = bot.y() + bot.height() / 2.0
        p.drawPolygon([QPointF(cx, cy_dn + self.ARROW),
                       QPointF(cx - self.ARROW, cy_dn - self.ARROW),
                       QPointF(cx + self.ARROW, cy_dn - self.ARROW)])


def _url_keypress(widget):
    _orig = widget.keyPressEvent
    def keyPressEvent(event):
        if event.matches(QKeySequence.StandardKey.Paste):
            t = QApplication.clipboard().text().strip()
            if t:
                p = widget.parent()
                while p and not isinstance(p, URLContainerWidget):
                    p = p.parent()
                clean = p.clean_url(t) if p and hasattr(p, 'clean_url') else t
                widget.original_url = t
                widget.insert(clean)
                _clear_row_siblings(widget)
                return
        _orig(event)
    return keyPressEvent


# ============================================================
#  URLContainerWidget
# ============================================================
class URLContainerWidget(QWidget):
    def __init__(self, parent=None, rows=5, line_height=30):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(3)
        self.row_frames = []
        self.row_states = {}
        self.url_width = 242
        self.time_width = 54
        self.line_height = line_height
        self.initial_visible_rows = 3
        self.cookie_ua_widget = None
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self._dur_timer = QTimer(self)
        self._dur_timer.setSingleShot(True)
        self._dur_timer.setInterval(1200)
        self._dur_timer.timeout.connect(self._autofill_duration)
        self._dur_pending = None

        for i in range(rows):
            frame = QFrame()
            frame.setStyleSheet("background:#3c4048;border-radius:8px;padding:0;")
            frame.setFixedHeight(line_height + 2)
            rl = QHBoxLayout(frame)
            rl.setContentsMargins(1, 1, 1, 1)
            rl.setSpacing(5)

            url = QLineEdit()
            url.setPlaceholderText(f"URL {i+1}")
            url.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            url.setFixedHeight(line_height)
            url.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            url.setStyleSheet(_LE_MAIN)
            url.keyPressEvent = _url_keypress(url)

            ini = QLineEdit()
            ini.setPlaceholderText("Start")
            fin = QLineEdit()
            fin.setPlaceholderText("End")
            dur = QLineEdit()
            dur.setPlaceholderText("Dur")

            self._time_validator = QRegularExpressionValidator(
                QRegularExpression(r"[0-9:,.;\-]*"), self)

            for w in (ini, fin, dur):
                w.setValidator(self._time_validator)
                w.setAlignment(Qt.AlignVCenter | Qt.AlignHCenter)
                w.setFixedWidth(self.time_width)
                w.setFixedHeight(line_height)
                w.setStyleSheet(_LE_TIME)
                w.editingFinished.connect(
                    lambda w=w: w.setText(normalize_time_separators(w.text())))

            dur.textEdited.connect(lambda w=dur: setattr(w, '_auto_set', False))

            _attach_line_edit(url, True, self)
            for w in (ini, fin, dur):
                _attach_line_edit(w, False, self)
            url.textChanged.connect(
                lambda u=url: (not getattr(u, 'original_url', None)) and u.text().strip()
                and setattr(u, 'original_url', self._full_url(u.text().strip())))
            url.textChanged.connect(lambda *_, idx=i: self._schedule_dur_check(idx))

            for w in (url, ini, fin, dur):
                rl.addWidget(w)
            self.layout.addWidget(frame)
            self.row_frames.append((url, ini, fin, dur, frame))

        for i in range(self.initial_visible_rows, rows):
            self.row_frames[i][4].setVisible(False)
        self.update_container_height(self.initial_visible_rows)

    def _schedule_dur_check(self, idx):
        self._dur_pending = idx
        self._dur_timer.start()

    def _autofill_duration(self):
        i = self._dur_pending
        if i is None or not (0 <= i < len(self.row_frames)):
            return
        u, ini, fin, dur_w, frame = self.row_frames[i]
        if not frame.isVisible() or not isinstance(dur_w, QLineEdit):
            return
        if self._start_text(ini) or (isinstance(fin, QLineEdit) and fin.text().strip()):
            return
        full = getattr(u, 'original_url', '') or (
            u.text().strip() if u.text().strip().startswith('http') else '')
        if not full:
            return

        if dur_w.text().strip() and not getattr(dur_w, '_auto_set', False):
            return

        if dur_w.text().strip() and getattr(dur_w, '_for_url', None) == full:
            return

        if dur_w.text().strip():
            dur_w.clear()
            dur_w._auto_set = False
            dur_w._for_url = None

        dur, err = get_video_duration_via_cdp(9222, expected_url=full)
        if dur and not dur_w.text().strip():
            dur_w.setText(dur)
            dur_w._for_url = full
            dur_w._auto_set = True

    def update_placeholders(self):
        rl = self.get_recu_launcher()
        if not rl:
            return
        for i, (u, ini, fin, dur, _) in enumerate(self.row_frames):
            u.setPlaceholderText(rl.tr_text("url_placeholder").format(i + 1))
            if isinstance(ini, QLineEdit):
                ini.setPlaceholderText(rl.tr_text("start_placeholder"))
            if isinstance(fin, QLineEdit):
                fin.setPlaceholderText(rl.tr_text("end_placeholder"))
            if isinstance(dur, QLineEdit):
                dur.setPlaceholderText(rl.tr_text("dur_placeholder"))

    def set_cookie_ua_widget(self, w): self.cookie_ua_widget = w

    def _start_text(self, ini):
        if isinstance(ini, QLineEdit):
            return ini.text().strip()
        if isinstance(ini, QPushButton) and hasattr(ini, 'original_ini_widget'):
            return ini.original_ini_widget.text().strip()
        return ""

    def save_backup_manual(self, is_closing=False, is_reboot=False):
        try:
            lines = []
            for i, (u, ini, fin, dur, fr) in enumerate(self.row_frames):
                if not fr.isVisible():
                    continue
                url = u.text().strip()
                full = (getattr(u, 'original_url', None) or self._full_url(url)) if url else ""
                s = self._start_text(ini)
                e = fin.text().strip() if isinstance(fin, QLineEdit) else ""
                d = dur.text().strip() if isinstance(dur, QLineEdit) else ""
                if not (full or s or e or d):
                    continue
                lines.append(f"  [URL {i+1}]")
                for lbl, val in (("URL", full), ("START", s), ("END", e), ("DUR", d)):
                    if val:
                        lines.append(f"  {lbl} = {val}")
                lines.append("")
            if not lines:
                return False
            content = "\n".join(lines).rstrip()
            sid = get_or_create_session_id()
            base = (os.path.dirname(sys.executable) if getattr(sys, 'frozen', False)
                    else os.path.dirname(os.path.abspath(__file__)))
            path = os.path.join(base, "backup.txt")
            sessions = []
            if os.path.exists(path):
                try:
                    with open(path, encoding="utf-8") as f:
                        bl = re.split(r'^\s*===== SESSION: (.+?) =====\s*$', f.read(), flags=re.MULTILINE)
                    sessions = [{'id': bl[i].strip(), 'content': bl[i+1].strip('\n')}
                                for i in range(1, len(bl) - 1, 2) if bl[i].strip()]
                except Exception:
                    sessions = []
            sessions = [s for s in sessions if s['id'] != sid]
            sessions.insert(0, {'id': sid, 'content': content})
            if is_reboot:
                reset_session_id()
            sessions = sessions[:10]
            out = []
            for s in sessions:
                out += [f"  ===== SESSION: {s['id']} =====", "", s['content'], ""]
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(out).rstrip() + "\n")
            return True
        except Exception:
            return False

    def update_container_height(self, qty):
        h = qty * (self.line_height + 2) + 3 * max(0, qty - 1)
        self.setFixedHeight(h)
        return h

    def save_row_state(self, i):
        if i >= len(self.row_frames):
            return False
        u, ini, fin, dur, _ = self.row_frames[i]
        state = {'url': u.text(), 'ini_text': self._start_text(ini),
                 'fin_text': fin.text() if isinstance(fin, QLineEdit) else '',
                 'dur_text': dur.text() if isinstance(dur, QLineEdit) else '',
                 'has_play_button': isinstance(ini, QPushButton),
                 'original_url': getattr(u, 'original_url', '')}
        if isinstance(ini, QPushButton):
            state.update({'video_filename': getattr(ini, 'video_filename', ''),
                          'renamed_filename': getattr(ini, 'renamed_filename', ''),
                          'original_ini_widget': ini.original_ini_widget})
        self.row_states[i] = state
        return True

    def restore_row_state(self, i):
        if i not in self.row_states:
            return False
        s = self.row_states[i]
        u, ini, fin, dur, _ = self.row_frames[i]
        u.setText(s['url'])
        if s['original_url']:
            u.original_url = s['original_url']
        if isinstance(ini, QLineEdit):
            ini.setText(s['ini_text'])
        if isinstance(fin, QLineEdit):
            fin.setText(s['fin_text'])
        if isinstance(dur, QLineEdit):
            dur.setText(s['dur_text'])
            dur._auto_set = False
            dur._for_url = s['original_url'] or None
        if s.get('has_play_button') and 'video_filename' in s:
            self.convert_to_play_button(s['video_filename'], s['renamed_filename'], i + 1)
        return True

    def clean_url(self, url):
        for p in ('https://es.recu.me/', 'http://es.recu.me/', 'https://recu.me/',
                  'http://recu.me/', 'https://es.', 'http://es.', 'https://', 'http://'):
            if url.startswith(p):
                return url.replace(p, '', 1)
        return url

    def get_urls_for_config(self):
        result = []
        for row_idx, (u, ini, fin, dur, fr) in enumerate(self.row_frames):
            if not fr.isVisible():
                continue
            t = u.text().strip()
            if not t:
                continue
            full = getattr(u, 'original_url', None) or self._full_url(t)
            u.original_url = full
            ini_text = self._start_text(ini)
            fin_text = fin.text().strip() if isinstance(fin, QLineEdit) else ""
            dur_text = dur.text().strip() if isinstance(dur, QLineEdit) else ""
            result.append([full, ini_text, fin_text, dur_text, row_idx])
        return result

    def _full_url(self, u):
        if u.startswith('http'):
            return u
        for w, *_ in self.row_frames:
            if getattr(w, 'original_url', None):
                return w.original_url
        return (f"https://es.recu.me/{u.lstrip('/')}" if 'recu.me/' in u else f"https://{u}")

    def update_visible_rows(self, qty):
        for i in range(len(self.row_frames)):
            if self.row_frames[i][4].isVisible():
                self.save_row_state(i)
        for i, (*_, frame) in enumerate(self.row_frames):
            frame.setVisible(i < qty)
        for i in range(qty):
            if i in self.row_states and not self.row_frames[i][0].text().strip():
                self.restore_row_state(i)
        self.update_container_height(qty)
        p = self.get_recu_launcher()
        if p and hasattr(p, 'adjust_window_height'):
            p.adjust_window_height()

    def convert_to_play_button(self, video_filename, renamed, url_index):
        i = url_index - 1
        if not (0 <= i < len(self.row_frames)):
            return 0
        u, ini, fin, dur, frame = self.row_frames[i]
        if not (frame.isVisible() and isinstance(ini, QLineEdit)):
            return 0
        pb = QPushButton("▶")
        pb.setFixedSize(54, 30)
        pb.setStyleSheet(
            "QPushButton{background:#484e55;color:#d0d0d0;border:1px solid #a0a0a0;"
            "border-radius:6px;font-weight:bold;font-size:18px;padding:0;}"
            "QPushButton:hover{background:#60676f;border:1px solid #c0c0c0;}"
            "QPushButton:pressed{background:#3a3f45;border:1px solid #909090;}")
        rl = self.get_recu_launcher()
        pb.clicked.connect(lambda: (play_key_tap(),
                                    self.open_video_file(video_filename, renamed, rl)))
        lay = frame.layout()
        if not lay:
            return 0
        ini.hide()
        lay.removeWidget(ini)
        lay.insertWidget(1, pb)
        pb.original_ini_widget = ini
        pb.video_filename = video_filename
        pb.renamed_filename = renamed
        self.row_frames[i] = (u, pb, fin, dur, frame)
        return url_index

    def restore_start_fields(self, only_rows=None):
        for i, (u, ini, fin, dur, frame) in enumerate(self.row_frames):
            if only_rows is not None and i not in only_rows:
                continue
            if frame.isVisible() and isinstance(ini, QPushButton) and hasattr(ini, 'original_ini_widget'):
                orig = ini.original_ini_widget
                lay = frame.layout()
                if lay:
                    lay.removeWidget(ini)
                    ini.hide()
                    orig.show()
                    lay.insertWidget(1, orig)
                    self.row_frames[i] = (u, orig, fin, dur, frame)
                    if i in self.row_states:
                        self.row_states[i]['has_play_button'] = False

    def get_recu_launcher(self): return get_recu_launcher(self)

    def open_video_file(self, video_filename, renamed, rl):
        try:
            folder = (rl.download_folder if rl and hasattr(rl, 'download_folder')
                      else None)
            if not folder or not os.path.exists(folder):
                folder = os.path.join(os.getcwd(), "videos")
            fmt = rl.download_format.lower() if rl else 'ts'
            path = None
            for ext in ([fmt, 'ts'] if fmt != 'ts' else ['ts']):
                p = os.path.join(folder, f"{renamed}.{ext}")
                if os.path.exists(p):
                    path = p
                    break
            if not path and os.path.exists(folder):
                for f in os.listdir(folder):
                    if (f.endswith(f'.{fmt}') or f.endswith('.ts')) and (
                            video_filename in f or renamed in f):
                        path = os.path.join(folder, f)
                        break
            if path and os.path.exists(path):
                try:
                    if os.name == 'nt':
                        os.startfile(path)
                    elif sys.platform == 'darwin':
                        subprocess.run(['open', path], check=False, capture_output=True)
                    else:
                        subprocess.run(['xdg-open', path], check=False, capture_output=True)
                except Exception:
                    pass
        except Exception:
            pass

    def get_all_parameters(self):
        rl = self.get_recu_launcher()
        return {
            'visible_rows': rl.spin_qty.value() if rl else 3,
            'rows': [{
                'url': u.text(), 'original_url': getattr(u, 'original_url', ''),
                'start': self._start_text(ini),
                'end': fin.text() if isinstance(fin, QLineEdit) else '',
                'duration': dur.text() if isinstance(dur, QLineEdit) else '',
                'is_visible': fr.isVisible(),
            } for u, ini, fin, dur, fr in self.row_frames],
        }

    def set_all_parameters(self, params):
        if not params:
            return
        if 'visible_rows' in params and (p := self.get_recu_launcher()):
            p.spin_qty.setValue(params['visible_rows'])
        for i, row in enumerate(params.get('rows', [])):
            if i >= len(self.row_frames):
                break
            u, ini, fin, dur, _ = self.row_frames[i]
            u.setText(row.get('url', ''))
            if row.get('original_url'):
                u.original_url = row['original_url']
            if isinstance(ini, QLineEdit):
                ini.setText(row.get('start', ''))
            if isinstance(fin, QLineEdit):
                fin.setText(row.get('end', ''))
            if isinstance(dur, QLineEdit):
                dur.setText(row.get('duration', ''))
                dur._auto_set = False


# ============================================================
#  CookieUAContainer
# ============================================================
class CookieUAContainer(QWidget):
    download_folder_changed = Signal(str)

    def __init__(self, parent=None, url_width=315, line_height=30):
        super().__init__(parent)
        self.parent_app = parent
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)
        left = QVBoxLayout()
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(3)

        def _wrap(edit):
            fr = QFrame()
            fr.setStyleSheet("background:#3c4048;border-radius:8px;padding:0;")
            fr.setFixedSize(url_width + 2, line_height + 2)
            frl = QHBoxLayout(fr)
            frl.setContentsMargins(1, 1, 1, 1)
            frl.setSpacing(0)
            frl.addWidget(edit)
            return fr

        self.cookie_edit = QLineEdit()
        self.cookie_edit.setPlaceholderText("Cookies")
        self.cookie_edit.setFixedSize(url_width, line_height)
        self.ua_edit = QLineEdit()
        self.ua_edit.setPlaceholderText("User-Agent")
        self.ua_edit.setFixedSize(url_width, line_height)

        for w in (self.cookie_edit, self.ua_edit):
            w.setStyleSheet(_LE_MAIN.replace("#e0e0e0", "#f0f0f0"))
            _attach_line_edit(w, False, self, double_click_paste=False)

        left.addWidget(_wrap(self.cookie_edit))
        left.addWidget(_wrap(self.ua_edit))
        layout.addLayout(left)

        self.download_btn = QPushButton("⯈ Download")
        self.download_btn.setStyleSheet(
            BTN_QSS.replace("padding: 0px 0px 4px 0px;", "padding: 0px 0px 2px 0px;"))
        self.download_btn.setFont(QFont("Arial", 10, QFont.Bold))
        self.download_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.download_btn.setFixedHeight(65)
        self.download_btn.setContextMenuPolicy(Qt.NoContextMenu)

        btn_frame = QFrame()
        btn_frame.setStyleSheet("background:#3c4048;border-radius:8px;padding:0;")
        btn_frame.setFixedHeight(67)
        btn_layout = QHBoxLayout(btn_frame)
        btn_layout.setContentsMargins(1, 1, 1, 1)
        btn_layout.setSpacing(0)
        btn_layout.addWidget(self.download_btn)

        layout.addWidget(btn_frame)
        self.setFixedHeight(67)

    def update_placeholders(self):
        rl = self.get_recu_launcher()
        if rl:
            self.cookie_edit.setPlaceholderText(rl.tr_text("cookies_placeholder"))
            self.ua_edit.setPlaceholderText(rl.tr_text("user_agent_placeholder"))
            self.download_btn.setText(rl.tr_text("download_button"))

    def get_recu_launcher(self): return get_recu_launcher(self)

    def choose_download_folder(self):
        f = QFileDialog.getExistingDirectory(
            self, "Select Download Folder", os.getcwd(),
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        if f:
            self._save_config(f)
            self.download_folder_changed.emit(f)
            rl = self.get_recu_launcher()
            if rl and hasattr(rl, 'console'):
                rl.console.append(f"> {rl.tr_text('download_folder_set')}")
                rl.console.append(f"> {f}")

    def _save_config(self, folder, retries=3):
        path = os.path.join(os.getcwd(), "download_config.json")
        cfg = {}
        existing = _read_json(path, {}) or {}
        for k in ("download_mode", "download_language", "download_format", "rename_format"):
            if k in existing:
                cfg[k] = existing[k]
        cfg["download_folder"] = folder
        cfg["last_updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
        return _write_json(path, cfg, indent=2, retries=retries)

    def get_parameters(self):
        return {'cookie': self.cookie_edit.text(), 'user_agent': self.ua_edit.text()}

    def set_parameters(self, p):
        if p:
            self.cookie_edit.setText(p.get('cookie', ''))
            self.ua_edit.setText(p.get('user_agent', ''))


# ============================================================
#  CustomTitleBar
# ============================================================
class CustomTitleBar(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setFixedHeight(25)
        self.setStyleSheet("background:#3c4048;margin:0;padding:0;")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        v = QLabel("v2.5")
        v.setFont(QFont("Arial", 9, QFont.Bold))
        v.setStyleSheet("QLabel{color:#bfbfbf;background:transparent;border:none;"
                        "padding:0 10px;margin:0;}")
        lay.addWidget(v)
        lay.addStretch()

        self.settings_btn = self._btn("⛭", 28, 28, "font:13pt 'Arial Bold';", "#5c6169", -5)
        self.settings_btn.clicked.connect(lambda: (play_key_tap(), self.on_settings()))
        lay.addWidget(self.settings_btn)

        self.top_btn = self._btn("⛶", 28, 28, "font:12pt 'Arial';", "#5c6169", -6,
                                 checked="#99e9f7")
        self.top_btn.setCheckable(True)
        self.top_btn.clicked.connect(lambda: (play_key_tap(), self.toggle_top()))
        lay.addWidget(self.top_btn)

        self.min_btn = self._btn("–", 25, 25, "font:14pt 'Arial';", "#3399ff", 0, "#1a5c9e")
        self.min_btn.clicked.connect(lambda: (play_key_tap(), self.parent.showMinimized()))
        lay.addWidget(self.min_btn)

        self.close_btn = self._btn("✕", 25, 25, "font:13pt 'Arial';", "#e74c3c", 0, "#c0392b")
        self.close_btn.clicked.connect(lambda: (play_key_tap(), self.parent.close()))
        lay.addWidget(self.close_btn)

        self._drag = False

    def _btn(self, text, w, h, font, hover, mt, pressed="#3c4048", checked=None):
        b = QPushButton(text)
        b.setFixedSize(w, h)
        chk = f"QPushButton:checked{{color:{checked};}}" if checked else ""
        b.setStyleSheet(
            f"QPushButton{{color:#f0f0f0;background:transparent;border:none;{font}"
            f"margin:{mt}px 0 0 0;padding:0;min-width:{w}px;max-width:{w}px;}}"
            f"QPushButton:hover{{background:{hover};}}"
            f"QPushButton:pressed{{background:{pressed};color:#f0f0f0;}}{chk}")
        return b

    def on_settings(self):
        if self.parent and hasattr(self.parent, 'show_quick_settings'):
            self.parent.show_quick_settings()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag = True
            self._pos = e.globalPosition().toPoint() - self.parent.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag:
            self.parent.move(e.globalPosition().toPoint() - self._pos)

    def mouseReleaseEvent(self, e): self._drag = False

    def toggle_top(self):
        wh = self.parent.windowHandle()
        if wh:
            flags = wh.flags()
            wh.setFlags(flags & ~Qt.WindowStaysOnTopHint if flags & Qt.WindowStaysOnTopHint
                        else flags | Qt.WindowStaysOnTopHint)
            self.top_btn.setChecked(bool(wh.flags() & Qt.WindowStaysOnTopHint))
        else:
            wf = self.parent.windowFlags()
            self.parent.setWindowFlags(wf & ~Qt.WindowStaysOnTopHint if wf & Qt.WindowStaysOnTopHint
                                       else wf | Qt.WindowStaysOnTopHint)
            self.parent.show()


# ============================================================
#  CookiePlainTextEdit
# ============================================================
class CookiePlainTextEdit(QPlainTextEdit):
    def paste(self):
        super().paste()
        self._scroll_to_top()

    def insertFromMimeData(self, source):
        super().insertFromMimeData(source)
        self._scroll_to_top()

    def _scroll_to_top(self):
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.Start)
        self.setTextCursor(cursor)
        self.verticalScrollBar().setValue(0)
        self.horizontalScrollBar().setValue(0)


# ============================================================
#  CookieInjectDialog
# ============================================================
class CookieInjectDialog(QDialog):
    _STYLE = (
        "QDialog, QFrame{background-color:#1a1c1f;color:#e0e0e0;}"
        "QLabel{color:#bfbfbf;font-size:10pt;font-family:Arial;}"
        "QPlainTextEdit{background-color:#34383f;color:#fff;border:1px solid #50575d;"
        "border-radius:4px;padding:2px 0px 6px 8px;font-family:Consolas;font-size:9pt;}"
        "QScrollBar:vertical{width:10px;background:transparent;border-radius:5px;}"
        "QScrollBar::handle:vertical{background:#555;min-height:20px;border-radius:5px;}"
        "QScrollBar::handle:vertical:hover{background:#888;}"
        "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}"
        "QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical{background:none;}"
    ) + BTN_QSS

    LETTER = 100
    GAP = 10
    MARGIN = 10
    EDITOR_H = 142

    def __init__(self, parent=None, initial_text=""):
        super().__init__(parent)
        self.parent_app = parent
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.original_language = getattr(parent, 'download_language', 'English')
        self.setStyleSheet(self._STYLE)

        main = QFrame(self)
        main.setStyleSheet("QFrame{background-color:#1a1c1f;border:1px solid #50575d;}")
        ml = QVBoxLayout(main)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(0)

        self.title_bar = QFrame()
        self.title_bar.setFixedHeight(25)
        self.title_bar.setStyleSheet("background:#3c4048;border:none;")
        tl = QHBoxLayout(self.title_bar)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(0)
        self.title_label = QLabel(self.tr_text("cookies_inject_header"))
        self.title_label.setFont(QFont("Arial", 10, QFont.Bold))
        self.title_label.setStyleSheet("color:#bfbfbf;background:transparent;border:none;padding:0 8px 0 10px;")
        tl.addWidget(self.title_label)
        tl.addStretch()
        x = QPushButton("✕")
        x.setFixedSize(25, 25)
        x.setStyleSheet("QPushButton{color:#f0f0f0;background:transparent;border:none;"
                        "border-radius:0px;font:13pt Arial;padding:0;}"
                        "QPushButton:hover{background:#e74c3c;border-radius:0px;}"
                        "QPushButton:pressed{background:#c0392b;border-radius:0px;}")
        x.clicked.connect(lambda: (play_key_tap(), self.reject()))
        tl.addWidget(x)

        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setContentsMargins(self.MARGIN, self.MARGIN, self.MARGIN, self.MARGIN)
        cl.setSpacing(self.GAP)

        hint = QLabel(self.tr_text("cookies_inject_hint"))
        hf = QFont("Arial", 10, QFont.Bold)
        hf.setLetterSpacing(QFont.PercentageSpacing, self.LETTER)
        hint.setFont(hf)
        hint.setWordWrap(True)
        hint.setStyleSheet("QLabel{color:#bfbfbf;background:transparent;border:none;padding-left:1px;}")
        cl.addWidget(hint)

        self.editor = CookiePlainTextEdit(initial_text or "")
        self.editor.setPlaceholderText("Supported format: JSON, Header string")
        self.editor.setFixedHeight(self.EDITOR_H)
        self.editor.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.editor.setWordWrapMode(QTextOption.WrapAnywhere)
        self.editor.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.editor.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.editor.setContextMenuPolicy(Qt.CustomContextMenu)
        self.editor.customContextMenuRequested.connect(self._editor_context_menu)

        self.editor.setFrameShape(QFrame.NoFrame)
        self.editor.setStyleSheet(
            "QPlainTextEdit{background-color:#1e1e1e;color:#ffffff;border:1px solid #50575d;"
            "border-radius:4px;padding:3px 0px 6px 6px;font-family:Consolas;font-size:9pt;"
            "selection-background-color:#4a6a8a;}"
            "QPlainTextEdit:focus{border:1px solid #bfbfbf;}")
        self.editor.viewport().setStyleSheet("background-color:#1e1e1e; border:none;")

        cl.addWidget(self.editor)

        bl = QHBoxLayout()
        bl.setSpacing(self.GAP)

        for key, slot in (("cookies_inject_confirm", self.accept),
                          ("cookies_export_btn", self.export_to_clipboard)):
            b = QPushButton(self.tr_text(key))
            b.setFixedHeight(30)
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            b.setStyleSheet(BTN_QSS)
            bf = QFont("Arial", 10, QFont.Bold)
            bf.setLetterSpacing(QFont.PercentageSpacing, self.LETTER)
            b.setFont(bf)
            b.clicked.connect(lambda _=False, s=slot: (play_key_tap(), s()))

            frame = QWidget()
            frame.setStyleSheet("background-color:#3c4048;border-radius:8px;")
            frame.setFixedHeight(32)
            frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

            fl = QHBoxLayout(frame)
            fl.setContentsMargins(1, 1, 1, 1)
            fl.setSpacing(0)
            fl.addWidget(b)

            bl.addWidget(frame)

        cl.addLayout(bl)

        ml.addWidget(self.title_bar)
        ml.addWidget(content)
        QVBoxLayout(self).addWidget(main)
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.setFixedWidth(330)
        self._drag = None

        self.adjustSize()
        self._position_near_parent(parent)

    def _position_near_parent(self, parent):
        if parent and hasattr(parent, 'top_bar'):
            tb = parent.top_bar
            pos = tb.mapToGlobal(tb.rect().bottomLeft())
            x, y = pos.x() + (tb.width() - self.width()) // 2, pos.y() + 1
        elif parent:
            g = parent.geometry()
            x = g.x() + (g.width() - self.width()) // 2
            y = g.y() + (g.height() - self.height()) // 2 - 34
        else:
            return
        sg = QApplication.primaryScreen().availableGeometry()
        self.move(max(0, min(x, sg.width() - self.width())),
                  max(0, min(y, sg.height() - self.height())))

    def tr_text(self, key):
        return TRANSLATIONS.get(self.original_language, TRANSLATIONS["English"]).get(
            key, TRANSLATIONS["English"].get(key, key))

    def get_text(self): return self.editor.toPlainText().strip()

    def _editor_context_menu(self, pos):
        menu = QMenu()
        menu.setStyleSheet(MENU_STYLE)
        menu.addAction(make_menu_item(menu, "📋", self.tr_text("paste"),
                                      self.editor.paste, "4px 3px 4px 8px", "6px 8px 6px 2px"))
        menu.addAction(make_menu_item(menu, "📄", self.tr_text("copy"),
                                      self.editor.copy, "4px 3px 4px 8px", "6px 8px 6px 2px"))
        menu.setFixedWidth(112)
        menu.exec(self.editor.mapToGlobal(pos))

    def export_to_clipboard(self):
        cookies, err = get_cookies_via_cdp(9222, "recu.me")
        if not cookies:
            self.editor.setPlainText(f"// No session cookies found: {err or 'unknown error'}")
            return
        texto = "; ".join(f"{k}={v}" for k, v in cookies.items())
        QApplication.clipboard().setText(texto)
        self.editor.setPlainText(texto)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and e.position().y() < 25:
            self._drag = (e.globalPosition().toPoint(), self.pos())
        else:
            super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._drag:
            self.move(self._drag[1] + e.globalPosition().toPoint() - self._drag[0])
        else:
            super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        self._drag = None
        super().mouseReleaseEvent(e)


# ============================================================
#  RoundedTooltip
# ============================================================
class RoundedTooltip(QWidget):
    def __init__(self, text):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint |
                               Qt.NoDropShadowWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)

        lbl = QLabel(text, self)
        lbl.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        lbl.setStyleSheet("QLabel{color:#f0f0f0;background:transparent;border:none;"
                          "font-family:Arial;font-size:9pt;}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(7, 6, 7, 6)
        lay.setSpacing(0)
        lay.addWidget(lbl)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setBrush(QColor("#3c4048"))
        p.setPen(QColor("#50575d"))
        p.drawRoundedRect(r, 4, 4)


# ============================================================
#  TooltipBelowCursor
# ============================================================
class TooltipBelowCursor(QObject):
    def __init__(self, parent=None, predicate=None):
        super().__init__(parent)
        self.predicate = predicate
        self._label = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._hide)

    def eventFilter(self, obj, event):
        t = event.type()
        if t == QEvent.Type.ToolTip:
            if self.predicate and not self.predicate(obj, event):
                self._hide()
                return True
            txt = obj.toolTip() or (obj.parent().toolTip() if obj.parent() else "")
            if txt:
                self._show(txt)
            return True
        if t in (QEvent.Type.Leave, QEvent.Type.MouseButtonPress):
            self._hide()
        return super().eventFilter(obj, event)

    def _show(self, text):
        self._hide()
        tip = RoundedTooltip(text)
        tip.adjustSize()
        sg = QApplication.primaryScreen().availableGeometry()
        p = QCursor.pos() + QPoint(-45, 22)
        tip.move(min(p.x(), sg.right() - tip.width()),
                 min(p.y(), sg.bottom() - tip.height()))
        tip.show()
        tip.raise_()
        self._label = tip
        self._timer.start(4000)

    def _hide(self):
        if self._label:
            self._label.close()
            self._label.deleteLater()
            self._label = None
        self._timer.stop()


# ============================================================
#  Constantes
# ============================================================
CONSOLE_HEIGHT = 127


# ============================================================
#  RecuLauncher
# ============================================================
class RecuLauncher(QWidget):
    console_signal = Signal(str)
    enable_download_btn_signal = Signal()
    video_completed_seq = Signal(str, str, int)

    def __init__(self):
        super().__init__()
        reset_session_id()
        get_or_create_session_id()
        self.setWindowTitle("RecuDown 2")
        self.initial_width = 442
        self.setFixedWidth(self.initial_width)
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setStyleSheet("background:#1a1c1f;color:#e0e0e0;")

        self.setup_icon()
        self.process = None
        self._running_procs = []
        self._procs_lock = threading.Lock()
        self._finalize_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._recu_v_shown = False
        self._launched_browser_name = None
        self.config_path = os.path.join(os.getcwd(), "config.json")
        self.download_mode = "parallel"
        self.download_language = "English"
        self.download_format = "TS"
        self.rename_format = "yyyy-mm-dd"
        self.load_download_config()

        self.download_folder = None
        self.original_working_dir = os.getcwd()
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.current_url_markers = {}
        self.current_url_path_counts = {}
        self.current_url_row_map = {}
        self.downloaded_files = set()
        self._progress_file_lock = threading.Lock()
        self._bad_time_rows = set()

        self.close_click_count = 0
        self.close_timer = QTimer()
        self.close_timer.setSingleShot(True)
        self.close_timer.timeout.connect(self.reset_close_counter)

        self.auto_save_timer = QTimer()
        self.auto_save_timer.setInterval(30000)
        self.auto_save_timer.timeout.connect(self.auto_save_parameters)
        self.auto_save_timer.start()

        self.last_auto_save_hash = None
        self.sound_path = (os.path.join(getattr(sys, "_MEIPASS", ""), "sound.wav")
                           if hasattr(sys, "_MEIPASS") else "sound.wav")
        self._ffmpeg_open = False
        self._ffmpeg_missing = False
        self._ffmpeg_saved_html = ""
        self._no_cookies_shown = False
        self._in_help = False
        self._last_run_no_cookies = False

        self.init_ui()
        self.console_signal.connect(self.console.append)
        self.enable_download_btn_signal.connect(
            lambda: self.cookie_ua_widget.download_btn.setEnabled(True))
        self.video_completed_seq.connect(self.on_video_completed_with_index)
        QTimer.singleShot(500, self._launch_browser_debug_on_start)
        self.update_ui_language()
        QTimer.singleShot(100, self.check_ffmpeg_status)
        self.load_download_folder()
        self.ensure_videos_folder_exists()
        QTimer.singleShot(3000, self._maybe_insert_ffmpeg_link)

        self.spin_qty.setValue(5)
        self.url_container.update_visible_rows(5)
        self.adjust_window_height()

    def _register_proc(self, proc):
        with self._procs_lock:
            self._running_procs.append(proc)

    def _unregister_proc(self, proc):
        with self._procs_lock:
            try:
                self._running_procs.remove(proc)
            except ValueError:
                pass

    def _hard_kill_proc(self, p):
        try:
            if p.poll() is None:
                try: p.kill()
                except Exception: pass
                try: p.wait(timeout=1)
                except Exception: pass
                try:
                    kw, cf = _subprocess_kwargs()
                    subprocess.run(['taskkill', '/F', '/T', '/PID', str(p.pid)],
                                   capture_output=True, timeout=2,
                                   creationflags=cf, **kw)
                except Exception: pass
        except Exception:
            pass

    def _kill_all_procs(self):
        self._stop_event.set()
        with self._procs_lock:
            procs = list(self._running_procs)
            self._running_procs.clear()
        for p in procs:
            self._hard_kill_proc(p)
        if self.process is not None:
            self._hard_kill_proc(self.process)
        self.process = None

    # ============================================================
    #  Progreso persistente (reintento selectivo)
    # ============================================================
    def _progress_file_path(self, target): return os.path.join(target, "download_progress.json")

    def _url_key(self, url, start, end):
        import hashlib
        p = urlparse(url or "")
        path = (p.path or p.netloc or url or "").lstrip("/").rstrip("/")

        def _norm_t(s):
            s = (s or "").strip().replace(".", ":").replace(",", ":")
            return ":".join(seg.zfill(2) if seg.isdigit() else seg for seg in s.split(":"))

        raw = f"{path}|{_norm_t(start)}|{_norm_t(end)}"
        return hashlib.md5(raw.encode("utf-8")).hexdigest()[:16]

    def _load_progress(self, target):
        data = _read_json(self._progress_file_path(target), {})
        return data if isinstance(data, dict) else {}

    def _save_progress(self, target, progress):
        return _write_json(self._progress_file_path(target), progress,
                           indent=2, atomic=True, retries=1)

    def _mark_completed(self, target, url, start, end, dur, filename, dup_num=0):
        try:
            with self._progress_file_lock:
                progress = self._load_progress(target)
                key = self._url_key(url, start, end)
                progress[key] = {
                    "url": url, "start": start, "end": end, "dur": dur,
                    "file": filename, "dup_num": dup_num,
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                }
                if not self._save_progress(target, progress):
                    time.sleep(0.2)
                    self._save_progress(target, progress)
        except Exception:
            pass

    def _file_exists_for_progress(self, target, info):
        filename = info.get("file", "")
        if not filename:
            return False
        full = os.path.join(target, filename)
        if os.path.exists(full):
            return True
        stem = full[:-3] if full.endswith(".ts") else full
        for ext in (".ts", ".mp4", ".mkv"):
            if os.path.exists(stem + ext):
                return True
        try:
            stem_name = os.path.basename(stem)
            pat = re.compile(re.escape(stem_name) + r'\s*\(\d+\)\.(?:ts|mp4|mkv)$', re.IGNORECASE)
            for f in os.listdir(target):
                if pat.match(f):
                    return True
        except Exception:
            pass
        return False

    def _filter_already_downloaded(self, target, urls):
        progress = self._load_progress(target)
        filtered, skipped = [], []
        for entry in urls:
            url, start, end, dur, row_idx = entry
            key = self._url_key(url, start, end)
            info = progress.get(key)
            if info and self._file_exists_for_progress(target, info):
                skipped.append((entry, info, 0))
                continue
            filtered.append(entry)
        return filtered, skipped

    def _show_bad_time_summary(self):
        if not self._bad_time_rows:
            return
        for n in sorted(self._bad_time_rows):
            self.console_signal.emit(
                f'> {self.tr_text("url_bad_times").format(n=n)}<br>'
                f'> {self.tr_text("url_bad_times_fix")}')

    def _emit_init_msgs(self, to_console=True):
        msgs = [f"> {self.tr_text(k)}" for k in
                ('saving_config', 'config_updated', 'starting_download')]
        for m in msgs:
            (self.console.append if to_console else self.console_signal.emit)(m)

    def _on_sequential_done(self):
        self.convert_downloaded_videos()
        if not self._last_run_no_cookies:
            self.console_signal.emit(f"> {self.tr_text('process_completed')}")
        self._show_bad_time_summary()
        self.enable_download_btn_signal.emit()

    def tr_text(self, key):
        return TRANSLATIONS.get(self.download_language, TRANSLATIONS["English"]).get(
            key, TRANSLATIONS["English"].get(key, key))

    def update_ui_language(self):
        if hasattr(self, 'title_label'):
            self.title_label.setText(self.tr_text("recudown_title"))
        if hasattr(self, 'url_container'):
            self.url_container.update_placeholders()
        if hasattr(self, 'cookie_ua_widget'):
            self.cookie_ua_widget.update_placeholders()
        if hasattr(self, 'import_btn'):
            self.import_btn.setToolTip(self.tr_text("update_cookies_tooltip"))
        if hasattr(self, 'inject_btn'):
            self.inject_btn.setToolTip(self.tr_text("inject_cookies_tooltip"))
        if hasattr(self, 'spin_qty'):
            txt = self.tr_text("url_quantity")
            self.spin_qty.setToolTip(txt)
            self.spin_qty.lineEdit().setToolTip(txt)
        if hasattr(self, 'title_label') and hasattr(self, 'top_bar'):
            QTimer.singleShot(0, self._layout_top_bar_children)

    def load_download_config(self):
        c = _read_json(os.path.join(os.getcwd(), "download_config.json"), {}) or {}
        for attr, key, default in (
            ("download_mode", "download_mode", self.download_mode),
            ("download_language", "download_language", self.download_language),
            ("download_format", "download_format", self.download_format),
            ("rename_format", "rename_format", "yyyy-mm-dd"),
        ):
            setattr(self, attr, c.get(key, default))

    def save_download_config(self):
        p = os.path.join(os.getcwd(), "download_config.json")
        return _write_json(p, {
            "download_folder": self.download_folder,
            "download_mode": self.download_mode,
            "download_language": self.download_language,
            "download_format": self.download_format,
            "rename_format": self.rename_format,
            "last_updated": time.strftime("%Y-%m-%d %H:%M:%S"),
        }, indent=2)

    def check_ffmpeg_status(self):
        found = check_ffmpeg()
        if not found:
            self.console.append(f"> {self.tr_text('ffmpeg_not_found')}")
            self.console.append(f"> {self.tr_text('ffmpeg_ts_only')}")
            self._ffmpeg_missing = True
            self._ffmpeg_open = False
            return False
        self._ffmpeg_missing = False
        return True

    def _maybe_insert_ffmpeg_link(self):
        if self._ffmpeg_missing and not self._ffmpeg_open:
            self.console.append(
                f'<span style="color:#f0f0f0;font-family:Consolas;font-size:12px;">'
                f'&gt; ▼ {self.tr_text("ffmpeg_install_details")}</span>')

    def eventFilter(self, obj, event):
        if obj is self.console.viewport() and event.type() == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.LeftButton:
                cursor = self.console.cursorForPosition(event.position().toPoint())
                cursor.select(cursor.SelectionType.LineUnderCursor)
                txt = cursor.selectedText()
                cursor.clearSelection()
                if self.tr_text("ffmpeg_install_details") in txt:
                    self._toggle_ffmpeg_block()
                    return True
        return super().eventFilter(obj, event)

    def _copy_console_clean(self):
        cursor = self.console.textCursor()
        if cursor.hasSelection():
            txt = cursor.selectedText().replace("\u2029", "\n")
        else:
            txt = self.console.toPlainText()
        c1 = self.tr_text("ffmpeg_install_cmd1").strip()
        c2 = self.tr_text("ffmpeg_install_cmd2").strip()
        txt = txt.replace(f"> {c1}", c1).replace(f"> {c2}", c2)
        if c1 in txt and c2 in txt:
            txt = re.sub(re.escape(c1) + r"\s*\n\s*" + re.escape(c2), c1 + c2, txt)
        QApplication.clipboard().setText(txt)

    def _toggle_ffmpeg_block(self):
        if not self._ffmpeg_open:
            self._ffmpeg_saved_html = self.console.toHtml()
            for k in ('ffmpeg_install_step1', 'ffmpeg_install_step2'):
                self.console.append(f"> {self.tr_text(k)}")
            self.console.append(f"> {self.tr_text('ffmpeg_install_cmd1')}")
            self.console.append(f"> {self.tr_text('ffmpeg_install_cmd2')}")
            for k in ('ffmpeg_install_step3', 'ffmpeg_install_step4'):
                self.console.append(f"> {self.tr_text(k)}")
            self._ffmpeg_open = True
        else:
            if self._ffmpeg_saved_html:
                self.console.setHtml(self._ffmpeg_saved_html)
            self._ffmpeg_open = False

    def show_quick_settings(self):
        folder = self.download_folder or os.path.join(self.original_working_dir, "videos")
        d = QuickSettingsDialog(self, folder, self.download_mode,
                                self.download_language, self.download_format)
        d.setModal(True)
        # Si cierra con ✕ y nada cambió, salir en silencio (sin "> Save settings")
        if d.exec() != QDialog.Accepted or d._current_settings() == d._initial:
            return
        self.download_language = d.language_btn.text()
        self.console.append(f"> {self.tr_text('save_settings_msg')}")
        old = self.download_mode
        new = "parallel" if d.mode_btn.text() in (
            self.tr_text("parallel"), "Parallel", "Paralelo", "Паралл") else "series"
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
                time.sleep(0.5)
                if self.process.poll() is None:
                    self.process.kill()
            except Exception:
                pass
        self.download_folder = d.folder_path_edit.text()
        self.download_mode = new
        self.download_format = d.format_btn.text()
        self.rename_format = d.rename_format_value
        self.update_ui_language()
        self.save_download_config()
        self.rename_config_by_mode(old, new)
        self.cookie_ua_widget.download_btn.setEnabled(True)

    def rename_config_by_mode(self, old, new):
        if old == new:
            return
        folder = (self.download_folder if self.download_folder and os.path.exists(self.download_folder)
                  else os.path.join(self.original_working_dir, "videos"))
        os.makedirs(folder, exist_ok=True)
        old_p = os.path.join(folder, f"config.json {old}")
        new_p = os.path.join(folder, f"config.json {new}")
        std = os.path.join(folder, "config.json")
        try:
            if os.path.exists(new_p):
                os.remove(new_p)
            if os.path.exists(old_p):
                os.rename(old_p, new_p)
            elif os.path.exists(std):
                os.rename(std, new_p)
        except Exception:
            pass

    def auto_save_parameters(self):
        try:
            if not self.has_parameters():
                return
            h = self.get_current_state_hash()
            if h == self.last_auto_save_hash:
                return
            self.url_container.save_backup_manual()
            self.last_auto_save_hash = h
        except Exception:
            pass

    def get_current_state_hash(self):
        p = []
        for i, (u, ini, fin, dur, fr) in enumerate(self.url_container.row_frames):
            if not fr.isVisible():
                continue
            if u.text().strip():
                p.append(f"U{i}:{getattr(u, 'original_url', None) or u.text().strip()}")
            if (s := self.url_container._start_text(ini)):
                p.append(f"S{i}:{s}")
            if isinstance(fin, QLineEdit) and fin.text().strip():
                p.append(f"E{i}:{fin.text().strip()}")
            if isinstance(dur, QLineEdit) and dur.text().strip():
                p.append(f"D{i}:{dur.text().strip()}")
        if (c := self.cookie_ua_widget.cookie_edit.text().strip()):
            p.append(f"C:{c}")
        p += [f"M:{self.download_mode}", f"L:{self.download_language}",
              f"F:{self.download_format}", f"R:{self.rename_format}"]
        return hash("|".join(p)) if p else 0

    def reset_close_counter(self): self.close_click_count = 0

    def _launch_browser_debug_on_start(self):
        try:
            ok, msg, name = launch_browser_with_debug()
            if ok:
                self._launched_browser_name = name
                key = "browser_already_open_debug" if msg == "ya estaba abierto" else "browser_launched_debug"
                self.console.append(f"> {self.tr_text(key).format(name)}")
                if msg != "ya estaba abierto":
                    self.console.append(f"> {self.tr_text('login_prompt')}")
                    self.console.append(f"> {self.tr_text('paste_cookies_prompt')}")
            else:
                self.console.append(f"> {msg}")
        except Exception as e:
            self.console.append(f"> Error: {e}")

    def showEvent(self, event): super().showEvent(event); QApplication.processEvents()

    def resizeEvent(self, event): super().resizeEvent(event); self._layout_top_bar_children()

    def setup_icon(self):
        try:
            icon = self._load_icon()
            self.setWindowIcon(icon if icon and not icon.isNull() else self._default_icon())
            if sys.platform == "win32":
                try:
                    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('RecuDown 2.v2.5')
                except Exception:
                    pass
        except Exception:
            self.setWindowIcon(self._default_icon())

    def _load_icon(self):
        mp = getattr(sys, "_MEIPASS", "")
        frozen = getattr(sys, 'frozen', False)
        bases = [mp, os.path.dirname(os.path.abspath(__file__)), os.getcwd()]
        if frozen:
            bases.append(os.path.dirname(sys.executable))
        for base in bases:
            for ext in ("ico", "png"):
                path = os.path.join(base, f"icon.{ext}") if base else ""
                if path and os.path.exists(path):
                    try:
                        ic = QIcon(path)
                        if not ic.isNull():
                            return ic
                    except Exception:
                        pass
        return None

    def _default_icon(self):
        try:
            pm = QPixmap(64, 64)
            pm.fill(Qt.transparent)
            p = QPainter(pm)
            p.setRenderHint(QPainter.Antialiasing)
            p.setBrush(QColor("#3c4048"))
            p.setPen(Qt.NoPen)
            p.drawEllipse(4, 4, 56, 56)
            p.setFont(QFont("Arial", 28, QFont.Bold))
            p.setPen(QColor("#99e9f7"))
            p.drawText(pm.rect(), Qt.AlignCenter, "R")
            p.end()
            return QIcon(pm)
        except Exception:
            return QApplication.style().standardIcon(QApplication.style().SP_ComputerIcon)

    def ensure_videos_folder_exists(self):
        f = os.path.join(self.original_working_dir, "videos")
        if not os.path.exists(f):
            try:
                os.makedirs(f)
                self.console.append(f"> {self.tr_text('created_videos_folder')}")
            except Exception:
                pass

    def _fmt_folder_line(self, path):
        safe = path.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        parts = re.findall(r'[^/\\]+[/\\]?', safe)
        lines, cur = [], ""
        for p in parts:
            if len(cur) + len(p) > 47:
                lines.append(cur)
                cur = ""
            cur += p
        lines.append(cur)
        return (f'<div style="font-family:Consolas;font-size:12px;">'
                f'&gt;&nbsp;{"<br>&gt;&nbsp;".join(lines)}</div>')

    def load_download_folder(self):
        c = _read_json(os.path.join(os.getcwd(), "download_config.json"), {})
        if c and "download_folder" in c:
            self.download_folder = c["download_folder"]
            self.console.append(f"> {self.tr_text('custom_folder_using')}")
            self.console.append(self._fmt_folder_line(self.download_folder))
            return
        self.console.append(f"> {self.tr_text('no_custom_folder')}")

    def _make_top_btn(self, txt, tip, slot, font_size, y_pad):
        b = QPushButton(txt)
        b.setFixedSize(28, 28)
        b.setStyleSheet(
            f"QPushButton{{"
            f"  background:#3c4048;"
            f"  color:#d0d0d0;"
            f"  border:1px solid #50575d;"
            f"  border-radius:5px;"
            f"  font-weight:bold;font-size:{font_size}px;"
            f"  padding:0 0 {y_pad}px 2px;"
            f"}}"
            f"QPushButton:hover{{"
            f"  background:#60676f;"
            f"  border:1px solid #7a828b;"
            f"}}"
            f"QPushButton:pressed{{"
            f"  background:#3a3f45;"
            f"  border:1px solid #50575d;"
            f"}}")
        b.setToolTip(tip)
        b.clicked.connect(lambda: (play_key_tap(), slot()))
        return b

    def init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        border_wrap = QFrame()
        border_wrap.setObjectName("mainBorderWrap")
        border_wrap.setStyleSheet(
            "QFrame#mainBorderWrap {"
            "  border: 1px solid #50575d;"
            "  border-radius: 0px;"
            "}"
        )
        outer.addWidget(border_wrap)

        main = QVBoxLayout(border_wrap)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        self.title_bar = CustomTitleBar(self)
        main.addWidget(self.title_bar)

        container = QFrame()
        cl = QVBoxLayout(container)
        cl.setContentsMargins(10, 8, 10, 8)
        cl.setSpacing(0)
        self._container_layout = cl

        self.top_bar_wrap = QFrame()
        self.top_bar_wrap.setFixedHeight(62)
        self.top_bar_wrap.setStyleSheet("background:#3c4048;border-radius:8px;padding:0;")
        _wrap_lay = QVBoxLayout(self.top_bar_wrap)
        _wrap_lay.setContentsMargins(1, 1, 1, 1)
        _wrap_lay.setSpacing(0)

        self.top_bar = QFrame()
        self.top_bar.setFixedHeight(60)
        self.top_bar.setStyleSheet(
            "QFrame{"
            "  background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, "
            "    stop:0 #50575d, stop:0.48 #34383f, stop:0.52 #2a2e33, stop:1 #222529);"
            "  border-top: 1px solid #6c747d;"
            "  border-left: 1px solid #50575d;"
            "  border-right: 1px solid #1f2226;"
            "  border-bottom: 1px solid #1a1c1f;"
            "  border-radius: 6px;"
            "}"
        )
        _wrap_lay.addWidget(self.top_bar)

        self.left_widget = QWidget(self.top_bar)
        self.left_widget.setStyleSheet("QWidget{background:transparent;border:none;border-radius:0;}")
        self.left_widget.setAttribute(Qt.WA_StyledBackground, False)
        self.left_widget.setAutoFillBackground(False)
        left = QHBoxLayout(self.left_widget)
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(5)

        self.spin_qty = FixedSpinBox()
        self.spin_qty.setRange(1, 5)
        self.spin_qty.setValue(5)
        self.spin_qty.setFixedSize(48, 30)
        self.spin_qty.setAlignment(Qt.AlignCenter)
        self.spin_qty.valueChanged.connect(self.update_url_rows)
        self.spin_qty.setFocusPolicy(Qt.ClickFocus)
        left.addWidget(self.spin_qty)
        left.addSpacing(4)

        self.import_btn = self._make_top_btn(
            "⭮", self.tr_text("update_cookies_tooltip"),
            self.auto_import_via_browser, font_size=19, y_pad=3)
        left.addWidget(self.import_btn)
        left.addSpacing(4)
        self.inject_btn = self._make_top_btn(
            "⭡", self.tr_text("inject_cookies_tooltip"),
            self.inject_cookies_manual, font_size=21, y_pad=4)
        left.addWidget(self.inject_btn)

        self._tip_filter = TooltipBelowCursor(self)
        for w in (self.import_btn, self.inject_btn):
            w.installEventFilter(self._tip_filter)

        def _spin_on_number(obj, ev):
            return (not self.spin_qty._rect().contains(ev.pos())
                    if obj is self.spin_qty else True)

        self._spin_tip_filter = TooltipBelowCursor(self, predicate=_spin_on_number)
        txt = self.tr_text("url_quantity")
        for w in (self.spin_qty, self.spin_qty.lineEdit()):
            w.setToolTip(txt)
            w.installEventFilter(self._spin_tip_filter)

        self.title_label = QLabel(self.tr_text("recudown_title"), self.top_bar)
        self.title_label.setFont(QFont("Arial", 10, QFont.Bold))
        self.title_label.setStyleSheet("background:transparent;border:none;color:#d0d0d0;")
        self.title_label.setAlignment(Qt.AlignVCenter)

        cl.addWidget(self.top_bar_wrap)
        QTimer.singleShot(0, self._layout_top_bar_children)
        cl.addSpacing(8)

        self.url_container = URLContainerWidget(self, rows=5, line_height=30)
        cl.addWidget(self.url_container)
        cl.addSpacing(8)

        self.cookie_ua_widget = CookieUAContainer(self, url_width=self.url_container.url_width,
                                                  line_height=30)
        self.url_container.set_cookie_ua_widget(self.cookie_ua_widget)
        self.cookie_ua_widget.download_btn.clicked.connect(
            lambda: (play_key_tap(), self.start_process()))
        self.cookie_ua_widget.download_folder_changed.connect(self.on_download_folder_changed)
        cl.addWidget(self.cookie_ua_widget)
        cl.addSpacing(8)

        cc = QWidget()
        cc.setFixedHeight(CONSOLE_HEIGHT)
        ccl = QVBoxLayout(cc)
        ccl.setContentsMargins(0, 0, 0, 0)
        ccl.setSpacing(0)

        self.console = QTextBrowser()
        self.console.setReadOnly(True)
        self.console.setFixedHeight(CONSOLE_HEIGHT)
        self.console.setStyleSheet(
            "QTextBrowser{background:#1e1e1e;color:#f0f0f0;border:1px solid #50575d;"
            "border-radius:6px;font-family:Consolas;font-size:12px;padding:4px 0 4px 8px;"
            "selection-background-color:#4a6a8a;selection-color:#ffffff;}"
            "QScrollBar:vertical{width:10px;background:#1e1e1e;border-radius:5px;}"
            "QScrollBar::handle:vertical{background:#555;min-height:20px;border-radius:5px;}"
            "QScrollBar::handle:vertical:hover{background:#888;}"
            "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}"
            "QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical{background:none;}")
        self.console.setContextMenuPolicy(Qt.CustomContextMenu)
        self.console.customContextMenuRequested.connect(
            lambda pos: create_console_context_menu(self.console, self).exec(
                self.console.mapToGlobal(pos)))
        self.console.setOpenExternalLinks(False)
        self.console.viewport().installEventFilter(self)

        QShortcut(QKeySequence.StandardKey.Copy, self.console).activated.connect(
            self._copy_console_clean)

        ccl.addWidget(self.console)
        cl.addWidget(cc)
        main.addWidget(container)
        self.url_container.update_visible_rows(4)

    def _layout_top_bar_children(self):
        if not hasattr(self, 'top_bar') or not hasattr(self, 'left_widget') or not hasattr(self, 'title_label'):
            return
        self.left_widget.adjustSize()
        self.title_label.adjustSize()
        self.left_widget.move(62, 15)
        self.title_label.move(278, 23)

    def auto_import_via_browser(self):
        cookies, err = get_cookies_via_cdp(9222, "recu.me")
        has_login = bool(cookies and (
            cookies.get("ref") == "recuto" or cookies.get("ref_") == "_"
            or "ref_ets" in cookies or "akey" in cookies or "mid" in cookies
            or "cf_clearance" in cookies))
        if not has_login:
            for k in ("no_debug_browser", "open_debug_browser", "close_browser",
                      "run_app_again", "login_recu", "click_again"):
                self.console.append(f"> {self.tr_text(k)}")
            return

        reload_ok, _ = reload_tab_via_cdp(9222, wait_seconds=3.0)
        if self._launched_browser_name == "Opera GX":
            time.sleep(1.5)
        cookies, _ = get_cookies_via_cdp(9222, "recu.me")
        if cookies:
            self.cookie_ua_widget.cookie_edit.setText(
                "; ".join(f"{k}={v}" for k, v in cookies.items()))

        ua, _ = get_user_agent_via_cdp(9222)
        self.cookie_ua_widget.ua_edit.setText(ua or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36 Edg/139.0.0.0"))

        self.console.append(f"> {self.tr_text('cookies_ua_updated')}")
        if reload_ok:
            self.console.append(f"> {self.tr_text('tab_reloaded')}")

    def inject_cookies_manual(self):
        d = CookieInjectDialog(self, initial_text="")
        if d.exec() != QDialog.Accepted or not (t := d.get_text()):
            return
        if "=" not in t and not t.startswith("["):
            self.console.append(f"> {self.tr_text('cookies_invalid_format')}")
            return
        ok, err, _ = inject_cookies_via_cdp(t, url="https://recu.me", port=9222,
                                            reload_page=True, recu_launcher=self)
        if ok:
            self.console.append(f"> {self.tr_text('cookies_inject_success')}")
        elif err:
            self.console.append(f"> {self.tr_text('cookies_inject_failed').format(err=err)}")

    def adjust_window_height(self):
        url_h = self.url_container.height() or (
            self.spin_qty.value() * 32 + 3 * max(0, self.spin_qty.value() - 1))
        if hasattr(self, '_container_layout'):
            _l, _top, _r, _bottom = self._container_layout.getContentsMargins()
        else:
            _top, _bottom = 7, 7
        self.setFixedHeight(
            2 + 25 + _top + 62 + 8 + url_h + 8 + 67 + 10 + CONSOLE_HEIGHT + _bottom)

    def update_url_rows(self): self.url_container.update_visible_rows(self.spin_qty.value())

    def on_video_completed_with_index(self, video_filename, renamed, url_index):
        self.url_container.convert_to_play_button(video_filename, renamed, url_index)
        self.downloaded_files.add(f"{video_filename}.ts")

    def on_download_folder_changed(self, folder):
        self.download_folder = folder
        self.console.append(f"> {self.tr_text('download_folder_updated')}")
        self.console.append(self._fmt_folder_line(folder))

    def delete_all_parameters(self):
        self._kill_all_procs()
        self._stop_event.clear()
        self.url_container.save_backup_manual(is_reboot=True)
        for i, (u, ini, fin, dur, fr) in enumerate(self.url_container.row_frames):
            if not fr.isVisible():
                continue
            u.clear()
            if hasattr(u, 'original_url'):
                delattr(u, 'original_url')
            if isinstance(ini, QLineEdit):
                ini.clear()
            elif isinstance(ini, QPushButton) and hasattr(ini, 'original_ini_widget'):
                orig = ini.original_ini_widget
                orig.clear()
                if (lay := fr.layout()):
                    lay.removeWidget(ini)
                    ini.hide()
                    orig.show()
                    lay.insertWidget(1, orig)
                    self.url_container.row_frames[i] = (u, orig, fin, dur, fr)
            if isinstance(fin, QLineEdit):
                fin.clear()
            if isinstance(dur, QLineEdit):
                dur.clear()
                dur._auto_set = False
                dur._for_url = None
        self.url_container.row_states.clear()
        self.cookie_ua_widget.cookie_edit.clear()
        self.cookie_ua_widget.ua_edit.clear()
        self.console.append(f"> {self.tr_text('all_params_cleared')}")
        self.console.append(f"> {self.tr_text('ready_new_config')}")

    def restart_process(self):
        self.console.append(f"> {self.tr_text('restarting_process')}")
        self.url_container.save_backup_manual()
        self._kill_all_procs()
        self._stop_event.clear()
        self.console.append(f"> {self.tr_text('previous_process_killed')}")
        self.url_container.restore_start_fields()
        self.console.append(f"> {self.tr_text('start_fields_restored')}")
        self._delete_progress_file()
        self.cookie_ua_widget.download_btn.setEnabled(True)
        self.console.clear()
        self.console.append(f"> {self.tr_text('console_restarted')}")
        self.console.append(f"> {self.tr_text('adjust_params')}")

    def has_parameters(self):
        for row in self.url_container.get_all_parameters().get('rows', []):
            if any(row.get(k, '').strip() for k in ('url', 'start', 'end', 'duration')):
                return True
        return bool(self.cookie_ua_widget.get_parameters().get('cookie', '').strip())

    def save_config(self, target_folder=None, urls_override=None):
        urls = urls_override if urls_override is not None else self.url_container.get_urls_for_config()
        if not urls:
            self.console.append(f"> {self.tr_text('url_required')}")
            return False
        markers, counts, row_map = {}, {}, {}
        for d in urls:
            p = urlparse(d[0]).path or d[0]
            counts[p] = counts.get(p, 0) + 1
        processed = []
        for i, entry in enumerate(urls, 1):
            url, start, end, dur, row_idx = entry
            m = f"URL{i}_{''.join(random.choices(string.ascii_lowercase + string.digits, k=6))}"
            markers[i] = m
            row_map[i] = row_idx
            sep = "&" if "?" in url else "?"
            processed.append([f"{url}{sep}recu_marker={m}#recu_marker_{m}",
                              start if isinstance(start, str) else "", end, dur])
        self.current_url_markers = markers
        self.current_url_path_counts = counts
        self.current_url_row_map = row_map
        cfg = {"urls": processed,
               "header": {"Cookie": self.cookie_ua_widget.cookie_edit.text(),
                          "User-Agent": self.cookie_ua_widget.ua_edit.text().strip()}}
        name = "config.json parallel"
        path = os.path.join(target_folder, name) if target_folder else os.path.join(os.getcwd(), name)
        if _write_json(path, cfg, indent=4, sleep=0.2):
            return True
        fb = os.path.join(os.getcwd(), f"config_fallback_{self.download_mode}.json")
        return _write_json(fb, cfg, indent=4)

    def _is_folder_writable(self, folder):
        try:
            t = os.path.join(folder, "write_test.tmp")
            with open(t, 'w') as f:
                f.write("test")
            os.remove(t)
            return True
        except Exception:
            return False

    def convert_downloaded_videos(self):
        if self.download_format.lower() == 'ts' or not check_ffmpeg():
            return
        time.sleep(1.5)
        folder = (self.download_folder if self.download_folder and os.path.exists(self.download_folder)
                  else os.path.join(self.original_working_dir, "videos"))
        if not os.path.exists(folder):
            return

        fmt = self.download_format.lower()
        from collections import defaultdict

        groups = defaultdict(list)
        try:
            entries = os.listdir(folder)
        except Exception:
            return

        for f in entries:
            if not f.endswith('.ts') or f.startswith('CB_'):
                continue
            if f not in self.downloaded_files:
                continue
            stem = f[:-3]
            m = re.match(r'^(.*)\s+\((\d+)\)$', stem)
            if m:
                base, idx = m.group(1), int(m.group(2))
            else:
                base, idx = stem, 0
            groups[base].append((idx, f, os.path.join(folder, f)))

        for base, items in groups.items():
            items.sort(key=lambda x: x[0])

            claimed = set()
            assignments = []
            for src_idx, src_name, src_path in items:
                target = src_idx
                while True:
                    mp4_name = (f"{base} ({target}).{fmt}" if target > 0 else f"{base}.{fmt}")
                    ts_name  = (f"{base} ({target}).ts"       if target > 0 else f"{base}.ts")
                    mp4_path = os.path.join(folder, mp4_name)
                    ts_path  = os.path.join(folder, ts_name)

                    conflict = os.path.exists(mp4_path) or target in claimed
                    if not conflict and target != src_idx and os.path.exists(ts_path):
                        in_batch = any(i == target for i, _, _ in items)
                        if not in_batch:
                            conflict = True
                    if not conflict:
                        break
                    target += 1
                claimed.add(target)
                assignments.append((src_idx, src_name, src_path, target))

            renames = sorted(
                [(s, n, p, d) for s, n, p, d in assignments if s != d],
                key=lambda x: x[0], reverse=True)
            for src_idx, src_name, src_path, dst_idx in renames:
                dst_name = (f"{base} ({dst_idx}).ts" if dst_idx > 0 else f"{base}.ts")
                dst_path = os.path.join(folder, dst_name)
                try:
                    os.rename(src_path, dst_path)
                except OSError:
                    pass

            for src_idx, src_name, src_path, dst_idx in sorted(assignments, key=lambda x: x[3]):
                ts_name  = (f"{base} ({dst_idx}).ts"       if dst_idx > 0 else f"{base}.ts")
                ts_path  = os.path.join(folder, ts_name)
                mp4_name = (f"{base} ({dst_idx}).{fmt}" if dst_idx > 0 else f"{base}.{fmt}")
                mp4_path = os.path.join(folder, mp4_name)

                if not os.path.exists(ts_path):
                    continue

                ok = convert_video_with_ffmpeg(ts_path, mp4_path, self.download_format)
                if ok:
                    try:
                        os.remove(ts_path)
                    except Exception:
                        pass

    def start_process(self):
        self._no_cookies_shown = False
        self._in_help = False
        self._last_run_no_cookies = False
        self._bad_time_rows.clear()
        QApplication.processEvents()
        self._stop_event.clear()
        self._recu_v_shown = False
        self.downloaded_files.clear()

        for u, ini, fin, dur, fr in self.url_container.row_frames:
            if not fr.isVisible() or not u.text().strip():
                continue
            has_start = bool(self.url_container._start_text(ini))
            has_end = isinstance(fin, QLineEdit) and bool(fin.text().strip())
            if not has_start and not has_end and isinstance(dur, QLineEdit):
                dur.clear()
                dur._auto_set = False
                dur._for_url = None

        self.url_container.save_backup_manual()

        for i in list(self.url_container.row_states.keys()):
            if i >= self.spin_qty.value():
                del self.url_container.row_states[i]
        if self.download_folder and os.path.exists(self.download_folder):
            target = self.download_folder
            self.console.append(f"> {self.tr_text('downloading_to').format('custom')}")
        else:
            target = os.path.join(self.original_working_dir, "videos")
            self.console.append(f"> {self.tr_text('downloading_to').format('videos')}")
        self.console.append(self._fmt_folder_line(target))
        QApplication.processEvents()
        if not self._is_folder_writable(target):
            self.console.append(f"> {self.tr_text('write_error')}")
            self.console.append(f"> {self.tr_text('choose_folder')}")
            return

        cleanup_old_configs(target)

        urls = self.url_container.get_urls_for_config()

        if not urls:
            self.console.append(f"> {self.tr_text('url_required')}")
            return

        def _parse_ts(s):
            try:
                parts = [int(x) for x in str(s).replace('.', ':').replace(',', ':').split(':')
                         if x != '']
                return sum(v * (60 ** (len(parts) - 1 - i)) for i, v in enumerate(parts))
            except Exception:
                return None

        def _is_valid_time_format(s):
            s = (s or "").strip()
            if not s:
                return True
            parts = s.translate(str.maketrans(',.;-', '::::')).split(':')
            if len(parts) < 2:
                return False
            if not parts[0].isdigit() or len(parts[0]) == 0:
                return False
            for seg in parts[1:]:
                if not seg.isdigit() or len(seg) != 2:
                    return False
            return True

        valid_urls = []
        for entry in urls:
            _u, _s, _e, _d, _row = entry

            if (_s and not _is_valid_time_format(_s)) or \
               (_e and not _is_valid_time_format(_e)) or \
               (_d and not _is_valid_time_format(_d)):
                self._bad_time_rows.add(_row + 1)
                continue

            sv = _parse_ts(_s) if _s else None
            ev = _parse_ts(_e) if _e else None
            dv = _parse_ts(_d) if _d else None

            if bool(_s) != bool(_e):
                self._bad_time_rows.add(_row + 1)
                continue

            if (_s or _e) and not _d:
                self._bad_time_rows.add(_row + 1)
                continue

            if sv is not None and ev is not None and ev <= sv:
                self._bad_time_rows.add(_row + 1)
                continue

            if dv is not None:
                if sv is not None and sv >= dv:
                    self._bad_time_rows.add(_row + 1)
                    continue
                if ev is not None and ev > dv:
                    self._bad_time_rows.add(_row + 1)
                    continue

            valid_urls.append(entry)
        urls = valid_urls

        if not urls:
            self.console.append(f"> {self.tr_text('process_completed')}")
            self._show_bad_time_summary()
            self.cookie_ua_widget.download_btn.setEnabled(True)
            return

        exe = next((c for c in (os.path.join(self.original_working_dir, "recu-windows-amd64.exe"),
                                os.path.join(self.script_dir, "recu-windows-amd64.exe"),
                                os.path.join(getattr(sys, "_MEIPASS", ""), "recu-windows-amd64.exe"),
                                os.path.join(target, "recu-windows-amd64.exe"))
                    if c and os.path.exists(c)), None)
        if not exe:
            self.console.append(f"> {self.tr_text('exe_not_found')}")
            self.console.append(f"> {self.tr_text('place_exe')}")
            self._show_bad_time_summary()
            return

        urls, skipped = self._filter_already_downloaded(target, urls)
        if skipped:
            for entry, info, _dup_num in skipped:
                _, _, _, _, row_idx = entry
                fname = info.get("file", "")
                display = fname[:-3] if fname.endswith(".ts") else fname
                self.video_completed_seq.emit(display, display, row_idx + 1)
        if not urls:
            self.console.append(f"> {self.tr_text('process_completed')}")
            self._show_bad_time_summary()
            self.cookie_ua_widget.download_btn.setEnabled(True)
            return

        self.url_container.restore_start_fields(
            only_rows={entry[4] for entry in urls})

        path_counts = {}
        for u in urls:
            p = urlparse(u[0]).path or u[0]
            path_counts[p] = path_counts.get(p, 0) + 1

        dup_urls = [u for u in urls if path_counts[urlparse(u[0]).path or u[0]] > 1]
        uniq_urls = [u for u in urls if path_counts[urlparse(u[0]).path or u[0]] == 1]

        has_dupes = len(dup_urls) > 0
        has_uniq = len(uniq_urls) > 0

        if self.download_mode == "series":
            self.cookie_ua_widget.download_btn.setEnabled(False)
            self._emit_init_msgs(to_console=True)

            threading.Thread(target=self._worker_sequential,
                             args=(urls, target, exe, self._on_sequential_done),
                             kwargs={"emit_init": False, "path_counts": path_counts},
                             daemon=True).start()
            return

        if has_dupes and has_uniq:
            self._start_mix(dup_urls, uniq_urls, target, exe, path_counts)
            return

        if has_dupes:
            self.cookie_ua_widget.download_btn.setEnabled(False)
            threading.Thread(target=self._worker_sequential,
                             args=(dup_urls, target, exe, self._on_sequential_done),
                             kwargs={"path_counts": path_counts},
                             daemon=True).start()
            return

        self.console.append(f"> {self.tr_text('saving_config')}")
        QApplication.processEvents()
        if not self.save_config(target, urls_override=urls):
            self.console.append(f"> {self.tr_text('config_save_error')}")
            self._show_bad_time_summary()
            return
        self.console.append(f"> {self.tr_text('config_updated')}")
        name = "config.json parallel"
        QApplication.processEvents()
        self.cookie_ua_widget.download_btn.setEnabled(False)
        cmd = [exe, name]
        self.console.append(f"> {self.tr_text('starting_download')}")
        QApplication.processEvents()
        try:
            kw, cf = _subprocess_kwargs()
            self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                            stderr=subprocess.STDOUT, text=True, bufsize=1,
                                            encoding='utf-8', errors='replace',
                                            creationflags=cf, cwd=target,
                                            universal_newlines=True, **kw)
            self._register_proc(self.process)
            self.reader = ProcessReader(self.process, target, self.sound_path, self,
                                        self.current_url_markers,
                                        self.current_url_path_counts,
                                        self.current_url_row_map,
                                        urls_data=urls)
            self.reader.output_signal.connect(lambda l: self.console.append(l))
            self.reader.video_completed_signal.connect(self.on_video_completed_with_index)
            self.reader.finished_signal.connect(self.process_finished)
        except Exception as e:
            self.console.append(f"> {self.tr_text('process_error').format(e)}")
            self.cookie_ua_widget.download_btn.setEnabled(False)

    def _play_sound(self):
        try:
            if os.path.exists(self.sound_path):
                threading.Thread(
                    target=lambda: winsound.PlaySound(
                        self.sound_path,
                        winsound.SND_FILENAME | winsound.SND_ASYNC),
                    daemon=True).start()
        except Exception:
            pass

    def _start_mix(self, dup_urls, uniq_urls, target, exe, path_counts=None):
        path_counts = path_counts or {}
        self.cookie_ua_widget.download_btn.setEnabled(False)
        self._emit_init_msgs(to_console=True)

        lock = threading.Lock()
        state = {"remaining": 2}

        def _finish_one():
            with lock:
                state["remaining"] -= 1
                done = state["remaining"] <= 0
            if done:
                self._on_sequential_done()

        threading.Thread(target=self._worker_sequential,
                         args=(dup_urls, target, exe, _finish_one),
                         kwargs={"emit_init": False, "suppress_recu_v": True,
                                 "path_counts": path_counts},
                         daemon=True).start()
        threading.Thread(target=self._worker_parallel_uniq,
                         args=(uniq_urls, target, exe, _finish_one),
                         kwargs={"emit_init": False},
                         daemon=True).start()

    def _worker_parallel_uniq(self, urls, work_dir, exe, on_done=None, emit_init=True):
        stopped_early = False
        try:
            if self._stop_event.is_set():
                stopped_early = True
                return

            if emit_init:
                self._emit_init_msgs(to_console=False)

            markers, row_map = {}, {}
            for i, entry in enumerate(urls, 1):
                url, _s, _e, _d, row_idx = entry
                m = f"URL{i}_{''.join(random.choices(string.ascii_lowercase + string.digits, k=6))}"
                markers[i] = m
                row_map[i] = row_idx

            processed = []
            for i, entry in enumerate(urls, 1):
                url, start, end, dur, _ = entry
                m = markers[i]
                sep = "&" if "?" in url else "?"
                processed.append([f"{url}{sep}recu_marker={m}#recu_marker_{m}",
                                  start if isinstance(start, str) else "", end, dur])

            cfg = {"urls": processed,
                   "header": {"Cookie": self.cookie_ua_widget.cookie_edit.text(),
                              "User-Agent": self.cookie_ua_widget.ua_edit.text().strip()}}
            cfg_name = "config.json parallel"
            cfg_path = os.path.join(work_dir, cfg_name)
            if not _write_json(cfg_path, cfg, indent=4):
                return

            if self._stop_event.is_set():
                stopped_early = True
                return

            try:
                kw, cf = _subprocess_kwargs()
                proc = subprocess.Popen(
                    [exe, cfg_name],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, bufsize=1, encoding='utf-8', errors='replace',
                    creationflags=cf, cwd=work_dir, universal_newlines=True, **kw)
                self._register_proc(proc)
            except Exception as e:
                self.console_signal.emit(f"> Error parallel (mix): {e}")
                return

            first_line = ""
            try:
                while True:
                    raw = proc.stdout.readline()
                    if not raw:
                        break
                    s = raw.strip()
                    if s:
                        first_line = s
                        break
            except Exception:
                pass

            if first_line.startswith("Recu v"):
                if not self._recu_v_shown:
                    self._recu_v_shown = True
                    self.console_signal.emit(f"> {first_line}")
                first_line = ""

            for _i, _ in enumerate(urls):
                if self._stop_event.is_set():
                    stopped_early = True
                    break
                self.console_signal.emit(
                    f"> {self.tr_text('downloading_playlists_complete')}")
                if _i < len(urls) - 1:
                    time.sleep(0.4)

            if stopped_early or self._stop_event.is_set():
                stopped_early = True
                try:
                    proc.kill()
                except Exception:
                    pass
                return

            last_out = ""
            seen_cb = set()

            if first_line:
                out = self._fmt_console_line(first_line)
                if out:
                    last_out = out
                    self.console_signal.emit(out)

            try:
                for raw in iter(proc.stdout.readline, ''):
                    if self._stop_event.is_set():
                        break
                    line = raw.strip()
                    if not line:
                        continue
                    if line.startswith("Recu v"):
                        if not self._recu_v_shown:
                            self._recu_v_shown = True
                            self.console_signal.emit(f"> {line}")
                        continue
                    if "Downloading Playlists:" in line and "Complete" in line:
                        continue

                    if "Completed:" in line:
                        m_cb = re.search(r'Completed:\s*([^\s:]+?)(?::https?://|$)', line)
                        if m_cb:
                            cb_name = m_cb.group(1).strip()
                            if not cb_name.endswith(".ts"):
                                cb_name += ".ts"
                            if cb_name not in seen_cb:
                                seen_cb.add(cb_name)
                                self._play_sound()
                                m_idx_found = None
                                for m_idx, m_name in markers.items():
                                    if m_name in line:
                                        m_idx_found = m_idx
                                        break
                                if m_idx_found:
                                    row_real_1based = row_map.get(m_idx_found, m_idx_found) + 1
                                    new_name = self._finalize_named_file(
                                        work_dir, cb_name, m_idx_found,
                                        use_index_suffix=False)
                                    if new_name:
                                        self.video_completed_seq.emit(
                                            new_name[:-3], new_name[:-3], row_real_1based)
                                        display = (new_name[:-3]
                                                   if new_name.endswith(".ts") else new_name)
                                        self.console_signal.emit(
                                            f"> {self.tr_text('completed')}: {display} ✓")
                                        if 0 <= m_idx_found - 1 < len(urls):
                                            u_, s_, e_, d_, _ = urls[m_idx_found - 1]
                                            self._mark_completed(
                                                work_dir, u_, s_, e_, d_, new_name, 0)
                                        last_out = ""
                                        continue

                    out = self._fmt_console_line(line)
                    if not out or out == last_out:
                        continue
                    last_out = out
                    self.console_signal.emit(out)
            except Exception:
                pass

            if self._stop_event.is_set():
                try:
                    proc.kill()
                except Exception:
                    pass
                try:
                    proc.wait(timeout=1)
                except Exception:
                    pass
                stopped_early = True
            else:
                proc.wait()
            self._unregister_proc(proc)
            hide_file_windows(cfg_path)
        except Exception as e:
            self.console_signal.emit(f"> Error parallel (mix): {e}")
        finally:
            if on_done is not None and not stopped_early and not self._stop_event.is_set():
                try: on_done()
                except Exception:
                    pass

    def _fmt_console_line(self, line):
        if not line:
            return ""
        if "Process completed" in line or "timestamps is in wrong format:" in line:
            return ""
        if "Completed:" in line and "✓" not in line:
            m = re.search(r'Completed:\s*([^:\s]+?)(?::https?://|$)', line)
            if m:
                raw = m.group(1).strip()
                name = raw[3:] if raw.startswith("CB_") else raw
                if name.endswith(".ts"):
                    name = name[:-3]
                mm = re.search(r'(\d{2})-(\d{2})-(\d{2})', name)
                if mm:
                    n1, n2, n3 = mm.groups()
                    name = name[:mm.start()] + f"20{n1}-{n2}-{n3}" + name[mm.end():]
                name = re.sub(r'_\d{2}-\d{2}$', '', name)
                return f"> {self.tr_text('completed')}: {name} ✓"
            return ""

        line = re.sub(r'\x1b\[[0-9;]*[A-Za-z]', '', line).lstrip()

        if "Please fill in the config.json" in line:
            self._in_help = True
            self._last_run_no_cookies = True
            if not self._no_cookies_shown:
                self._no_cookies_shown = True
                return (f'> {self.tr_text("no_cookies_ua")}<br>'
                        f'> {self.tr_text("press_refresh_cookies")}')
            return ""
        if self._in_help:
            if line.strip() in ("URLs to Download", "Cookies", "User-Agent"):
                return ""
            self._in_help = False

        if "Downloading Playlists:" in line:
            key = 'downloading_playlists_complete' if "Complete" in line else 'downloading_playlists'
            return f"> {self.tr_text(key)}"
        if "Downloading HTML:" in line and "Complete" in line:
            return ""
        if "Getting Link to Playlist:" in line and "Complete" in line:
            return ""
        if "Downloading:" in line and "Remaining:" in line and ("KB/s" in line or "MB/s" in line):
            return _format_progress(line, self.tr_text, self.download_language)
        return f"> {line}"

    def _worker_sequential(self, urls, target, exe, on_done=None, emit_init=True,
                           suppress_recu_v=False, path_counts=None):
        path_counts = path_counts or {}
        cfg_name = "config_seq.json"
        cfg_path = os.path.join(target, cfg_name)
        stopped_early = False

        try:
            for f in os.listdir(target):
                if f == "config_seq.json" or (
                        f.startswith("config_seq_") and f.endswith(".json")):
                    _safe_remove(os.path.join(target, f))
        except Exception:
            pass

        try:
            if emit_init:
                self._emit_init_msgs(to_console=False)

            dup_counters = {}
            for idx, (url, start, end, dur, row_idx) in enumerate(urls, 1):
                if self._stop_event.is_set():
                    stopped_early = True
                    break

                p = urlparse(url).path or url
                is_dup = path_counts.get(p, 0) > 1
                if is_dup:
                    dup_counters[p] = dup_counters.get(p, 0) + 1
                    dup_num = dup_counters[p]
                else:
                    dup_num = 0

                cfg = {
                    "urls": [[url, start if isinstance(start, str) else "", end, dur]],
                    "header": {
                        "Cookie": self.cookie_ua_widget.cookie_edit.text(),
                        "User-Agent": self.cookie_ua_widget.ua_edit.text().strip(),
                    },
                }
                if not _write_json(cfg_path, cfg, indent=4):
                    self.console_signal.emit(f"> Error escribiendo config {idx}")
                    continue

                try:
                    kw, cf = _subprocess_kwargs()
                    proc = subprocess.Popen(
                        [exe, cfg_name, "series"],
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        text=True, bufsize=1, encoding='utf-8', errors='replace',
                        creationflags=cf, cwd=target, universal_newlines=True, **kw)
                    self._register_proc(proc)
                except Exception as e:
                    self.console_signal.emit(f"> Error lanzando URL {idx}: {e}")
                    continue

                cb_produced = None
                last_out = ""
                try:
                    for raw in iter(proc.stdout.readline, ''):
                        if self._stop_event.is_set():
                            break
                        line = raw.strip()
                        if not line:
                            continue
                        if line.startswith("Recu v"):
                            if not suppress_recu_v and not self._recu_v_shown:
                                self._recu_v_shown = True
                                self.console_signal.emit(f"> {line}")
                            continue

                        if "Completed:" in line and cb_produced is None:
                            m_cb = re.search(r'Completed:\s*([^\s:]+?)(?::https?://|$)', line)
                            if m_cb:
                                cb_name = m_cb.group(1).strip()
                                if not cb_name.endswith(".ts"):
                                    cb_name += ".ts"
                                cb_produced = cb_name
                                self._play_sound()
                                new_name = self._finalize_named_file(
                                    target, cb_produced, dup_num,
                                    use_index_suffix=is_dup)
                                if new_name:
                                    self.video_completed_seq.emit(
                                        new_name[:-3], new_name[:-3], row_idx + 1)
                                    display = (new_name[:-3]
                                               if new_name.endswith(".ts") else new_name)
                                    self.console_signal.emit(
                                        f"> {self.tr_text('completed')}: {display} ✓")
                                    self._mark_completed(
                                        target, url, start, end, dur, new_name, dup_num)
                                    last_out = ""
                                    continue

                        out = self._fmt_console_line(line)
                        if not out or out == last_out:
                            continue
                        last_out = out
                        self.console_signal.emit(out)
                except Exception:
                    pass

                if self._stop_event.is_set():
                    try:
                        proc.kill()
                    except Exception:
                        pass
                    try:
                        proc.wait(timeout=1)
                    except Exception:
                        pass
                    self._unregister_proc(proc)
                    stopped_early = True
                    break

                proc.wait()
                self._unregister_proc(proc)
                time.sleep(0.5)

                if cb_produced is None:
                    new_name = self._finalize_seq_file(target, dup_num, use_index_suffix=is_dup)
                    if new_name:
                        self.video_completed_seq.emit(new_name[:-3], new_name[:-3], row_idx + 1)
                        display = new_name[:-3] if new_name.endswith(".ts") else new_name
                        self.console_signal.emit(
                            f"> {self.tr_text('completed')}: {display} ✓")
                        self._mark_completed(
                            target, url, start, end, dur, new_name, dup_num)
        finally:
            hide_file_windows(cfg_path)
            if on_done is not None and not stopped_early and not self._stop_event.is_set():
                try: on_done()
                except Exception:
                    pass

    def _next_available_index(self, target, base):
        pattern = re.compile(
            r'^' + re.escape(base) + r'(?:\s+\((\d+)\))?\.(?:ts|mp4|mkv)$',
            re.IGNORECASE)
        max_idx = -1
        try:
            for f in os.listdir(target):
                m = pattern.match(f)
                if m:
                    idx = int(m.group(1)) if m.group(1) else 0
                    if idx > max_idx:
                        max_idx = idx
        except Exception:
            pass
        return max_idx + 1

    def _index_exists(self, target, base, idx):
        suffix = "" if idx == 0 else f" ({idx})"
        try:
            return any(
                os.path.exists(os.path.join(target, f"{base}{suffix}.{ext}"))
                for ext in ("ts", "mp4", "mkv"))
        except Exception:
            return False

    def _finalize_target_path(self, target, base, idx, use_index_suffix):
        if use_index_suffix:
            next_idx = max(idx, 1)
            while self._index_exists(target, base, next_idx):
                next_idx += 1
        else:
            next_idx = self._next_available_index(target, base)
        if next_idx == 0:
            return os.path.join(target, f"{base}.ts")
        return os.path.join(target, f"{base} ({next_idx}).ts")

    def _finalize_seq_file(self, target, idx, use_index_suffix=False):
        try:
            candidates = [f for f in os.listdir(target)
                          if f.startswith("CB_") and f.endswith(".ts")]
            if not candidates:
                return None
            candidates.sort(key=lambda f: os.path.getmtime(os.path.join(target, f)),
                            reverse=True)
            f = candidates[0]
            old_path = os.path.join(target, f)
            base = format_video_name(f, self.rename_format)

            with self._finalize_lock:
                new_path = self._finalize_target_path(target, base, idx, use_index_suffix)
                for _ in range(30):
                    try:
                        os.rename(old_path, new_path)
                        return os.path.basename(new_path)
                    except OSError:
                        time.sleep(0.5)
            return None
        except Exception as e:
            self.console_signal.emit(f"> Error finalize: {e}")
            return None

    def _finalize_named_file(self, target, cb_name, idx, use_index_suffix=False):
        try:
            old_path = os.path.join(target, cb_name)
            if not os.path.exists(old_path):
                return None

            base = format_video_name(cb_name, self.rename_format)

            with self._finalize_lock:
                new_path = self._finalize_target_path(target, base, idx, use_index_suffix)
                for attempt in range(3):
                    if attempt:
                        time.sleep(0.2)
                    try:
                        os.rename(old_path, new_path)
                        return os.path.basename(new_path)
                    except OSError:
                        continue

                for _ in range(30):
                    try:
                        shutil.copy2(old_path, new_path)
                        try:
                            os.remove(old_path)
                        except OSError:
                            pass
                        return os.path.basename(new_path)
                    except OSError:
                        time.sleep(0.5)
                return None
        except Exception as e:
            self.console_signal.emit(f"> Error finalize: {e}")
            return None

    def process_finished(self):
        self.convert_downloaded_videos()
        if not self._last_run_no_cookies:
            self.console.append(f"> {self.tr_text('process_completed')}")
        self._show_bad_time_summary()
        self.cookie_ua_widget.download_btn.setEnabled(True)

    def _delete_progress_file(self):
        folders = set()
        if self.download_folder:
            folders.add(self.download_folder)
        folders.add(os.path.join(self.original_working_dir, "videos"))
        for folder in folders:
            path = os.path.join(folder, "download_progress.json")
            for f in (path, path + ".tmp"):
                _safe_remove(f)

    def closeEvent(self, event):
        if not self.has_parameters():
            self._kill_all_procs()
            self._delete_progress_file()
            event.accept()
            return
        self.close_click_count += 1
        if self.close_click_count == 1:
            self.console.append(f"> {self.tr_text('close_confirm')}")
            self.close_timer.start(5000)
            event.ignore()
        else:
            self._kill_all_procs()
            self.url_container.save_backup_manual(is_closing=True)
            self._delete_progress_file()
            self.console.append(f"> {self.tr_text('exiting_app')}")
            event.accept()


# ============================================================
#  FFmpeg helpers
# ============================================================
_ffmpeg_exe_cache = None
_ffmpeg_checked = False


def find_ffmpeg_exe():
    global _ffmpeg_exe_cache, _ffmpeg_checked
    if _ffmpeg_checked:
        return _ffmpeg_exe_cache
    _ffmpeg_checked = True

    kw, cf = _subprocess_kwargs()
    LOCAL = os.environ.get('LOCALAPPDATA', '')
    PF = os.environ.get('ProgramFiles', '')
    PF86 = os.environ.get('ProgramFiles(x86)', '')
    UP = os.environ.get('USERPROFILE', '')
    cands = ["ffmpeg"]
    if LOCAL:
        cands.append(os.path.join(LOCAL, "Microsoft", "WinGet", "Links", "ffmpeg.exe"))
        pk = os.path.join(LOCAL, "Microsoft", "WinGet", "Packages")
        if os.path.isdir(pk):
            for root, _, files in os.walk(pk):
                if "ffmpeg.exe" in files:
                    cands.append(os.path.join(root, "ffmpeg.exe"))
                    break
    if PF:
        cands.append(os.path.join(PF, "ffmpeg", "bin", "ffmpeg.exe"))
    if PF86:
        cands.append(os.path.join(PF86, "ffmpeg", "bin", "ffmpeg.exe"))
    if os.environ.get('ChocolateyInstall'):
        cands.append(os.path.join(os.environ['ChocolateyInstall'], "bin", "ffmpeg.exe"))
    cands.append(r"C:\ProgramData\chocolatey\bin\ffmpeg.exe")
    if UP:
        cands.append(os.path.join(UP, "scoop", "shims", "ffmpeg.exe"))
    cands += [r"C:\ProgramData\scoop\shims\ffmpeg.exe",
              r"C:\msys64\mingw64\bin\ffmpeg.exe", r"C:\msys64\usr\bin\ffmpeg.exe"]
    for exe in cands:
        try:
            if subprocess.run([exe, '-version'], capture_output=True, text=True,
                              timeout=5, creationflags=cf, **kw).returncode == 0:
                _ffmpeg_exe_cache = exe
                return exe
        except Exception:
            continue
    _ffmpeg_exe_cache = None
    return None


def check_ffmpeg():
    return find_ffmpeg_exe() is not None


def convert_video_with_ffmpeg(inp, out, fmt, cb=None):
    try:
        fmt = fmt.lower()
        exe = find_ffmpeg_exe()
        if not exe or fmt not in ('mp4', 'mkv'):
            return False
        kw, cf = _subprocess_kwargs()
        cmd = ([exe, '-i', inp, '-c', 'copy', '-movflags', '+faststart', '-y', out]
               if fmt == 'mp4' else [exe, '-i', inp, '-c', 'copy', '-y', out])
        return subprocess.run(cmd, capture_output=True, text=True, timeout=300,
                              creationflags=cf, **kw).returncode == 0
    except Exception:
        return False


# ============================================================
#  Main
# ============================================================
if __name__ == "__main__":
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet("QToolTip{background-color:#3c4048;color:#f0f0f0;"
                      "border:1px solid #50575d;border-radius:6px;padding:3px 6px;"
                      "font-family:Arial;font-size:9pt;}")

    try:
        mp = getattr(sys, "_MEIPASS", "")
        frozen = getattr(sys, 'frozen', False)
        bases = [mp, os.path.dirname(os.path.abspath(__file__)), os.getcwd()]
        if frozen:
            bases.append(os.path.dirname(sys.executable))
        for base in bases:
            path = os.path.join(base, "icon.ico") if base else ""
            if path and os.path.exists(path):
                app.setWindowIcon(QIcon(path))
                break
    except Exception:
        pass
    window = RecuLauncher()
    window.show()
    sys.exit(app.exec())