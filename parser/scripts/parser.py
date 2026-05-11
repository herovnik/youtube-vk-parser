import yt_dlp
import argparse
import os
import sys
import re
from pathlib import Path


# ─────────────────────────────────────────────
# Вспомогательные функции для VK
# ─────────────────────────────────────────────

def is_vk_url(url: str) -> bool:
    """Определяет, является ли ссылка ссылкой на VK Видео."""
    return bool(re.search(r"vk\.com/(video|clip|wall|feed)", url, re.IGNORECASE)
                or re.search(r"vk\.com/@", url, re.IGNORECASE)
                or re.search(r"vkvideo\.ru", url, re.IGNORECASE))


def get_vk_ydl_opts(cookies_file: str | None = None) -> dict:
    """
    Возвращает базовые опции yt-dlp, специфичные для VK.
    VK требует авторизации для большинства приватных видео.
    Передайте cookies_file — путь к файлу cookies.txt (Netscape-формат),
    экспортированному из браузера расширением «Get cookies.txt LOCALLY».
    """
    opts: dict = {
        # VK отдаёт m3u8-потоки; этот экстрактор работает стабильнее
        "extractor_args": {
            "vk": {
                # Принудительно использовать DASH/HLS вместо прямых ссылок
                "download_archive": [],
            }
        },
        # Некоторые VK-видео отдают потоки только с правильным User-Agent
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Referer": "https://vk.com/",
        },
    }
    if cookies_file:
        opts["cookiefile"] = cookies_file
    return opts


# ─────────────────────────────────────────────
# Хуки прогресса
# ─────────────────────────────────────────────

def progress_hook(d: dict) -> None:
    """Хук для отображения прогресса скачивания."""
    if d["status"] == "downloading":
        percent = d.get("_percent_str", "?%").strip()
        speed   = d.get("_speed_str", "?").strip()
        eta     = d.get("_eta_str", "?").strip()
        print(f"\r⬇️  {percent}  Скорость: {speed}  Осталось: {eta}", end="", flush=True)
    elif d["status"] == "finished":
        print(f"\n✅ Файл скачан: {d['filename']}")


def postprocessor_hook(d: dict) -> None:
    """Хук для отображения финального файла после слияния/постобработки."""
    if d["status"] == "finished":
        filepath = d.get("info_dict", {}).get("_filename")
        if filepath:
            print(f"\n🎉 Финальный файл готов: {filepath}")


# ─────────────────────────────────────────────
# Информация и форматы
# ─────────────────────────────────────────────

def get_video_info(url: str, vk_cookies: str | None = None) -> dict:
    """Получает информацию о видео без скачивания."""
    opts: dict = {"quiet": True}
    if is_vk_url(url):
        opts.update(get_vk_ydl_opts(vk_cookies))
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False)


def list_formats(url: str, vk_cookies: str | None = None) -> None:
    """Показывает доступные форматы видео."""
    opts: dict = {"listformats": True, "quiet": False}
    if is_vk_url(url):
        opts.update(get_vk_ydl_opts(vk_cookies))
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.extract_info(url, download=False)


# ─────────────────────────────────────────────
# Скачивание
# ─────────────────────────────────────────────

