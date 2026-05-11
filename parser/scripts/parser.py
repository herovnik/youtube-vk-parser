import yt_dlp
import argparse
import os
import sys
from pathlib import Path


def progress_hook(d: dict) -> None:
    """Хук для отображения прогресса скачивания."""
    if d["status"] == "downloading":
        percent = d.get("_percent_str", "?%").strip()
        speed   = d.get("_speed_str", "?").strip()
        eta     = d.get("_eta_str", "?").strip()
        print(f"\r⬇️  {percent}  Скорость: {speed}  Осталось: {eta}", end="", flush=True)
    elif d["status"] == "finished":
        print(f"\n✅ Файл скачан: {d['filename']}")


def get_video_info(url: str) -> dict:
    """Получает информацию о видео без скачивания."""
    with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
        return ydl.extract_info(url, download=False)


def list_formats(url: str) -> None:
    """Показывает доступные форматы видео."""
    ydl_opts = {"listformats": True, "quiet": False}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.extract_info(url, download=False)


def postprocessor_hook(d: dict) -> None:
    """Хук для отображения финального файла после слияния/постобработки."""
    if d["status"] == "finished":
        # В d["info_dict"] находится информация о финальном файле
        filepath = d.get("info_dict", {}).get("_filename")
        if filepath:
            print(f"\n🎉 Финальный файл готов: {filepath}")

def download_video(
    url: str,
    output_dir: str = ".",
    quality: str = "best",
    format_ext: str = "mp4",
    audio_only: bool = False,
    subtitles: bool = False,
    custom_name: str = None,
) -> None:
    """
    Скачивает видео с расширенными настройками.

    :param url:         Ссылка на видео или плейлист
    :param output_dir:  Папка для сохранения
    :param quality:     Качество: best | 1080 | 720 | 480 | 360
    :param format_ext:  Формат выходного файла: mp4 | mkv | webm
    :param audio_only:  Скачать только аудио в MP3
    :param subtitles:   Скачать субтитры
    :param custom_name: Пользовательское название скачиваемого файла
    """
    # Создаём абсолютный путь, чтобы избежать проблем с путями
    abs_output_dir = os.path.abspath(output_dir)
    Path(abs_output_dir).mkdir(parents=True, exist_ok=True)

    # Выбор формата по качеству
    if audio_only:
        fmt = "bestaudio/best"
    elif quality == "best":
        fmt = "bestvideo+bestaudio/best"
    else:
        fmt = f"bestvideo[height<={quality}]+bestaudio/best[height<={quality}]"

    # Формируем шаблон имени файла
    # Использование `paths` вместо `os.path.join` в outtmpl решает множество проблем с путями в yt-dlp
    if custom_name:
        outtmpl = {"default": f"{custom_name}.%(ext)s"}
    else:
        outtmpl = {"default": "%(title)s.%(ext)s"}

    ydl_opts = {
        "format": fmt,
        "paths": {"home": abs_output_dir},
        "outtmpl": outtmpl,
        "merge_output_format": format_ext,
        "progress_hooks": [progress_hook],
        "postprocessor_hooks": [postprocessor_hook],
        "noplaylist": False,   # Разрешаем плейлисты
    }

    # Только аудио → конвертируем в MP3
    if audio_only:
        ydl_opts["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "320",
            }
        ]

    # Субтитры
    if subtitles:
        ydl_opts.update({
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": ["ru", "en"],
            "subtitlesformat": "srt",
        })

    # Скачиваем (сразу собираем инфу и качаем в один проход, чтобы не дублировать запросы)
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        # Извлекаем метаданные и сразу скачиваем
        info = ydl.extract_info(url, download=True)
        title = info.get("title", "Неизвестное видео")
        duration = info.get("duration", 0)
        print(f"\n🎬 Видео: {title}")
        print(f"⏱️  Длительность: {duration // 60}:{duration % 60:02d}")
        print(f"📁 Файл сохранен в: {abs_output_dir}\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="🎬 YouTube Downloader на yt-dlp",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  python yt_downloader.py https://youtu.be/VIDEO_ID
  python yt_downloader.py https://youtu.be/VIDEO_ID -n "Мое супер видео"
  python yt_downloader.py https://youtu.be/VIDEO_ID -q 720 -o ~/Videos
  python yt_downloader.py https://youtu.be/VIDEO_ID --audio-only
  python yt_downloader.py https://youtu.be/PLAYLIST_ID --subtitles
  python yt_downloader.py https://youtu.be/VIDEO_ID --list-formats
        """
    )
    parser.add_argument("url", help="Ссылка на YouTube видео или плейлист")
    parser.add_argument("-o", "--output", default="downloads", help="Папка для сохранения")
    parser.add_argument("-n", "--name", help="Своё название для скачиваемого файла (без расширения)")
    parser.add_argument("-q", "--quality", default="best",
                        choices=["best", "2160", "1440", "1080", "720", "480", "360"],
                        help="Качество видео")
    parser.add_argument("-f", "--format", default="mp4",
                        choices=["mp4", "mkv", "webm"],
                        help="Формат файла")
    parser.add_argument("--audio-only", action="store_true",
                        help="Скачать только аудио (MP3)")
    parser.add_argument("--subtitles", action="store_true",
                        help="Скачать субтитры (ru, en)")
    parser.add_argument("--list-formats", action="store_true",
                        help="Показать доступные форматы и выйти")
    return parser.parse_args()


def main():
    args = parse_args()

    if args.list_formats:
        list_formats(args.url)
        sys.exit(0)

    download_video(
        url=args.url,
        output_dir=args.output,
        quality=args.quality,
        format_ext=args.format,
        audio_only=args.audio_only,
        subtitles=args.subtitles,
        custom_name=args.name,
    )


if __name__ == "__main__":
    main()