def download_video(
    url: str,
    output_dir: str = ".",
    quality: str = "best",
    format_ext: str = "mp4",
    audio_only: bool = False,
    subtitles: bool = False,
    custom_name: str | None = None,
    vk_cookies: str | None = None,
) -> None:
    """
    Скачивает видео с расширенными настройками.
    Поддерживаемые платформы: YouTube, VK Видео и любые другие, поддерживаемые yt-dlp.

    :param url:         Ссылка на видео или плейлист
    :param output_dir:  Папка для сохранения
    :param quality:     Качество: best | 2160 | 1440 | 1080 | 720 | 480 | 360
    :param format_ext:  Формат выходного файла: mp4 | mkv | webm
    :param audio_only:  Скачать только аудио в MP3
    :param subtitles:   Скачать субтитры
    :param custom_name: Пользовательское название скачиваемого файла
    :param vk_cookies:  Путь к файлу cookies.txt для VK (опционально)
    """
    abs_output_dir = os.path.abspath(output_dir)
    Path(abs_output_dir).mkdir(parents=True, exist_ok=True)

    vk = is_vk_url(url)
    if vk:
        print("🔵 Определена ссылка VK Видео — используем специальные настройки.")

    # ── Выбор формата ──────────────────────────────────────────────────────────
    if audio_only:
        fmt = "bestaudio/best"
    elif quality == "best":
        # VK часто отдаёт видео и аудио в одном потоке (mp4),
        # поэтому ставим запасной вариант "best" после объединённого
        fmt = "bestvideo+bestaudio/best" if not vk else "bestvideo+bestaudio/best/best"
    else:
        fmt = (
            f"bestvideo[height<={quality}]+bestaudio/best[height<={quality}]"
        )

    # ── Шаблон имени ───────────────────────────────────────────────────────────
    if custom_name:
        outtmpl = {"default": f"{custom_name}.%(ext)s"}
    else:
        outtmpl = {"default": "%(title)s.%(ext)s"}

    # ── Базовые опции ──────────────────────────────────────────────────────────
    ydl_opts: dict = {
        "format": fmt,
        "paths": {"home": abs_output_dir},
        "outtmpl": outtmpl,
        "merge_output_format": format_ext,
        "progress_hooks": [progress_hook],
        "postprocessor_hooks": [postprocessor_hook],
        "noplaylist": False,
    }

    # ── Специфичные настройки VK ───────────────────────────────────────────────
    if vk:
        ydl_opts.update(get_vk_ydl_opts(vk_cookies))

    # ── Только аудио ───────────────────────────────────────────────────────────
    if audio_only:
        ydl_opts["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "320",
            }
        ]

    # ── Субтитры ───────────────────────────────────────────────────────────────
    if subtitles:
        ydl_opts.update({
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": ["ru", "en"],
            "subtitlesformat": "srt",
        })

    # ── Скачивание ─────────────────────────────────────────────────────────────
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        title    = info.get("title", "Неизвестное видео")
        duration = info.get("duration") or 0
        print(f"\n🎬 Видео: {title}")
        print(f"⏱️  Длительность: {duration // 60}:{duration % 60:02d}")
        print(f"📁 Файл сохранён в: {abs_output_dir}\n")


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="🎬 YouTube & VK Видео Downloader на yt-dlp",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  # YouTube
  python yt_downloader.py https://youtu.be/VIDEO_ID
  python yt_downloader.py https://youtu.be/VIDEO_ID -n "Моё видео" -q 720
  python yt_downloader.py https://youtu.be/PLAYLIST_ID --subtitles
  python yt_downloader.py https://youtu.be/VIDEO_ID --audio-only

  # VK Видео (публичные видео не требуют cookies)
  python yt_downloader.py https://vk.com/video-12345_67890
  python yt_downloader.py https://vk.com/video-12345_67890 -q 1080 -o ~/Videos

  # VK Видео с авторизацией (приватные / закрытые сообщества)
  python yt_downloader.py https://vk.com/video-12345_67890 --vk-cookies cookies.txt

  # Показать доступные форматы
  python yt_downloader.py https://vk.com/video-12345_67890 --list-formats
        """
    )
    parser.add_argument("url", help="Ссылка на YouTube / VK видео или плейлист")
    parser.add_argument("-o", "--output", default="downloads",
                        help="Папка для сохранения (по умолчанию: downloads)")
    parser.add_argument("-n", "--name",
                        help="Своё название файла (без расширения)")
    parser.add_argument("-q", "--quality", default="best",
                        choices=["best", "2160", "1440", "1080", "720", "480", "360"],
                        help="Качество видео (по умолчанию: best)")
    parser.add_argument("-f", "--format", default="mp4",
                        choices=["mp4", "mkv", "webm"],
                        help="Формат выходного файла (по умолчанию: mp4)")
    parser.add_argument("--audio-only", action="store_true",
                        help="Скачать только аудио (MP3 320 kbps)")
    parser.add_argument("--subtitles", action="store_true",
                        help="Скачать субтитры (ru, en)")
    parser.add_argument("--list-formats", action="store_true",
                        help="Показать доступные форматы и выйти")
    parser.add_argument("--vk-cookies", metavar="FILE",
                        help="Путь к файлу cookies.txt для авторизации в VK "
                             "(нужен для приватных видео)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.list_formats:
        list_formats(args.url, vk_cookies=args.vk_cookies)
        sys.exit(0)

    download_video(
        url=args.url,
        output_dir=args.output,
        quality=args.quality,
        format_ext=args.format,
        audio_only=args.audio_only,
        subtitles=args.subtitles,
        custom_name=args.name,
        vk_cookies=args.vk_cookies,
    )


if __name__ == "__main__":
    main()
